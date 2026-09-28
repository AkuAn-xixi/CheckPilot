"""TextComparer / AsrContextWords / transcribe_audio 单元测试。"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from backend.app.services.asr_service import (
    AsrContextWords,
    AsrRuntimeError,
    AsrService,
    MAX_CONTEXT_WORD_CHARS,
    MAX_CONTEXT_WORDS,
    NORMALIZATION_GAIN_MAX,
    NORMALIZATION_GAIN_MIN,
    NOISE_FLOOR_SKIP_DBFS,
    Recorder,
    TextComparer,
    TRANSCRIPT_ECHO_REASON,
    TRANSCRIPT_SILENT_REASON,
    VOICE_BAND_BOOST,
    VOICE_BAND_HIGH_HZ,
    VOICE_BAND_LOW_HZ,
    _is_prompt_echo,
    _is_silent_audio,
    _measure_noise_floor_dbfs,
    _should_reduce_noise,
    _to_mono_float,
)


def _use_substitutions(rules: dict[str, str]):
    """注入规则并跳过文件 IO（clean_text 走类缓存）。"""
    return mock.patch.object(TextComparer, "_substitutions_cache", rules)


class TextComparerSubstitutionTests(unittest.TestCase):
    def test_clean_text_substitution_value_is_lowercased_after_replacement(self):
        """回归：替换值原样插入会破坏开头的 lowercase 约定，
        大写规则值（如 "HOME"）必须再次小写，否则与全小写参考文本比对得 0 分。"""
        with _use_substitutions({"um.": "HOME"}):
            self.assertEqual(TextComparer.clean_text("Um."), "home")

    def test_compare_matches_uppercase_substitution_value(self):
        """回归：规则值带大写时，比对应判定通过（而非 0 分 FAIL）。"""
        with _use_substitutions({"um.": "HOME", "yes": "APPS", "ads.": "APPS"}):
            for reference, transcript in [("home", "Um."), ("APPS", "YES"), ("apps", "Ads.")]:
                result = TextComparer.compare(transcript, reference, threshold=0.9)
                self.assertEqual(result["result"], "PASS")
                self.assertEqual(result["average"], 1.0)

    def test_clean_text_applies_rules_before_punctuation_removal(self):
        """规则 key 可含标点（如 "ads."），须在标点移除前完成匹配。"""
        with _use_substitutions({"ads.": "apps"}):
            self.assertEqual(TextComparer.clean_text("Ads."), "apps")

    def test_no_rules_leaves_text_unchanged(self):
        with _use_substitutions({}):
            self.assertEqual(TextComparer.clean_text("HOME!"), "home")


class TextComparerConnectorPunctuationTests(unittest.TestCase):
    """连字符 / 斜杠必须转成空格，而不是被标点清理直接删掉。"""

    def test_clean_text_hyphen_becomes_space(self):
        """回归：删掉连字符会把 "Wi-Fi" 并成 "wifi"，与参考列 "Wi Fi" 差一个空格，
        实测只能拿到 95.81%，永远到不了 100%。"""
        with _use_substitutions({}):
            self.assertEqual(TextComparer.clean_text("Wi-Fi off."), "wi fi off")

    def test_clean_text_slash_becomes_space(self):
        with _use_substitutions({}):
            self.assertEqual(TextComparer.clean_text("A/B test"), "a b test")

    def test_compare_hyphenated_transcript_matches_spaced_reference(self):
        with _use_substitutions({}):
            result = TextComparer.compare("Wi-Fi off.", "Wi Fi Off", threshold=0.9)
        self.assertEqual(result["result"], "PASS")
        self.assertEqual(round(result["average"] * 100, 2), 100.0)

    def test_clean_text_still_deletes_apostrophe(self):
        """撇号行为必须保持不变：参考列写 "dont" 时要能匹配识别文本 "don't"。"""
        with _use_substitutions({}):
            self.assertEqual(TextComparer.clean_text("don't"), "dont")


class AsrContextWordsTests(unittest.TestCase):
    """AsrContextWords 单元测试（txt 词表读取清洗与 context 提示串组装）。"""

    def setUp(self):
        AsrContextWords._words_cache = None
        AsrContextWords._words_mtime = 0.0
        self._tmp = tempfile.TemporaryDirectory()
        self._words_path = Path(self._tmp.name) / "asr_hotwords.txt"
        path_patcher = mock.patch.object(AsrContextWords, "_get_words_path", return_value=self._words_path)
        self._path_patcher = path_patcher.start()
        self.addCleanup(self._path_patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def _write_raw(self, content: str) -> None:
        self._words_path.write_text(content, encoding="utf-8")

    def test_get_words_missing_file_returns_empty_and_creates_nothing(self):
        """文件缺失 → 空词表（基线），且不自动建文件。"""
        self.assertEqual(AsrContextWords.get_words(), [])
        self.assertFalse(self._words_path.exists())

    def test_get_words_empty_or_comment_only_file_returns_empty(self):
        """空文件 / 纯注释文件 → 空词表。"""
        self._write_raw("")
        self.assertEqual(AsrContextWords.get_words(), [])
        self._write_raw("# Qwen3-ASR 热词表\n# app setting\n")
        self.assertEqual(AsrContextWords.get_words(), [])

    def test_get_words_parses_lines_and_skips_comments(self):
        """行解析：strip、跳过空行与 # 注释行（含行首空白）、保序去重，
        词条内部空格原样保留（"app setting" 作为整体热词）。"""
        raw = "  app setting  \n\n# 注释\n  # 缩进注释\nHOME\napp setting\n"
        self._write_raw(raw)
        self.assertEqual(AsrContextWords.get_words(), ["app setting", "HOME"])

    def test_get_words_reads_crlf_line_endings(self):
        """CRLF 行尾（Windows 手改文件）可正常解析。"""
        self._write_raw("# header\r\napp setting\r\nHOME\r\n")
        self.assertEqual(AsrContextWords.get_words(), ["app setting", "HOME"])

    def test_get_words_truncates_overflow_lines(self):
        """超限防护：词条数 ≤ 上限、单条 ≤ 字符上限。"""
        self._write_raw("\n".join(f"term-{index}" for index in range(MAX_CONTEXT_WORDS + 5)))
        os.utime(self._words_path, ns=(10_000, 10_000))
        words = AsrContextWords.get_words()
        self.assertEqual(len(words), MAX_CONTEXT_WORDS)
        self.assertEqual(words[-1], f"term-{MAX_CONTEXT_WORDS - 1}")

        self._write_raw("x" * (MAX_CONTEXT_WORD_CHARS + 10))
        os.utime(self._words_path, ns=(20_000, 20_000))
        self.assertEqual(AsrContextWords.get_words(), ["x" * MAX_CONTEXT_WORD_CHARS])

    def test_get_words_mtime_gates_reload(self):
        """mtime 缓存语义：内容变但 mtime 未变命中缓存（返回旧词表），
        mtime 前进则重读文件（外部手改可感知）。"""
        first_mtime_ns = 1_000
        second_mtime_ns = 2_000
        self._write_raw("app setting\n")
        os.utime(self._words_path, ns=(first_mtime_ns, first_mtime_ns))
        self.assertEqual(AsrContextWords.get_words(), ["app setting"])

        # 内容被外部改写但 mtime 回拨与缓存一致 → 命中缓存返回旧词表
        self._write_raw("HOME\n")
        os.utime(self._words_path, ns=(first_mtime_ns, first_mtime_ns))
        self.assertEqual(AsrContextWords.get_words(), ["app setting"])
        # mtime 前进 → 重读文件
        os.utime(self._words_path, ns=(second_mtime_ns, second_mtime_ns))
        self.assertEqual(AsrContextWords.get_words(), ["HOME"])

    def test_get_words_file_deleted_after_cache_returns_empty(self):
        """缓存建立后文件被删 → 返回空词表（不再注入）。"""
        self._write_raw("app setting\n")
        self.assertEqual(AsrContextWords.get_words(), ["app setting"])
        self._words_path.unlink()
        self.assertEqual(AsrContextWords.get_words(), [])

    def test_build_context_prompt_empty_word_list_returns_empty(self):
        self._write_raw("# 仅注释\n")
        self.assertEqual(AsrContextWords.build_context_prompt(), "")

    def test_build_context_prompt_joins_vocabulary_style(self):
        """短语热词保留内部空格，词表以 ", " 连接成 Vocabulary 前缀串。"""
        self._write_raw("app setting\nHOME\n")
        self.assertEqual(AsrContextWords.build_context_prompt(), "Vocabulary: app setting, HOME")


class TranscribeAudioContextTests(unittest.TestCase):
    """AsrService.transcribe_audio 的 context 自动套用 / 显式覆盖行为。"""

    def setUp(self):
        self._service = AsrService()

    def test_transcribe_audio_hotwords_are_applied(self):
        """词表非空时，context 自动套用为 Vocabulary 提示串。"""
        fake_backend = mock.Mock()
        fake_backend.transcribe.return_value = "ok"
        with mock.patch.object(AsrContextWords, "get_words", return_value=["app setting"]), \
             mock.patch.object(self._service, "_load_runtime_model", return_value=fake_backend):
            transcript = self._service.transcribe_audio("demo.wav", language="English")
        self.assertEqual(transcript.text, "ok")
        self.assertTrue(transcript.is_available)
        fake_backend.transcribe.assert_called_once_with(
            "demo.wav", language="English", context="Vocabulary: app setting"
        )

    def test_transcribe_audio_empty_word_list_passes_empty_context(self):
        """词表为空 → 注入空串，与旧行为（A/B 基线）一致。"""
        fake_backend = mock.Mock()
        with mock.patch.object(AsrContextWords, "get_words", return_value=[]), \
             mock.patch.object(self._service, "_load_runtime_model", return_value=fake_backend):
            self._service.transcribe_audio("demo.wav", language="English")
        fake_backend.transcribe.assert_called_once_with("demo.wav", language="English", context="")

    def test_transcribe_audio_explicit_context_overrides_word_list(self):
        """显式传 context（含空串）覆盖全局词表。"""
        fake_backend = mock.Mock()
        with mock.patch.object(AsrContextWords, "get_words", return_value=["app setting"]), \
             mock.patch.object(self._service, "_load_runtime_model", return_value=fake_backend):
            self._service.transcribe_audio("demo.wav", context="custom prompt")
        fake_backend.transcribe.assert_called_once_with("demo.wav", language="English", context="custom prompt")


class PromptEchoDetectionTests(unittest.TestCase):
    """热词提示串复读判定：静音录音下模型会顺势吐回整张词表。"""

    PROMPT = "Vocabulary: app setting, HOME, Apps, Netflix, Whale TV"

    def test_exact_prompt_echo_is_detected(self):
        """实测原样：把提示串整串吐回，仅多一个尾随句点。"""
        self.assertTrue(_is_prompt_echo(f"{self.PROMPT}.", self.PROMPT))

    def test_echo_without_prefix_is_detected(self):
        """丢掉 "Vocabulary: " 前缀的复读同样要拦住。"""
        self.assertTrue(_is_prompt_echo(self.PROMPT.replace("Vocabulary: ", ""), self.PROMPT))

    def test_normal_speech_is_kept(self):
        """正常语音即便夹带热词也不是复读，不得误杀。"""
        self.assertFalse(_is_prompt_echo("the apps menu shows HOME, Netflix, Prime Video", self.PROMPT))
        self.assertFalse(_is_prompt_echo("Flowers", self.PROMPT))

    def test_empty_transcript_or_prompt_is_kept(self):
        """空识别结果、未注入词表（显式传空 context）都不判复读。"""
        self.assertFalse(_is_prompt_echo("", self.PROMPT))
        self.assertFalse(_is_prompt_echo(self.PROMPT, ""))

    def test_tiny_word_list_cannot_be_echoed(self):
        """词表本身不足段数下限时不判复读，避免误杀短用例。"""
        self.assertFalse(_is_prompt_echo("HOME, Netflix", "Vocabulary: HOME, Netflix"))


class SilentAudioGuardTests(unittest.TestCase):
    """静音录音判定：能量低于下限即视为没录到语音。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._path = Path(self._tmp.name) / "recording.wav"

    def _write_wav(self, samples: np.ndarray) -> None:
        """按录音器的方式落盘（stdlib wave + int16），复现真实读取条件。"""
        import wave

        with wave.open(str(self._path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(16000)
            handle.writeframes(samples.astype(np.int16).tobytes())

    def test_digital_silence_is_detected(self):
        """实测掉采集那条的形态：全零采样。"""
        self._write_wav(np.zeros(16000))
        self.assertTrue(_is_silent_audio(self._path))

    def test_recorded_speech_is_kept(self):
        """实测正常录音 RMS ≈ 2e-2，不能误判成静音。"""
        t = np.linspace(0, 1.0, 16000, endpoint=False)
        self._write_wav(np.sin(2 * np.pi * 440 * t) * 0.02 * 32767)
        self.assertFalse(_is_silent_audio(self._path))

    def test_unreadable_recording_proceeds_with_recognition(self):
        """读不到的文件放行识别：判定失败不应反过来阻断正常流程。"""
        self.assertFalse(_is_silent_audio(self._path))


class TranscribeAudioGuardTests(unittest.TestCase):
    """transcribe_audio 的静音 / 复读拦截（防幻觉文本进入比对）。"""

    def setUp(self):
        self._service = AsrService()

    def test_silent_recording_skips_model_call(self):
        """静音录音不调用模型：省一次推理，且结果标明原因供调用方记 NO_REF。"""
        fake_backend = mock.Mock()
        with mock.patch.object(AsrContextWords, "get_words", return_value=["HOME"]), \
             mock.patch.object(self._service, "_load_runtime_model", return_value=fake_backend), \
             mock.patch("backend.app.services.asr_service._is_silent_audio", return_value=True):
            outcome = self._service.transcribe_audio("demo.wav")

        self.assertFalse(outcome.is_available)
        self.assertEqual(outcome.text, "")
        self.assertEqual(outcome.unavailable_reason, TRANSCRIPT_SILENT_REASON)
        fake_backend.transcribe.assert_not_called()

    def test_prompt_echo_is_discarded(self):
        """模型复读提示串时丢弃幻觉文本，不得当成识别结果参与比对。"""
        fake_backend = mock.Mock()
        fake_backend.transcribe.return_value = "Vocabulary: HOME, Netflix, Apps"
        with mock.patch.object(AsrContextWords, "get_words", return_value=["HOME", "Netflix", "Apps"]), \
             mock.patch.object(self._service, "_load_runtime_model", return_value=fake_backend), \
             mock.patch("backend.app.services.asr_service._is_silent_audio", return_value=False):
            outcome = self._service.transcribe_audio("demo.wav")

        self.assertFalse(outcome.is_available)
        self.assertEqual(outcome.text, "")
        self.assertEqual(outcome.unavailable_reason, TRANSCRIPT_ECHO_REASON)

    def test_real_transcript_passes_through(self):
        """正常识别结果原样返回。"""
        fake_backend = mock.Mock()
        fake_backend.transcribe.return_value = "hello world"
        with mock.patch.object(AsrContextWords, "get_words", return_value=["HOME", "Netflix", "Apps"]), \
             mock.patch.object(self._service, "_load_runtime_model", return_value=fake_backend), \
             mock.patch("backend.app.services.asr_service._is_silent_audio", return_value=False):
            outcome = self._service.transcribe_audio("demo.wav")

        self.assertTrue(outcome.is_available)
        self.assertEqual(outcome.text, "hello world")

    def test_unavailable_outcome_carries_no_reason_on_success(self):
        """成功路径不带不可用原因，调用方据此走正常比对。"""
        fake_backend = mock.Mock()
        fake_backend.transcribe.return_value = ""
        with mock.patch.object(AsrContextWords, "get_words", return_value=["HOME"]), \
             mock.patch.object(self._service, "_load_runtime_model", return_value=fake_backend), \
             mock.patch("backend.app.services.asr_service._is_silent_audio", return_value=False):
            outcome = self._service.transcribe_audio("demo.wav")

        self.assertTrue(outcome.is_available)
        self.assertEqual(outcome.unavailable_reason, "")


class EnhanceAudioTests(unittest.TestCase):
    """enhance_audio 的音量归一化与人声频段增强。

    回归背景：旧实现按 ``data_mono / mono_mix`` **逐样本**计算增益。``data_mono``
    里含有带通分量（带群延迟，与 mono_mix 的过零点不重合），于是比值在信号每个
    过零处爆掉并被 clip 到 [0.1, 10]。实测相对理想标量增益的 SNR 仅 18dB（约
    12% 幅度失真），听感即强烈的锯齿感。现改为标量增益 + 逐通道带通。
    """

    SAMPLE_RATE = 48000
    TARGET_DB = -20.0

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._path = Path(self._tmp.name) / "recording.wav"

    def _write_wav(self, samples: np.ndarray, sample_rate: int | None = None) -> None:
        from scipy.io import wavfile

        wavfile.write(str(self._path), sample_rate or self.SAMPLE_RATE, samples)

    def _read_wav(self) -> np.ndarray:
        from scipy.io import wavfile

        return wavfile.read(str(self._path))[1]

    def _speech_like_wave(self, duration: float = 1.0) -> np.ndarray:
        """类语音信号：基频加谐波，再叠包络起伏，过零点密集以复现原故障条件。"""
        t = np.arange(int(self.SAMPLE_RATE * duration)) / self.SAMPLE_RATE
        wave = sum(
            amplitude * np.sin(2 * np.pi * 140 * harmonic * t)
            for harmonic, amplitude in ((1, 0.5), (2, 0.3), (3, 0.2), (5, 0.12))
        )
        return wave * 0.05 * (0.5 * (1 + np.sin(2 * np.pi * 3.5 * t)))

    def test_multi_channel_matches_scalar_gain_reference(self):
        """多通道输出必须等于"标量增益 + 逐通道滤波"的参考实现。

        这是本次回归的核心断言：逐样本增益会改变波形形状，与参考值对不上——
        即便它给两个通道乘的是同一个（抖动的）系数，通道比例仍然保持不变，
        所以只比较通道比例是抓不到这个 bug 的。
        """
        from scipy.signal import butter, filtfilt

        wave = self._speech_like_wave()
        quantized = (np.stack([wave, wave * 0.5], axis=1) * 32767).astype(np.int16)
        self._write_wav(quantized)

        AsrService.enhance_audio(self._path, target_db=self.TARGET_DB)

        # 参考实现从量化后的 int16 反推，与实现内部读到的浮点值完全一致
        source = quantized.astype(np.float64) / 32767.0
        current_rms = float(np.sqrt(np.mean(source.mean(axis=1) ** 2)))
        gain = min(
            max(10 ** (self.TARGET_DB / 20) / current_rms, NORMALIZATION_GAIN_MIN),
            NORMALIZATION_GAIN_MAX,
        )
        nyquist = self.SAMPLE_RATE / 2
        b, a = butter(4, [VOICE_BAND_LOW_HZ / nyquist, VOICE_BAND_HIGH_HZ / nyquist], btype="band")
        expected = source * gain
        expected = expected + VOICE_BAND_BOOST * filtfilt(b, a, expected, axis=0)
        expected = (np.clip(expected, -1.0, 1.0) * 32767).astype(np.int16)

        np.testing.assert_allclose(self._read_wav(), expected, atol=1)

    def test_gain_is_applied_uniformly_across_channels(self):
        """两通道只差固定倍数时，处理后仍保持该倍数（立体声平衡不变）。"""
        wave = self._speech_like_wave()
        self._write_wav((np.stack([wave, wave * 0.5], axis=1) * 32767).astype(np.int16))

        AsrService.enhance_audio(self._path)

        out = self._read_wav().astype(np.float64)
        left = out[:, 0]
        audible = np.abs(left) > 200  # 避开量化噪声主导的静音段
        ratio = out[audible, 1] / left[audible]
        self.assertAlmostEqual(float(ratio.mean()), 0.5, places=2)
        self.assertLess(float(ratio.std()), 0.01)

    def test_mono_recording_is_processed_in_place(self):
        """单声道路径不受多通道改动影响。"""
        wave = self._speech_like_wave()
        self._write_wav((wave * 32767).astype(np.int16))

        AsrService.enhance_audio(self._path)

        out = self._read_wav()
        self.assertEqual(out.ndim, 1)
        self.assertGreater(float(np.max(np.abs(out))), 0)

    def test_output_never_exceeds_full_scale(self):
        """削波保护：输出不得越过满量程，否则 int16 回绕成刺耳失真。"""
        wave = self._speech_like_wave() * 4  # 故意做大声，逼出削波保护
        self._write_wav((np.stack([wave, wave], axis=1) * 32767).astype(np.int16))

        AsrService.enhance_audio(self._path, target_db=6.0)  # 目标为正 dB，必然削波

        self.assertLessEqual(int(np.max(np.abs(self._read_wav()))), 32767)

    def test_voice_boost_skipped_below_min_sample_rate(self):
        """采样率过低时只做归一化，不叠加人声频段。"""
        low_sample_rate = 4000
        t = np.arange(low_sample_rate) / low_sample_rate
        quantized = (0.05 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
        self._write_wav(quantized, sample_rate=low_sample_rate)

        AsrService.enhance_audio(self._path, voice_boost=True)

        # 参考值同样从量化数据反推，避免把 int16 量化误差算进容差
        source = quantized.astype(np.float64) / 32767.0
        gain = 10 ** (-20.0 / 20) / float(np.sqrt(np.mean(source ** 2)))
        expected = np.clip(source * gain, -1.0, 1.0) * 32767
        np.testing.assert_allclose(self._read_wav(), expected, atol=1)


class NormalizationGainTests(unittest.TestCase):
    """_compute_normalization_gain：标量增益取值与区间约束。"""

    def test_returns_scalar_from_multichannel_reference(self):
        """多通道参考信号只产出一个标量增益（逐样本增益是本次故障的根源）。"""
        gain = AsrService._compute_normalization_gain(np.array([0.2, -0.2, 0.2, -0.2]), -20.0)
        self.assertIsInstance(gain, float)

    def test_silent_reference_skips_normalization(self):
        """近似静音时不做归一化，否则本底噪声会被放大到上限倍数。"""
        self.assertEqual(AsrService._compute_normalization_gain(np.zeros(64), -20.0), 1.0)

    def test_gain_clamped_to_upper_bound(self):
        """极弱信号（-60dB 级采集卡）也须被限制在上限内。"""
        self.assertEqual(
            AsrService._compute_normalization_gain(np.full(64, 1e-5), -20.0),
            NORMALIZATION_GAIN_MAX,
        )

    def test_gain_clamped_to_lower_bound(self):
        """过响录音只衰减到下限，避免把信号压没。"""
        self.assertEqual(
            AsrService._compute_normalization_gain(np.full(64, 2.0), -20.0),
            NORMALIZATION_GAIN_MIN,
        )


class VoiceBandBoostTests(unittest.TestCase):
    """_add_voice_band：带通叠加效果与频带越界保护。"""

    def test_boost_adds_energy_within_voice_band(self):
        """落在通带内的分量应被增强。"""
        t = np.arange(48000) / 48000
        data = 0.1 * np.sin(2 * np.pi * 1000 * t)
        boosted = AsrService._add_voice_band(data, 48000)
        self.assertGreater(
            float(np.sqrt(np.mean(boosted ** 2))),
            float(np.sqrt(np.mean(data ** 2))),
        )

    def test_band_above_nyquist_returns_input_unchanged(self):
        """300Hz 已越过奈奎斯特时不处理，避免设计出非法频带。"""
        data = np.linspace(-0.5, 0.5, 4000)
        np.testing.assert_array_equal(AsrService._add_voice_band(data, 600), data)


class SaveRecordingMonoTests(unittest.TestCase):
    """save_recording：多通道采集一律降混成单声道落盘。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._path = Path(self._tmp.name) / "recording.wav"

    def _make_recorder(self, blocks: list[np.ndarray]) -> Recorder:
        recorder = Recorder(sample_rate=16000, channels=1)
        recorder.recording_data = blocks
        return recorder

    def _read_header(self) -> tuple[int, int, int]:
        import wave

        with wave.open(str(self._path), "rb") as handle:
            return handle.getnchannels(), handle.getframerate(), handle.getsampwidth()

    def test_stereo_buffer_is_written_as_mono(self):
        """设备原生 2 通道时也落成单声道。

        立体声没有信息增益（各路内容一致），却会触发 enhance_audio 的立体声专属
        分支——那个分支正是本次锯齿感故障的所在。录成单声道后根本不会进入它。
        """
        stereo_block = np.concatenate([np.full((100, 1), 0.5), np.full((100, 1), 0.5)], axis=1)

        self._make_recorder([stereo_block]).save_recording(self._path)

        self.assertEqual(self._read_header(), (1, 16000, 2))

    def test_stereo_downmix_averages_channels(self):
        """降混取通道均值，与 reduce_noise / ASR 读入的单声道化方式保持一致。"""
        from scipy.io import wavfile

        stereo_block = np.concatenate([np.full((100, 1), 0.5), np.full((100, 1), 1.0)], axis=1)

        self._make_recorder([stereo_block]).save_recording(self._path)

        samples = wavfile.read(str(self._path))[1]
        self.assertEqual(samples.ndim, 1)
        self.assertAlmostEqual(float(samples.mean()), 0.75 * 32767, delta=2)

    def test_mono_buffer_still_written_as_mono(self):
        self._make_recorder([np.full((100, 1), 0.25)]).save_recording(self._path)

        self.assertEqual(self._read_header()[0], 1)

    def test_empty_buffer_raises(self):
        with self.assertRaises(AsrRuntimeError):
            self._make_recorder([]).save_recording(self._path)


class NoiseFloorGateTests(unittest.TestCase):
    """降噪前置门控：本底噪声已贴量化极限时没有噪声可降，必须跳过。

    回归背景：采集卡数字直采的录音底噪在 -91dBFS（16bit 量化极限），
    stationary=False 的非平稳门控仍会逐帧追着量化噪声开合，实测每遍改动
    16% 信号能量且不收敛，27 条真实录音对照显示多降一遍 99.20% → 96.19%。
    """

    SAMPLE_RATE = 48000

    def _speech_like(self, seconds: float = 3.0) -> np.ndarray:
        t = np.arange(int(self.SAMPLE_RATE * seconds)) / self.SAMPLE_RATE
        return 0.3 * np.sin(2 * np.pi * 440 * t) * (np.sin(2 * np.pi * 2 * t) > 0)

    def _with_noise(self, noise_db: float) -> np.ndarray:
        rng = np.random.default_rng(0)
        speech = self._speech_like()
        return speech + rng.normal(0, 10 ** (noise_db / 20), len(speech))

    def test_measure_noise_floor_tracks_injected_noise_level(self):
        """估计值应贴近注入的噪声电平，否则门控阈值无从谈起。"""
        for noise_db in (-40, -50, -60, -70):
            measured = _measure_noise_floor_dbfs(self._with_noise(noise_db), self.SAMPLE_RATE)
            self.assertAlmostEqual(measured, noise_db, delta=2.0)

    def test_measure_noise_floor_clean_recording_sits_at_quantization_limit(self):
        """纯语音无底噪时，本底应远低于 -80dBFS 阈值。"""
        measured = _measure_noise_floor_dbfs(self._speech_like(), self.SAMPLE_RATE)
        self.assertLess(measured, NOISE_FLOOR_SKIP_DBFS)

    def test_measure_noise_floor_too_short_returns_none(self):
        """短于一帧无从判断，返回 None 而非编造一个值。"""
        self.assertIsNone(_measure_noise_floor_dbfs(np.zeros(10), self.SAMPLE_RATE))

    def test_should_reduce_noise_clean_recording_is_skipped(self):
        """数字直采录音（本底 -91dBFS）必须跳过降噪。"""
        self.assertFalse(_should_reduce_noise(-91.3))

    def test_should_reduce_noise_real_noise_is_processed(self):
        for noise_floor_db in (-60.0, -40.0, -20.0):
            self.assertTrue(_should_reduce_noise(noise_floor_db))

    def test_should_reduce_noise_at_threshold_is_skipped(self):
        """阈值本身算"够干净"，用严格大于比较。"""
        self.assertFalse(_should_reduce_noise(NOISE_FLOOR_SKIP_DBFS))
        self.assertTrue(_should_reduce_noise(NOISE_FLOOR_SKIP_DBFS + 0.1))

    def test_should_reduce_noise_unknown_floor_is_skipped(self):
        """无从判断时不做：降噪实测有害，拿不准就不动。"""
        self.assertFalse(_should_reduce_noise(None))

    def test_reduce_noise_skips_clean_recording_without_calling_denoiser(self):
        """干净录音必须原样返回，且不得调用 noisereduce（调用即产生伪影）。"""
        from scipy.io import wavfile

        path = Path(tempfile.mkdtemp()) / "clean.wav"
        wavfile.write(str(path), self.SAMPLE_RATE, (self._speech_like() * 32767).astype(np.int16))
        original = path.read_bytes()

        with mock.patch("noisereduce.reduce_noise") as denoiser:
            returned = AsrService.reduce_noise(path)

        denoiser.assert_not_called()
        self.assertEqual(returned, path)
        self.assertEqual(path.read_bytes(), original)

    def test_reduce_noise_processes_recording_with_real_noise(self):
        """真有本底噪声时才走降噪，且写回文件。"""
        from scipy.io import wavfile

        path = Path(tempfile.mkdtemp()) / "noisy.wav"
        noisy = self._with_noise(-45.0)
        wavfile.write(str(path), self.SAMPLE_RATE, (noisy * 32767).astype(np.int16))

        denoised = np.zeros_like(noisy)
        with mock.patch("noisereduce.reduce_noise", return_value=denoised) as denoiser:
            AsrService.reduce_noise(path)

        denoiser.assert_called_once()
        self.assertEqual(wavfile.read(str(path))[1].shape, denoised.shape)


class ToMonoFloatTests(unittest.TestCase):
    """_to_mono_float：整数归一化 + 降混，reduce_noise 与 ASR 读入共用。"""

    def test_int16_is_normalized_to_unit_range(self):
        result = _to_mono_float(np.array([32767, -32768, 0], dtype=np.int16))
        self.assertAlmostEqual(float(result.max()), 1.0, places=4)
        self.assertAlmostEqual(float(result.min()), -1.0, places=4)

    def test_stereo_is_downmixed_by_averaging_channels(self):
        stereo = np.array([[100, 300], [-100, -300]], dtype=np.int16)
        result = _to_mono_float(stereo)
        self.assertEqual(result.ndim, 1)
        self.assertAlmostEqual(float(result[0]), 200 / 32767, places=6)

    def test_mono_stays_one_dimensional(self):
        self.assertEqual(_to_mono_float(np.zeros(8, dtype=np.int16)).ndim, 1)


if __name__ == "__main__":
    unittest.main()

import unittest
import wave
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import numpy as np
from fastapi import UploadFile

from backend.app.services.asr_service import AsrService


class AsrServiceDependencyStatusTests(unittest.TestCase):
    @staticmethod
    def _detail(available: bool, missing_module: str | None = None, error: str = "") -> dict:
        return {
            "available": available,
            "missing_module": missing_module,
            "error": error,
        }

    def test_get_runtime_dependency_status_reports_frozen_runtime_guidance(self):
        service = AsrService()
        dependency_details = {
            "sounddevice": self._detail(True),
            "qwen_asr": self._detail(False, "qwen_asr", "未找到模块 qwen_asr"),
            "torch": self._detail(True),
        }

        with mock.patch.object(service, "_inspect_dependency", side_effect=lambda name: dependency_details[name]), \
             mock.patch("backend.app.services.asr_service.sys.frozen", True, create=True), \
             mock.patch("backend.app.services.asr_service.sys.executable", "D:/Project/Check/dist/AutoDeck.exe"):
            status = service.get_runtime_dependency_status()

        self.assertEqual(status["runtime_mode"], "frozen")
        self.assertEqual(status["executable_path"], "D:/Project/Check/dist/AutoDeck.exe")
        self.assertEqual(status["missing"], ["qwen_asr"])
        self.assertTrue(status["restart_required"])
        self.assertIn("当前运行的是打包版 AutoDeck.exe", status["install_steps"][0])
        self.assertIn("build_exe.bat", " ".join(status["install_steps"]))
        self.assertTrue(any("AutoDeck.exe" in note for note in status["notes"]))
        self.assertEqual(status["dependency_details"]["qwen_asr"]["missing_module"], "qwen_asr")

    def test_get_runtime_dependency_status_surfaces_transitive_import_failure(self):
        service = AsrService()
        dependency_details = {
            "sounddevice": self._detail(True),
            "qwen_asr": self._detail(
                False,
                "nagisa",
                "导入 qwen_asr 失败，当前缺少其传递依赖 nagisa: No module named 'nagisa'",
            ),
            "torch": self._detail(True),
        }

        with mock.patch.object(service, "_inspect_dependency", side_effect=lambda name: dependency_details[name]):
            status = service.get_runtime_dependency_status()

        self.assertEqual(status["missing"], ["qwen_asr"])
        self.assertIn("nagisa", status["dependency_details"]["qwen_asr"]["error"])
        self.assertTrue(any("nagisa" in note for note in status["notes"]))


class EnhanceAudioTests(unittest.TestCase):
    @staticmethod
    def _write_wav(path: Path, samples: np.ndarray, sr: int = 48000) -> None:
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes((np.clip(samples, -1, 1) * 32767).astype(np.int16).tobytes())

    @staticmethod
    def _read_wav_rms(path: Path) -> tuple[float, float]:
        with wave.open(str(path), "rb") as w:
            data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
        return float(np.sqrt(np.mean(data ** 2))), float(np.max(np.abs(data)))

    def test_enhance_audio_boosts_very_quiet_signal_to_target_level(self):
        # 模拟采集卡极弱信号（RMS ~ -63dB），归一化后应接近 -20dB 目标且不削波
        sr = 48000
        t = np.arange(sr * 2) / sr
        sig = 0.001 * np.sin(2 * np.pi * 800 * t)  # RMS ≈ 0.0007
        with TemporaryDirectory() as tmp_dir:
            audio_path = Path(tmp_dir) / "quiet.wav"
            self._write_wav(audio_path, sig, sr)

            AsrService.enhance_audio(audio_path, target_db=-20.0)

            rms, peak = self._read_wav_rms(audio_path)
            target_rms = 10 ** (-20 / 20)
            self.assertGreater(rms, target_rms * 0.5, "弱信号应被放大到接近 -20dB 目标")
            self.assertLess(rms, target_rms * 2.0, "不应过度放大")
            self.assertLessEqual(peak, 1.0, "不应削波溢出")

    def test_enhance_audio_caps_extreme_gain(self):
        # 噪声级极弱信号应受 200x 增益上限约束，不会被无限放大
        sr = 48000
        t = np.arange(sr) / sr
        sig = 0.0001 * np.sin(2 * np.pi * 800 * t)  # RMS ≈ 7e-5，需要 1400x 才到目标
        with TemporaryDirectory() as tmp_dir:
            audio_path = Path(tmp_dir) / "tiny.wav"
            self._write_wav(audio_path, sig, sr)

            AsrService.enhance_audio(audio_path, target_db=-20.0)

            rms, peak = self._read_wav_rms(audio_path)
            self.assertLess(rms, 0.05, "增益应被 200x 上限约束，不会爆音")


class AsrServiceResourceResolutionTests(unittest.TestCase):
    def test_find_reference_uses_bundled_reference_root_when_runtime_copy_missing(self):
        with TemporaryDirectory() as runtime_dir, TemporaryDirectory() as bundle_dir:
            runtime_root = Path(runtime_dir)
            bundle_root = Path(bundle_dir)
            bundled_reference_dir = bundle_root / "Project" / "voice_recorder_compare" / "references"
            bundled_reference_dir.mkdir(parents=True, exist_ok=True)
            reference_file = bundled_reference_dir / "case_1001.txt"
            reference_file.write_text("hello bundled world", encoding="utf-8")

            with mock.patch("backend.app.services.asr_service.settings.WORKING_DIR", runtime_root), \
                 mock.patch("backend.app.services.asr_service.settings.BUNDLE_DIR", bundle_root):
                service = AsrService()

            result = service.find_reference("case 1001")

            self.assertIsNotNone(result)
            self.assertEqual(result["text"], "hello bundled world")
            self.assertEqual(result["path"], str(reference_file))

    def test_save_imported_model_file_persists_uploaded_file_and_sets_active_model(self):
        with TemporaryDirectory() as runtime_dir, TemporaryDirectory() as bundle_dir:
            runtime_root = Path(runtime_dir)
            bundle_root = Path(bundle_dir)

            with mock.patch("backend.app.services.asr_service.settings.WORKING_DIR", runtime_root), \
                 mock.patch("backend.app.services.asr_service.settings.BUNDLE_DIR", bundle_root), \
                 mock.patch("backend.app.services.asr_service.settings.ASR_MODELS_DIR", runtime_root / "asr_models"):
                service = AsrService()

            upload = UploadFile(filename="weights.bin", file=BytesIO(b"model-bytes"))

            result = service.save_imported_model_file("demo_model", "nested/weights.bin", upload)

            saved_path = Path(result["saved_path"])
            self.assertTrue(saved_path.exists())
            self.assertEqual(saved_path.read_bytes(), b"model-bytes")
            self.assertEqual(result["status"], "success")
            self.assertEqual(service.get_active_model()["name"], "demo_model")


if __name__ == "__main__":
    unittest.main()
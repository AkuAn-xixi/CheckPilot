"""图片校验配置的单一真源。

默认值此前在 ``services/image_service.py`` 与 ``api/customization.py`` 各写了一份，
改一处要记得同步另一处。这里集中定义，两侧都从这里取，新增校验参数不会再制造
第二处不一致。

本模块刻意只依赖标准库：``image_service`` 需要在避开 openpyxl（首次导入约 1.6s）
的前提下复用它，而 ``utils`` 包的 ``__init__`` 会连带导入 adb_controller，故这里
既不导入 api 层也不导入 utils 层。
"""

from dataclasses import asdict, dataclass
from typing import Any, Mapping

ENGINE_OPENCV = "opencv"
ENGINE_AIRTEXT = "airtest"
SUPPORTED_ENGINES: tuple[str, ...] = (ENGINE_OPENCV, ENGINE_AIRTEXT)
DEFAULT_VERIFY_ENGINE = ENGINE_OPENCV

DEFAULT_COLOR_MIN_SIMILARITY = 0.4
DEFAULT_COLOR_WEIGHT = 0.2
DEFAULT_FEATURE_MIN_SIMILARITY = 0.3
# 颜色下限取 0.4 的依据（opencv 引擎，实测）：形状/结构匹配但颜色明显不同的按钮
# （如同一按钮换主题色）不应被判为匹配；同一按钮的明暗差异（HSV 直方图忽略 V）
# 与轻微色差仍能通过（同图基线实测 ≥0.72），色相明显不同（≥20° 偏移，实测 ≤0.31）
# 则判不匹配。

# airtest 的 confidence 与 opencv 引擎的融合分不是同一把尺子，阈值不可平移：
# airtest 自身的 Settings.THRESHOLD 默认是 0.7，但本项目实测 0.7 会放过约 6% 的
# 未命中，故取 0.85。完整实测记录见 utils/airtest_matcher/models.DEFAULT_THRESHOLD。
DEFAULT_AIRTEXT_THRESHOLD = 0.85
DEFAULT_AIRTEXT_RGB = False
# 与 utils.airtest_matcher 的内核默认值一致，由 test_verify_config 的漂移守卫锁定
DEFAULT_AIRTEXT_STRATEGY = "tpl"
SUPPORTED_AIRTEXT_STRATEGIES: tuple[str, ...] = (DEFAULT_AIRTEXT_STRATEGY, "mstpl")


@dataclass(frozen=True)
class VerifyConfig:
    """一次图片校验的全部参数。

    Attributes:
        verify_engine: 校验引擎，``opencv``（默认）或 ``airtest``。
        color_min_similarity: opencv 引擎的颜色相似度下限。
        color_weight: opencv 引擎最终分里颜色的权重。
        feature_min_similarity: opencv 引擎的特征相似度下限。
        airtest_threshold: airtest 引擎的置信度阈值。
        airtest_rgb: airtest 引擎是否启用逐通道比色（更慢，对配色敏感）。
        airtest_strategy: airtest 引擎的匹配策略，``tpl`` 或 ``mstpl``。
    """

    verify_engine: str = DEFAULT_VERIFY_ENGINE
    color_min_similarity: float = DEFAULT_COLOR_MIN_SIMILARITY
    color_weight: float = DEFAULT_COLOR_WEIGHT
    feature_min_similarity: float = DEFAULT_FEATURE_MIN_SIMILARITY
    airtest_threshold: float = DEFAULT_AIRTEXT_THRESHOLD
    airtest_rgb: bool = DEFAULT_AIRTEXT_RGB
    airtest_strategy: str = DEFAULT_AIRTEXT_STRATEGY

    def to_dict(self) -> dict[str, Any]:
        """转成可直接落盘/返回给前端的普通字典。"""
        return asdict(self)


def normalize_unit_interval(value: Any, default: float) -> float:
    """把任意输入归一化为 0~1 的小数；非法值回落到 ``default``。"""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if 0.0 <= parsed <= 1.0 else default


def normalize_engine(value: Any) -> str:
    """把任意输入归一化为受支持的引擎名；非法值回落到默认引擎。"""
    if isinstance(value, str) and value.strip() in SUPPORTED_ENGINES:
        return value.strip()
    return DEFAULT_VERIFY_ENGINE


def normalize_airtest_strategy(value: Any) -> str:
    """把任意输入归一化为受支持的匹配策略；非法值回落到默认策略。"""
    if isinstance(value, str) and value.strip() in SUPPORTED_AIRTEXT_STRATEGIES:
        return value.strip()
    return DEFAULT_AIRTEXT_STRATEGY


def normalize_airtest_rgb(value: Any) -> bool:
    """把任意输入归一化为布尔值；非法值回落到默认（灰度匹配）。"""
    return value if isinstance(value, bool) else DEFAULT_AIRTEXT_RGB


def normalize_verify_config(data: Mapping[str, Any] | None) -> VerifyConfig:
    """把原始配置字典归一化为 :class:`VerifyConfig`。

    Args:
        data: customization.json 的内容；None 或非映射时全取默认值。

    Returns:
        归一化后的配置，任何非法字段各自回落到默认值，不抛异常。
    """
    if not isinstance(data, Mapping):
        data = {}

    return VerifyConfig(
        verify_engine=normalize_engine(data.get("verify_engine")),
        color_min_similarity=normalize_unit_interval(
            data.get("color_min_similarity"), DEFAULT_COLOR_MIN_SIMILARITY
        ),
        color_weight=normalize_unit_interval(data.get("color_weight"), DEFAULT_COLOR_WEIGHT),
        feature_min_similarity=normalize_unit_interval(
            data.get("feature_min_similarity"), DEFAULT_FEATURE_MIN_SIMILARITY
        ),
        airtest_threshold=normalize_unit_interval(
            data.get("airtest_threshold"), DEFAULT_AIRTEXT_THRESHOLD
        ),
        airtest_rgb=normalize_airtest_rgb(data.get("airtest_rgb")),
        airtest_strategy=normalize_airtest_strategy(data.get("airtest_strategy")),
    )

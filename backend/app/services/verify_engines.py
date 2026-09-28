"""图片校验引擎的注册表与 airtest 适配器。

依赖方向 ``image_service → verify_engines → utils.airtest_matcher``，单向无环。
本模块**不 import ``image_service``**（否则与 ``services/__init__`` 的 eager import
成环）；opencv 引擎由 ``image_service`` 在导入时自行注册。

范式照搬 ``asr_service`` 的「常量 + 注册表 + 工厂 + 未知值回落」四件套。
"""

import logging
from typing import Any, Callable, Dict, Protocol

import numpy as np

from ..models.verify_config import (
    DEFAULT_AIRTEXT_THRESHOLD,
    ENGINE_AIRTEXT,
    ENGINE_OPENCV,
    VerifyConfig,
)
from ..utils.airtest_matcher import MatchOptions, MatchOutcome, match_template

_log = logging.getLogger(__name__)

_DECIMALS = 4


class VerifyEngine(Protocol):
    """图片校验引擎：给定截图、模板与请求级阈值，返回统一结构的结果字典。"""

    name: str

    def match(self, screen: np.ndarray, template: np.ndarray, threshold: float) -> Dict[str, Any]:
        """执行一次校验并返回 canonical 结果字典。"""
        ...


_ENGINE_FACTORIES: Dict[str, Callable[[VerifyConfig], VerifyEngine]] = {}


def register_engine(kind: str, factory: Callable[[VerifyConfig], VerifyEngine]) -> None:
    """注册一个引擎工厂（由各引擎自己的模块在导入时调用）。"""
    _ENGINE_FACTORIES[kind] = factory


def build_engine(kind: str, config: VerifyConfig) -> VerifyEngine:
    """按引擎名构造引擎实例；未知或未注册的引擎回落到 opencv。

    Raises:
        RuntimeError: 连兜底的 opencv 引擎都未注册（说明导入顺序有误）。
    """
    factory = _ENGINE_FACTORIES.get(kind)
    if factory is None:
        _log.warning("未知或未注册的校验引擎 %s，回落 %s", kind, ENGINE_OPENCV)
        factory = _ENGINE_FACTORIES.get(ENGINE_OPENCV)
    if factory is None:
        raise RuntimeError(f"校验引擎 {ENGINE_OPENCV} 未注册，检查 image_service 是否已导入")
    return factory(config)


class AirtestEngine:
    """airtest 模板匹配引擎。

    airtest 不产出模板/结构/特征/颜色四路分数，故结果字典里**不填**这些键 ——
    报告端按「有键才显示」渲染，缺键自然不显示，比编造可比性存疑的数字诚实。
    """

    name = ENGINE_AIRTEXT

    def __init__(self, config: VerifyConfig) -> None:
        """初始化引擎。

        Args:
            config: 校验配置；阈值与开关逐次传入内核，不依赖内核类默认值。
        """
        self._config = config

    def match(self, screen: np.ndarray, template: np.ndarray, threshold: float) -> Dict[str, Any]:
        """在截图中查找模板，返回带匹配坐标的结果字典。

        Args:
            screen: 截图（BGR）。
            template: 参考图（BGR）。
            threshold: 请求级阈值，**仅 opencv 引擎使用**；airtest 用自己的配置
                阈值（两者量纲不同，不可互换）。

        Returns:
            canonical 结果字典，含 ``engine``/``confidence``/``match_rect_*`` 等键。
        """
        airtest_threshold = _normalize_threshold(self._config.airtest_threshold)
        outcome = match_template(
            screen,
            template,
            MatchOptions(
                threshold=airtest_threshold,
                rgb=self._config.airtest_rgb,
                strategy=self._config.airtest_strategy,
            ),
        )
        result = _build_result(outcome, self._config, airtest_threshold)
        if outcome.rect is not None:
            _apply_coordinates(result, outcome)
        return result


def _normalize_threshold(value: Any) -> float:
    """把配置里的 airtest 阈值兜底成合法小数（配置层已归一化，这里防御性再取一次）。"""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return DEFAULT_AIRTEXT_THRESHOLD
    return parsed if 0.0 <= parsed <= 1.0 else DEFAULT_AIRTEXT_THRESHOLD


def _build_result(outcome: MatchOutcome, config: VerifyConfig, threshold: float) -> Dict[str, Any]:
    """把 :class:`MatchOutcome` 映射成本项目的 canonical 结果字典。"""
    matched = outcome.matched
    result: Dict[str, Any] = {
        "success": True,
        "matched": matched,
        "engine": ENGINE_AIRTEXT,
        # airtest 的 confidence 直接作为相似度展示，与既有「相似度 X%」口径一致
        "score": round(float(outcome.confidence), _DECIMALS),
        "confidence": round(float(outcome.confidence), _DECIMALS),
        "airtest_threshold": threshold,
        "strategy": outcome.strategy,
        "rgb_used": bool(config.airtest_rgb),
        "message": "验证成功" if matched else "验证失败",
    }
    if outcome.message:
        result["message"] = f"{result['message']}：{outcome.message}"
    return result


def _apply_coordinates(result: Dict[str, Any], outcome: MatchOutcome) -> None:
    """把匹配坐标写入结果字典。

    坐标必须扁平化成标量：报告端 ``_normalize_compare_details`` 只放行
    str/int/float/bool，元组与嵌套数组会被静默丢掉。
    """
    left, top, width, height = outcome.rect
    result.update({
        "match_rect_x": int(left),
        "match_rect_y": int(top),
        "match_rect_w": int(width),
        "match_rect_h": int(height),
    })
    if outcome.target is not None:
        result.update({
            "match_target_x": int(outcome.target[0]),
            "match_target_y": int(outcome.target[1]),
        })


register_engine(ENGINE_AIRTEXT, AirtestEngine)

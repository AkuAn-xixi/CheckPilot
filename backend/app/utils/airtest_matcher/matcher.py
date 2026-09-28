"""本包唯一对外入口：把上游两类匹配器统一成 :class:`MatchOutcome`。

这一层是本项目自有的胶水代码（非上游移植）：负责入参校验、灰度/BGRA 归一化、
按策略选择匹配器，以及把上游的 ``{"result","rectangle","confidence"}`` 字典
翻译成领域无关的返回值。业务语义（如何判定通过、怎么写报告）不在这里，
由 ``services/verify_engines.py`` 负责。
"""

import logging
import time

import numpy as np

from .errors import TemplateInputError
from .image_ops import check_source_larger_than_search, img_mat_rgb_2_gray
from .models import (
    DEFAULT_STRATEGY,
    STRATEGY_MULTISCALE,
    STRATEGY_TEMPLATE,
    MatchOptions,
    MatchOutcome,
)
from .multiscale_template_matching import MultiScaleTemplateMatching
from .template_matching import TemplateMatching

_log = logging.getLogger(__name__)

_MAX_CHANNELS = 3

# 模板灰度标准差低于此值即视为纯色（实测纯色模板的 std 恒为 0.0，
# 而含内容的模板即便整体偏色也在 5 以上，两者之间留足余量）
_FLAT_TEMPLATE_STD_EPS = 1.0


def match_template(
    screen: np.ndarray,
    template: np.ndarray,
    options: MatchOptions | None = None,
) -> MatchOutcome:
    """在截图中查找模板。

    Args:
        screen: 截图图像（BGR ndarray；灰度或 BGRA 会被自动转换）。
        template: 模板图像（同上）。
        options: 匹配参数；None 时取本项目默认值（阈值 0.7、灰度、单尺度）。

    Returns:
        匹配结果。入参不合法（空图、模板大于截图）时以 ``matched=False`` +
        ``message`` 返回而不抛异常，便于上层统一记为该次校验未命中，
        而不是执行错误。
    """
    opts = options or MatchOptions()
    problem = _describe_input_problem(screen, template)
    if problem:
        return _failed_outcome(opts, problem)
    return _run_match(_ensure_bgr(screen), _ensure_bgr(template), opts)


def _describe_input_problem(screen: np.ndarray, template: np.ndarray) -> str:
    """检查入参是否可用于匹配，返回问题描述（无问题返回空串）。"""
    for name, image in (("截图", screen), ("模板", template)):
        if not isinstance(image, np.ndarray) or image.size == 0:
            return f"{name}为空，无法匹配"
        if image.ndim not in (2, _MAX_CHANNELS):
            return f"{name}维度非法：{image.ndim}"
    return ""


def _ensure_bgr(image: np.ndarray) -> np.ndarray:
    """把灰度/BGRA 图像统一成三通道 BGR。"""
    if image.ndim == 2:
        return np.stack([image] * _MAX_CHANNELS, axis=-1)
    if image.shape[2] == 4:
        return image[:, :, :_MAX_CHANNELS]
    return image


def _failed_outcome(options: MatchOptions, message: str) -> MatchOutcome:
    """构造一个「未命中」结果。"""
    return MatchOutcome(
        matched=False,
        confidence=0.0,
        strategy=options.strategy,
        message=message,
    )


def _run_match(
    screen: np.ndarray,
    template: np.ndarray,
    options: MatchOptions,
) -> MatchOutcome:
    """按策略执行匹配并整理结果。"""
    if _is_flat_template(template):
        return _match_flat_template(screen, template, options)

    matcher = _build_matcher(screen, template, options)
    started_at = time.perf_counter()
    try:
        best_match = matcher.find_best_result()
    except TemplateInputError as e:
        _log.warning("模板匹配入参非法: %s", e)
        return _failed_outcome(options, str(e))
    elapsed = time.perf_counter() - started_at

    if best_match is None:
        # 未命中也要给出真实分数，报告里才能看出「差多少」以便标定阈值
        return MatchOutcome(
            matched=False,
            confidence=float(matcher.last_confidence),
            strategy=options.strategy,
            elapsed_seconds=elapsed,
            message=(
                f"未达到阈值 {options.threshold:.2f}"
                f"（实际 {matcher.last_confidence:.4f}）"
            ),
        )

    return MatchOutcome(
        matched=True,
        confidence=float(best_match["confidence"]),
        strategy=options.strategy,
        rect=_to_bounding_box(best_match["rectangle"]),
        target=(int(best_match["result"][0]), int(best_match["result"][1])),
        elapsed_seconds=elapsed,
    )


def _is_flat_template(template: np.ndarray) -> bool:
    """模板是否为纯色（零方差）。"""
    return float(img_mat_rgb_2_gray(template).std()) < _FLAT_TEMPLATE_STD_EPS


def _match_flat_template(
    screen: np.ndarray,
    template: np.ndarray,
    options: MatchOptions,
) -> MatchOutcome:
    """纯色模板一律判为未命中。

    零方差模板在两条路子上都给不出可用位置：``TM_CCOEFF_NORMED`` 对它的相关系
    数无定义，OpenCV 恒返回 1.0 并取扫描序第一个位置，纯色校验图会稳定输出
    ``(0, 0)`` 这个假坐标；``TM_SQDIFF_NORMED`` 在纯黑模板上同样退化为恒 1.0
    （分母含模板自身平方和），非黑的纯色模板又会与画面上任何同色区域同分，
    位置不唯一。

    纯色参考图本就不携带位置信息，报一个「命中」出来比判未命中更容易误导使用
    者。故直接判未命中，与既有 opencv 引擎对纯色模板的判定保持一致（opencv 引
    擎对纯黑/纯白/纯灰模板实测均返回 matched=False），避免切换引擎后同一用例
    的结论翻转。
    """
    try:
        check_source_larger_than_search(screen, template)
    except TemplateInputError as e:
        return _failed_outcome(options, str(e))

    return MatchOutcome(
        matched=False,
        confidence=0.0,
        strategy=options.strategy,
        message="纯色参考图不携带位置信息，无法定位；请改用含内容的参考图",
    )


def _build_matcher(
    screen: np.ndarray,
    template: np.ndarray,
    options: MatchOptions,
) -> MultiScaleTemplateMatching | TemplateMatching:
    """按策略构造匹配器；未知策略回落到默认策略。"""
    if options.strategy == STRATEGY_MULTISCALE:
        return MultiScaleTemplateMatching(
            im_search=template,
            im_source=screen,
            threshold=options.threshold,
            rgb=options.rgb,
            scale_max=options.scale_max,
            scale_step=options.scale_step,
        )

    if options.strategy != STRATEGY_TEMPLATE:
        _log.warning("未知匹配策略 %s，回落到 %s", options.strategy, DEFAULT_STRATEGY)

    return TemplateMatching(
        im_search=template, im_source=screen, threshold=options.threshold, rgb=options.rgb
    )


def _to_bounding_box(rectangle: tuple[tuple[int, int], ...]) -> tuple[int, int, int, int]:
    """把上游的四角点矩形转成 ``(左上角 x, 左上角 y, 宽, 高)``。"""
    left_top, _, right_bottom, _ = rectangle
    return (
        int(left_top[0]),
        int(left_top[1]),
        int(right_bottom[0] - left_top[0]),
        int(right_bottom[1] - left_top[1]),
    )

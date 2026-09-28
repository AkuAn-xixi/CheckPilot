"""移植自 aircv/utils.py 的图像 helper（Apache-2.0，见同目录 NOTICE）。

上游该文件还包含 PIL 互转、base64/PIL 压缩等 helper，本项目不需要（输入统一为
BGR ndarray），故只保留模板匹配实际用到的四个：

- :func:`generate_result`：把匹配结果整理成上游约定的字典结构
- :func:`check_source_larger_than_search`：模板不得大于截图
- :func:`img_mat_rgb_2_gray`：BGR 转灰度
- :func:`log_run_time`：记录单次匹配耗时（上游 ``print_run_time``）
"""

import functools
import logging
import time
from typing import Any, Callable, TypeVar

import cv2
import numpy as np

from .errors import TemplateInputError

_log = logging.getLogger(__name__)

_F = TypeVar("_F", bound=Callable[..., Any])


def log_run_time(func: _F) -> _F:
    """记录被装饰方法的执行耗时。

    上游会把耗时写回结果字典的 ``time`` 键；此处保持该行为不变，
    调用方可直接从匹配结果里取得单次耗时用于性能观测。
    """

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        start_time = time.time()
        result = func(self, *args, **kwargs)
        elapsed = time.time() - start_time
        _log.debug("%s() 耗时 %.3f 秒", func.__name__, elapsed)
        if result and isinstance(result, dict):
            result["time"] = elapsed
        return result

    return wrapper  # type: ignore[return-value]


def generate_result(
    middle_point: tuple[int, int],
    pypts: tuple[tuple[int, int], ...],
    confidence: float,
) -> dict[str, Any]:
    """整理图像识别结果。

    Args:
        middle_point: 目标中心点坐标 (x, y)。
        pypts: 目标矩形四个角点，点序为左上 -> 左下 -> 右下 -> 右上。
        confidence: 匹配置信度。

    Returns:
        含 ``result``（中心点）/``rectangle``（角点）/``confidence`` 的字典。
    """
    return dict(result=middle_point, rectangle=pypts, confidence=confidence)


def check_source_larger_than_search(im_source: np.ndarray, im_search: np.ndarray) -> None:
    """校验模板尺寸不大于截图尺寸。

    Raises:
        TemplateInputError: 模板的高或宽大于截图时抛出。
    """
    h_search, w_search = im_search.shape[:2]
    h_source, w_source = im_source.shape[:2]
    if h_search > h_source or w_search > w_source:
        raise TemplateInputError(
            f"模板({w_search}x{h_search})大于截图({w_source}x{h_source})，无法匹配"
        )


def img_mat_rgb_2_gray(img_mat: np.ndarray) -> np.ndarray:
    """把 BGR 图像矩阵转为灰度矩阵（cv2.matchTemplate 只接受单通道）。

    Args:
        img_mat: 三通道 BGR 图像矩阵。

    Returns:
        单通道灰度矩阵。
    """
    assert isinstance(img_mat[0][0], np.ndarray), "input must be instance of np.ndarray"
    return cv2.cvtColor(img_mat, cv2.COLOR_BGR2GRAY)

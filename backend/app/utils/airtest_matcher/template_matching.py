"""移植自 aircv/template_matching.py 的单尺度模板匹配（Apache-2.0，见同目录 NOTICE）。

对应 airtest 的 ``tpl`` 策略：只在模板原始尺度下做一次 TM_CCOEFF_NORMED 匹配。
"""

import logging
from typing import Any

import cv2
import numpy as np

from .confidence import cal_rgb_confidence
from .image_ops import (
    check_source_larger_than_search,
    generate_result,
    img_mat_rgb_2_gray,
    log_run_time,
)

_log = logging.getLogger(__name__)


class TemplateMatching:
    """单尺度模板匹配。

    Attributes:
        last_confidence: 最近一次匹配的实际置信度。上游在低于阈值时直接返回 None
            并丢弃分数，本项目保留它用于报告与阈值标定。
        last_result: 最近一次匹配的原始结果字典（未过阈值）。
    """

    METHOD_NAME = "Template"
    MAX_RESULT_COUNT = 10

    def __init__(
        self,
        im_search: np.ndarray,
        im_source: np.ndarray,
        threshold: float = 0.8,
        rgb: bool = True,
    ) -> None:
        """初始化匹配器。

        Args:
            im_search: 模板图像（BGR）。
            im_source: 截图图像（BGR）。
            threshold: 判定阈值。
            rgb: 是否启用彩色（HSV）置信度；False 用灰度相关系数。
        """
        self.im_source = im_source
        self.im_search = im_search
        self.threshold = threshold
        self.rgb = rgb
        self.last_confidence: float = 0.0
        self.last_result: dict[str, Any] | None = None

    @log_run_time
    def find_all_results(self) -> list[dict[str, Any]] | None:
        """查找所有满足阈值的目标区域（按置信度从高到低）。"""
        check_source_larger_than_search(self.im_source, self.im_search)
        res = self._get_template_result_matrix()

        result: list[dict[str, Any]] = []
        h, w = self.im_search.shape[:2]

        while True:
            max_val, max_loc = self._peek_best(res)
            confidence = self._get_confidence_from_matrix(max_loc, max_val, w, h)

            if confidence < self.threshold or len(result) > self.MAX_RESULT_COUNT:
                break

            middle_point, rectangle = self._get_target_rectangle(max_loc, w, h)
            result.append(generate_result(middle_point, rectangle, confidence))

            # 屏蔽已取出的最优结果，进入下轮循环继续寻找
            cv2.rectangle(
                res,
                (int(max_loc[0] - w / 2), int(max_loc[1] - h / 2)),
                (int(max_loc[0] + w / 2), int(max_loc[1] + h / 2)),
                (0, 0, 0),
                -1,
            )

        return result if result else None

    @log_run_time
    def find_best_result(self) -> dict[str, Any] | None:
        """查找置信度最高的目标区域。

        Returns:
            命中且达标时返回结果字典；低于阈值时返回 None（实际分数见
            :attr:`last_confidence`）。
        """
        check_source_larger_than_search(self.im_source, self.im_search)
        res = self._get_template_result_matrix()
        max_val, max_loc = self._peek_best(res)

        h, w = self.im_search.shape[:2]
        confidence = self._get_confidence_from_matrix(max_loc, max_val, w, h)
        middle_point, rectangle = self._get_target_rectangle(max_loc, w, h)
        best_match = generate_result(middle_point, rectangle, confidence)

        # 本项目新增：阈值判断前先记录实际分数，供报告与阈值标定使用
        self.last_confidence = confidence
        self.last_result = best_match

        _log.debug(
            "[%s] threshold=%s, confidence=%.4f, result=%s",
            self.METHOD_NAME,
            self.threshold,
            confidence,
            best_match,
        )

        return best_match if confidence >= self.threshold else None

    @staticmethod
    def _peek_best(res: np.ndarray) -> tuple[float, tuple[int, int]]:
        """取出结果矩阵中的最优值与位置。"""
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        return float(max_val), max_loc

    def _get_confidence_from_matrix(
        self,
        max_loc: tuple[int, int],
        max_val: float,
        w: int,
        h: int,
    ) -> float:
        """根据结果矩阵求出 confidence。"""
        if self.rgb:
            # 有颜色校验时，对目标区域做 BGR 三通道校验
            img_crop = self.im_source[max_loc[1] : max_loc[1] + h, max_loc[0] : max_loc[0] + w]
            return cal_rgb_confidence(img_crop, self.im_search)
        return max_val

    def _get_template_result_matrix(self) -> np.ndarray:
        """求取模板匹配的结果矩阵（cv2.matchTemplate 只接受灰度图）。"""
        s_gray = img_mat_rgb_2_gray(self.im_search)
        i_gray = img_mat_rgb_2_gray(self.im_source)
        return cv2.matchTemplate(i_gray, s_gray, cv2.TM_CCOEFF_NORMED)

    @staticmethod
    def _get_target_rectangle(
        left_top_pos: tuple[int, int],
        w: int,
        h: int,
    ) -> tuple[tuple[int, int], tuple[tuple[int, int], ...]]:
        """根据左上角点和宽高求出目标中心点与矩形角点。"""
        x_min, y_min = left_top_pos
        middle_point = (int(x_min + w / 2), int(y_min + h / 2))
        # 点序：左上 -> 左下 -> 右下 -> 右上
        rectangle = (
            (x_min, y_min),
            (x_min, y_min + h),
            (x_min + w, y_min + h),
            (x_min + w, y_min),
        )
        return middle_point, rectangle

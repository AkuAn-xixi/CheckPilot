"""移植自 aircv/multiscale_template_matching.py 的多尺度模板匹配。

对应 airtest 的 ``mstpl`` 策略（默认策略）：按比例逐步缩放模板做多轮匹配，
能适配与录制时分辨率不同的设备。Apache-2.0，见同目录 NOTICE。

相对上游的两处改动：
1. 只保留基类 ``MultiScaleTemplateMatching``；``MultiScaleTemplateMatchingPre``
   依赖 Airtest IDE 录制元数据（record_pos/resolution），本项目用不到，连同类上
   的这两个构造参数一并移除。
2. 新增 ``last_confidence`` / ``last_result``，用于在未命中时仍能报告实际分数。
"""

import logging
import time
from typing import Any

import cv2
import numpy as np

from .confidence import cal_ccoeff_confidence, cal_rgb_confidence
from .image_ops import (
    check_source_larger_than_search,
    generate_result,
    img_mat_rgb_2_gray,
    log_run_time,
)

_log = logging.getLogger(__name__)


class MultiScaleTemplateMatching:
    """多尺度模板匹配。

    Attributes:
        last_confidence: 最近一次匹配的实际置信度（未命中时也有值）。
        last_result: 最近一次匹配的原始结果字典（未过阈值）。
    """

    METHOD_NAME = "MSTemplate"

    def __init__(
        self,
        im_search: np.ndarray,
        im_source: np.ndarray,
        threshold: float = 0.8,
        rgb: bool = True,
        scale_max: int = 800,
        scale_step: float = 0.005,
    ) -> None:
        """初始化匹配器。

        Args:
            im_search: 模板图像（BGR）。
            im_source: 截图图像（BGR）。
            threshold: 判定阈值。
            rgb: 是否启用彩色（HSV）置信度；False 用灰度相关系数。
            scale_max: 截图长边缩放上限，越大越慢、对小 UI 的适应性越好。
            scale_step: 多尺度搜索的比例步长，越小越慢、越精细。
        """
        self.im_source = im_source
        self.im_search = im_search
        self.threshold = threshold
        self.rgb = rgb
        self.scale_max = scale_max
        self.scale_step = scale_step
        self.last_confidence: float = 0.0
        self.last_result: dict[str, Any] | None = None

    def find_all_results(self) -> None:
        """多尺度策略不支持一次返回多个结果。"""
        raise NotImplementedError("MultiScaleTemplateMatching 不支持 find_all_results")

    @log_run_time
    def find_best_result(self) -> dict[str, Any] | None:
        """查找置信度最高的目标区域。

        Returns:
            命中且达标时返回结果字典；低于阈值时返回 None（实际分数见
            :attr:`last_confidence`）。
        """
        check_source_larger_than_search(self.im_source, self.im_search)

        s_gray = img_mat_rgb_2_gray(self.im_search)
        i_gray = img_mat_rgb_2_gray(self.im_source)
        confidence, max_loc, w, h, _ = self.multi_scale_search(
            i_gray,
            s_gray,
            ratio_min=0.01,
            ratio_max=0.99,
            src_max=self.scale_max,
            step=self.scale_step,
            threshold=self.threshold,
        )

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

    def _get_confidence_from_matrix(
        self,
        max_loc: tuple[int, int],
        w: int,
        h: int,
    ) -> float:
        """在原始尺度的候选区域上重算置信度。"""
        sch_h, sch_w = self.im_search.shape[0], self.im_search.shape[1]
        img_crop = self.im_source[max_loc[1] : max_loc[1] + h, max_loc[0] : max_loc[0] + w]
        resized_crop = cv2.resize(img_crop, (sch_w, sch_h))

        if self.rgb:
            return cal_rgb_confidence(resized_crop, self.im_search)
        return cal_ccoeff_confidence(resized_crop, self.im_search)

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

    @staticmethod
    def _resize_by_ratio(
        src: np.ndarray,
        templ: np.ndarray,
        ratio: float = 1.0,
        src_max: int = 800,
    ) -> tuple[np.ndarray, np.ndarray, float, float]:
        """按模板相对屏幕的长边比例，同步缩放截图与模板。

        Returns:
            缩放后的截图、缩放后的模板、模板缩放比、截图缩放比。
        """
        # 截图最大尺寸限制
        sr = min(src_max / max(src.shape), 1.0)
        src = cv2.resize(src, (int(src.shape[1] * sr), int(src.shape[0] * sr)))
        h, w = src.shape[0], src.shape[1]
        th, tw = templ.shape[0], templ.shape[1]
        if th / h >= tw / w:
            tr = (h * ratio) / th
        else:
            tr = (w * ratio) / tw
        templ = cv2.resize(templ, (max(int(tw * tr), 1), max(int(th * tr), 1)))
        return src, templ, tr, sr

    @staticmethod
    def _org_size(
        max_loc: tuple[int, int],
        w: int,
        h: int,
        sr: float,
    ) -> tuple[tuple[int, int], int, int]:
        """把缩放坐标系下的位置与尺寸还原到原截图坐标系。"""
        max_loc = (int(max_loc[0] / sr), int(max_loc[1] / sr))
        w, h = int(w / sr), int(h / sr)
        return max_loc, w, h

    def multi_scale_search(
        self,
        org_src: np.ndarray,
        org_templ: np.ndarray,
        templ_min: int = 10,
        src_max: int = 800,
        ratio_min: float = 0.01,
        ratio_max: float = 0.99,
        step: float = 0.01,
        threshold: float = 0.8,
        time_out: float = 3.0,
    ) -> tuple[float, tuple[int, int], int, int, float]:
        """多尺度模板匹配主循环。

        逐比例缩放后做 TM_CCOEFF_NORMED；超过 ``time_out`` 且已找到达标结果时提前返回，
        否则扫完全部比例取全局最优。

        Returns:
            (置信度, 左上角坐标, 宽, 高, 命中比例)；全程未产生候选时为 ``(0, (0, 0), 0, 0, 0)``。
        """
        mmax_val = 0.0
        max_info: tuple[float, float, tuple[int, int], int, int, float] | None = None
        r = ratio_min
        start_time = time.time()
        while r <= ratio_max:
            src, templ, _, sr = self._resize_by_ratio(
                org_src.copy(), org_templ.copy(), r, src_max=src_max
            )
            if min(templ.shape) > templ_min:
                src[0, 0] = templ[0, 0] = 0
                src[0, 1] = templ[0, 1] = 255
                result = cv2.matchTemplate(src, templ, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(result)
                h, w = templ.shape
                if mmax_val < max_val:
                    mmax_val = float(max_val)
                    max_info = (r, mmax_val, max_loc, w, h, sr)
                if time.time() - start_time > time_out and max_val >= threshold:
                    omax_loc, ow, oh = self._org_size(max_loc, w, h, sr)
                    confidence = self._get_confidence_from_matrix(omax_loc, ow, oh)
                    if confidence >= threshold:
                        return confidence, omax_loc, ow, oh, r
            r += step

        if max_info is None:
            return 0, (0, 0), 0, 0, 0

        max_r, _, max_loc, w, h, sr = max_info
        omax_loc, ow, oh = self._org_size(max_loc, w, h, sr)
        confidence = self._get_confidence_from_matrix(omax_loc, ow, oh)
        return confidence, omax_loc, ow, oh, max_r

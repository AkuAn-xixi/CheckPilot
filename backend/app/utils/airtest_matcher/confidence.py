"""移植自 aircv/cal_confidence.py 的置信度计算（Apache-2.0，见同目录 NOTICE）。

两个函数都要求传入**同尺寸**的两张图：调用方先按模板尺寸裁剪/缩放候选区域，
再交给这里算相似度。
"""

import cv2
import numpy as np

from .image_ops import img_mat_rgb_2_gray


def cal_ccoeff_confidence(im_source: np.ndarray, im_search: np.ndarray) -> float:
    """灰度相关系数置信度（TM_CCOEFF_NORMED）。

    上游通过 copyMakeBorder 扩展边界、并注入 (0, 255) 极端值，用于抑制算法
    把微小差异过度放大。

    Args:
        im_source: 候补区域图像（BGR，尺寸同模板）。
        im_search: 模板图像（BGR）。

    Returns:
        置信度，取值通常在 [0, 1]。
    """
    # 扩展置信度计算区域
    im_source = cv2.copyMakeBorder(im_source, 10, 10, 10, 10, cv2.BORDER_REPLICATE)
    # 加入取值范围干扰，防止算法过于放大微小差异
    im_source[0, 0] = 0
    im_source[0, 1] = 255

    im_source, im_search = img_mat_rgb_2_gray(im_source), img_mat_rgb_2_gray(im_search)
    res = cv2.matchTemplate(im_source, im_search, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)

    return float(max_val)


def cal_rgb_confidence(img_src_rgb: np.ndarray, img_sch_rgb: np.ndarray) -> float:
    """彩色置信度（HSV 三通道取最小值）。

    转 HSV 后逐通道做 TM_CCOEFF_NORMED，取三通道最小值，用于强化颜色差异的影响。

    Args:
        img_src_rgb: 候补区域图像（BGR，尺寸同模板）。
        img_sch_rgb: 模板图像（BGR）。

    Returns:
        置信度，取值通常在 [0, 1]。
    """
    # 减少极限值对 hsv 角度计算的影响
    img_src_rgb = np.clip(img_src_rgb, 10, 245)
    img_sch_rgb = np.clip(img_sch_rgb, 10, 245)
    # 转 HSV 强化颜色的影响
    img_src_rgb = cv2.cvtColor(img_src_rgb, cv2.COLOR_BGR2HSV)
    img_sch_rgb = cv2.cvtColor(img_sch_rgb, cv2.COLOR_BGR2HSV)

    # 扩展置信度计算区域
    img_src_rgb = cv2.copyMakeBorder(img_src_rgb, 10, 10, 10, 10, cv2.BORDER_REPLICATE)
    # 加入取值范围干扰，防止算法过于放大微小差异
    img_src_rgb[0, 0] = 0
    img_src_rgb[0, 1] = 255

    # 计算 BGR 三通道的 confidence，取最小值
    src_bgr, sch_bgr = cv2.split(img_src_rgb), cv2.split(img_sch_rgb)
    bgr_confidence = [0.0, 0.0, 0.0]
    for i in range(3):
        res_temp = cv2.matchTemplate(src_bgr[i], sch_bgr[i], cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res_temp)
        bgr_confidence[i] = max_val

    return float(min(bgr_confidence))

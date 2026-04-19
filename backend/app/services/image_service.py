"""图片验证服务模块"""
import cv2
import numpy as np
from typing import Dict, Any

class ImageVerifier:
    """图片验证器"""

    @staticmethod
    def calc_color_hist_similarity(img1, img2) -> float:
        """计算彩色直方图相似度（颜色一致度）"""
        hsv1 = cv2.cvtColor(img1, cv2.COLOR_BGR2HSV)
        hsv2 = cv2.cvtColor(img2, cv2.COLOR_BGR2HSV)

        hist1 = cv2.calcHist([hsv1], [0, 1], None, [50, 60], [0, 180, 0, 256])
        hist2 = cv2.calcHist([hsv2], [0, 1], None, [50, 60], [0, 180, 0, 256])

        cv2.normalize(hist1, hist1)
        cv2.normalize(hist2, hist2)
        return cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)

    @staticmethod
    def multi_scale_color_match(big_img, small_icon, threshold: float) -> tuple:
        """多尺度彩色匹配"""
        scales = [0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3]
        best_score = 0.0

        for scale in scales:
            h, w = small_icon.shape[:2]
            new_w, new_h = int(w * scale), int(h * scale)
            icon_resized = cv2.resize(small_icon, (new_w, new_h), interpolation=cv2.INTER_AREA)

            res = cv2.matchTemplate(big_img, icon_resized, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)

            if max_val > best_score:
                best_score = max_val

        color_sim = ImageVerifier.calc_color_hist_similarity(
            cv2.resize(big_img, (256, 256)),
            cv2.resize(small_icon, (256, 256))
        )

        final_score = (best_score * 0.6) + (color_sim * 0.4)
        return final_score, best_score, color_sim

    def verify(self, screen_img_path: str, icon_img_path: str, threshold: float = 0.8) -> Dict[str, Any]:
        """
        验证屏幕截图与图标是否匹配

        Args:
            screen_img_path: 屏幕截图路径
            icon_img_path: 图标路径
            threshold: 阈值，默认为0.8

        Returns:
            dict: 包含验证结果的字典
        """
        try:
            img_screen = cv2.imread(screen_img_path)
            img_icon = cv2.imread(icon_img_path)

            if img_screen is None:
                return {
                    "success": False,
                    "message": f"屏幕截图读取失败: {screen_img_path}",
                    "score": 0,
                    "matched": False
                }

            if img_icon is None:
                return {
                    "success": False,
                    "message": f"图标读取失败: {icon_img_path}",
                    "score": 0,
                    "matched": False
                }

            final_score, struct_score, color_score = self.multi_scale_color_match(img_screen, img_icon, threshold)
            matched = final_score >= threshold

            return {
                "success": True,
                "matched": matched,
                "score": float(final_score),
                "struct_score": float(struct_score),
                "color_score": float(color_score),
                "message": "验证成功" if matched else "验证失败"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"验证过程出错: {str(e)}",
                "score": 0,
                "matched": False
            }

image_verifier = ImageVerifier()

def verify_image_match(screen_img_path: str, icon_img_path: str, threshold: float = 0.8) -> Dict[str, Any]:
    """验证图片匹配的便捷函数"""
    return image_verifier.verify(screen_img_path, icon_img_path, threshold)

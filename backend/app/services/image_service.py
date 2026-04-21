"""图片验证服务模块"""
import base64
import cv2
import numpy as np
from typing import Dict, Any

class ImageVerifier:
    """图片验证器"""

    STANDARD_SIZE = (320, 180)
    TEMPLATE_SCALES = (0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4)

    @staticmethod
    def _resize_for_compare(img1, img2):
        resized1 = cv2.resize(img1, ImageVerifier.STANDARD_SIZE, interpolation=cv2.INTER_AREA)
        resized2 = cv2.resize(img2, ImageVerifier.STANDARD_SIZE, interpolation=cv2.INTER_AREA)
        return resized1, resized2

    @staticmethod
    def calc_color_hist_similarity(img1, img2) -> float:
        """计算弱权重颜色相似度，避免深色界面被误判为高分。"""
        resized1, resized2 = ImageVerifier._resize_for_compare(img1, img2)

        hsv1 = cv2.cvtColor(resized1, cv2.COLOR_BGR2HSV)
        hsv2 = cv2.cvtColor(resized2, cv2.COLOR_BGR2HSV)

        hist1 = cv2.calcHist([hsv1], [0, 1], None, [50, 60], [0, 180, 0, 256])
        hist2 = cv2.calcHist([hsv2], [0, 1], None, [50, 60], [0, 180, 0, 256])

        cv2.normalize(hist1, hist1)
        cv2.normalize(hist2, hist2)
        distance = cv2.compareHist(hist1, hist2, cv2.HISTCMP_BHATTACHARYYA)
        return float(max(0.0, min(1.0, 1.0 - distance)))

    @staticmethod
    def calc_structure_similarity(img1, img2) -> float:
        """计算整体结构相似度。"""
        resized1, resized2 = ImageVerifier._resize_for_compare(img1, img2)
        gray1 = cv2.cvtColor(resized1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(resized2, cv2.COLOR_BGR2GRAY)
        gray1 = cv2.GaussianBlur(gray1, (5, 5), 0)
        gray2 = cv2.GaussianBlur(gray2, (5, 5), 0)

        res = cv2.matchTemplate(gray1, gray2, cv2.TM_CCOEFF_NORMED)
        score = float(res[0][0]) if res.size else 0.0
        return float(max(0.0, min(1.0, score)))

    @staticmethod
    def calc_feature_similarity(img1, img2) -> float:
        """计算 ORB 特征匹配相似度。"""
        resized1, resized2 = ImageVerifier._resize_for_compare(img1, img2)
        gray1 = cv2.cvtColor(resized1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(resized2, cv2.COLOR_BGR2GRAY)

        orb = cv2.ORB_create(nfeatures=800)
        keypoints1, descriptors1 = orb.detectAndCompute(gray1, None)
        keypoints2, descriptors2 = orb.detectAndCompute(gray2, None)

        if descriptors1 is None or descriptors2 is None or not keypoints1 or not keypoints2:
            return 0.0

        matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        raw_matches = matcher.knnMatch(descriptors1, descriptors2, k=2)

        good_matches = []
        for pair in raw_matches:
            if len(pair) < 2:
                continue
            best, second = pair
            if best.distance < 0.75 * second.distance:
                good_matches.append(best)

        normalizer = max(min(len(keypoints1), len(keypoints2)), 1)
        score = min(len(good_matches) / normalizer * 2.0, 1.0)
        return float(max(0.0, min(1.0, score)))

    @staticmethod
    def calc_aspect_ratio_penalty(img1, img2) -> float:
        """宽高比偏差越大，惩罚越强。"""
        h1, w1 = img1.shape[:2]
        h2, w2 = img2.shape[:2]
        if not h1 or not h2 or not w1 or not w2:
            return 0.0

        ratio1 = w1 / h1
        ratio2 = w2 / h2
        deviation = abs(ratio1 - ratio2) / max(ratio1, ratio2)
        return float(max(0.0, 1.0 - deviation))

    @staticmethod
    def _best_subimage_match(screen_img, reference_img):
        screen_gray = cv2.cvtColor(screen_img, cv2.COLOR_BGR2GRAY)
        screen_edges = cv2.Canny(screen_gray, 80, 160)

        best_match = None
        screen_h, screen_w = screen_gray.shape[:2]

        for scale in ImageVerifier.TEMPLATE_SCALES:
            ref_h, ref_w = reference_img.shape[:2]
            scaled_w = max(1, int(ref_w * scale))
            scaled_h = max(1, int(ref_h * scale))
            if scaled_w > screen_w or scaled_h > screen_h:
                continue
            if scaled_w < 24 or scaled_h < 24:
                continue

            interpolation = cv2.INTER_AREA if scale <= 1.0 else cv2.INTER_LINEAR
            scaled_ref = cv2.resize(reference_img, (scaled_w, scaled_h), interpolation=interpolation)
            ref_gray = cv2.cvtColor(scaled_ref, cv2.COLOR_BGR2GRAY)
            ref_edges = cv2.Canny(ref_gray, 80, 160)

            gray_result = cv2.matchTemplate(screen_gray, ref_gray, cv2.TM_CCOEFF_NORMED)
            _, gray_score, _, gray_loc = cv2.minMaxLoc(gray_result)

            edge_score = 0.0
            if np.count_nonzero(ref_edges) > 50:
                edge_result = cv2.matchTemplate(screen_edges, ref_edges, cv2.TM_CCOEFF_NORMED)
                _, edge_score, _, _ = cv2.minMaxLoc(edge_result)

            template_score = gray_score * 0.75 + edge_score * 0.25
            candidate = {
                "template_score": float(max(0.0, min(1.0, template_score))),
                "gray_score": float(max(0.0, min(1.0, gray_score))),
                "edge_score": float(max(0.0, min(1.0, edge_score))),
                "loc": gray_loc,
                "size": (scaled_w, scaled_h),
                "reference": scaled_ref,
            }

            if best_match is None or candidate["template_score"] > best_match["template_score"]:
                best_match = candidate

        if best_match is None:
            fallback_ref = cv2.resize(reference_img, (screen_w, screen_h), interpolation=cv2.INTER_AREA)
            return {
                "template_score": 0.0,
                "gray_score": 0.0,
                "edge_score": 0.0,
                "loc": (0, 0),
                "size": (screen_w, screen_h),
                "reference": fallback_ref,
            }

        return best_match

    @staticmethod
    def multi_signal_match(screen_img, reference_img) -> tuple:
        """多信号匹配：先在截图中搜索参考图，再对候选区域复核。"""
        match = ImageVerifier._best_subimage_match(screen_img, reference_img)
        x, y = match["loc"]
        w, h = match["size"]
        roi = screen_img[y:y + h, x:x + w]
        reference_patch = match["reference"]

        structure_score = ImageVerifier.calc_structure_similarity(roi, reference_patch)
        feature_score = ImageVerifier.calc_feature_similarity(roi, reference_patch)
        color_score = ImageVerifier.calc_color_hist_similarity(roi, reference_patch)
        template_score = match["template_score"]

        final_score = (
            template_score * 0.5 +
            structure_score * 0.2 +
            feature_score * 0.2 +
            color_score * 0.1
        )

        return final_score, template_score, color_score, feature_score, structure_score

    @staticmethod
    def _decode_base64_image(image_base64: str):
        payload = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64
        image_bytes = base64.b64decode(payload)
        image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        return cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    def _build_result(self, img_screen, img_icon, threshold: float) -> Dict[str, Any]:
        final_score, struct_score, color_score, feature_score, local_structure_score = self.multi_signal_match(img_screen, img_icon)
        matched = (
            final_score >= threshold and
            struct_score >= 0.55 and
            local_structure_score >= 0.5
        )

        return {
            "success": True,
            "matched": matched,
            "score": float(final_score),
            "struct_score": float(struct_score),
            "color_score": float(color_score),
            "feature_score": float(feature_score),
            "aspect_ratio_score": 1.0,
            "local_structure_score": float(local_structure_score),
            "message": "验证成功" if matched else "验证失败"
        }

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

            return self._build_result(img_screen, img_icon, threshold)
        except Exception as e:
            return {
                "success": False,
                "message": f"验证过程出错: {str(e)}",
                "score": 0,
                "matched": False
            }

    def verify_base64(self, screen_img_path: str, icon_img_base64: str, threshold: float = 0.8) -> Dict[str, Any]:
        """验证屏幕截图与 base64 图片是否匹配。"""
        try:
            img_screen = cv2.imread(screen_img_path)
            img_icon = self._decode_base64_image(icon_img_base64)

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
                    "message": "base64校验图片解析失败",
                    "score": 0,
                    "matched": False
                }

            return self._build_result(img_screen, img_icon, threshold)
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


def verify_image_base64_match(screen_img_path: str, icon_img_base64: str, threshold: float = 0.8) -> Dict[str, Any]:
    """验证 base64 图片匹配的便捷函数"""
    return image_verifier.verify_base64(screen_img_path, icon_img_base64, threshold)

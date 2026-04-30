"""图片验证服务模块"""
import base64
import cv2
import numpy as np
from typing import Dict, Any

class ImageVerifier:
    """图片验证器"""

    STANDARD_SIZE = (320, 180)
    TEMPLATE_SCALES = (0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4)
    MAX_POST_VERIFY_CANDIDATES = 8

    @staticmethod
    def _collect_border_pixels(image, border_width: int):
        h, w = image.shape[:2]
        border_width = max(1, min(border_width, h // 2, w // 2))
        if border_width <= 0:
            return image.reshape(-1, image.shape[2])

        top = image[:border_width, :, :]
        bottom = image[h - border_width:, :, :]
        left = image[border_width:h - border_width, :border_width, :]
        right = image[border_width:h - border_width, w - border_width:, :]
        return np.concatenate(
            [
                top.reshape(-1, image.shape[2]),
                bottom.reshape(-1, image.shape[2]),
                left.reshape(-1, image.shape[2]),
                right.reshape(-1, image.shape[2]),
            ],
            axis=0,
        )

    @staticmethod
    def _crop_focus_region(reference_img):
        """裁掉大块纯色边框，避免模板留白把得分拖低。"""
        return ImageVerifier._crop_focus_region_with_padding(reference_img, pad_ratio=0.08)

    @staticmethod
    def _crop_focus_region_with_padding(reference_img, pad_ratio: float):
        """按前景边界裁剪参考图，可选保留少量边缘。"""
        if reference_img is None or reference_img.size == 0:
            return reference_img

        h, w = reference_img.shape[:2]
        if h < 32 or w < 32:
            return reference_img

        border_width = max(2, min(h, w) // 16)
        border_pixels = ImageVerifier._collect_border_pixels(reference_img, border_width)
        background = np.median(border_pixels, axis=0)

        color_diff = np.max(
            np.abs(reference_img.astype(np.int16) - background.astype(np.int16)),
            axis=2,
        )
        gray = cv2.cvtColor(reference_img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 60, 160)

        mask = np.where((color_diff > 22) | (edges > 0), 255, 0).astype(np.uint8)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

        coords = cv2.findNonZero(mask)
        if coords is None:
            return reference_img

        x, y, crop_w, crop_h = cv2.boundingRect(coords)
        area_ratio = (crop_w * crop_h) / float(w * h)
        if area_ratio >= 0.9:
            return reference_img
        if crop_w < max(20, int(w * 0.18)) or crop_h < max(20, int(h * 0.18)):
            return reference_img

        pad_x = max(0, int(crop_w * pad_ratio))
        pad_y = max(0, int(crop_h * pad_ratio))
        x1 = max(0, x - pad_x)
        y1 = max(0, y - pad_y)
        x2 = min(w, x + crop_w + pad_x)
        y2 = min(h, y + crop_h + pad_y)

        cropped = reference_img[y1:y2, x1:x2]
        if cropped.size == 0:
            return reference_img
        return cropped

    @staticmethod
    def _reference_variants(reference_img):
        variants = [reference_img]
        current = reference_img

        for _ in range(3):
            cropped = ImageVerifier._crop_focus_region(current)
            if cropped.shape[:2] == current.shape[:2]:
                break
            variants.append(cropped)

            tight_cropped = ImageVerifier._crop_focus_region_with_padding(cropped, pad_ratio=0.0)
            if tight_cropped.shape[:2] != cropped.shape[:2]:
                variants.append(tight_cropped)

            current = cropped

        return variants

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

        candidate_matches = []
        screen_h, screen_w = screen_gray.shape[:2]

        for reference_variant in ImageVerifier._reference_variants(reference_img):
            for scale in ImageVerifier.TEMPLATE_SCALES:
                ref_h, ref_w = reference_variant.shape[:2]
                scaled_w = max(1, int(ref_w * scale))
                scaled_h = max(1, int(ref_h * scale))
                if scaled_w > screen_w or scaled_h > screen_h:
                    continue
                if scaled_w < 24 or scaled_h < 24:
                    continue

                interpolation = cv2.INTER_AREA if scale <= 1.0 else cv2.INTER_LINEAR
                scaled_ref = cv2.resize(reference_variant, (scaled_w, scaled_h), interpolation=interpolation)
                ref_gray = cv2.cvtColor(scaled_ref, cv2.COLOR_BGR2GRAY)
                ref_edges = cv2.Canny(ref_gray, 80, 160)

                gray_result = cv2.matchTemplate(screen_gray, ref_gray, cv2.TM_CCOEFF_NORMED)
                _, gray_score, _, gray_loc = cv2.minMaxLoc(gray_result)

                edge_score = 0.0
                edge_loc = None
                if np.count_nonzero(ref_edges) > 50:
                    edge_result = cv2.matchTemplate(screen_edges, ref_edges, cv2.TM_CCOEFF_NORMED)
                    _, edge_score, _, edge_loc = cv2.minMaxLoc(edge_result)

                locations = [(gray_loc, gray_score)]
                if edge_loc is not None and edge_loc != gray_loc:
                    locations.append((edge_loc, edge_score))

                for loc, location_anchor_score in locations:
                    candidate_template_score = gray_score * 0.75
                    if edge_loc is not None:
                        edge_distance = abs(loc[0] - edge_loc[0]) + abs(loc[1] - edge_loc[1])
                        gray_distance = abs(loc[0] - gray_loc[0]) + abs(loc[1] - gray_loc[1])
                        if edge_distance <= gray_distance:
                            candidate_template_score += edge_score * 0.25
                        else:
                            candidate_template_score += max(edge_score * 0.1, 0.0)

                    candidate_matches.append({
                        "template_score": float(max(0.0, min(1.0, candidate_template_score))),
                        "gray_score": float(max(0.0, min(1.0, gray_score))),
                        "edge_score": float(max(0.0, min(1.0, edge_score))),
                        "anchor_score": float(max(0.0, min(1.0, location_anchor_score))),
                        "loc": loc,
                        "size": (scaled_w, scaled_h),
                        "reference": scaled_ref,
                    })

        if candidate_matches:
            candidate_matches.sort(
                key=lambda candidate: (candidate["template_score"], candidate["anchor_score"]),
                reverse=True,
            )

            deduped_matches = []
            seen_cells = set()
            for candidate in candidate_matches:
                cell = (
                    candidate["loc"][0] // 8,
                    candidate["loc"][1] // 8,
                    candidate["size"][0] // 8,
                    candidate["size"][1] // 8,
                )
                if cell in seen_cells:
                    continue
                seen_cells.add(cell)
                deduped_matches.append(candidate)
                if len(deduped_matches) >= ImageVerifier.MAX_POST_VERIFY_CANDIDATES:
                    break

            best_match = None
            best_score = -1.0
            for candidate in deduped_matches:
                x, y = candidate["loc"]
                w, h = candidate["size"]
                roi = screen_img[y:y + h, x:x + w]
                if roi.shape[:2] != candidate["reference"].shape[:2]:
                    continue

                structure_score = ImageVerifier.calc_structure_similarity(roi, candidate["reference"])
                feature_score = ImageVerifier.calc_feature_similarity(roi, candidate["reference"])
                color_score = ImageVerifier.calc_color_hist_similarity(roi, candidate["reference"])
                final_score = (
                    candidate["template_score"] * 0.5 +
                    structure_score * 0.2 +
                    feature_score * 0.2 +
                    color_score * 0.1
                )
                ranking_score = final_score + structure_score * 0.15 + color_score * 0.05

                if ranking_score > best_score:
                    best_score = ranking_score
                    best_match = {
                        **candidate,
                        "post_score": float(final_score),
                        "post_structure_score": float(structure_score),
                        "post_feature_score": float(feature_score),
                        "post_color_score": float(color_score),
                    }

            if best_match is not None:
                return best_match

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

        structure_score = match.get("post_structure_score")
        if structure_score is None:
            structure_score = ImageVerifier.calc_structure_similarity(roi, reference_patch)

        feature_score = match.get("post_feature_score")
        if feature_score is None:
            feature_score = ImageVerifier.calc_feature_similarity(roi, reference_patch)

        color_score = match.get("post_color_score")
        if color_score is None:
            color_score = ImageVerifier.calc_color_hist_similarity(roi, reference_patch)

        template_score = match["template_score"]

        final_score = match.get("post_score")
        if final_score is None:
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
        final_score, template_score, color_score, feature_score, structure_score = self.multi_signal_match(img_screen, img_icon)
        required_score = max(float(threshold), 0.9)
        strict_match = (
            final_score >= required_score and
            template_score >= 0.55 and
            structure_score >= 0.5
        )
        padded_template_match = (
            final_score >= 0.43 and
            template_score >= 0.57 and
            structure_score >= 0.6 and
            color_score >= 0.2
        )
        icon_focus_match = (
            final_score >= 0.68 and
            template_score >= 0.72 and
            feature_score >= 0.85 and
            color_score >= 0.85
        )
        strong_visual_match = (
            final_score >= 0.64 and
            template_score >= 0.64 and
            feature_score >= 0.95 and
            color_score >= 0.95
        )
        matched = strict_match or padded_template_match or icon_focus_match or strong_visual_match
        visual_confidence_score = max(
            final_score,
            template_score * 0.6 + color_score * 0.2 + feature_score * 0.2,
            template_score * 0.7 + structure_score * 0.2 + color_score * 0.1,
        )
        reported_score = visual_confidence_score if matched else final_score
        matched = matched and reported_score >= required_score

        return {
            "success": True,
            "matched": matched,
            "score": float(max(0.0, min(1.0, reported_score))),
            "template_score": float(template_score),
            "struct_score": float(template_score),
            "color_score": float(color_score),
            "feature_score": float(feature_score),
            "aspect_ratio_score": 1.0,
            "structure_score": float(structure_score),
            "local_structure_score": float(structure_score),
            "message": "验证成功" if matched else "验证失败"
        }

    def verify(self, screen_img_path: str, icon_img_path: str, threshold: float = 0.9) -> Dict[str, Any]:
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

    def verify_base64(self, screen_img_path: str, icon_img_base64: str, threshold: float = 0.9) -> Dict[str, Any]:
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

def verify_image_match(screen_img_path: str, icon_img_path: str, threshold: float = 0.9) -> Dict[str, Any]:
    """验证图片匹配的便捷函数"""
    return image_verifier.verify(screen_img_path, icon_img_path, threshold)


def verify_image_base64_match(screen_img_path: str, icon_img_base64: str, threshold: float = 0.9) -> Dict[str, Any]:
    """验证 base64 图片匹配的便捷函数"""
    return image_verifier.verify_base64(screen_img_path, icon_img_base64, threshold)

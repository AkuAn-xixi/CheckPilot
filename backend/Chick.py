import cv2
import numpy as np

def calc_color_hist_similarity(img1, img2):
    """计算彩色直方图相似度（颜色一致度）"""
    hsv1 = cv2.cvtColor(img1, cv2.COLOR_BGR2HSV)
    hsv2 = cv2.cvtColor(img2, cv2.COLOR_BGR2HSV)

    hist1 = cv2.calcHist([hsv1], [0, 1], None, [50, 60], [0, 180, 0, 256])
    hist2 = cv2.calcHist([hsv2], [0, 1], None, [50, 60], [0, 180, 0, 256])

    cv2.normalize(hist1, hist1)
    cv2.normalize(hist2, hist2)
    return cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)

def multi_scale_color_match(big_img, small_icon, threshold):
    # 多尺度：适配截图里图标大小不一样
    scales = [0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3]
    best_score = 0.0

    for scale in scales:
        h, w = small_icon.shape[:2]
        new_w, new_h = int(w * scale), int(h * scale)
        icon_resized = cv2.resize(small_icon, (new_w, new_h), interpolation=cv2.INTER_AREA)

        # 彩色模板匹配
        res = cv2.matchTemplate(big_img, icon_resized, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)

        if max_val > best_score:
            best_score = max_val

    # 额外：全局颜色相似度兜底
    color_sim = calc_color_hist_similarity(
        cv2.resize(big_img, (256,256)),
        cv2.resize(small_icon, (256,256))
    )

    # 综合得分：结构分 + 颜色分
    final_score = (best_score * 0.6) + (color_sim * 0.4)
    return final_score, best_score, color_sim

def verify_image_match(screen_img_path, icon_img_path, threshold=0.8):
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
                "score": 0
            }

        if img_icon is None:
            return {
                "success": False,
                "message": f"图标读取失败: {icon_img_path}",
                "score": 0
            }

        final_score, struct_score, color_score = multi_scale_color_match(img_screen, img_icon, threshold)
        matched = final_score >= threshold

        return {
            "success": True,
            "matched": matched,
            "score": final_score,
            "struct_score": struct_score,
            "color_score": color_score,
            "message": "验证成功" if matched else "验证失败"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"验证过程出错: {str(e)}",
            "score": 0
        }

if __name__ == "__main__":
    # 示例用法
    screen_img = "1776478500381.jpg"   # 电视截图
    icon_img = "APPS-2.png"    # 目标图标
    threshold = 0.8          # 阈值，越高越严格
    
    result = verify_image_match(screen_img, icon_img, threshold)
    print(f"验证结果: {result}")
    
    if result["success"] and result["matched"]:
        print("✅ 判定：图标匹配成功（存在）")
    else:
        print("❌ 判定：图标不匹配（不存在）")
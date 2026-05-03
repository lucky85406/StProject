# core/qr_login.py
"""產生 QR Code 圖片（bytes），供 Streamlit st.image() 顯示"""
from __future__ import annotations

import io

import qrcode
from qrcode.image.pil import PilImage
from PIL import Image, ImageDraw, ImageFont, ImageColor
from core.network import get_app_base_url


def generate_qr_image(url: str,center_text: str = "Bllln", box_size: int = 8) -> bytes:
    """
    將 URL 編碼成 QR Code，回傳 PNG bytes。

    Args:
        url:      要編碼的完整 URL（含 token 參數）
        box_size: 每個方格的像素大小，預設 8
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size,
        border=3,
    )
    qr.add_data(url)
    qr.make(fit=True)

    # 2. 生成 QR 碼並立即強制轉為 RGBA
    # 這是錯誤發生的關鍵點，確保 img 是 RGBA
    img = qr.make_image(fill_color="#3b3552", back_color="#ffffff").convert("RGBA")
    width, height = img.size
    center_x, center_y = width // 2, height // 2

    # 3. 準備字型與尺寸計算
    font_size = int(width / 6)
    try:
        font = ImageFont.truetype("arialbd.ttf", font_size)
    except:
        font = ImageFont.load_default()

    draw_tools = ImageDraw.Draw(img)
    bbox = draw_tools.textbbox(
        (center_x, center_y), center_text, font=font, anchor="mm"
    )

    # 確保寬高涵蓋所有字元（包含字母下緣）
    text_l, text_t, text_r, text_b = bbox
    txt_w_int = int(text_r - text_l)
    txt_h_int = int(text_b - text_t)

    # 4. 建立 Overlay 層，必須與 img 模式 (RGBA) 與 大小 (width, height) 完全一致
    overlay = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    # 5. 繪製半透明背景
    padding = 10 
    bg_rect = [text_l - padding, text_t - padding, text_r + padding, text_b + padding]
    overlay_draw.rounded_rectangle(bg_rect, fill=(0, 0, 0, 180), radius=8)
    # 6. 製作漸層文字
    if txt_w_int > 0 and txt_h_int > 0:
        # 建立一個足夠大的文字遮罩，避免裁切
        text_mask = Image.new('L', (txt_w_int, txt_h_int), 0)
        mask_draw = ImageDraw.Draw(text_mask)

        # 在遮罩的 (0,0) 位置繪製文字，但 anchor 改用 "lt" (Left-Top)
        # 這樣文字就會從畫布左上角精確開始，不會超出邊界
        mask_draw.text((0, 0), center_text, font=font, fill=255, anchor="lt")

        # 建立漸層色塊
        gradient = Image.new('RGBA', (txt_w_int, txt_h_int), (0, 0, 0, 0))
        grad_draw = ImageDraw.Draw(gradient)
        c1 = ImageColor.getrgb("#A6B8E3")  # 起始色
        c2 = ImageColor.getrgb("#B8FDF6")  # 結束色

        for y in range(txt_h_int):
            ratio = y / (txt_h_int - 1) if txt_h_int > 1 else 1
            r = int(c1[0] + (c2[0] - c1[0]) * ratio)
            g = int(c1[1] + (c2[1] - c1[1]) * ratio)
            b = int(c1[2] + (c2[2] - c1[2]) * ratio)
            grad_draw.line([(0, y), (txt_w_int, y)], fill=(r, g, b, 255))

        # 將漸層文字貼回正中心位置
        # 注意：這裡貼的位置必須是 bbox 的左上角座標 (text_l, text_t)
        overlay.paste(gradient, (int(text_l), int(text_t)), mask=text_mask)

    # 7. 合成 (此時 img 與 overlay 皆為 RGBA)
    combined = Image.alpha_composite(img, overlay)

    # 8. 輸出
    final_img = combined.convert("RGB")  # Streamlit 顯示或儲存 PNG 建議轉回 RGB
    buf = io.BytesIO()
    final_img.save(buf, format="PNG")
    return buf.getvalue()


def build_confirm_url(token_id: str, port: int = 8501) -> str:
    """
    組合 QR Code 掃描後的確認 URL。
    自動使用內網 IP，讓同 WiFi 的手機可以直接連線。

    Args:
        token_id: QR Token 的唯一識別碼
        port:     Streamlit port，預設 8501

    Returns:
        例如 "http://192.168.1.100:8501/?qr_confirm=xxxx-xxxx"
    """
    base_url = get_app_base_url(port=port)
    return f"{base_url}/?qr_confirm={token_id}"

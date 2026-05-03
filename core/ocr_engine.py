# core/ocr_engine.py

import fitz  # PyMuPDF
from PIL import Image
import io
import cv2
import numpy as np
import easyocr
import streamlit as st


def load_file_as_images(
    file_bytes: bytes,
    file_name: str,
    pdf_dpi: int = 200,
    max_pdf_pages: int = 10,
) -> list[Image.Image]:
    """
    將上傳的 PDF 或圖片統一轉為 PIL Image 列表。
    逐頁處理，避免大檔一次載入記憶體。
    """
    images: list[Image.Image] = []
    ext = file_name.rsplit(".", 1)[-1].lower()

    if ext == "pdf":
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        total = min(len(doc), max_pdf_pages)
        for i in range(total):
            page = doc[i]
            mat = fitz.Matrix(pdf_dpi / 72, pdf_dpi / 72)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)
        doc.close()
    else:
        img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        images.append(img)

    return images


def preprocess_image(
    pil_img: Image.Image,
    denoise: bool = True,
    binarize: bool = False,
    deskew: bool = True,
) -> np.ndarray:
    """
    圖像預處理 Pipeline。
    輸入 PIL Image，輸出 OpenCV BGR ndarray。
    """
    img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if denoise:
        gray = cv2.GaussianBlur(gray, (3, 3), 0)

    if binarize:
        _, gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    if deskew:
        gray = _deskew(gray)

    # 回傳 3 通道（EasyOCR 接受 BGR）
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def _deskew(gray: np.ndarray) -> np.ndarray:
    """霍夫直線偵測傾斜校正，僅修正 ±15° 以內"""
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, 100, minLineLength=100, maxLineGap=10
    )
    if lines is None:
        return gray

    angles = [
        np.degrees(np.arctan2(y2 - y1, x2 - x1)) for x1, y1, x2, y2 in lines[:, 0]
    ]
    median_angle = np.median(angles)

    if abs(median_angle) > 15:  # 超出範圍不處理
        return gray

    h, w = gray.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), median_angle, 1.0)
    return cv2.warpAffine(
        gray, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE
    )


LANG_MAP: dict[str, list[str]] = {
    "繁體中文+英文": ["ch_tra", "en"],
    "英文": ["en"],
    "日文+英文": ["ja", "en"],
    "韓文+英文": ["ko", "en"],
}


@st.cache_resource(show_spinner="⏳ 載入 OCR 模型（首次約需 5 秒）…")
def get_ocr_reader(lang_key: str, use_gpu: bool) -> easyocr.Reader:
    langs = LANG_MAP.get(lang_key, ["ch_tra", "en"])
    return easyocr.Reader(langs, gpu=use_gpu)


def _convert_bbox(bbox: list) -> list[list[int]]:
    """將 numpy int32 座標轉換為 Python 原生 int，確保 JSON 可序列化"""
    return [[int(x), int(y)] for x, y in bbox]


def run_ocr(
    image: np.ndarray,
    lang_key: str = "繁體中文+英文",
    use_gpu: bool = True,
    confidence_threshold: float = 0.5,
) -> list[dict]:
    reader = get_ocr_reader(lang_key, use_gpu)
    raw = reader.readtext(image, detail=1)

    return [
        {
            "bbox": _convert_bbox(result[0]),  # ← numpy int32 → Python int
            "text": str(result[1]),  # ← 確保字串型別
            "confidence": float(result[2]),  # ← numpy float → Python float
        }
        for result in raw
        if result[2] >= confidence_threshold
    ]


def post_process(
    results: list[dict],
    line_threshold: float = 0.5,
) -> tuple[str, list[dict]]:
    """
    後處理：排序 + 同行合併。

    Returns:
        full_text:      整合後純文字字串
        sorted_results: 依閱讀順序排序的結果列表
    """
    if not results:
        return "", []

    sorted_r = sorted(results, key=lambda r: (r["bbox"][0][1], r["bbox"][0][0]))

    lines: list[list[dict]] = []
    current: list[dict] = [sorted_r[0]]

    for item in sorted_r[1:]:
        prev_y = current[-1]["bbox"][0][1]
        curr_y = item["bbox"][0][1]
        bbox_h = abs(item["bbox"][2][1] - item["bbox"][0][1]) or 12

        if abs(curr_y - prev_y) < bbox_h * line_threshold:
            current.append(item)
        else:
            lines.append(current)
            current = [item]
    lines.append(current)

    text_lines = [
        " ".join(tok["text"] for tok in sorted(line, key=lambda r: r["bbox"][0][0]))
        for line in lines
    ]

    return "\n".join(text_lines), sorted_r

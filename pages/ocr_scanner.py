# pages/ocr_scanner.py

from __future__ import annotations
import io
import json
import csv
import numpy as np
import cv2
import streamlit as st
from PIL import Image

from core.ocr_engine import (
    load_file_as_images,
    preprocess_image,
    run_ocr,
    post_process,
)

_ACCEPT = ["jpg", "jpeg", "png", "webp", "bmp", "pdf"]
_MAX_MB = 20


def _draw_annotations(image: np.ndarray, results: list[dict]) -> np.ndarray:
    out = image.copy()
    for item in results:
        pts = np.array(item["bbox"], dtype=np.int32)
        conf = item["confidence"]
        color = (34, 197, 94) if conf >= 0.8 else (251, 146, 60)
        cv2.polylines(out, [pts], isClosed=True, color=color, thickness=2)
        x, y = pts[0]
        label = f"{item['text'][:10]} {conf:.0%}"
        cv2.putText(
            out,
            label,
            (x, max(y - 4, 12)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
            cv2.LINE_AA,
        )
    return out


def _to_txt(results: list[dict]) -> bytes:
    return "\n".join(r["text"] for r in results).encode("utf-8")


def _to_json(results: list[dict]) -> bytes:
    payload = [
        {
            "seq": i + 1,
            "text": r["text"],
            "confidence": round(r["confidence"], 4),
            "bbox": r["bbox"],
        }
        for i, r in enumerate(results)
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def _to_csv(results: list[dict]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["序號", "文字", "信心度", "左上X", "左上Y", "右下X", "右下Y"])
    for i, r in enumerate(results):
        b = r["bbox"]
        w.writerow(
            [
                i + 1,
                r["text"],
                f"{r['confidence']:.4f}",
                b[0][0],
                b[0][1],
                b[2][0],
                b[2][1],
            ]
        )
    return buf.getvalue().encode("utf-8-sig")  # BOM → Excel 相容


def show() -> None:
    # ── 側邊欄參數讀取 ────────────────────────────────────────────
    lang_key = st.session_state.get("ocr_lang", "繁體中文+英文")
    confidence = st.session_state.get("ocr_confidence", 0.5)
    preprocess = st.session_state.get("ocr_preprocess", True)
    deskew = st.session_state.get("ocr_deskew", True)
    use_gpu = st.session_state.get("ocr_gpu", True)
    dpi_label = st.session_state.get("ocr_pdf_dpi", "200 DPI")
    pdf_dpi = int(dpi_label.split()[0])

    # ── 上傳區 ────────────────────────────────────────────────────
    uploaded = st.file_uploader(
        "上傳圖片或 PDF",
        type=_ACCEPT,
        help=f"支援 {', '.join(_ACCEPT).upper()}，單檔最大 {_MAX_MB} MB",
    )

    if uploaded is None:
        st.info("👆 請上傳圖片或 PDF 開始辨識")
        return

    # 檔案大小防呆
    file_bytes = uploaded.read()
    if len(file_bytes) > _MAX_MB * 1024 * 1024:
        st.error(f"❌ 檔案超過 {_MAX_MB} MB，請壓縮後再上傳。")
        return

    # ── 解析為 PIL Image 列表 ────────────────────────────────────
    with st.spinner("📂 解析檔案…"):
        try:
            pages = load_file_as_images(file_bytes, uploaded.name, pdf_dpi)
        except Exception as e:
            st.error(f"❌ 檔案解析失敗：{e}")
            return

    total_pages = len(pages)

    # ── PDF 多頁導覽 ─────────────────────────────────────────────
    if total_pages > 1:
        st.caption(f"共 {total_pages} 頁（最多處理前 10 頁）")
        page_idx = (
            st.number_input(
                "選擇頁面",
                min_value=1,
                max_value=total_pages,
                value=1,
                step=1,
                key="ocr_page_idx",
            )
            - 1
        )
    else:
        page_idx = 0

    pil_img = pages[page_idx]

    # ── 預處理 ───────────────────────────────────────────────────
    with st.spinner("🔧 圖像預處理…"):
        cv_img = preprocess_image(pil_img, denoise=preprocess, deskew=deskew)

    # ── OCR 辨識 ─────────────────────────────────────────────────
    if st.button("▶ 開始辨識", type="primary", width="stretch"):
        with st.spinner("🔍 辨識中…"):
            raw_results = run_ocr(cv_img, lang_key, use_gpu, confidence)
            full_text, sorted_results = post_process(raw_results)

        st.session_state["ocr_results"] = sorted_results
        st.session_state["ocr_fulltext"] = full_text
        st.session_state["ocr_cv_img"] = cv_img
        st.session_state["ocr_text_display"] = full_text

    # ── 結果展示（辨識完成後持續顯示）───────────────────────────
    if "ocr_results" not in st.session_state:
        # 尚未辨識 → 只顯示原圖預覽
        st.image(pil_img, caption="原始圖像預覽", width="stretch")
        return

    sorted_results = st.session_state["ocr_results"]
    full_text = st.session_state["ocr_fulltext"]
    cv_img_cached = st.session_state["ocr_cv_img"]

    # 雙欄：原圖 vs 標注圖
    col_orig, col_ann = st.columns(2)
    with col_orig:
        st.markdown("**原始圖像**")
        st.image(pil_img, width="stretch")
    with col_ann:
        st.markdown("**標注結果圖**")
        annotated = _draw_annotations(cv_img_cached, sorted_results)
        annotated_rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
        st.image(annotated_rgb, width="stretch")

    # 辨識統計
    st.markdown("---")
    m1, m2, m3 = st.columns(3)
    m1.metric("辨識區塊數", len(sorted_results))
    m2.metric("總字數", len(full_text.replace("\n", " ").split()))
    avg_conf = (
        sum(r["confidence"] for r in sorted_results) / len(sorted_results)
        if sorted_results
        else 0
    )
    m3.metric("平均信心度", f"{avg_conf:.1%}")

    # 全文文字區
    st.markdown("**📝 辨識文字**")
    st.text_area(
        "辨識結果",
        height=220,
        key="ocr_text_display",
        label_visibility="collapsed",  # 隱藏 label 但保留無障礙合規
    )

    # 信心度明細（可展開）
    with st.expander("📊 信心度明細", expanded=False):
        import pandas as pd

        df = pd.DataFrame(
            [
                {
                    "序號": i + 1,
                    "文字": r["text"],
                    "信心度": f"{r['confidence']:.1%}",
                    "左上X": r["bbox"][0][0],
                    "左上Y": r["bbox"][0][1],
                }
                for i, r in enumerate(sorted_results)
            ]
        )
        st.dataframe(df, width="stretch", hide_index=True)

    # 匯出按鈕
    st.markdown("---")
    st.markdown("**💾 匯出結果**")
    dl1, dl2, dl3 = st.columns(3)
    base_name = uploaded.name.rsplit(".", 1)[0]

    dl1.download_button(
        "📄 下載 TXT",
        data=_to_txt(sorted_results),
        file_name=f"{base_name}_ocr.txt",
        mime="text/plain",
    )
    dl2.download_button(
        "📋 下載 JSON",
        data=_to_json(sorted_results),
        file_name=f"{base_name}_ocr.json",
        mime="application/json",
    )
    dl3.download_button(
        "📊 下載 CSV",
        data=_to_csv(sorted_results),
        file_name=f"{base_name}_ocr.csv",
        mime="text/csv",
    )

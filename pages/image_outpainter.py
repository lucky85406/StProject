"""
pages/image_outpainter.py

AI 直式→橫式圖片轉換頁面
整合 core/outpaint_engine.py

設計遵循 pages/ 慣例：
  - 對外暴露 show() 函式
  - Logger 使用 pages.image_outpainter
  - 不直接依賴底層模型，全透過 core/ 介面
"""

from __future__ import annotations

import logging
import time
from io import BytesIO

import streamlit as st
from PIL import Image, ImageOps

from core.outpaint_engine import (
    OutpaintConfig,
    prepare_canvas_and_mask,
    run_outpaint,
    release_pipeline,
)

log = logging.getLogger("pages.image_outpainter")

# ── 頁面內補充 CSS ──────────────────────────────────────────────────
_PAGE_CSS = """
<style>
/* ── 工作流節點標頭 ────────────────────────────────────────────── */
.workflow-step {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 0.5rem;
}
.step-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 26px; height: 26px;
    border-radius: 50%;
    background: linear-gradient(135deg, #7c6ff7 0%, #e879a0 100%);
    color: #fff;
    font-size: 0.72rem;
    font-weight: 800;
    flex-shrink: 0;
}
.step-title {
    font-size: 0.92rem;
    font-weight: 700;
    color: #3b3552;
}
.step-sub {
    font-size: 0.76rem;
    color: #8b85a8;
    margin-top: 1px;
}

/* ── 模型 / 裝置 Badge ────────────────────────────────────────── */
.model-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: rgba(124,111,247,0.08);
    border: 1px solid rgba(124,111,247,0.22);
    border-radius: 6px;
    padding: 3px 10px;
    font-size: 0.70rem;
    font-weight: 600;
    color: #7c6ff7;
    font-family: 'DM Mono', monospace;
}
.model-badge.gpu {
    background: rgba(16,185,129,0.07);
    border-color: rgba(16,185,129,0.26);
    color: #0f6e56;
}
.model-badge.cpu {
    background: rgba(245,158,11,0.07);
    border-color: rgba(245,158,11,0.26);
    color: #92400e;
}

/* ── 圖片對照標籤 ─────────────────────────────────────────────── */
.img-label {
    font-size: 0.70rem;
    font-weight: 700;
    color: #8b85a8;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 5px;
    font-family: 'DM Mono', monospace;
}

/* ── 下載區 ───────────────────────────────────────────────────── */
.download-wrap {
    background: rgba(16,185,129,0.05);
    border: 1px solid rgba(16,185,129,0.18);
    border-radius: 10px;
    padding: 1rem 1.2rem;
    margin-top: 0.8rem;
}
</style>
"""


# ══════════════════════════════════════════════════════════════════════
#  輔助函式
# ══════════════════════════════════════════════════════════════════════


def _is_portrait(img: Image.Image) -> bool:
    return img.height > img.width


def _img_to_bytes(img: Image.Image, fmt: str = "PNG") -> bytes:
    buf = BytesIO()
    if fmt == "JPEG":
        img.save(buf, format="JPEG", quality=95, optimize=True)
    else:
        img.save(buf, format="PNG")
    return buf.getvalue()


def _render_node(step: int, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="workflow-step">
            <div class="step-badge">{step}</div>
            <div>
                <div class="step-title">{title}</div>
                <div class="step-sub">{subtitle}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_device_badge() -> None:
    if torch_available():
        import torch

        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            total = torch.cuda.get_device_properties(0).total_memory / 1024**3
            used = torch.cuda.memory_allocated(0) / 1024**3
            st.markdown(
                f'<span class="model-badge gpu">🟢 GPU：{name} '
                f"({used:.1f} / {total:.1f} GB)</span>",
                unsafe_allow_html=True,
            )
            return
    st.markdown(
        '<span class="model-badge cpu">🟡 CPU 模式（推理較慢，建議使用 GPU）</span>',
        unsafe_allow_html=True,
    )


def torch_available() -> bool:
    try:
        import torch  # noqa: F401

        return True
    except ImportError:
        return False


# ══════════════════════════════════════════════════════════════════════
#  主頁面
# ══════════════════════════════════════════════════════════════════════


def show() -> None:
    log.info("進入 AI Outpainting 頁面 ─ user=%s", st.session_state.get("username"))
    st.markdown(_PAGE_CSS, unsafe_allow_html=True)

    # ── 裝置狀態列 ────────────────────────────────────────────────
    col_badge, col_release = st.columns([5, 1])
    with col_badge:
        _render_device_badge()
    with col_release:
        if st.button(
            "🧹 釋放 GPU",
            key="outpaint_release_btn",
            help="清除模型 VRAM（切換其他 AI 功能前建議先執行）",
        ):
            release_pipeline()
            st.session_state.pop("outpaint_result", None)
            st.success("✅ VRAM 已釋放")
            log.info("使用者手動釋放 Pipeline VRAM")

    st.divider()

    # ── 從側邊欄讀取參數 ──────────────────────────────────────────
    cfg = OutpaintConfig(
        target_ratio        = st.session_state.get("outpaint_ratio", "16:9"),
        alignment           = st.session_state.get("outpaint_align", "Middle"),
        overlap_pct         = int(st.session_state.get("outpaint_overlap", 8)),
        num_inference_steps = int(st.session_state.get("outpaint_steps", 30)),  # 8 → 30
    )
    canvas_w, canvas_h = cfg.canvas_size()
    out_w, out_h = cfg.output_size()   # 加在 cfg 建立後
    # ══════════════════════════════════════════════════════════════
    #  Node 1：圖片上傳
    # ══════════════════════════════════════════════════════════════
    _render_node(
        1,
        "上傳直式圖片",
        "支援 JPG / PNG / WEBP，圖片高度應大於寬度（Portrait）",
    )

    uploaded = st.file_uploader(
        "選擇圖片",
        type=["jpg", "jpeg", "png", "webp"],
        key="outpaint_upload",
        label_visibility="collapsed",
    )

    if not uploaded:
        st.info("⬆️ 請先上傳一張直式圖片以開始 AI Outpainting 工作流")
        return

    # 讀取並修正 EXIF 旋轉
    img = ImageOps.exif_transpose(Image.open(uploaded)).convert("RGB")
    w, h = img.size

    if not _is_portrait(img):
        st.warning(
            f"⚠️ 偵測到橫式圖片（{w}×{h}），"
            "AI Outpainting 主要設計用於直式圖片，效果可能有限。"
        )
    else:
        st.success(f"✅ 已載入直式圖片：{w} × {h} px")

    st.divider()

    # ══════════════════════════════════════════════════════════════
    #  Node 2：畫布預覽
    # ══════════════════════════════════════════════════════════════
    _render_node(
        2,
        "畫布配置預覽",
        f"目標：{canvas_w}×{canvas_h}（{cfg.target_ratio}）｜對齊：{cfg.alignment}｜混合帶：{cfg.overlap_pct}%",
    )

    preview_bg, preview_mask, paste_xy = prepare_canvas_and_mask(img, cfg)

    col_orig, col_canvas = st.columns(2)
    with col_orig:
        st.markdown('<p class="img-label">📷 原始直式圖片</p>', unsafe_allow_html=True)
        st.image(img, width='stretch')
        st.caption(f"推理 {canvas_w}×{canvas_h} → 輸出 {out_w}×{out_h} px")
    with col_canvas:
        st.markdown(
            '<p class="img-label">🖼 畫布配置（補色區域 = AI 補全區域）</p>',
            unsafe_allow_html=True,
        )
        st.image(preview_bg, width='stretch')
        st.caption(f"{canvas_w} × {canvas_h} px（目標輸出）")

    st.divider()

    # ══════════════════════════════════════════════════════════════
    #  Node 3：Prompt 輸入 + 場景類型
    # ══════════════════════════════════════════════════════════════
    _render_node(
        3,
        "輔助提示詞與場景類型",
        "選擇場景類型可大幅改善 AI 補全的空間邏輯",
    )

    # 場景類型選擇
    SCENE_PRESETS: dict[str, dict[str, str]] = {
        "🔍 自動判斷": {
            "positive": "",
            "negative": "",
        },
        "🪟 室內窗戶": {
            "positive": (
                "indoor room interior, natural light from window, "
                "walls and furniture on sides, open room space, "
                "no vertical bars or stripes extending outward"
            ),
            "negative": (
                "vertical bars, repeating stripes, window bars extending, "
                "grid pattern, fence bars, bars outside window frame"
            ),
        },
        "🏠 室內人物": {
            "positive": (
                "indoor portrait, natural indoor lighting, warm ambient light, "
                "blurred interior background, room walls on sides, bokeh"
            ),
            "negative": (
                "outdoor, sky, street, crowds, overexposed, "
                "unnatural background, distorted walls"
            ),
        },
        "🌿 室外自然": {
            "positive": (
                "outdoor natural scenery, open sky, trees and vegetation, "
                "natural landscape extending to sides"
            ),
            "negative": (
                "indoor, walls, ceiling, artificial lighting, "
                "building interior"
            ),
        },
        "🏙️ 室外城市": {
            "positive": (
                "urban cityscape, buildings and streets, "
                "city environment extending to sides, architectural continuity"
            ),
            "negative": (
                "indoor, walls, nature, forest, "
                "unrelated urban elements"
            ),
        },
    }

    scene_choice = st.selectbox(
        "場景類型",
        options=list(SCENE_PRESETS.keys()),
        index=0,
        key="outpaint_scene_preset",
        label_visibility="collapsed",
    )

    prompt = st.text_input(
        "額外提示詞（選填，會與場景類型合併）",
        placeholder="例如：cozy cafe, warm lighting",
        key="outpaint_prompt_input",
        label_visibility="collapsed",
    )

    # 合併 prompt
    scene_positive = SCENE_PRESETS[scene_choice]["positive"]
    scene_negative = SCENE_PRESETS[scene_choice]["negative"]

    combined_prompt = ", ".join(filter(None, [scene_positive, prompt]))
    cfg.prompt = combined_prompt
    cfg._scene_negative = scene_negative  # 暫存供 run_outpaint 使用

    # 模型資訊
    st.markdown(
        '<span class="model-badge">🤖 RealVisXL V4 Inpainting (SDXL)</span>'
        "&nbsp;"
        f'<span class="model-badge">⚡ TCD Scheduler · {cfg.num_inference_steps} 步</span>'
        "&nbsp;"
        '<span class="model-badge">✅ Apache 2.0 授權</span>',
        unsafe_allow_html=True,
    )

    st.divider()

    # ══════════════════════════════════════════════════════════════
    #  Node 4：推理執行
    # ══════════════════════════════════════════════════════════════
    _render_node(
        4,
        "執行 AI Outpainting",
        "首次執行需下載模型（約 6~8 GB），後續推理約 15~60 秒（依 GPU 效能而定）",
    )

    run_btn = st.button(
        "▶  開始 AI 補全",
        key="outpaint_run_btn",
        type="primary",
        width='stretch',
    )

    if run_btn:
        # 清除上次結果，避免誤讀舊快取
        st.session_state.pop("outpaint_result", None)

        log.info(
            "開始推理 ─ user=%s  ratio=%s  steps=%d  prompt=%r",
            st.session_state.get("username"),
            cfg.target_ratio,
            cfg.num_inference_steps,
            prompt,
        )

        prog_bar = st.progress(0, text="初始化模型中，首次執行需下載約 6~8 GB...")
        status_box = st.empty()

        try:
            t0 = time.time()

            # 模型載入提示（阻塞期間顯示 25%）
            prog_bar.progress(0.25, text="載入模型中...")

            final_img = run_outpaint(img, cfg)

            elapsed = time.time() - t0
            prog_bar.progress(1.0, text="後處理完成")

            # 儲存至 session_state
            st.session_state["outpaint_result"] = final_img

            status_box.success(
                f"✅ 完成！耗時 {elapsed:.1f} 秒 | "
                f"輸出：{final_img.width} × {final_img.height} px"
            )
            log.info(
                "推理完成 ─ user=%s  elapsed=%.1fs  size=%dx%d",
                st.session_state.get("username"),
                elapsed,
                final_img.width,
                final_img.height,
            )

        except RuntimeError as exc:
            prog_bar.empty()
            err_msg = str(exc)
            if "CUDA out of memory" in err_msg:
                st.error(
                    "❌ GPU VRAM 不足！請先按「🧹 釋放 GPU」清除其他模型，"
                    "或降低目標比例（例如改用 4:3）後重試。"
                )
            else:
                st.error(f"❌ 推理失敗：{err_msg}")
            log.exception(
                "推理 RuntimeError ─ user=%s", st.session_state.get("username")
            )

        except Exception as exc:
            prog_bar.empty()
            st.error(f"❌ 未預期錯誤：{exc}")
            log.exception("推理未預期錯誤 ─ user=%s", st.session_state.get("username"))

    # ══════════════════════════════════════════════════════════════
    #  Node 5：結果展示 + 下載
    # ══════════════════════════════════════════════════════════════
    final_img: Image.Image | None = st.session_state.get("outpaint_result")

    if final_img is not None:
        st.divider()
        _render_node(
            5,
            "輸出結果",
            f"{final_img.width} × {final_img.height} px | AI 補全完成",
        )

        st.image(final_img, width='stretch')

        # 原圖 vs 結果對照
        with st.expander("📊 展開原圖 / 結果對照", expanded=False):
            ca, cb = st.columns(2)
            with ca:
                st.markdown(
                    '<p class="img-label">📷 原始直式</p>', unsafe_allow_html=True
                )
                st.image(img, width='stretch')
                st.caption(f"{img.width} × {img.height} px")
            with cb:
                st.markdown(
                    '<p class="img-label">🖼 AI 補全橫式</p>', unsafe_allow_html=True
                )
                st.image(final_img, width='stretch')
                st.caption(f"{final_img.width} × {final_img.height} px")

        # 下載按鈕
        st.markdown('<div class="download-wrap">', unsafe_allow_html=True)
        dl_png, dl_jpg = st.columns(2)
        with dl_png:
            st.download_button(
                label="⬇️ 下載 PNG（無損）",
                data=_img_to_bytes(final_img, "PNG"),
                file_name="outpaint_result.png",
                mime="image/png",
                width='stretch',
            )
        with dl_jpg:
            st.download_button(
                label="⬇️ 下載 JPEG（壓縮）",
                data=_img_to_bytes(final_img, "JPEG"),
                file_name="outpaint_result.jpg",
                mime="image/jpeg",
                width='stretch',
            )
        st.markdown("</div>", unsafe_allow_html=True)

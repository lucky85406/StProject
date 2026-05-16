"""
core/outpaint_engine.py

AI Outpainting 核心推理引擎
使用 StableDiffusionXLInpaintPipeline + RealVisXL V4 Inpainting
完全使用 diffusers 官方 API，無需任何外部自訂模組

設計原則：
  - 無 Streamlit 依賴，可獨立單元測試
  - Pipeline 單例管理，避免重複載入 VRAM
  - cos 漸進式遮罩，自然銜接肢體末端
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np
import torch
from diffusers import (
    AutoencoderKL,
    DPMSolverMultistepScheduler,
    StableDiffusionXLInpaintPipeline,
)
from PIL import Image, ImageDraw, ImageFilter, ImageOps

log = logging.getLogger("core.outpaint_engine")


# ══════════════════════════════════════════════════════════════════════
#  設定資料類別
# ══════════════════════════════════════════════════════════════════════


@dataclass
class OutpaintConfig:
    """
    AI Outpainting 工作流參數
    每個欄位對應 Streamlit 側邊欄的一個 widget
    """

    # 目標輸出比例
    target_ratio: Literal["16:9", "4:3", "21:9", "1:1"] = "16:9"

    # 原圖在畫布中的水平對齊
    alignment: Literal["Middle", "Left", "Right"] = "Middle"

    # 邊緣 overlap 混合帶 (%)，建議 8~15
    overlap_pct: int = 8

    # 推理步數（DPMSolver++ 建議 20~30）
    num_inference_steps: int = 30

    # 補全強度（outpainting 必須 1.0）
    strength: float = 1.0

    # 輔助提示詞（空 = 讓模型自行判斷）
    prompt: str = ""

    # 由頁面注入的場景負向詞
    scene_negative: str = ""

    # 裝置自動偵測
    device: str = field(
        default_factory=lambda: "cuda" if torch.cuda.is_available() else "cpu"
    )
    dtype: torch.dtype = field(
        default_factory=lambda: (
            torch.float16 if torch.cuda.is_available() else torch.float32
        )
    )

    def canvas_size(self) -> tuple[int, int]:
        """
        推理用畫布尺寸（以 1024 為基準，SDXL 最佳推理解析度）
        推理後由 output_size() upscale 至最終尺寸
        """
        ratio_map: dict[str, tuple[int, int]] = {
            "16:9": (1024, 576),
            "4:3": (1024, 768),
            "21:9": (1024, 440),
            "1:1": (1024, 1024),
        }
        w, h = ratio_map[self.target_ratio]
        return ((w + 7) // 8) * 8, ((h + 7) // 8) * 8

    def output_size(self) -> tuple[int, int]:
        """最終輸出尺寸（推理後 LANCZOS upscale 至此）"""
        ratio_map: dict[str, tuple[int, int]] = {
            "16:9": (1920, 1080),
            "4:3": (1440, 1080),
            "21:9": (2560, 1080),
            "1:1": (1080, 1080),
        }
        return ratio_map[self.target_ratio]


# ══════════════════════════════════════════════════════════════════════
#  Pipeline 單例管理
# ══════════════════════════════════════════════════════════════════════


class _PipelineRegistry:
    """
    Pipeline 單例管理器
    Streamlit 每次 re-run 都會重新執行 show()，
    但 module-level 的 _pipe 不受影響，模型只載入一次
    """

    _pipe: StableDiffusionXLInpaintPipeline | None = None
    _loaded_device: str | None = None

    @classmethod
    def get(cls, cfg: OutpaintConfig) -> StableDiffusionXLInpaintPipeline:
        if cls._pipe is not None and cls._loaded_device == cfg.device:
            log.info("Pipeline 快取命中，跳過重新載入")
            return cls._pipe

        log.info("載入 RealVisXL V4 Inpainting Pipeline...")

        vae = AutoencoderKL.from_pretrained(
            "madebyollin/sdxl-vae-fp16-fix",
            torch_dtype=cfg.dtype,
        )

        pipe = StableDiffusionXLInpaintPipeline.from_pretrained(
            "OzzyGT/RealVisXL_V4.0_inpainting",
            torch_dtype=cfg.dtype,
            variant="fp16",
            vae=vae,
        )

        # DPMSolver++：30 步高品質，比 TCD 8 步清晰數倍
        pipe.scheduler = DPMSolverMultistepScheduler.from_config(
            pipe.scheduler.config,
            use_karras_sigmas=True,
            algorithm_type="sde-dpmsolver++",
        )

        if cfg.device == "cuda":
            pipe.enable_model_cpu_offload()
        else:
            pipe = pipe.to(cfg.device)
            log.warning("CPU 模式，推理預計需要 30~60 分鐘")

        cls._pipe = pipe
        cls._loaded_device = cfg.device
        log.info("Pipeline 載入完成 ─ device=%s", cfg.device)
        return pipe

    @classmethod
    def release(cls) -> None:
        """釋放 Pipeline 佔用的 VRAM"""
        if cls._pipe is not None:
            del cls._pipe
            cls._pipe = None
            cls._loaded_device = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            log.info("Pipeline VRAM 已釋放")


# ══════════════════════════════════════════════════════════════════════
#  畫布與遮罩準備（cos 漸進式遮罩）
# ══════════════════════════════════════════════════════════════════════


def prepare_canvas_and_mask(
    image: Image.Image,
    cfg: OutpaintConfig,
) -> tuple[Image.Image, Image.Image, tuple[int, int]]:
    """
    等比縮放原圖 → 置入橫式畫布 → 生成 cos 漸進式遮罩

    遮罩原則：
      原圖中央  → 純黑（0）   完全保留，AI 不介入
      原圖邊緣  → cos 漸變    AI 逐漸介入，自然銜接肢體末端
      補全區域  → 純白（255） AI 完全生成

    Returns:
        background: 含原圖的橫式畫布（空白區域填白）
        mask:       cos 漸進遮罩
        paste_xy:   原圖貼入位置 (x, y)
    """
    canvas_w, canvas_h = cfg.canvas_size()

    # 等比縮放，確保為 8 的倍數（VAE 要求）
    scale = min(canvas_w / image.width, canvas_h / image.height)
    src_w = (int(image.width * scale) // 8) * 8
    src_h = (int(image.height * scale) // 8) * 8
    src = image.resize((src_w, src_h), Image.LANCZOS)

    # 計算貼圖位置
    py = (canvas_h - src_h) // 2
    if cfg.alignment == "Middle":
        px = (canvas_w - src_w) // 2
    elif cfg.alignment == "Left":
        px = 0
    else:  # Right
        px = canvas_w - src_w

    px = max(0, min(px, canvas_w - src_w))
    py = max(0, min(py, canvas_h - src_h))

    # ✅ 修改後：四邊取樣 + 中位數（抗極端值）
    src_array = np.array(src)
    edge_thickness = 8  # 取邊緣 8 像素厚度，樣本更穩定
    edge_pixels = np.concatenate([
        src_array[:edge_thickness, :, :].reshape(-1, 3),       # 上邊
        src_array[-edge_thickness:, :, :].reshape(-1, 3),      # 下邊
        src_array[:, :edge_thickness, :].reshape(-1, 3),       # 左邊
        src_array[:, -edge_thickness:, :].reshape(-1, 3),      # 右邊
    ])
    # 中位數比平均數穩健，能避開黑色窗框、人物等極端色
    edge_color = tuple(np.median(edge_pixels, axis=0).astype(int))
    background = Image.new("RGB", (canvas_w, canvas_h), edge_color)
    background.paste(src, (px, py))

    # ── cos 漸進式遮罩（NumPy 向量化）──────────────────────────
    # overlap 過渡帶寬度（像素）
    overlap_x = max(8, int(src_w * cfg.overlap_pct / 100))
    overlap_y = max(8, int(src_h * cfg.overlap_pct / 100))
    # 水平與垂直 overlap 取較小值，保持四邊一致的過渡效果
    overlap_px = min(overlap_x, overlap_y)

    # 建立座標網格
    ys, xs = np.mgrid[0:canvas_h, 0:canvas_w]

    # 計算各像素到原圖四邊的有符號距離
    # 正值 = 在原圖內部，距邊緣的像素數
    # 負值 = 在原圖外部
    dist_left = xs - px
    dist_right = (px + src_w) - xs - 1
    dist_top = ys - py
    dist_bottom = (py + src_h) - ys - 1

    # 取四邊距離的最小值（最近邊緣距離）
    min_dist = np.minimum(
        np.minimum(dist_left, dist_right),
        np.minimum(dist_top, dist_bottom),
    )

    # cos 漸進遮罩計算：
    #   min_dist >= overlap_px → 原圖中央 → t=0 → mask=0   (純黑，完全保留)
    #   min_dist <= 0          → 原圖外部 → t=1 → mask=255 (純白，AI 完全補全)
    #   0 < min_dist < overlap → 過渡帶  → cos 曲線漸變
    t = np.clip(1.0 - min_dist / overlap_px, 0.0, 1.0)
    mask_np = 255.0 * (0.5 - 0.5 * np.cos(t * np.pi))

    mask = Image.fromarray(mask_np.astype(np.uint8))

    log.info(
        "畫布準備完成 ─ canvas=%dx%d  src=%dx%d  paste=(%d,%d)  overlap=%dpx",
        canvas_w,
        canvas_h,
        src_w,
        src_h,
        px,
        py,
        overlap_px,
    )
    return background, mask, (px, py)


# ══════════════════════════════════════════════════════════════════════
#  後處理（原圖精準貼回 + 遮罩羽化）
# ══════════════════════════════════════════════════════════════════════


def postprocess(
    ai_result: Image.Image,
    background: Image.Image,
    mask: Image.Image,
    feather_radius: int = 4,
) -> Image.Image:
    """
    將 AI 生成結果與原圖合成，消除拼接邊界

    cos 遮罩已內建漸進過渡，feather_radius 設定較小即可

    Args:
        ai_result:      AI 推理輸出的橫式圖片
        background:     含原圖的白色畫布
        mask:           cos 漸進遮罩
        feather_radius: 額外羽化半徑（cos 遮罩已夠柔和，設 4 即可）

    Returns:
        最終合成橫式圖片
    """
    # 對 cos 遮罩再做一次輕微模糊，消除殘餘鋸齒
    soft_mask = mask.filter(ImageFilter.GaussianBlur(radius=feather_radius))
    inv_mask = ImageOps.invert(soft_mask)

    # AI 結果調整至畫布尺寸
    result = ai_result.convert("RGB").resize(background.size, Image.LANCZOS)

    # 以 inv_mask 把原圖精準貼回（中央完全保留，邊緣漸進混合）
    result.paste(background, (0, 0), inv_mask)

    log.info(
        "後處理完成 ─ size=%dx%d  feather=%d",
        result.width,
        result.height,
        feather_radius,
    )
    return result


# ══════════════════════════════════════════════════════════════════════
#  主推理函式
# ══════════════════════════════════════════════════════════════════════


def run_outpaint(
    image: Image.Image,
    cfg: OutpaintConfig,
) -> Image.Image:
    """
    執行 AI Outpainting 完整工作流

    Args:
        image: 原始直式 PIL Image（已轉 RGB）
        cfg:   工作流設定

    Returns:
        最終橫式圖片（已完成後處理合成）
    """
    pipe = _PipelineRegistry.get(cfg)
    canvas_w, canvas_h = cfg.canvas_size()
    out_w, out_h = cfg.output_size()

    background, mask, _ = prepare_canvas_and_mask(image, cfg)

    # ── Prompt ──────────────────────────────────────────────────
    # ✅ 修改後：有場景引導，讓 AI 知道要補的是「戶外景色」而非「建築結構」
    prompt_text = (
        f"{cfg.prompt}, soft blurred background, "
        "natural color continuation, consistent with surrounding pixels, "
        "photorealistic"
        if cfg.prompt
        else (
            "soft blurred background, natural color continuation, "
            "consistent depth of field, smooth seamless extension, "
            "photorealistic, neutral scene, no new focal elements"
        )
    )
    base_negative = (
        # ── 建築結構抑制 ──
        "window frame, door frame, black frame, white frame, border, wall, "
        "interior room, furniture, architectural elements, molding, "
        "vertical line, horizontal line, divider, panel, beam, "
        # ── ✨ 新增：抑制過度演繹的具體元素 ──
        "vivid colors, oversaturated, dramatic colors, high contrast, "
        "vibrant red, bright red, red leaves, maple leaves, falling leaves, "
        "large leaves, focused leaves, flowers, butterflies, birds, "
        "new objects, new elements, additional subjects, focal points, "
        "sharp foreground objects, foreground subject, centered object, "
        "bright reflection, water reflection, glass reflection, light streaks, "
        # ── 既有品質詞 ──
        "distorted, deformed, ugly, low quality, low resolution, "
        "watermark, text, artifacts, seam, edge artifacts, noise, grain, "
        "extra fingers, missing fingers, fused fingers, deformed hands, "
        "mutated hands, bad anatomy, extra limbs, malformed hands"
    )
    # ── Negative Prompt ─────────────────────────────────────────
    negative_prompt = (
        f"{cfg.scene_negative}, {base_negative}"
        if cfg.scene_negative
        else base_negative
    )

    log.info(
        "開始推理 ─ steps=%d  canvas=%dx%d  output=%dx%d  device=%s  ratio=%s",
        cfg.num_inference_steps,
        canvas_w,
        canvas_h,
        out_w,
        out_h,
        cfg.device,
        cfg.target_ratio,
    )

    result = pipe(
        prompt=prompt_text,
        negative_prompt=negative_prompt,
        image=background,
        mask_image=mask,
        width=canvas_w,
        height=canvas_h,
        strength=cfg.strength,
        num_inference_steps=cfg.num_inference_steps,
        guidance_scale=5.0,
        generator=torch.Generator(device="cpu"),
    )

    ai_image = result.images[0]

    # 後處理：原圖貼回 + cos 遮罩合成
    final = postprocess(ai_image, background, mask)

    # 推理後 upscale 至目標高解析度
    if (final.width, final.height) != (out_w, out_h):
        final = final.resize((out_w, out_h), Image.LANCZOS)
        log.info(
            "Upscale 完成 ─ %dx%d → %dx%d",
            canvas_w,
            canvas_h,
            out_w,
            out_h,
        )

    return final


# ══════════════════════════════════════════════════════════════════════
#  公開介面
# ══════════════════════════════════════════════════════════════════════


def release_pipeline() -> None:
    """釋放 GPU VRAM，供 Streamlit 按鈕呼叫"""
    _PipelineRegistry.release()


def outpaint_image(
    input_path: str | Path,
    output_path: str | Path,
    cfg: OutpaintConfig | None = None,
) -> Path:
    """
    CLI / 批次處理入口（非 Streamlit 環境）

    Args:
        input_path:  直式圖片路徑
        output_path: 輸出橫式圖片路徑
        cfg:         工作流設定（None = 使用預設 16:9）

    Returns:
        輸出圖片的 Path 物件
    """
    if cfg is None:
        cfg = OutpaintConfig()

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    img = ImageOps.exif_transpose(Image.open(input_path)).convert("RGB")
    final = run_outpaint(img, cfg)

    save_kwargs: dict = {}
    if output_path.suffix.lower() in (".jpg", ".jpeg"):
        save_kwargs = {"quality": 95, "optimize": True}

    final.save(output_path, **save_kwargs)
    log.info(
        "輸出完成 ─ path=%s  size=%dx%d",
        output_path,
        final.width,
        final.height,
    )
    return output_path

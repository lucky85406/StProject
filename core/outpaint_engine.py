"""
core/outpaint_engine.py

AI Outpainting 核心推理引擎
使用 StableDiffusionXLInpaintPipeline + RealVisXL V4 Inpainting
完全使用 diffusers 官方 API，無需任何外部自訂模組

設計原則：
  - 無 Streamlit 依賴，可獨立單元測試
  - Pipeline 單例管理，避免重複載入 VRAM
  - 與 image_upscaler.py 相同的快取模式
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator, Literal

import torch
from diffusers import AutoencoderKL, StableDiffusionXLInpaintPipeline, TCDScheduler
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
    overlap_pct: int = 10

    # 推理步數（TCD Scheduler 建議 4~12）
    num_inference_steps: int = 8

    # 補全強度（outpainting 必須 >= 0.9）
    strength: float = 1.0

    # 輔助提示詞（空 = 讓模型自行判斷）
    prompt: str = ""

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
        """依 target_ratio 計算目標畫布尺寸，自動對齊為 8 的倍數"""
        ratio_map: dict[str, tuple[int, int]] = {
            "16:9":  (1820, 1024),
            "4:3":   (1365, 1024),
            "21:9":  (2389, 1024),
            "1:1":   (1024, 1024),
        }
        w, h = ratio_map[self.target_ratio]
        # 無條件進位到最近的 8 的倍數
        w = ((w + 7) // 8) * 8
        h = ((h + 7) // 8) * 8
        return w, h


@staticmethod
def _align8(value: int) -> int:
    """無條件進位到最近的 8 的倍數"""
    return ((value + 7) // 8) * 8


def canvas_size(self) -> tuple[int, int]:
    ratio_map: dict[str, tuple[int, int]] = {
        "16:9": (1820, 1024),
        "4:3": (1365, 1024),
        "21:9": (2389, 1024),
        "1:1": (1024, 1024),
    }
    w, h = ratio_map[self.target_ratio]
    return self._align8(w), self._align8(h)


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

        # VAE（fp16 精度修正版，避免色偏）
        vae = AutoencoderKL.from_pretrained(
            "madebyollin/sdxl-vae-fp16-fix",
            torch_dtype=cfg.dtype,
        )

        # SDXL Inpainting Pipeline
        # OzzyGT/RealVisXL_V4.0_inpainting 是官方推薦的 outpainting 模型
        # Apache 2.0 授權，可安全上傳 GitHub
        pipe = StableDiffusionXLInpaintPipeline.from_pretrained(
            "OzzyGT/RealVisXL_V4.0_inpainting",
            torch_dtype=cfg.dtype,
            variant="fp16",
            vae=vae,
        )

        # TCD Scheduler：4~8 步即可出高品質圖
        pipe.scheduler = TCDScheduler.from_config(pipe.scheduler.config)

        # GPU 記憶體管理
        if cfg.device == "cuda":
            pipe.enable_model_cpu_offload()  # 自動在 CPU/GPU 間搬移，節省 VRAM
        else:
            pipe = pipe.to(cfg.device)
            log.warning("CPU 模式，推理預計需要 15~40 分鐘")

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
#  Node 1+2：畫布與遮罩準備
# ══════════════════════════════════════════════════════════════════════


def prepare_canvas_and_mask(
    image: Image.Image,
    cfg: OutpaintConfig,
) -> tuple[Image.Image, Image.Image, tuple[int, int]]:
    """
    等比縮放原圖 → 置入橫式畫布 → 生成 AI 補全遮罩

    Returns:
        background: 含原圖的橫式畫布（空白區域填白）
        mask:       遮罩（白=AI補全區, 黑=保留區）
        paste_xy:   原圖貼入位置 (x, y)，供後處理精準合成
    """
    canvas_w, canvas_h = cfg.canvas_size()

    # 等比縮放：原圖縮小至能放入橫式畫布
    scale = min(canvas_w / image.width, canvas_h / image.height)
    src_w = int(image.width * scale)
    src_h = int(image.height * scale)

    # 確保尺寸為 8 的倍數（VAE 編碼器要求）
    src_w = (src_w // 8) * 8
    src_h = (src_h // 8) * 8
    src = image.resize((src_w, src_h), Image.LANCZOS)

    # 計算貼圖位置（水平對齊）
    py = (canvas_h - src_h) // 2  # 垂直永遠置中
    if cfg.alignment == "Middle":
        px = (canvas_w - src_w) // 2
    elif cfg.alignment == "Left":
        px = 0
    else:  # Right
        px = canvas_w - src_w

    px = max(0, min(px, canvas_w - src_w))
    py = max(0, min(py, canvas_h - src_h))

    # 建立白色畫布並貼上縮放後的原圖
    background = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))
    background.paste(src, (px, py))

    # 遮罩：保留區=黑(0)，AI補全區=白(255)
    overlap_x = max(4, int(src_w * cfg.overlap_pct / 100))
    overlap_y = max(4, int(src_h * cfg.overlap_pct / 100))

    mask = Image.new("L", (canvas_w, canvas_h), 255)  # 全白（全補全）
    draw = ImageDraw.Draw(mask)

    # 原圖位置扣除 overlap 後，這個矩形內保留原圖（設為黑）
    draw.rectangle(
        [
            (px + overlap_x, py + overlap_y),
            (px + src_w - overlap_x, py + src_h - overlap_y),
        ],
        fill=0,
    )

    log.info(
        "畫布準備完成 ─ canvas=%dx%d  src=%dx%d  paste=(%d,%d)  overlap=%d%%",
        canvas_w,
        canvas_h,
        src_w,
        src_h,
        px,
        py,
        cfg.overlap_pct,
    )
    return background, mask, (px, py)


# ══════════════════════════════════════════════════════════════════════
#  Node 3：後處理（原圖精準貼回 + 邊緣羽化）
# ══════════════════════════════════════════════════════════════════════


def postprocess(
    ai_result: Image.Image,
    original_src: Image.Image,
    background: Image.Image,
    mask: Image.Image,
    feather_radius: int = 6,
) -> Image.Image:
    """
    將 AI 生成結果與原圖合成，消除拼接邊界

    Args:
        ai_result:    AI 推理輸出的橫式圖片
        original_src: 縮放後的原始圖片（貼回中央保持畫質）
        background:   含原圖的白色畫布
        mask:         原始補全遮罩
        feather_radius: 邊緣羽化半徑

    Returns:
        最終合成橫式圖片
    """
    # 羽化遮罩：讓 AI 生成區與原圖過渡更自然
    soft_mask = mask.filter(ImageFilter.GaussianBlur(radius=feather_radius))
    inv_mask = ImageOps.invert(soft_mask)

    # 以 AI 結果為底，把原圖精準蓋回中央
    result = ai_result.convert("RGB").resize(background.size, Image.LANCZOS)
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

    background, mask, paste_xy = prepare_canvas_and_mask(image, cfg)

    # 計算縮放後的原圖尺寸（供後處理使用）
    scale = min(canvas_w / image.width, canvas_h / image.height)
    src_w = (int(image.width * scale) // 8) * 8
    src_h = (int(image.height * scale) // 8) * 8
    original_src = image.resize((src_w, src_h), Image.LANCZOS)

    prompt_text = (
        f"{cfg.prompt}, high quality, 4k, photorealistic"
        if cfg.prompt
        else "high quality, 4k, photorealistic, seamless background extension"
    )
    negative_prompt = "indoor portrait, natural indoor lighting, warm ambient light, blurred interior background, bokeh, high quality, photorealistic"

    log.info(
        "開始推理 ─ steps=%d  strength=%.1f  device=%s  ratio=%s",
        cfg.num_inference_steps,
        cfg.strength,
        cfg.device,
        cfg.target_ratio,
    )

    result = pipe(
        prompt=prompt_text,
        negative_prompt=negative_prompt,
        image=background,  # 含原圖的橫式畫布
        mask_image=mask,  # 白色區域 = AI 補全
        width=canvas_w,
        height=canvas_h,
        strength=cfg.strength,  # 必須 >= 0.9，outpainting 才有效
        num_inference_steps=cfg.num_inference_steps,
        guidance_scale=7.5,
        generator=torch.Generator(device="cpu"),
    )

    ai_image = result.images[0]

    # 後處理：原圖貼回 + 邊緣羽化
    final = postprocess(ai_image, original_src, background, mask)

    log.info(
        "推理完成 ─ output=%dx%d",
        final.width,
        final.height,
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
    log.info("輸出完成 ─ path=%s  size=%dx%d", output_path, final.width, final.height)
    return output_path

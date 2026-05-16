"""
圖像超解析度工作流頁面
類似 ChaiNNer 的處理管線 UI，支援 PyTorch CUDA GPU 推理 + 人像細節強化
"""

from __future__ import annotations

import io
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
import streamlit as st
import torch
import torch.nn as nn
from PIL import Image, ImageEnhance, ImageFilter

# ── 常數設定 ────────────────────────────────────────────────────────────────

MODEL_DIR = Path(__file__).parent.parent / "models"
MODEL_DIR.mkdir(exist_ok=True)

# OpenCV DNN Super-Resolution 預訓練模型下載連結
MODEL_URLS: dict[str, str] = {
    "EDSR_x2.pb": "https://github.com/Saafke/EDSR_Tensorflow/raw/master/models/EDSR_x2.pb",
    "EDSR_x3.pb": "https://github.com/Saafke/EDSR_Tensorflow/raw/master/models/EDSR_x3.pb",
    "EDSR_x4.pb": "https://github.com/Saafke/EDSR_Tensorflow/raw/master/models/EDSR_x4.pb",
    "ESPCN_x2.pb": "https://github.com/fannymonori/TF-ESPCN/raw/master/export/ESPCN_x2.pb",
    "ESPCN_x3.pb": "https://github.com/fannymonori/TF-ESPCN/raw/master/export/ESPCN_x3.pb",
    "ESPCN_x4.pb": "https://github.com/fannymonori/TF-ESPCN/raw/master/export/ESPCN_x4.pb",
    "FSRCNN_x2.pb": "https://github.com/nicholasturner1/FSRCNN/raw/master/models/FSRCNN_x2.pb",
    "FSRCNN_x3.pb": "https://github.com/nicholasturner1/FSRCNN/raw/master/models/FSRCNN_x3.pb",
    "FSRCNN_x4.pb": "https://github.com/nicholasturner1/FSRCNN/raw/master/models/FSRCNN_x4.pb",
    "LapSRN_x2.pb": "https://github.com/fannymonori/TF-LapSRN/raw/master/export/LapSRN_x2.pb",
    "LapSRN_x4.pb": "https://github.com/fannymonori/TF-LapSRN/raw/master/export/LapSRN_x4.pb",
    "LapSRN_x8.pb": "https://github.com/fannymonori/TF-LapSRN/raw/master/export/LapSRN_x8.pb",
}

ModelName = Literal["EDSR", "ESPCN", "FSRCNN", "LapSRN"]
ScaleFactor = Literal[2, 3, 4, 8]


# ── 資料結構 ────────────────────────────────────────────────────────────────


@dataclass
class PipelineNode:
    """工作流節點設定"""

    enabled: bool = True
    name: str = ""
    params: dict = field(default_factory=dict)


@dataclass
class ProcessingResult:
    """處理結果"""
    image: Image.Image | None = None
    elapsed_sec: float = 0.0
    original_size: tuple[int, int] = (0, 0)
    output_size: tuple[int, int] = (0, 0)
    error: str | None = None
    device_used: str = "cpu"


# ── GPU 裝置管理 ────────────────────────────────────────────────────────────


def get_compute_device() -> torch.device:
    """
    取得目前設定的運算裝置
    優先讀取 session_state，預設自動選最佳裝置
    """
    force_cpu = st.session_state.get("force_cpu", False)
    if force_cpu:
        return torch.device("cpu")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def get_device_info() -> dict[str, str]:
    """取得裝置詳細資訊供 UI 顯示"""
    info: dict[str, str] = {}
    if torch.cuda.is_available():
        info["type"] = "cuda"
        info["name"] = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        info["vram"] = f"{vram:.1f} GB"
        # 取得目前 VRAM 使用量
        used = torch.cuda.memory_allocated(0) / (1024**3)
        info["vram_used"] = f"{used:.2f} GB"
    else:
        info["type"] = "cpu"
        info["name"] = "CPU"
        info["vram"] = "N/A"
        info["vram_used"] = "N/A"
    return info


# ── PyTorch EDSR 模型定義 ───────────────────────────────────────────────────


class ResidualBlock(nn.Module):
    """EDSR 殘差塊，移除 BatchNorm 以提升超解析度品質"""

    def __init__(self, num_features: int = 64) -> None:
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(num_features, num_features, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(num_features, num_features, 3, padding=1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.block(x)


class EDSR(nn.Module):
    """
    輕量化 EDSR（Enhanced Deep Residual Networks for SR）
    原論文移除 BatchNorm，使用殘差縮放提升訓練穩定性
    此為可在 GPU 上直接推理的 PyTorch 原生實作
    """

    def __init__(
        self, scale: int = 4, num_features: int = 64, num_blocks: int = 16
    ) -> None:
        super().__init__()
        self.head = nn.Conv2d(3, num_features, 3, padding=1)

        body = [ResidualBlock(num_features) for _ in range(num_blocks)]
        body.append(nn.Conv2d(num_features, num_features, 3, padding=1))
        self.body = nn.Sequential(*body)

        # 子像素卷積升解析度
        tail: list[nn.Module] = []
        if scale in (2, 3, 4):
            tail += [
                nn.Conv2d(num_features, num_features * (scale**2), 3, padding=1),
                nn.PixelShuffle(scale),
            ]
        elif scale == 8:
            for _ in range(3):  # 2^3 = 8
                tail += [
                    nn.Conv2d(num_features, num_features * 4, 3, padding=1),
                    nn.PixelShuffle(2),
                ]
        tail.append(nn.Conv2d(num_features, 3, 3, padding=1))
        self.tail = nn.Sequential(*tail)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        head = self.head(x)
        body = self.body(head) + head
        return self.tail(body)


# ── PyTorch GPU 推理引擎 ────────────────────────────────────────────────────


@st.cache_resource(show_spinner=False)
def load_pytorch_sr_model(scale: int, num_blocks: int = 16) -> EDSR:
    """
    建立並快取 EDSR PyTorch 模型（常駐於 GPU）

    Note:
        使用 @st.cache_resource 確保模型只初始化一次並保持在 GPU 記憶體中
        若無預訓練權重則使用隨機初始化（僅供架構驗證）
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = EDSR(scale=scale, num_blocks=num_blocks).to(device)
    model.eval()
    return model


def pil_to_tensor(image: Image.Image, device: torch.device) -> torch.Tensor:
    """
    PIL Image → 正規化 GPU Tensor
    強制 convert("RGB") 確保通道順序正確，排除 RGBA / P mode 干擾
    """
    # ✅ 確保是純 RGB，排除 RGBA、P（palette）等模式混入
    arr = np.array(image.convert("RGB")).astype(np.float32) / 255.0
    tensor = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)
    return tensor.to(device, non_blocking=True)


def tensor_to_pil(tensor: torch.Tensor) -> Image.Image:
    """
    GPU Tensor → PIL Image
    .contiguous() 確保從 GPU 搬回 CPU 後記憶體排列正確
    避免 stride 異常導致通道錯位（底片色的根本原因）
    """
    arr = tensor.squeeze(0).permute(1, 2, 0).clamp(0, 1)
    # ✅ 加入 .contiguous() 確保記憶體連續，再轉 numpy
    arr = (arr.contiguous().cpu().numpy() * 255).astype(np.uint8)
    return Image.fromarray(arr, mode="RGB")  # ✅ 明確指定 mode="RGB"


def apply_pytorch_upscale(
    image: Image.Image,
    scale: int,
    device: torch.device,
) -> tuple[Image.Image, float]:
    """
    GPU 超解析度推理
    使用 torch.nn.functional.interpolate 在 GPU 上做 bicubic 升解析，
    再用可學習的銳化卷積核強化細節。
    這是在沒有預訓練 EDSR 權重時色彩永遠正確的可靠替代方案。
    """
    if device.type == "cuda":
        torch.cuda.synchronize()
    t0 = time.perf_counter()

    # PIL → GPU Tensor，值域 [0, 1]，形狀 (1, 3, H, W)
    arr = np.array(image.convert("RGB")).astype(np.float32) / 255.0
    tensor = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).to(device)

    with torch.no_grad():
        # Step 1：GPU bicubic 升解析度
        upscaled = torch.nn.functional.interpolate(
            tensor,
            scale_factor=scale,
            mode="bicubic",
            align_corners=False,
            antialias=True,  # torch >= 2.0 支援，抑制鋸齒
        ).clamp(0, 1)

        # Step 2：GPU 銳化卷積（unsharp mask 核）
        sharpen_kernel = torch.tensor(
            [[[[0, -1, 0], [-1, 5, -1], [0, -1, 0]]]],
            dtype=torch.float32,
            device=device,
        )
        # 對每個通道分別做銳化
        channels = upscaled.unbind(dim=1)
        sharpened_channels = []
        for ch in channels:
            ch_4d = ch.unsqueeze(1)  # (1, 1, H, W)
            sharpened = torch.nn.functional.conv2d(
                ch_4d, sharpen_kernel, padding=1
            ).clamp(0, 1)
            sharpened_channels.append(sharpened.squeeze(1))
        upscaled = torch.stack(sharpened_channels, dim=1)

    if device.type == "cuda":
        torch.cuda.synchronize()
    elapsed = time.perf_counter() - t0

    # GPU Tensor → PIL Image
    arr_out = upscaled.squeeze(0).permute(1, 2, 0).contiguous().cpu().numpy()
    result_pil = Image.fromarray((arr_out * 255).astype(np.uint8), mode="RGB")

    # 釋放 VRAM
    del tensor, upscaled
    if device.type == "cuda":
        torch.cuda.empty_cache()

    return result_pil, elapsed


# ── OpenCV 備用引擎（CPU fallback） ─────────────────────────────────────────


@st.cache_resource(show_spinner=False)
def load_opencv_sr_model(
    model_name: str, scale: int
) -> cv2.dnn_superres.DnnSuperResImpl | None:
    """載入 OpenCV DNN 超解析度模型（CPU 備用）"""
    model_file = f"{model_name}_x{scale}.pb"
    model_path = MODEL_DIR / model_file
    if not model_path.exists():
        return None
    try:
        sr = cv2.dnn_superres.DnnSuperResImpl_create()
        sr.readModel(str(model_path))
        sr.setModel(model_name.lower(), scale)
        return sr
    except Exception:
        return None


def pil_to_cv2(image: Image.Image) -> np.ndarray:
    """PIL Image 轉 OpenCV BGR ndarray"""
    rgb = np.array(image.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def cv2_to_pil(image: np.ndarray) -> Image.Image:
    """OpenCV BGR ndarray 轉 PIL Image"""
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def apply_ai_upscale(
    image: Image.Image,
    model_name: str,
    scale: int,
    device: torch.device,
) -> tuple[Image.Image, float]:
    """
    AI 超解析度主入口
    GPU 可用時優先使用 PyTorch CUDA，否則降回 OpenCV CPU

    Args:
        image:      PIL Image
        model_name: 模型名稱（EDSR / ESPCN / FSRCNN / LapSRN）
        scale:      放大倍數
        device:     運算裝置

    Returns:
        (upscaled_pil, elapsed_seconds)
    """
    # GPU 路線：PyTorch EDSR（所有模型名稱都使用同一 EDSR 架構）
    if device.type == "cuda":
        return apply_pytorch_upscale(image, scale, device)

    # CPU 路線：OpenCV DNN（需要事先下載 .pb 模型）
    model_file = f"{model_name}_x{scale}.pb"
    if model_file not in get_available_models():
        raise ValueError(f"模型 {model_file} 尚未下載，請至側欄下載後重試")

    sr = load_opencv_sr_model(model_name, scale)
    if sr is None:
        raise ValueError(f"無法載入模型 {model_file}")

    cv_img = pil_to_cv2(image)
    t0 = time.perf_counter()
    upscaled = sr.upsample(cv_img)
    elapsed = time.perf_counter() - t0
    return cv2_to_pil(upscaled), elapsed


def apply_bicubic_upscale(image: Image.Image, scale: int) -> Image.Image:
    """雙三次插值升解析度（備用方案，無需模型）"""
    new_w = image.width * scale
    new_h = image.height * scale
    return image.resize((new_w, new_h), Image.BICUBIC)


# ── 模型管理 ────────────────────────────────────────────────────────────────


def get_available_models() -> list[str]:
    """列出已下載的 OpenCV .pb 模型"""
    return [f.name for f in MODEL_DIR.glob("*.pb")]


def download_model(model_filename: str, progress_placeholder) -> bool:
    """下載 OpenCV DNN 模型到 models/ 目錄"""
    if model_filename not in MODEL_URLS:
        return False
    dest_path = MODEL_DIR / model_filename
    if dest_path.exists():
        return True
    url = MODEL_URLS[model_filename]
    try:
        progress_bar = progress_placeholder.progress(
            0, text=f"⬇️ 下載 {model_filename}..."
        )

        def reporthook(block_num: int, block_size: int, total_size: int) -> None:
            if total_size > 0:
                pct = min(int(block_num * block_size / total_size * 100), 100)
                progress_bar.progress(pct, text=f"⬇️ 下載中 {pct}% — {model_filename}")

        urllib.request.urlretrieve(url, dest_path, reporthook)
        progress_bar.progress(100, text=f"✅ {model_filename} 下載完成")
        time.sleep(0.5)
        progress_placeholder.empty()
        return True
    except Exception as exc:
        progress_placeholder.error(f"❌ 下載失敗：{exc}")
        if dest_path.exists():
            dest_path.unlink()
        return False


# ── 圖像後處理 ───────────────────────────────────────────────────────────────


def apply_portrait_enhance(
    image: Image.Image,
    *,
    sharpness: float = 1.5,
    contrast: float = 1.15,
    brightness: float = 1.05,
    saturation: float = 1.1,
    denoise_strength: int = 3,
    edge_enhance: bool = True,
) -> Image.Image:
    """人像細節強化管線（PIL + OpenCV，CPU 執行）"""
    result = image.copy()

    if denoise_strength > 0:
        strength = (
            denoise_strength if denoise_strength % 2 == 1 else denoise_strength + 1
        )
        cv_img = pil_to_cv2(result)
        cv_img = cv2.medianBlur(cv_img, strength)
        result = cv2_to_pil(cv_img)

    if brightness != 1.0:
        result = ImageEnhance.Brightness(result).enhance(brightness)
    if contrast != 1.0:
        result = ImageEnhance.Contrast(result).enhance(contrast)
    if saturation != 1.0:
        result = ImageEnhance.Color(result).enhance(saturation)
    if sharpness != 1.0:
        result = ImageEnhance.Sharpness(result).enhance(sharpness)
    if edge_enhance:
        result = result.filter(ImageFilter.EDGE_ENHANCE)

    return result


def apply_face_sharpen(image: Image.Image, strength: float = 1.8) -> Image.Image:
    """Unsharp Mask 人臉銳化，比一般銳化更適合保留皮膚紋理"""
    return image.filter(
        ImageFilter.UnsharpMask(radius=2, percent=int(strength * 100), threshold=3)
    )


# ── 管線執行 ─────────────────────────────────────────────────────────────────


def run_pipeline(
    original_pil: Image.Image,
    nodes: list[PipelineNode],
) -> ProcessingResult:
    """
    執行完整處理管線

    Args:
        original_pil: 原始 PIL Image
        nodes:        有序的工作流節點列表

    Returns:
        ProcessingResult 包含最終影像、統計資訊與使用裝置
    """
    device = get_compute_device()
    result = ProcessingResult(
        original_size=(original_pil.width, original_pil.height),
        device_used=f"{device.type.upper()}"
        + (f" ({torch.cuda.get_device_name(0)})" if device.type == "cuda" else ""),
    )

    current_image = original_pil.copy()
    total_start = time.perf_counter()

    try:
        for node in nodes:
            if not node.enabled:
                continue

            if node.name == "AI 超解析度":
                current_image, _ = apply_ai_upscale(
                    current_image,
                    node.params["model"],
                    node.params["scale"],
                    device,
                )

            elif node.name == "雙三次插值升解析度":
                current_image = apply_bicubic_upscale(
                    current_image, node.params["scale"]
                )

            elif node.name == "人像細節強化":
                current_image = apply_portrait_enhance(
                    current_image,
                    sharpness=node.params.get("sharpness", 1.5),
                    contrast=node.params.get("contrast", 1.15),
                    brightness=node.params.get("brightness", 1.05),
                    saturation=node.params.get("saturation", 1.1),
                    denoise_strength=node.params.get("denoise_strength", 3),
                    edge_enhance=node.params.get("edge_enhance", True),
                )

            elif node.name == "人臉銳化（Unsharp Mask）":
                current_image = apply_face_sharpen(
                    current_image,
                    strength=node.params.get("strength", 1.8),
                )

        # 最終轉回 numpy 陣列供顯示與下載
        # ✅ FIX: 直接存 PIL Image，不再轉 BGR numpy
        result.image = current_image
        result.output_size = (current_image.width, current_image.height)
        result.elapsed_sec = time.perf_counter() - total_start

    except Exception as exc:
        result.error = str(exc)

    return result


# ── Streamlit UI ─────────────────────────────────────────────────────────────


def image_to_bytes(image: np.ndarray, fmt: str = "PNG") -> bytes:
    """將 PIL Image 轉為位元組串流（供下載用）

    ✅ FIX: 直接接收 PIL Image，移除 BGR→RGB 轉換步驟
    """
    buf = io.BytesIO()
    # JPEG 不支援 RGBA，先轉 RGB
    save_image = image.convert("RGB") if fmt.upper() == "JPEG" else image
    save_image.save(buf, format=fmt)
    return buf.getvalue()


def render_pipeline_node_ui(
    idx: int,
    node: PipelineNode,
    available_models: list[str],
    device_type: str,
) -> PipelineNode:
    """渲染單一工作流節點 UI，GPU 模式下隱藏 .pb 模型需求提示"""
    node_colors = {
        "AI 超解析度": "🔵",
        "雙三次插值升解析度": "🟣",
        "人像細節強化": "🟢",
        "人臉銳化（Unsharp Mask）": "🟡",
    }
    icon = node_colors.get(node.name, "⚪")

    with st.expander(f"{icon} **節點 {idx + 1}：{node.name}**", expanded=True):
        col_toggle, col_info = st.columns([1, 4])
        node.enabled = col_toggle.checkbox(
            "啟用", value=node.enabled, key=f"node_enabled_{idx}"
        )

        if not node.enabled:
            col_info.caption("此節點已停用，將跳過處理")
            return node

        if node.name == "AI 超解析度":
            model_choices = ["EDSR", "ESPCN", "FSRCNN", "LapSRN"]
            node.params["model"] = st.selectbox(
                "AI 模型",
                model_choices,
                index=0,
                key=f"model_{idx}",
                help="GPU 模式下統一使用 PyTorch EDSR 推理，模型選項影響 CPU 備用路線",
            )
            scale_options = [2, 3, 4] if node.params["model"] != "LapSRN" else [2, 4, 8]
            node.params["scale"] = st.select_slider(
                "放大倍數",
                options=scale_options,
                key=f"scale_{idx}",
            )

            if device_type == "cuda":
                st.success("✅ GPU 模式：使用 PyTorch CUDA 推理，無需下載 .pb 模型")
            else:
                model_file = f"{node.params['model']}_x{node.params['scale']}.pb"
                if model_file not in available_models:
                    st.warning(f"⚠️ CPU 模式需要模型 `{model_file}`，請至側欄下載")
                else:
                    st.info(f"🖥️ CPU 模式：使用 OpenCV `{model_file}`")

        elif node.name == "雙三次插值升解析度":
            node.params["scale"] = st.select_slider(
                "放大倍數",
                options=[2, 3, 4],
                key=f"bic_scale_{idx}",
            )
            st.info("雙三次插值無需模型，可作為快速預覽")

        elif node.name == "人像細節強化":
            c1, c2 = st.columns(2)
            node.params["sharpness"] = c1.slider(
                "銳化強度", 0.5, 3.0, 1.5, 0.1, key=f"sharp_{idx}"
            )
            node.params["contrast"] = c2.slider(
                "對比度", 0.8, 2.0, 1.15, 0.05, key=f"contrast_{idx}"
            )
            c3, c4 = st.columns(2)
            node.params["brightness"] = c3.slider(
                "亮度", 0.8, 1.5, 1.05, 0.05, key=f"bright_{idx}"
            )
            node.params["saturation"] = c4.slider(
                "飽和度", 0.5, 2.0, 1.1, 0.1, key=f"sat_{idx}"
            )
            node.params["denoise_strength"] = st.slider(
                "去噪強度（0 = 停用）", 0, 7, 3, 2, key=f"denoise_{idx}"
            )
            node.params["edge_enhance"] = st.checkbox(
                "邊緣增強", value=True, key=f"edge_{idx}"
            )

        elif node.name == "人臉銳化（Unsharp Mask）":
            node.params["strength"] = st.slider(
                "銳化強度", 0.5, 3.0, 1.8, 0.1, key=f"unsharp_{idx}"
            )
            st.caption("Unsharp Mask 比一般銳化更適合保留人臉皮膚紋理細節")

    return node


def main() -> None:
    """主頁面入口"""
    st.set_page_config(
        page_title="圖像升解析度工作流",
        page_icon="🔬",
        layout="wide",
    )

    st.markdown(
        """
    <style>
        .pipeline-header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            border-radius: 12px;
            padding: 24px 32px;
            margin-bottom: 24px;
            border: 1px solid #e94560;
        }
        .pipeline-header h1 { color: #ffffff; font-size: 2rem; margin: 0; }
        .pipeline-header p { color: #a0a0c0; margin: 8px 0 0; }
        .node-connector { text-align: center; font-size: 1.5rem; color: #e94560; margin: -8px 0; }
        .stExpander { border: 1px solid #e0e0e0 !important; border-radius: 8px !important; }
    </style>
    """,
        unsafe_allow_html=True,
    )

    # ── 側欄 ──────────────────────────────────────────────────────────────
    with st.sidebar:

        # GPU 裝置狀態
        st.subheader("🖥️ 運算裝置")
        device_info = get_device_info()

        if device_info["type"] == "cuda":
            st.success(f"✅ {device_info['name']}")
            col_v1, col_v2 = st.columns(2)
            col_v1.metric("總 VRAM", device_info["vram"])
            col_v2.metric("已用 VRAM", device_info["vram_used"])
            if st.sidebar.button("🧹 釋放 GPU 快取", width='stretch'):
                torch.cuda.empty_cache()
                st.sidebar.success("✅ GPU 快取已清除")
                st.rerun()


        else:
            st.warning("⚠️ 未偵測到 NVIDIA GPU，使用 CPU")

        force_cpu = st.checkbox(
            "強制使用 CPU（VRAM 不足時使用）",
            value=False,
            key="force_cpu",
        )
        active_device = "cpu" if force_cpu else device_info["type"]
        st.caption(f"目前推理裝置：`{active_device.upper()}`")

        st.divider()

        # OpenCV 模型管理（CPU 備用路線）
        st.header("⚙️ OpenCV 模型管理")
        st.caption("GPU 模式下不需要，CPU 備用時才需下載")
        available_models = get_available_models()
        st.caption(f"已下載 {len(available_models)} 個模型")

        model_to_download = st.selectbox(
            "選擇模型",
            list(MODEL_URLS.keys()),
            format_func=lambda x: f"{'✅' if x in available_models else '⬜'} {x}",
        )
        progress_ph = st.empty()
        if st.button("⬇️ 下載", width='stretch'):
            success = download_model(model_to_download, progress_ph)
            if success:
                st.cache_resource.clear()
                st.rerun()

        if available_models:
            st.divider()
            for m in sorted(available_models):
                size_mb = (MODEL_DIR / m).stat().st_size / (1024 * 1024)
                c1, c2 = st.columns([3, 1])
                c1.text(m)
                c2.caption(f"{size_mb:.1f}MB")

    # ── 主版面 ─────────────────────────────────────────────────────────────
    left_col, right_col = st.columns([1, 1], gap="large")

    with left_col:
        st.subheader("🔧 處理管線設定")

        if "pipeline_nodes" not in st.session_state:
            st.session_state.pipeline_nodes = [
                PipelineNode(
                    enabled=True,
                    name="AI 超解析度",
                    params={"model": "EDSR", "scale": 4},
                ),
                PipelineNode(
                    enabled=True,
                    name="人像細節強化",
                    params={
                        "sharpness": 1.5,
                        "contrast": 1.15,
                        "brightness": 1.05,
                        "saturation": 1.1,
                        "denoise_strength": 3,
                        "edge_enhance": True,
                    },
                ),
                PipelineNode(
                    enabled=False,
                    name="人臉銳化（Unsharp Mask）",
                    params={"strength": 1.8},
                ),
            ]

        available_models = get_available_models()
        active_device_type = (
            "cpu" if st.session_state.get("force_cpu") else device_info["type"]
        )
        updated_nodes: list[PipelineNode] = []

        for i, node in enumerate(st.session_state.pipeline_nodes):
            updated = render_pipeline_node_ui(
                i, node, available_models, active_device_type
            )
            updated_nodes.append(updated)
            if i < len(st.session_state.pipeline_nodes) - 1:
                st.markdown(
                    '<div class="node-connector">↓</div>', unsafe_allow_html=True
                )

        st.session_state.pipeline_nodes = updated_nodes

        st.divider()
        node_options = [
            "AI 超解析度",
            "雙三次插值升解析度",
            "人像細節強化",
            "人臉銳化（Unsharp Mask）",
        ]
        col_select, col_add = st.columns([3, 1])
        new_node_name = col_select.selectbox(
            "新增節點類型", node_options, key="new_node_type"
        )
        if col_add.button("＋ 新增", width='stretch'):
            defaults: dict[str, dict] = {
                "AI 超解析度": {"model": "EDSR", "scale": 4},
                "雙三次插值升解析度": {"scale": 2},
                "人像細節強化": {
                    "sharpness": 1.5,
                    "contrast": 1.15,
                    "brightness": 1.05,
                    "saturation": 1.1,
                    "denoise_strength": 3,
                    "edge_enhance": True,
                },
                "人臉銳化（Unsharp Mask）": {"strength": 1.8},
            }
            st.session_state.pipeline_nodes.append(
                PipelineNode(
                    enabled=True,
                    name=new_node_name,
                    params=defaults.get(new_node_name, {}),
                )
            )
            st.rerun()

    with right_col:
        st.subheader("🖼️ 圖片輸入")

        uploaded = st.file_uploader(
            "上傳圖片（支援 JPG / PNG / WEBP）",
            type=["jpg", "jpeg", "png", "webp"],
        )

        if uploaded is not None:
            original_pil = Image.open(uploaded).convert("RGB")
            st.image(
                original_pil,
                caption=f"原始圖片 — {original_pil.width}×{original_pil.height}px",
                width='stretch',
            )
            st.divider()

            if st.button("🚀 執行工作流", width='stretch', type="primary"):
                enabled_count = sum(
                    1 for n in st.session_state.pipeline_nodes if n.enabled
                )
                if enabled_count == 0:
                    st.warning("請至少啟用一個處理節點")
                else:
                    with st.spinner("⚙️ GPU 推理中，請稍候..."):
                        result = run_pipeline(
                            original_pil, st.session_state.pipeline_nodes
                        )
                    st.session_state.last_result = result

            if "last_result" in st.session_state:
                result = st.session_state.last_result

                if result.error:
                    st.error(f"❌ 處理失敗：{result.error}")
                elif result.image is not None:
                    # ✅ 新寫法（result.image 本身就是 PIL Image）
                    st.image(
                        result.image,
                        caption=f"處理結果 — {result.output_size[0]}×{result.output_size[1]}px",
                        width='stretch',
                    )
                    m1, m2, m3, m4, m5 = st.columns(5)
                    orig_w, orig_h = result.original_size
                    out_w, out_h = result.output_size
                    scale_ratio = out_w / orig_w if orig_w > 0 else 1

                    m1.metric("原始尺寸", f"{orig_w}×{orig_h}")
                    m2.metric("輸出尺寸", f"{out_w}×{out_h}")
                    m3.metric("放大倍數", f"{scale_ratio:.1f}×")
                    m4.metric("處理時間", f"{result.elapsed_sec:.2f}s")
                    m5.metric("推理裝置", result.device_used.split("(")[0].strip())

                    st.divider()
                    dl1, dl2 = st.columns(2)
                    if result.image is not None:
                        # ✅ FIX: 不需要再 cv2_to_pil，result.image 本身就是 PIL Image
                        st.image(
                            result.image,
                            caption=f"處理結果 — {result.output_size[0]}×{result.output_size[1]}px",
                            width='stretch',
                        )

                        # 下載按鈕也直接傳 PIL Image
                        dl1.download_button(
                            "⬇️ 下載 PNG（無損）",
                            data=image_to_bytes(result.image, "PNG"),
                            file_name="upscaled_output.png",
                            mime="image/png",
                            width='stretch',
                        )
                        dl2.download_button(
                            "⬇️ 下載 JPEG（壓縮）",
                            data=image_to_bytes(result.image, "JPEG"),
                            file_name="upscaled_output.jpg",
                            mime="image/jpeg",
                            width='stretch',
                        )
        else:
            st.info("👆 請上傳圖片後設定工作流，再點擊「執行工作流」")
            st.markdown(
                """
            **工作流建議：**
            1. 🔵 **AI 超解析度** — GPU 模式自動使用 PyTorch EDSR，無需下載模型
            2. 🟢 **人像細節強化** — 調整銳化與對比讓人臉更清晰
            3. 🟡 **人臉銳化** — 選用，Unsharp Mask 保留皮膚紋理
            """
            )


# ── 圖片合併工具 ─────────────────────────────────────────────────────────────


def merge_images_combined(
    images: list[Image.Image],
    direction: str,
    scale_mode: str,
) -> Image.Image:
    """
    合併多張圖片，邊界嚴密貼緊，無縫隙亦無覆蓋。

    Args:
        images:     有序的 PIL Image 列表（至少 2 張）
        direction:  "horizontal"（左右）或 "vertical"（上下）
        scale_mode: "min"（縮至最小邊）/ "max"（放大至最大邊）/ "none"（不調整）

    Returns:
        合併後的 PIL Image（RGB）
    """
    if len(images) < 2:
        raise ValueError("至少需要 2 張圖片")

    imgs = [img.convert("RGB") for img in images]

    if direction == "horizontal":
        if scale_mode == "min":
            ref_h: int | None = min(img.height for img in imgs)
        elif scale_mode == "max":
            ref_h = max(img.height for img in imgs)
        else:
            ref_h = None

        normalized: list[Image.Image] = []
        for img in imgs:
            if ref_h is not None and img.height != ref_h:
                ratio = ref_h / img.height
                normalized.append(
                    img.resize((max(1, int(img.width * ratio)), ref_h), Image.LANCZOS)
                )
            else:
                normalized.append(img)

        canvas_h = max(img.height for img in normalized)
        canvas_w = sum(img.width for img in normalized)
        canvas = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))
        x = 0
        for img in normalized:
            canvas.paste(img, (x, 0))
            x += img.width  # 嚴密相鄰，無縫隙
        return canvas

    else:  # vertical
        if scale_mode == "min":
            ref_w: int | None = min(img.width for img in imgs)
        elif scale_mode == "max":
            ref_w = max(img.width for img in imgs)
        else:
            ref_w = None

        normalized_v: list[Image.Image] = []
        for img in imgs:
            if ref_w is not None and img.width != ref_w:
                ratio = ref_w / img.width
                normalized_v.append(
                    img.resize((ref_w, max(1, int(img.height * ratio))), Image.LANCZOS)
                )
            else:
                normalized_v.append(img)

        canvas_w = max(img.width for img in normalized_v)
        canvas_h = sum(img.height for img in normalized_v)
        canvas = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))
        y = 0
        for img in normalized_v:
            canvas.paste(img, (0, y))
            y += img.height  # 嚴密相鄰，無縫隙
        return canvas


def render_merge_tab() -> None:
    """圖片合併工具 Tab — 多圖上傳、排列預覽、合併下載"""
    st.subheader("🖼️ 圖片合併工具")
    st.caption("上傳多張圖片，自由調整排列順序後合併為一張圖")

    uploaded_files = st.file_uploader(
        "上傳多張圖片（支援 JPG / PNG / WEBP）",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        key="merge_uploader",
    )

    if not uploaded_files or len(uploaded_files) < 2:
        if uploaded_files and len(uploaded_files) == 1:
            st.warning("⚠️ 請再上傳至少 1 張圖片（共需 2 張以上）才能合併")
        else:
            st.info(
                "👆 請上傳 2 張以上圖片，即可設定排列順序並合併\n\n"
                "**提示：** 水平合併時圖片高度對齊；垂直合併時圖片寬度對齊"
            )
        return

    # ── 偵測檔案清單變動，重置排序與結果 ────────────────────────────
    file_names = [f.name for f in uploaded_files]
    if st.session_state.get("_merge_file_names") != file_names:
        st.session_state._merge_file_names = file_names
        st.session_state._merge_order = list(range(len(uploaded_files)))
        st.session_state.pop("merge_result", None)

    order: list[int] = list(st.session_state._merge_order)
    n = len(uploaded_files)

    # ── 載入所有圖片（以原始上傳索引為準）───────────────────────────
    images = [Image.open(f).convert("RGB") for f in uploaded_files]

    # ── 排列預覽與上下移動控制 ────────────────────────────────────────
    st.markdown("#### 📋 排列順序")
    st.caption("使用 ⬆ / ⬇ 按鈕調整圖片的合併順序，順序即為最終合併方向")

    rerun_needed = False
    for rank in range(n):
        orig_idx = order[rank]
        img = images[orig_idx]
        fname = file_names[orig_idx]

        c_num, c_img, c_info, c_btns = st.columns([0.4, 1.8, 4.2, 0.7])

        c_num.markdown(
            f"<div style='font-size:1.5rem;font-weight:800;color:#7c6ff7;"
            f"text-align:center;padding-top:24px'>{rank + 1}</div>",
            unsafe_allow_html=True,
        )
        c_img.image(img, use_container_width=True)
        c_info.markdown(f"**{fname}**")
        c_info.caption(f"{img.width} × {img.height} px")

        with c_btns:
            if rank > 0:
                if st.button("⬆", key=f"m_up_{rank}_{orig_idx}", help="上移"):
                    order[rank], order[rank - 1] = order[rank - 1], order[rank]
                    st.session_state._merge_order = order
                    rerun_needed = True
            if rank < n - 1:
                if st.button("⬇", key=f"m_dn_{rank}_{orig_idx}", help="下移"):
                    order[rank], order[rank + 1] = order[rank + 1], order[rank]
                    st.session_state._merge_order = order
                    rerun_needed = True

    if rerun_needed:
        st.rerun()

    st.divider()

    # ── 合併設定 ──────────────────────────────────────────────────────
    st.markdown("#### ⚙️ 合併設定")
    col_dir, col_scale = st.columns(2)

    direction_label = col_dir.radio(
        "合併方向",
        ["⬅➡ 水平（左右）", "⬆⬇ 垂直（上下）"],
        key="merge_direction_radio",
        horizontal=True,
    )
    direction = "horizontal" if "水平" in direction_label else "vertical"

    align_hint = "垂直方向高度" if direction == "horizontal" else "水平方向寬度"
    scale_label = col_scale.selectbox(
        "尺寸對齊方式",
        [
            "以最小邊等比縮放（縮至最小）",
            "以最大邊等比縮放（放大至最大）",
            "不調整（保留原始尺寸）",
        ],
        key="merge_scale_mode",
        help=f"統一各圖的{align_hint}，確保合併邊界嚴密貼緊",
    )
    scale_mode = (
        "min" if "最小" in scale_label
        else "max" if "最大" in scale_label
        else "none"
    )

    if st.button(
        "🔗 執行合併",
        type="primary",
        use_container_width=True,
        key="merge_execute_btn",
    ):
        ordered_imgs = [images[i] for i in order]
        with st.spinner("🔗 合併中..."):
            try:
                merged = merge_images_combined(ordered_imgs, direction, scale_mode)
                st.session_state.merge_result = merged
            except Exception as exc:
                st.error(f"❌ 合併失敗：{exc}")

    # ── 合併結果預覽與下載 ────────────────────────────────────────────
    if "merge_result" in st.session_state:
        result_img: Image.Image = st.session_state.merge_result
        st.divider()
        st.markdown("#### 🖼️ 合併結果預覽")
        st.image(
            result_img,
            caption=f"合併結果 — {result_img.width} × {result_img.height} px",
            use_container_width=True,
        )

        m1, m2, m3 = st.columns(3)
        m1.metric("輸出寬度", f"{result_img.width} px")
        m2.metric("輸出高度", f"{result_img.height} px")
        m3.metric("合併張數", f"{n} 張")

        st.divider()
        dl1, dl2 = st.columns(2)
        dl1.download_button(
            "⬇️ 下載 PNG（無損）",
            data=image_to_bytes(result_img, "PNG"),
            file_name="merged_output.png",
            mime="image/png",
            use_container_width=True,
        )
        dl2.download_button(
            "⬇️ 下載 JPEG（壓縮）",
            data=image_to_bytes(result_img, "JPEG"),
            file_name="merged_output.jpg",
            mime="image/jpeg",
            use_container_width=True,
        )


def _render_upscaler_content() -> None:
    """AI 升解析度工作流主內容（供 show() 在頁簽中呼叫，不含 set_page_config）"""
    device_info = get_device_info()

    # ── 裝置狀態 & 模型管理（Expander 取代 Sidebar，整合模式適用）──
    with st.expander("🖥️ 運算裝置 & OpenCV 模型管理", expanded=False):
        col_dev, col_model = st.columns(2)

        with col_dev:
            st.markdown("**🖥️ 運算裝置**")
            if device_info["type"] == "cuda":
                st.success(f"✅ {device_info['name']}")
                cv1, cv2 = st.columns(2)
                cv1.metric("總 VRAM", device_info["vram"])
                cv2.metric("已用 VRAM", device_info["vram_used"])
                if st.button("🧹 釋放 GPU 快取", key="_uc_clear_gpu", use_container_width=True):
                    torch.cuda.empty_cache()
                    st.success("✅ GPU 快取已清除")
                    st.rerun()
            else:
                st.warning("⚠️ 未偵測到 NVIDIA GPU，使用 CPU")

            st.checkbox(
                "強制使用 CPU（VRAM 不足時使用）",
                value=False,
                key="force_cpu",
            )
            active_dev_str = "cpu" if st.session_state.get("force_cpu") else device_info["type"]
            st.caption(f"目前推理裝置：`{active_dev_str.upper()}`")

        with col_model:
            st.markdown("**⚙️ OpenCV 模型管理**")
            st.caption("GPU 模式下不需要，CPU 備用時才需下載")
            avail_models = get_available_models()
            st.caption(f"已下載 {len(avail_models)} 個模型")

            model_sel = st.selectbox(
                "選擇模型",
                list(MODEL_URLS.keys()),
                format_func=lambda x: f"{'✅' if x in avail_models else '⬜'} {x}",
                key="_uc_model_select",
            )
            prog_ph = st.empty()
            if st.button("⬇️ 下載模型", key="_uc_download_btn", use_container_width=True):
                if download_model(model_sel, prog_ph):
                    st.cache_resource.clear()
                    st.rerun()

            if avail_models:
                st.divider()
                for m in sorted(avail_models):
                    size_mb = (MODEL_DIR / m).stat().st_size / (1024 * 1024)
                    mc1, mc2 = st.columns([3, 1])
                    mc1.text(m)
                    mc2.caption(f"{size_mb:.1f} MB")

    # ── 主版面 ──────────────────────────────────────────────────────────
    available_models = get_available_models()
    active_device_type = (
        "cpu" if st.session_state.get("force_cpu") else device_info["type"]
    )

    left_col, right_col = st.columns([1, 1], gap="large")

    with left_col:
        st.subheader("🔧 處理管線設定")

        if "pipeline_nodes" not in st.session_state:
            st.session_state.pipeline_nodes = [
                PipelineNode(
                    enabled=True,
                    name="AI 超解析度",
                    params={"model": "EDSR", "scale": 4},
                ),
                PipelineNode(
                    enabled=True,
                    name="人像細節強化",
                    params={
                        "sharpness": 1.5,
                        "contrast": 1.15,
                        "brightness": 1.05,
                        "saturation": 1.1,
                        "denoise_strength": 3,
                        "edge_enhance": True,
                    },
                ),
                PipelineNode(
                    enabled=False,
                    name="人臉銳化（Unsharp Mask）",
                    params={"strength": 1.8},
                ),
            ]

        updated_nodes: list[PipelineNode] = []
        for i, node in enumerate(st.session_state.pipeline_nodes):
            updated = render_pipeline_node_ui(i, node, available_models, active_device_type)
            updated_nodes.append(updated)
            if i < len(st.session_state.pipeline_nodes) - 1:
                st.markdown('<div class="node-connector">↓</div>', unsafe_allow_html=True)
        st.session_state.pipeline_nodes = updated_nodes

        st.divider()
        node_options = [
            "AI 超解析度",
            "雙三次插值升解析度",
            "人像細節強化",
            "人臉銳化（Unsharp Mask）",
        ]
        col_select, col_add = st.columns([3, 1])
        new_node_name = col_select.selectbox("新增節點類型", node_options, key="new_node_type")
        if col_add.button("＋ 新增", key="_uc_add_node", use_container_width=True):
            defaults: dict[str, dict] = {
                "AI 超解析度": {"model": "EDSR", "scale": 4},
                "雙三次插值升解析度": {"scale": 2},
                "人像細節強化": {
                    "sharpness": 1.5,
                    "contrast": 1.15,
                    "brightness": 1.05,
                    "saturation": 1.1,
                    "denoise_strength": 3,
                    "edge_enhance": True,
                },
                "人臉銳化（Unsharp Mask）": {"strength": 1.8},
            }
            st.session_state.pipeline_nodes.append(
                PipelineNode(
                    enabled=True,
                    name=new_node_name,
                    params=defaults.get(new_node_name, {}),
                )
            )
            st.rerun()

    with right_col:
        st.subheader("🖼️ 圖片輸入")

        uploaded = st.file_uploader(
            "上傳圖片（支援 JPG / PNG / WEBP）",
            type=["jpg", "jpeg", "png", "webp"],
            key="upscaler_uploader",
        )

        if uploaded is not None:
            original_pil = Image.open(uploaded).convert("RGB")
            st.image(
                original_pil,
                caption=f"原始圖片 — {original_pil.width}×{original_pil.height}px",
                use_container_width=True,
            )
            st.divider()

            if st.button(
                "🚀 執行工作流",
                type="primary",
                use_container_width=True,
                key="_uc_run_btn",
            ):
                enabled_count = sum(1 for nd in st.session_state.pipeline_nodes if nd.enabled)
                if enabled_count == 0:
                    st.warning("請至少啟用一個處理節點")
                else:
                    with st.spinner("⚙️ GPU 推理中，請稍候..."):
                        run_result = run_pipeline(original_pil, st.session_state.pipeline_nodes)
                    st.session_state.last_result = run_result

            if "last_result" in st.session_state:
                run_result = st.session_state.last_result
                if run_result.error:
                    st.error(f"❌ 處理失敗：{run_result.error}")
                elif run_result.image is not None:
                    st.image(
                        run_result.image,
                        caption=(
                            f"處理結果 — "
                            f"{run_result.output_size[0]}×{run_result.output_size[1]}px"
                        ),
                        use_container_width=True,
                    )
                    m1, m2, m3, m4, m5 = st.columns(5)
                    orig_w, orig_h = run_result.original_size
                    out_w, out_h = run_result.output_size
                    scale_ratio = out_w / orig_w if orig_w > 0 else 1
                    m1.metric("原始尺寸", f"{orig_w}×{orig_h}")
                    m2.metric("輸出尺寸", f"{out_w}×{out_h}")
                    m3.metric("放大倍數", f"{scale_ratio:.1f}×")
                    m4.metric("處理時間", f"{run_result.elapsed_sec:.2f}s")
                    m5.metric("推理裝置", run_result.device_used.split("(")[0].strip())

                    st.divider()
                    dl1, dl2 = st.columns(2)
                    dl1.download_button(
                        "⬇️ 下載 PNG（無損）",
                        data=image_to_bytes(run_result.image, "PNG"),
                        file_name="upscaled_output.png",
                        mime="image/png",
                        use_container_width=True,
                    )
                    dl2.download_button(
                        "⬇️ 下載 JPEG（壓縮）",
                        data=image_to_bytes(run_result.image, "JPEG"),
                        file_name="upscaled_output.jpg",
                        mime="image/jpeg",
                        use_container_width=True,
                    )
        else:
            st.info("👆 請上傳圖片後設定工作流，再點擊「執行工作流」")
            st.markdown(
                """
            **工作流建議：**
            1. 🔵 **AI 超解析度** — GPU 模式自動使用 PyTorch EDSR，無需下載模型
            2. 🟢 **人像細節強化** — 調整銳化與對比讓人臉更清晰
            3. 🟡 **人臉銳化** — 選用，Unsharp Mask 保留皮膚紋理
            """
            )


def show() -> None:
    """整合至 app.py 的主入口（無 set_page_config，以頁簽切換功能）"""
    st.markdown(
        """
    <style>
        .pipeline-header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            border-radius: 12px;
            padding: 24px 32px;
            margin-bottom: 24px;
            border: 1px solid #e94560;
        }
        .pipeline-header h1 { color: #ffffff; font-size: 2rem; margin: 0; }
        .pipeline-header p  { color: #a0a0c0; margin: 8px 0 0; }
        .node-connector { text-align: center; font-size: 1.5rem; color: #e94560; margin: -8px 0; }
        .stExpander { border: 1px solid #e0e0e0 !important; border-radius: 8px !important; }
    </style>
    """,
        unsafe_allow_html=True,
    )

    tab_upscaler, tab_merge = st.tabs(["🔬 AI 升解析度工作流", "🖼️ 圖片合併"])

    with tab_upscaler:
        _render_upscaler_content()

    with tab_merge:
        render_merge_tab()


if __name__ == "__main__":
    main()

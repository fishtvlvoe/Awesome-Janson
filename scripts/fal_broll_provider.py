#!/usr/bin/env python3
"""fal.ai 的可選 B-roll provider。

此模組只在短影音明確選擇 ``fal-image``／``fal-video`` 並帶有
``--allow-remote-broll`` 時才會呼叫遠端。未設定 key、模型或遠端失敗時，
呼叫端應回退到既有的本地 B-roll；本模組不會列印憑證、簽名媒體 URL 或完整
遠端回應。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from talking_head_adapter import anim_lib


W, H = 1080, 1920
QUEUE_BASE_URL = "https://queue.fal.run"
DEFAULT_IMAGE_MODEL = "fal-ai/flux/schnell"
DEFAULT_TIMEOUT_SECONDS = 180
MAX_TIMEOUT_SECONDS = 600
POLL_INTERVAL_SECONDS = 1.0
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_IMAGE_BYTES = 32 * 1024 * 1024
MAX_VIDEO_BYTES = 300 * 1024 * 1024
MAX_DECODED_IMAGE_PIXELS = 25_000_000
MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,200}$")
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9-]{1,200}$")
DOTENV_ASSIGNMENT_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
SENSITIVE_PROMPT_TOKEN_RE = re.compile(
    r"https?://\S+|www\.\S+|[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
    re.IGNORECASE,
)
ENV_KEYS = frozenset(
    {
        "FAL_KEY",
        "FAL_API_KEY",
        "AWJ_FAL_IMAGE_MODEL",
        "AWJ_FAL_VIDEO_MODEL",
        "AWJ_FAL_IMAGE_INPUT_JSON",
        "AWJ_FAL_VIDEO_INPUT_JSON",
        "AWJ_FAL_TIMEOUT_SECONDS",
    }
)


class FalBrollError(RuntimeError):
    """預期可回退的 fal provider 錯誤，訊息一律不包含機密內容。"""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class FalConfig:
    mode: str
    model: str
    api_key: str = field(repr=False)
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    input_overrides: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class GeneratedMedia:
    kind: str
    model: str
    cache_path: Path
    request_id: str | None
    cache_hit: bool


def _clean_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _dotenv_values(path: Path) -> dict[str, str]:
    """讀取限定白名單的 dotenv 欄位；不執行 shell 語法或展開變數。"""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FalBrollError("fal-env-file-unreadable") from exc
    values: dict[str, str] = {}
    for raw in content.splitlines():
        match = DOTENV_ASSIGNMENT_RE.match(raw)
        if not match or match.group(1) not in ENV_KEYS:
            continue
        values[match.group(1)] = _clean_env_value(match.group(2))
    return values


def _load_fal_values(
    env: Mapping[str, str] | None = None,
    env_file: Path | None = None,
) -> dict[str, str]:
    """載入 fal 設定，程序環境變數優先於本機 dotenv fallback。"""
    runtime_env = os.environ if env is None else env
    candidates: list[Path]
    if env_file is not None:
        candidates = [Path(env_file)]
    else:
        root = Path(__file__).resolve().parents[1]
        candidates = [Path.cwd() / ".env", root / ".env", root.parent / ".env"]

    values: dict[str, str] = {}
    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate
        if resolved in seen or not candidate.is_file():
            continue
        seen.add(resolved)
        for name, value in _dotenv_values(candidate).items():
            if value and name not in values:
                values[name] = value

    for name in ENV_KEYS:
        value = str(runtime_env.get(name, "") or "").strip()
        if value:
            values[name] = value
    return values


def _validate_model_id(model: str) -> str:
    model = str(model or "").strip()
    if (
        not MODEL_ID_RE.fullmatch(model)
        or model.startswith("/")
        or "//" in model
        or any(part in {"", ".", ".."} for part in model.split("/"))
    ):
        raise FalBrollError("fal-model-id-invalid")
    return model


def _parse_input_overrides(value: str, mode: str) -> dict[str, Any]:
    if not value:
        return {}
    if len(value) > 16_000:
        raise FalBrollError(f"fal-{mode}-input-json-too-large")
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise FalBrollError(f"fal-{mode}-input-json-invalid") from exc
    if not isinstance(payload, dict):
        raise FalBrollError(f"fal-{mode}-input-json-invalid")
    return payload


def _timeout_value(value: str | int | None) -> int:
    if value in (None, ""):
        return DEFAULT_TIMEOUT_SECONDS
    try:
        timeout = int(value)
    except (TypeError, ValueError) as exc:
        raise FalBrollError("fal-timeout-invalid") from exc
    if timeout < 10 or timeout > MAX_TIMEOUT_SECONDS:
        raise FalBrollError("fal-timeout-out-of-range")
    return timeout


def resolve_fal_config(
    mode: str,
    *,
    allow_remote: bool,
    image_model: str | None = None,
    video_model: str | None = None,
    timeout_seconds: int | None = None,
    env: Mapping[str, str] | None = None,
    env_file: Path | None = None,
) -> FalConfig:
    """建立一次性遠端設定；不回傳或輸出設定來源的機密內容。"""
    if mode not in {"image", "video"}:
        raise FalBrollError("fal-mode-invalid")
    if not allow_remote:
        raise FalBrollError("remote-opt-in-required")

    values = _load_fal_values(env=env, env_file=env_file)
    # FAL_KEY 與 FAL_API_KEY 是同義 alias；程序環境的任一 alias 都必須勝過 dotenv 的另一個 alias。
    runtime_env = os.environ if env is None else env
    runtime_key = str(runtime_env.get("FAL_KEY") or runtime_env.get("FAL_API_KEY") or "").strip()
    api_key = runtime_key or values.get("FAL_KEY") or values.get("FAL_API_KEY")
    if not api_key:
        raise FalBrollError("fal-key-not-configured")

    if mode == "image":
        selected_model = image_model or values.get("AWJ_FAL_IMAGE_MODEL") or DEFAULT_IMAGE_MODEL
        overrides = _parse_input_overrides(values.get("AWJ_FAL_IMAGE_INPUT_JSON", ""), mode)
    else:
        selected_model = video_model or values.get("AWJ_FAL_VIDEO_MODEL")
        overrides = _parse_input_overrides(values.get("AWJ_FAL_VIDEO_INPUT_JSON", ""), mode)
    if not selected_model:
        raise FalBrollError(f"fal-{mode}-model-not-configured")

    return FalConfig(
        mode=mode,
        model=_validate_model_id(selected_model),
        api_key=api_key,
        timeout_seconds=_timeout_value(timeout_seconds if timeout_seconds is not None else values.get("AWJ_FAL_TIMEOUT_SECONDS")),
        input_overrides=overrides,
    )


def _source_phrase(value: object, limit: int = 150) -> str:
    text = " ".join(str(value or "").split())
    text = SENSITIVE_PROMPT_TOKEN_RE.sub("[link omitted]", text)
    return text[:limit].strip(" ，、；;。")


def build_broll_prompt(params: Mapping[str, Any]) -> str:
    """只使用既有字幕事件中的內容，避免外部模型補造客戶成果或數字。"""
    fragments = [_source_phrase(params.get("headline")), _source_phrase(params.get("body"))]
    topic = "；".join(part for part in fragments if part) or "the spoken topic in this short video"
    return (
        "Create a vertical 9:16 editorial B-roll visual that illustrates only this spoken topic: "
        f"{topic}. "
        "Use a cinematic, abstract documentary style. Do not add readable text, subtitles, logos, "
        "watermarks, statistics, business results, or identifiable real people. Keep the lower third visually "
        "simple because subtitles will be added later."
    )


def _image_arguments(config: FalConfig, prompt: str) -> dict[str, Any]:
    model = config.model.lower()
    if "nano-banana" in model:
        arguments: dict[str, Any] = {
            "prompt": prompt,
            "aspect_ratio": "9:16",
            "resolution": "1K",
            "output_format": "jpeg",
            "limit_generations": True,
        }
    elif model == DEFAULT_IMAGE_MODEL or model.startswith("fal-ai/flux/"):
        arguments = {
            "prompt": prompt,
            "image_size": "portrait_16_9",
            "num_images": 1,
            "output_format": "jpeg",
            "enable_safety_checker": True,
        }
    else:
        # 任意 Marketplace model 至少可收 prompt；其他欄位由本機 JSON override 補上。
        arguments = {"prompt": prompt}
    arguments.update(config.input_overrides)
    arguments["prompt"] = prompt
    return arguments


def _video_duration(seconds: float) -> str:
    # Kling v3 等主流文字轉影片端點可接受 3～15 秒整數；短 B-roll 不讓單段過長。
    return str(max(3, min(6, int(round(seconds)))))


def _video_arguments(config: FalConfig, prompt: str, duration: float) -> dict[str, Any]:
    model = config.model.lower()
    if "kling-video/v3" in model:
        arguments: dict[str, Any] = {
            "prompt": prompt,
            "duration": _video_duration(duration),
            "aspect_ratio": "9:16",
            "generate_audio": False,
            "negative_prompt": "readable text, logo, watermark, distorted face, low quality",
        }
    else:
        arguments = {"prompt": prompt}
    arguments.update(config.input_overrides)
    arguments["prompt"] = prompt
    # 外部 B-roll 的音軌永遠不用，避免覆蓋原始口白；支援該欄位的模型一律關閉。
    if "generate_audio" in arguments:
        arguments["generate_audio"] = False
    return arguments


def _json_request(
    method: str,
    url: str,
    *,
    api_key: str,
    payload: Mapping[str, Any] | None = None,
    timeout_seconds: int,
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {
        "Authorization": f"Key {api_key}",
        "Accept": "application/json",
        "User-Agent": "Awesome-Janson/fal-broll-provider",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=min(timeout_seconds, 60)) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        raise FalBrollError(f"fal-http-{exc.code}") from exc
    except (TimeoutError, URLError, OSError) as exc:
        raise FalBrollError("fal-network-error") from exc
    if len(raw) > MAX_RESPONSE_BYTES:
        raise FalBrollError("fal-response-too-large")
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FalBrollError("fal-response-invalid") from exc
    if not isinstance(decoded, dict):
        raise FalBrollError("fal-response-invalid")
    return decoded


def _cancel_queue_request(config: FalConfig, endpoint: str, request_id: str) -> None:
    """盡力取消尚未完成的工作，避免本地 fallback 後仍發生延遲計費。"""
    try:
        _json_request(
            "PUT",
            f"{endpoint}/requests/{request_id}/cancel",
            api_key=config.api_key,
            timeout_seconds=config.timeout_seconds,
        )
    except FalBrollError:
        # 取消可能已和遠端完成／失敗競速；原始錯誤才是使用者應看到的回退原因。
        pass


def _queue_result(config: FalConfig, arguments: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    endpoint = f"{QUEUE_BASE_URL}/{config.model}"
    submitted = _json_request(
        "POST",
        endpoint,
        api_key=config.api_key,
        payload=arguments,
        timeout_seconds=config.timeout_seconds,
    )
    request_id = str(submitted.get("request_id", "")).strip()
    if not REQUEST_ID_RE.fullmatch(request_id):
        raise FalBrollError("fal-request-id-invalid")

    completed = False
    try:
        deadline = time.monotonic() + config.timeout_seconds
        status_url = f"{endpoint}/requests/{request_id}/status"
        while True:
            status_payload = _json_request(
                "GET",
                status_url,
                api_key=config.api_key,
                timeout_seconds=config.timeout_seconds,
            )
            status = str(status_payload.get("status", "")).upper()
            if status == "COMPLETED":
                completed = True
                break
            if status in {"FAILED", "CANCELLED", "ERROR"}:
                raise FalBrollError("fal-request-failed")
            if status not in {"IN_QUEUE", "IN_PROGRESS", "QUEUED"}:
                raise FalBrollError("fal-request-status-invalid")
            if time.monotonic() >= deadline:
                raise FalBrollError("fal-request-timeout")
            time.sleep(POLL_INTERVAL_SECONDS)

        result = _json_request(
            "GET",
            f"{endpoint}/requests/{request_id}",
            api_key=config.api_key,
            timeout_seconds=config.timeout_seconds,
        )
        return request_id, result
    except FalBrollError:
        if not completed:
            _cancel_queue_request(config, endpoint, request_id)
        raise


def _valid_media_url(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 4096:
        return None
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        return None
    return value


def _entry_url(value: object) -> str | None:
    if not isinstance(value, Mapping):
        return None
    for name in ("url", "file_url", "download_url"):
        valid = _valid_media_url(value.get(name))
        if valid:
            return valid
    return None


def _media_url(payload: Mapping[str, Any], kind: str) -> str:
    if kind == "image":
        images = payload.get("images")
        if isinstance(images, list):
            for image in images:
                valid = _entry_url(image)
                if valid:
                    return valid
        valid = _entry_url(payload.get("image"))
    else:
        valid = _entry_url(payload.get("video"))
        if not valid and isinstance(payload.get("videos"), list):
            valid = next((_entry_url(item) for item in payload["videos"] if _entry_url(item)), None)
    if valid:
        return valid
    raise FalBrollError(f"fal-{kind}-output-missing")


def _media_extension(url: str, kind: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    allowed = {".png", ".jpg", ".jpeg", ".webp"} if kind == "image" else {".mp4", ".mov", ".webm"}
    if suffix in allowed:
        return suffix
    return ".jpg" if kind == "image" else ".mp4"


def _download_media(url: str, destination: Path, kind: str, timeout_seconds: int) -> None:
    """下載 fal 回傳媒體；刻意不把 Authorization header 傳到簽名下載 URL。"""
    max_bytes = MAX_IMAGE_BYTES if kind == "image" else MAX_VIDEO_BYTES
    request = Request(url, headers={"User-Agent": "Awesome-Janson/fal-broll-provider"})
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with urlopen(request, timeout=min(timeout_seconds, 60)) as response:
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > max_bytes:
                raise FalBrollError(f"fal-{kind}-download-too-large")
            with tempfile.NamedTemporaryFile(delete=False, dir=destination.parent, prefix=".fal-download-") as handle:
                temp_path = Path(handle.name)
                total = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise FalBrollError(f"fal-{kind}-download-too-large")
                    handle.write(chunk)
        if temp_path is None or temp_path.stat().st_size == 0:
            raise FalBrollError(f"fal-{kind}-download-empty")
        os.replace(temp_path, destination)
        temp_path = None
    except FalBrollError:
        raise
    except HTTPError as exc:
        raise FalBrollError(f"fal-media-http-{exc.code}") from exc
    except (TimeoutError, URLError, OSError, ValueError) as exc:
        raise FalBrollError(f"fal-{kind}-download-failed") from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _cache_stem(config: FalConfig, arguments: Mapping[str, Any]) -> str:
    serialized = json.dumps(
        {"kind": config.mode, "model": config.model, "arguments": arguments},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:24]


def generate_media(
    config: FalConfig,
    params: Mapping[str, Any],
    duration: float,
    cache_dir: Path,
) -> GeneratedMedia:
    """送出 queue 工作並下載為輸出目錄專屬 cache；不保留遠端 URL。"""
    prompt = build_broll_prompt(params)
    arguments = _image_arguments(config, prompt) if config.mode == "image" else _video_arguments(config, prompt, duration)
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        stem = _cache_stem(config, arguments)

        # 副檔名尚未知道時，檢查同一 cache key 已有的合法媒體即可重用。
        for suffix in ((".png", ".jpg", ".jpeg", ".webp") if config.mode == "image" else (".mp4", ".mov", ".webm")):
            cached = cache_dir / f"{config.mode}-{stem}{suffix}"
            if cached.is_file() and cached.stat().st_size > 0:
                return GeneratedMedia(config.mode, config.model, cached, None, True)
    except OSError as exc:
        raise FalBrollError("fal-cache-unavailable") from exc

    request_id, payload = _queue_result(config, arguments)
    remote_url = _media_url(payload, config.mode)
    destination = cache_dir / f"{config.mode}-{stem}{_media_extension(remote_url, config.mode)}"
    _download_media(remote_url, destination, config.mode, config.timeout_seconds)
    return GeneratedMedia(config.mode, config.model, destination, request_id, False)


def _cover(image: Image.Image, width: int, height: int, zoom: float = 1.0) -> Image.Image:
    ratio = max(width / image.width, height / image.height) * zoom
    resized = image.resize((max(1, round(image.width * ratio)), max(1, round(image.height * ratio))), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - width) // 2)
    top = max(0, (resized.height - height) // 2)
    return resized.crop((left, top, left + width, top + height))


def _contain(image: Image.Image, width: int, height: int, zoom: float = 1.0) -> Image.Image:
    ratio = min(width / image.width, height / image.height) * zoom
    return image.resize((max(1, round(image.width * ratio)), max(1, round(image.height * ratio))), Image.Resampling.LANCZOS)


def _fade_opacity(local_time: float, duration: float) -> float:
    intro = max(0.0, min(1.0, local_time / 0.45))
    outro = max(0.0, min(1.0, (duration - local_time) / 0.38))
    return min(1.0, intro * outro)


def _compose_frame(source: Image.Image, progress: float, opacity: float) -> Image.Image:
    source = source.convert("RGB")
    background = _cover(source, W, H, 1.06)
    background = background.filter(ImageFilter.GaussianBlur(radius=22))
    background = ImageEnhance.Brightness(background).enhance(0.40).convert("RGBA")
    canvas = background

    foreground = _contain(source, 940, 1290, 1.0 + 0.035 * progress).convert("RGBA")
    x = (W - foreground.width) // 2
    y = 300 + max(0, (1190 - foreground.height) // 2)
    mask = Image.new("L", foreground.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, foreground.width - 1, foreground.height - 1], radius=42, fill=255)
    canvas.paste(foreground, (x, y), mask)

    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle([74, 222, 468, 286], radius=22, fill=(17, 34, 39, 222), outline=(20, 200, 190, 190), width=3)
    label_font = anim_lib.F("B", 25)
    draw.text((104, 240), "AI 情境示範 · fal.ai", font=label_font, fill=(255, 255, 255, 238))
    draw.rounded_rectangle([x - 3, y - 3, x + foreground.width + 2, y + foreground.height + 2], radius=44, outline=(20, 200, 190, 180), width=5)
    canvas.putalpha(int(255 * max(0.0, min(1.0, opacity))))
    return canvas


def _load_image(path: Path) -> Image.Image:
    try:
        # Pillow 對超大圖通常只發 warning；將它升級為例外，避免解碼時耗盡記憶體。
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                if image.width * image.height > MAX_DECODED_IMAGE_PIXELS:
                    raise FalBrollError("fal-image-media-too-large")
                return ImageOps.exif_transpose(image).convert("RGB").copy()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning, OSError, ValueError) as exc:
        raise FalBrollError("fal-image-media-invalid") from exc


def _write_composed_frames(
    sources: list[Path] | tuple[Path, ...],
    duration: float,
    output_dir: Path,
    fps: int,
    *,
    cache_sources: bool = True,
) -> int:
    """輸出 overlay frames；影片來源逐格解碼，避免累積數 GB 的 RGB frame cache。"""
    if not sources:
        raise FalBrollError("fal-media-frames-missing")
    output_dir.mkdir(parents=True, exist_ok=True)
    frame_count = max(1, int(round(duration * fps)))
    loaded: dict[Path, Image.Image] = {}
    try:
        for index in range(frame_count):
            source_path = sources[index % len(sources)]
            source = loaded.get(source_path) if cache_sources else None
            if source is None:
                source = _load_image(source_path)
                if cache_sources:
                    loaded[source_path] = source
            try:
                local = index / fps
                frame = _compose_frame(
                    source,
                    min(1.0, local / max(duration, 0.1)),
                    _fade_opacity(local, duration),
                )
                try:
                    frame.save(output_dir / f"ov_{index:04d}.png")
                finally:
                    frame.close()
            finally:
                if not cache_sources:
                    source.close()
    finally:
        for image in loaded.values():
            image.close()
    return frame_count


def _video_source_frames(media_path: Path, frame_count: int, fps: int, output_dir: Path) -> list[Path]:
    source_dir = Path(tempfile.mkdtemp(prefix=".fal-video-", dir=output_dir.parent))
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-stream_loop",
                "-1",
                "-i",
                str(media_path),
                "-an",
                "-vf",
                f"fps={fps}",
                "-frames:v",
                str(frame_count),
                str(source_dir / "source_%05d.png"),
            ],
            check=True,
        )
        frames = sorted(source_dir.glob("source_*.png"))
        if len(frames) < frame_count:
            raise FalBrollError("fal-video-frames-incomplete")
        # 呼叫端要在完成組圖前保留 source_dir；以 tuple path 回傳給 finally 管理。
        return frames
    except FalBrollError:
        shutil.rmtree(source_dir, ignore_errors=True)
        raise
    except (OSError, subprocess.CalledProcessError) as exc:
        shutil.rmtree(source_dir, ignore_errors=True)
        raise FalBrollError("fal-video-frame-extract-failed") from exc


def _render_image_media(media_path: Path, duration: float, output_dir: Path, fps: int) -> int:
    return _write_composed_frames([media_path], duration, output_dir, fps)


def _render_video_media(media_path: Path, duration: float, output_dir: Path, fps: int) -> int:
    frame_count = max(1, int(round(duration * fps)))
    source_dir: Path | None = None
    try:
        frames = _video_source_frames(media_path, frame_count, fps, output_dir)
        source_dir = frames[0].parent
        return _write_composed_frames(frames[:frame_count], duration, output_dir, fps, cache_sources=False)
    finally:
        if source_dir is not None:
            shutil.rmtree(source_dir, ignore_errors=True)


def render_fal_broll(
    config: FalConfig,
    params: Mapping[str, Any],
    duration: float,
    output_dir: Path,
    *,
    fps: int = 30,
    cache_dir: Path | None = None,
) -> dict[str, Any]:
    """產生既有 overlay contract 的 PNG 序列，回傳可安全寫入 manifest 的 metadata。"""
    if duration <= 0 or fps <= 0:
        raise FalBrollError("fal-render-timing-invalid")
    media = generate_media(config, params, duration, cache_dir or output_dir.parent / ".fal-cache")
    try:
        frame_count = (
            _render_image_media(media.cache_path, duration, output_dir, fps)
            if media.kind == "image"
            else _render_video_media(media.cache_path, duration, output_dir, fps)
        )
    except FalBrollError:
        raise
    except (MemoryError, OSError, ValueError) as exc:
        raise FalBrollError("fal-media-render-failed") from exc
    return {
        "provider": f"fal-{media.kind}",
        "model": media.model,
        "media_kind": media.kind,
        "request_id": media.request_id,
        "cache_hit": media.cache_hit,
        "frame_count": frame_count,
    }

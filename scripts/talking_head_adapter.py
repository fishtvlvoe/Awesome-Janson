#!/usr/bin/env python3
"""把 talking-head-video-cut 的動畫元件接到剪神時間軸。

上游引擎用 SPANS/LINES/ANIM 設定檔；剪神不複製那套設定檔，而是把
semantic_edit.json 的字幕 cue 轉成安全的 checklist／stamp 動畫事件。
"""
from __future__ import annotations

import math
import re
import shutil
import subprocess
import sys
from pathlib import Path


MAX_UNBROKEN_ASCII_EVENT_CHARS = 30


UPSTREAM_ANIM_DIR = (
	Path(__file__).resolve().parents[1]
	/ "integrations"
	/ "talking-head-video-cut"
	/ "scripts"
)
if str(UPSTREAM_ANIM_DIR) not in sys.path:
	sys.path.insert(0, str(UPSTREAM_ANIM_DIR))

import anim_lib  # noqa: E402
from subtitle_layout import ASCII_TOKEN_RE, mixed_text_tokens  # noqa: E402


def _clean(value: object) -> str:
	return " ".join(str(value or "").replace(r"\N", " ").split())


def _truncate_ascii_token(token: str) -> str:
	"""極長 URL／專名只在 token 尾端縮略，不留下 ``https:…`` 這類殘片。"""
	if len(token) <= MAX_UNBROKEN_ASCII_EVENT_CHARS:
		return token
	return token[: MAX_UNBROKEN_ASCII_EVENT_CHARS - 1] + "…"


def _shorten(value: object, limit: int = 18) -> str:
	text = _clean(value)
	if len(text) <= limit:
		return text
	visible = ""
	for token in mixed_text_tokens(text):
		candidate = visible + token
		if len(candidate) <= limit - 1:
			visible = candidate
			continue
		# URL、email、版本號等 token 要嘛完整顯示、要嘛從安全尾端縮略；不能切到 ``https:``。
		# 網址比「請到」這類前綴更有資訊量，所以即使前面已有短文字也優先保留網址本身。
		if ASCII_TOKEN_RE.fullmatch(token) and (
			not visible.strip() or token.lower().startswith(("https://", "http://", "www."))
		):
			return _truncate_ascii_token(token)
		return (visible.rstrip() + "…") if visible.strip() else _truncate_ascii_token(token)
	return visible.rstrip() + "…"


def _caption_groups(captions: list[dict], count: int) -> list[list[dict]]:
	groups: list[list[dict]] = []
	for index in range(count):
		start = round(index * len(captions) / count)
		end = round((index + 1) * len(captions) / count)
		groups.append(captions[start:end] or captions[-1:])
	return groups


def _group_items(group: list[dict], limit: int = 3) -> list[str]:
	items: list[str] = []
	for caption in group:
		text = _shorten(caption.get("zh"), 20)
		if text and text not in items:
			items.append(text)
		if len(items) >= limit:
			break
	return items or ["這段重點"]


def build_events(
	captions: list[dict],
	duration: float,
	include_broll: bool = True,
	broll_duration: float | None = None,
	cadence_seconds: float = 2.0,
) -> list[dict]:
	"""讓整支短片持續有視覺事件；所有文案仍只取自逐字稿。"""
	usable = [
		caption
		for caption in captions
		if re.search(r"[\u3400-\u9fffA-Za-z0-9]", _clean(caption.get("zh")))
		and float(caption.get("end", 0)) > 0
	]
	if not usable or duration < 12:
		return []

	# 固定視覺節拍：每次只揭露一個資訊，CTA 前保留收束空間。
	cadence = max(1.5, min(4.0, float(cadence_seconds)))
	first_start = 2.2
	cta_guard = 3.8
	event_duration = min(1.92, cadence)
	last_start = max(first_start, duration - cta_guard - event_duration)
	event_count = max(2, int(math.floor((last_start - first_start) / cadence)) + 1)
	groups = _caption_groups(usable, event_count)
	events: list[dict] = []
	scene_names = ["people", "network", "table", "pipeline", "people", "funnel", "table", "loop"]
	broll_count = 0
	for index, group in enumerate(groups):
		start = first_start + cadence * index
		if include_broll and index % 2 == 0:
			items = _group_items(group, limit=2)
			current_duration = min(event_duration, broll_duration) if broll_duration is not None else event_duration
			events.append({
				"start": round(start, 3), "duration": round(current_duration, 3), "kind": "broll",
				"params": {"scene": scene_names[broll_count % len(scene_names)], "headline": items[0], "body": " · ".join(items[1:])},
			})
			broll_count += 1
		elif index % 4 == 1:
			events.append({
				"start": round(start, 3), "duration": round(event_duration, 3), "kind": "checklist",
				"params": {"title": "這段重點", "items": _group_items(group, limit=2)},
			})
		else:
			last = _shorten(group[-1].get("zh"), 14)
			events.append({
				"start": round(start, 3), "duration": round(event_duration, 3), "kind": "stamp",
				"params": {"line1": "關鍵觀念", "line2": last or "這段重點", "size": 62},
			})
	return events


def _render_reusable_broll(media: Path, duration: float, output_dir: Path, fps: int) -> int:
	"""將已核准的本機 B-roll 轉為 overlay frame，避免重複付費生成。"""
	output_dir.mkdir(parents=True, exist_ok=True)
	# 重用的情境圖／影片是插鏡而非主畫面；alpha 淡入淡出讓底層簡報可連續可讀。
	fade_duration = min(0.25, max(0.08, duration / 3))
	fade_out_start = max(0.0, duration - fade_duration)
	filter_chain = (
		f"fps={fps},scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,format=rgba,"
		f"fade=t=in:st=0:d={fade_duration:.3f}:alpha=1,"
		f"fade=t=out:st={fade_out_start:.3f}:d={fade_duration:.3f}:alpha=1"
	)
	subprocess.run([
		"ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-stream_loop", "-1", "-i", str(media),
		"-t", f"{duration:.3f}", "-vf", filter_chain,
		str(output_dir / "ov_%04d.png"),
	], check=True)
	return len(list(output_dir.glob("ov_*.png")))


def render_events(
	events: list[dict],
	output_dir: Path,
	fps: int = 30,
	*,
	broll_provider: str = "local",
	fal_config: object | None = None,
	fal_cache_dir: Path | None = None,
	remote_broll_limit: int = 2,
	fallback_reason: str | None = None,
	reusable_broll_media: list[Path] | None = None,
) -> list[dict]:
	"""產生透明 PNG 序列；fal 遠端失敗時一律退回既有本地 B-roll。"""
	output_dir = output_dir.resolve()
	if output_dir.exists():
		shutil.rmtree(output_dir)
	output_dir.mkdir(parents=True, exist_ok=True)
	result: list[dict] = []
	remote_broll_count = 0
	reusable_media = list(reusable_broll_media or [])
	reusable_broll_count = 0
	for index, event in enumerate(events, start=1):
		event_dir = output_dir / f"event_{index:02d}_{event['kind']}"
		metadata: dict = {}
		if event["kind"] == "broll":
			from broll_adapter import render as render_broll

			if reusable_broll_count < len(reusable_media) and reusable_media[reusable_broll_count].is_file():
				media = reusable_media[reusable_broll_count]
				reusable_broll_count += 1
				_render_reusable_broll(media, float(event["duration"]), event_dir, fps)
				metadata = {"provider": "reused-local-media", "media_kind": "video", "cache_hit": True}
			else:
				use_fal = broll_provider in {"fal-image", "fal-video", "fal-image-to-video"}
				if use_fal and fal_config is not None and remote_broll_count < max(0, remote_broll_limit):
					remote_broll_count += 1
					try:
						from fal_broll_provider import FalBrollError, render_fal_broll, render_fal_image_to_video_broll

						renderer = render_fal_image_to_video_broll if broll_provider == "fal-image-to-video" else render_fal_broll
						metadata = renderer(
							fal_config, event["params"], float(event["duration"]), event_dir, fps=fps, cache_dir=fal_cache_dir,
						)
					except FalBrollError as exc:
						metadata = {"provider": "local", "fallback_from": broll_provider, "fallback_reason": exc.reason}
						render_broll("V", event["kind"], event["params"], float(event["duration"]), event_dir, fps=fps)
				else:
					reason = None
					if use_fal:
						reason = fallback_reason or ("remote-broll-limit" if remote_broll_count >= max(0, remote_broll_limit) else "fal-provider-unavailable")
					metadata = {"provider": "local"}
					if reason:
						metadata.update({"fallback_from": broll_provider, "fallback_reason": reason})
					render_broll("V", event["kind"], event["params"], float(event["duration"]), event_dir, fps=fps)
		else:
			anim_lib.render(
				"V",
				event["kind"],
				event["params"],
				float(event["duration"]),
				event_dir,
				fps=fps,
			)
		result.append({**event, **metadata, "frames": str(event_dir), "fps": fps})
	return result

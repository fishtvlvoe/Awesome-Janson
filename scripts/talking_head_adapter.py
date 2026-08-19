#!/usr/bin/env python3
"""把 talking-head-video-cut 的動畫元件接到剪神時間軸。

上游引擎用 SPANS/LINES/ANIM 設定檔；剪神不複製那套設定檔，而是把
semantic_edit.json 的字幕 cue 轉成安全的 checklist／stamp 動畫事件。
"""
from __future__ import annotations

import math
import re
import shutil
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


def build_events(captions: list[dict], duration: float, include_broll: bool = True) -> list[dict]:
	"""讓整支短片持續有視覺事件；所有文案仍只取自逐字稿。"""
	usable = [
		caption
		for caption in captions
		if re.search(r"[\u3400-\u9fffA-Za-z0-9]", _clean(caption.get("zh")))
		and float(caption.get("end", 0)) > 0
	]
	if not usable or duration < 12:
		return []

	# 避免標題卡之後又空白二十秒：依片長安排 2～6 個事件，最後替 CTA 留安全區。
	first_start = 3.8
	cta_guard = 5.2
	budget = max(0.0, duration - first_start - cta_guard)
	event_count = min(6, max(2, math.ceil(budget / 8.0)))
	event_duration = min(5.4, max(3.2, budget / max(event_count, 1) * 0.78))
	last_start = max(first_start, duration - cta_guard - event_duration)
	step = (last_start - first_start) / max(event_count - 1, 1)
	groups = _caption_groups(usable, event_count)
	events: list[dict] = []
	scene_names = ["network", "funnel", "pipeline", "loop", "funnel", "loop"]
	broll_indexes = {0, 2, 4, 5}
	for index, (start_group, group) in enumerate(zip(range(event_count), groups)):
		start = first_start + step * index
		kind_broll = include_broll and index in broll_indexes
		if kind_broll:
			items = _group_items(group, limit=2)
			events.append(
				{
					"start": round(start, 3),
					"duration": round(event_duration, 3),
					"kind": "broll",
					"params": {
						"scene": scene_names[index % len(scene_names)],
						"headline": items[0],
						"body": " · ".join(items[1:]),
					},
				}
			)
		elif index == 1:
			items = _group_items(group, limit=3)
			events.append(
				{
					"start": round(start, 3),
					"duration": round(event_duration, 3),
					"kind": "checklist",
					"params": {"title": "這段重點", "items": items},
				}
			)
		else:
			last = _shorten(group[-1].get("zh"), 14)
			events.append(
				{
					"start": round(start, 3),
					"duration": round(event_duration, 3),
					"kind": "stamp",
					"params": {"line1": "關鍵觀念", "line2": last or "這段重點", "size": 62},
				}
			)
	return events


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
) -> list[dict]:
	"""產生透明 PNG 序列；fal 遠端失敗時一律退回既有本地 B-roll。"""
	output_dir = output_dir.resolve()
	if output_dir.exists():
		shutil.rmtree(output_dir)
	output_dir.mkdir(parents=True, exist_ok=True)
	result: list[dict] = []
	remote_broll_count = 0
	for index, event in enumerate(events, start=1):
		event_dir = output_dir / f"event_{index:02d}_{event['kind']}"
		metadata: dict = {}
		if event["kind"] == "broll":
			from broll_adapter import render as render_broll

			use_fal = broll_provider in {"fal-image", "fal-video"}
			if use_fal and fal_config is not None and remote_broll_count < max(0, remote_broll_limit):
				remote_broll_count += 1
				try:
					from fal_broll_provider import FalBrollError, render_fal_broll

					metadata = render_fal_broll(
						fal_config,
						event["params"],
						float(event["duration"]),
						event_dir,
						fps=fps,
						cache_dir=fal_cache_dir,
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

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


def _clean(value: object) -> str:
	return " ".join(str(value or "").replace(r"\N", " ").split())


def _shorten(value: object, limit: int = 18) -> str:
	text = _clean(value)
	if len(text) <= limit:
		return text
	cut = text[: limit - 1].rstrip()
	# 不把 SEO／BNI／loader 等 ASCII 專有名詞切成半個字。
	if re.search(r"[A-Za-z0-9]$", cut):
		without_partial_term = re.sub(r"[A-Za-z0-9+./_-]+$", "", cut).rstrip()
		# 短 ASCII 專有名詞完整保留；極端長 token 則保留前綴＋省略號，確保圖卡不超出畫布。
		if not without_partial_term:
			if len(text) <= MAX_UNBROKEN_ASCII_EVENT_CHARS:
				return text
			return text[: MAX_UNBROKEN_ASCII_EVENT_CHARS - 1] + "…"
		cut = without_partial_term
	return cut + "…"


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


def render_events(events: list[dict], output_dir: Path, fps: int = 30) -> list[dict]:
	"""產生透明 PNG 序列；回傳給 FFmpeg overlay 使用的事件描述。"""
	output_dir = output_dir.resolve()
	if output_dir.exists():
		shutil.rmtree(output_dir)
	output_dir.mkdir(parents=True, exist_ok=True)
	result: list[dict] = []
	for index, event in enumerate(events, start=1):
		event_dir = output_dir / f"event_{index:02d}_{event['kind']}"
		if event["kind"] == "broll":
			from broll_adapter import render as render_broll

			render_broll(
				"V",
				event["kind"],
				event["params"],
				float(event["duration"]),
				event_dir,
				fps=fps,
			)
		else:
			anim_lib.render(
				"V",
				event["kind"],
				event["params"],
				float(event["duration"]),
				event_dir,
				fps=fps,
			)
		result.append({**event, "frames": str(event_dir), "fps": fps})
	return result

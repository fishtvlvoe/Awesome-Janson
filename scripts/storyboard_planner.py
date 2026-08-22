#!/usr/bin/env python3
"""短影音的人工核准分鏡表。

分鏡先以 talking-head 呈現，只有使用者把某個 beat 設為 approved 並指定 visual type，
渲染器才會插入 B-roll 或動畫；禁止用固定秒數自動抽卡。
"""
from __future__ import annotations

from typing import Any


def _text(value: object) -> str:
    return " ".join(str(value or "").split())


def plan_segment(segment: dict[str, Any], captions: list[dict[str, Any]]) -> dict[str, Any]:
    """由既有語意字幕建立可人工編輯的初始分鏡，不擅自安排視覺素材。"""
    beats: list[dict[str, Any]] = []
    for index, caption in enumerate(captions, start=1):
        start = round(float(caption.get("start", 0.0)), 3)
        end = round(float(caption.get("end", start)), 3)
        text = _text(caption.get("zh"))
        if not text or end <= start:
            continue
        beats.append({
            "id": f"S{int(segment.get('id', 0)):02d}-{index:02d}",
            "start": start,
            "end": end,
            "transcript": text,
            "approval": "pending",
            "visual": {"type": "talking-head"},
            "note": "預設保留說話者；由使用者決定是否、何時插入其他畫面。",
        })
    return {
        "schema_version": 1,
        "mode": "user-approved-short-storyboard",
        "segment_id": int(segment.get("id", 0)),
        "title": _text(segment.get("title")) or "短影音",
        "duration": round(max((float(item.get("end", 0.0)) for item in captions), default=0.0), 3),
        "beats": beats,
    }


def approved_events(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """只將使用者核准的非 talking-head 分鏡轉為 renderer event。"""
    scene_map = {
        "contextual-broll": "people",
        "relationship": "network",
        "process-table": "table",
        "pipeline": "pipeline",
        "funnel": "funnel",
    }
    events: list[dict[str, Any]] = []
    for beat in plan.get("beats", []):
        if beat.get("approval") != "approved":
            continue
        visual = beat.get("visual") if isinstance(beat.get("visual"), dict) else {}
        visual_type = str(visual.get("type", "talking-head"))
        if visual_type == "talking-head":
            continue
        start = float(beat.get("start", 0.0))
        end = float(beat.get("end", start))
        if end <= start:
            continue
        transcript = _text(beat.get("transcript"))
        duration = round(end - start, 3)
        if visual_type in scene_map:
            events.append({
                "start": round(start, 3), "duration": duration, "kind": "broll",
                "params": {"scene": scene_map[visual_type], "headline": transcript, "body": ""},
            })
        elif visual_type == "checklist":
            events.append({
                "start": round(start, 3), "duration": duration, "kind": "checklist",
                "params": {"title": "這段重點", "items": [transcript]},
            })
        elif visual_type == "stamp":
            events.append({
                "start": round(start, 3), "duration": duration, "kind": "stamp",
                "params": {"line1": "關鍵觀念", "line2": transcript[:14], "size": 62},
            })
        else:
            raise ValueError(f"不支援的 storyboard visual type：{visual_type}")
    return events


def markdown_table(plan: dict[str, Any]) -> str:
    rows = [
        f"# 分鏡表：{plan['title']}",
        "",
        "先確認每一段要不要換畫面，再將該段 `approval` 改為 `approved`，並設定 `visual.type`。未核准段落一律保留說話者。可用類型：`talking-head`、`contextual-broll`、`relationship`、`process-table`、`pipeline`、`funnel`、`checklist`、`stamp`。",
        "",
        "| ID | 時間 | 口白 | 畫面 | 狀態 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for beat in plan["beats"]:
        rows.append(
            f"| {beat['id']} | {beat['start']:.2f}–{beat['end']:.2f} | {beat['transcript']} | {beat['visual']['type']} | {beat['approval']} |"
        )
    return "\n".join(rows) + "\n"

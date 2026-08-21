#!/usr/bin/env python3
"""由短影音語意 cue 產出人工核准分鏡 JSON 與 Markdown 表。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from render_shorts import build_captions
from storyboard_planner import markdown_table, plan_segment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("edit", type=Path, help="語意剪輯 JSON")
    parser.add_argument("segments", type=Path, help="短影音候選 JSON")
    parser.add_argument("--output", type=Path, required=True, help="輸出的 storyboard.json")
    parser.add_argument("--speed", type=float, default=1.15)
    args = parser.parse_args()
    if args.speed <= 0:
        raise SystemExit("--speed 必須大於 0")

    edit = json.loads(args.edit.read_text(encoding="utf-8"))
    payload = json.loads(args.segments.read_text(encoding="utf-8"))
    plans = []
    markdown = []
    for segment in payload.get("segments", []):
        captions = build_captions(edit, float(segment["source_start"]), float(segment["source_end"]), args.speed)
        plan = plan_segment(segment, captions)
        plans.append(plan)
        markdown.append(markdown_table(plan))
    result = {"schema_version": 1, "mode": "user-approved-short-storyboard", "segments": plans}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output.with_suffix(".md").write_text("\n".join(markdown), encoding="utf-8")
    print(f"✅ 分鏡表：{args.output}（{len(plans)} 段；全部 pending，尚未安排自動字卡或 B-roll）")


if __name__ == "__main__":
    main()

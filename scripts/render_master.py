#!/usr/bin/env python3
"""依 EDL 逐段重編碼、串接，再疊章節卡與字幕。"""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path

from subtitle_layout import resolve_font_path, resolve_fonts_dir


def escape_filter_path(path: Path | str) -> str:
	return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def run(command: list[str]) -> None:
	print("$", " ".join(shlex.quote(item) for item in command[:8]), "...", flush=True)
	subprocess.run(command, check=True)


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("edl", type=Path)
	parser.add_argument("--subtitle", type=Path, required=True)
	parser.add_argument("--output", type=Path, required=True)
	parser.add_argument("--chapters", type=Path, required=True)
	parser.add_argument("--crf", default="23")
	parser.add_argument("--preset", default="veryfast")
	parser.add_argument("--reuse-base", action="store_true")
	args = parser.parse_args()
	edl = json.loads(args.edl.read_text(encoding="utf-8"))
	work = args.edl.parent
	clips = work / "clips_master"
	clips.mkdir(parents=True, exist_ok=True)
	segment_paths: list[Path] = []
	base = work / "master_base.mp4"
	if args.reuse_base and base.exists():
		print(f"♻️ 重用既有中間檔：{base}", flush=True)
	else:
		for index, item in enumerate(edl["ranges"]):
			source = Path(edl["sources"][item["source"]]).resolve()
			start = float(item["start"])
			duration = float(item["end"]) - start
			path = clips / f"segment_{index:03d}.mp4"
			fade_out = max(0.03, duration - 0.03)
			filters = f"format=yuv420p"
			audio = f"afade=t=in:st=0:d=0.03,afade=t=out:st={fade_out:.3f}:d=0.03,aresample=48000"
			run([
				"ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
				"-ss", f"{start:.3f}", "-i", str(source), "-t", f"{duration:.3f}",
				"-vf", filters, "-af", audio,
				"-c:v", "libx264", "-preset", args.preset, "-crf", args.crf,
				"-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "192k",
				"-ar", "48000", "-movflags", "+faststart", str(path),
			])
			segment_paths.append(path)
		concat_list = work / "concat_master.txt"
		concat_list.write_text("".join(f"file '{path.resolve()}'\n" for path in segment_paths), encoding="utf-8")
		run([
			"ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
			"-i", str(concat_list), "-c", "copy", "-movflags", "+faststart", str(base),
		])
	chapters = json.loads(args.chapters.read_text(encoding="utf-8"))
	font_path = resolve_font_path()
	font = escape_filter_path(font_path) if font_path else "STHeiti"
	fonts_dir = resolve_fonts_dir(font_path)
	fonts_dir_value = escape_filter_path(fonts_dir) if fonts_dir else "/System/Library/Fonts"
	filters: list[str] = []
	for chapter in chapters:
		text_file = work / f"chapter_{chapter['id']:02d}.txt"
		text_file.write_text(chapter["title"], encoding="utf-8")
		path = escape_filter_path(text_file)
		start = float(chapter["output_start"])
		end = start + 5.0
		filters.append(
			"drawtext="
			f"fontfile='{font}':textfile='{path}':fontcolor=white:fontsize=34:"
			f"x=48:y=42:box=1:boxcolor=0x9B0000CC:boxborderw=14:"
			f"enable='between(t,{start:.3f},{end:.3f})'"
		)
	filters.extend(
		[
			"drawbox=x=0:y=400:w=iw:h=40:color=black@0.025:t=fill",
			"drawbox=x=0:y=440:w=iw:h=40:color=black@0.045:t=fill",
			"drawbox=x=0:y=480:w=iw:h=40:color=black@0.07:t=fill",
			"drawbox=x=0:y=520:w=iw:h=40:color=black@0.095:t=fill",
			"drawbox=x=0:y=560:w=iw:h=40:color=black@0.12:t=fill",
			"drawbox=x=0:y=600:w=iw:h=40:color=black@0.15:t=fill",
			"drawbox=x=0:y=640:w=iw:h=40:color=black@0.18:t=fill",
			"drawbox=x=0:y=680:w=iw:h=40:color=black@0.20:t=fill",
		]
	)
	filters.append(f"subtitles=filename='{escape_filter_path(args.subtitle)}':fontsdir='{fonts_dir_value}'")
	args.output.parent.mkdir(parents=True, exist_ok=True)
	run([
		"ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(base),
		"-vf", ",".join(filters), "-c:v", "libx264", "-preset", args.preset,
		"-crf", args.crf, "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart",
		str(args.output),
	])
	print(f"✅ 完成：{args.output}")


if __name__ == "__main__":
	main()

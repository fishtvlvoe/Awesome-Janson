#!/usr/bin/env python3
"""以固定區段轉錄長音訊，避免長檔 VAD 提前結束。"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path

from faster_whisper import WhisperModel


def duration(path: Path) -> float:
	result = subprocess.run(
		[
			"ffprobe",
			"-v",
			"error",
			"-show_entries",
			"format=duration",
			"-of",
			"default=noprint_wrappers=1:nokey=1",
			str(path),
		],
		check=True,
		capture_output=True,
		text=True,
	)
	return float(result.stdout.strip())


def transcribe(args: argparse.Namespace) -> None:
	input_path = Path(args.input).resolve()
	output_path = Path(args.output).resolve()
	output_path.parent.mkdir(parents=True, exist_ok=True)
	length = duration(input_path)
	model = WhisperModel(args.model, device="cpu", compute_type="int8", cpu_threads=args.threads)
	all_segments: list[dict] = []
	started = time.monotonic()

	with tempfile.TemporaryDirectory(prefix="awesome-janson-chunks-") as temp_dir:
		for chunk_start in range(0, int(length) + 1, args.chunk_seconds):
			if chunk_start >= length:
				break
			chunk_duration = min(args.chunk_seconds + args.overlap, length - chunk_start)
			chunk_path = Path(temp_dir) / f"chunk-{chunk_start:06d}.wav"
			subprocess.run(
			[
				"ffmpeg",
				"-hide_banner",
				"-loglevel",
				"error",
				"-ss",
				str(chunk_start),
				"-i",
				str(input_path),
				"-t",
				str(chunk_duration),
				"-c",
				"copy",
				str(chunk_path),
			],
			check=True,
		)
			print(f"🎙️ 轉錄 {chunk_start / 60:.1f}–{min(chunk_start + chunk_duration, length) / 60:.1f} 分鐘", flush=True)
			segments, info = model.transcribe(
				str(chunk_path),
				beam_size=1,
				word_timestamps=True,
				language="zh",
				vad_filter=True,
				vad_parameters={"min_silence_duration_ms": 500},
			)
			for segment in segments:
				global_start = segment.start + chunk_start
				global_end = segment.end + chunk_start
				if all_segments and global_start < all_segments[-1]["end"] - 0.5:
					continue
				all_segments.append(
					{
						"id": len(all_segments),
						"start": round(global_start, 2),
						"end": round(global_end, 2),
						"text": segment.text.strip(),
						"words": [
							{
								"word": word.word,
								"start": round(word.start + chunk_start, 2),
								"end": round(word.end + chunk_start, 2),
								"probability": round(word.probability, 2),
							}
							for word in (segment.words or [])
						],
					}
				)
			with output_path.open("w", encoding="utf-8") as handle:
				json.dump(all_segments, handle, ensure_ascii=False, indent=2)
			print(f"   已累積 {len(all_segments)} 段，語言 {info.language}", flush=True)

	print(f"✅ 完成：{len(all_segments)} 段，耗時 {(time.monotonic() - started) / 60:.1f} 分鐘", flush=True)


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("input")
	parser.add_argument("output")
	parser.add_argument("--model", default="small")
	parser.add_argument("--chunk-seconds", type=int, default=600)
	parser.add_argument("--overlap", type=int, default=2)
	parser.add_argument("--threads", type=int, default=8)
	transcribe(parser.parse_args())

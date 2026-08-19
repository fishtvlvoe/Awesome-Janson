#!/usr/bin/env python3
"""產生剪神本地動畫音效；不下載素材、不含第三方取樣。"""
from __future__ import annotations

import argparse
import json
import wave
from pathlib import Path

import numpy as np

SR = 48_000


def _put(buffer: np.ndarray, start: float, signal: np.ndarray, gain: float = 1.0) -> None:
	index = max(0, int(start * SR))
	offset = max(0, -int(start * SR))
	if index >= len(buffer) or offset >= len(signal):
		return
	count = min(len(signal) - offset, len(buffer) - index)
	buffer[index : index + count] += signal[offset : offset + count] * gain


def _click() -> np.ndarray:
	time = np.arange(int(0.095 * SR)) / SR
	return (
		0.72 * np.sin(2 * np.pi * 1420 * time) + 0.28 * np.sin(2 * np.pi * 2380 * time)
	) * np.exp(-38 * time)


def _thump() -> np.ndarray:
	time = np.arange(int(0.28 * SR)) / SR
	frequency = 150 * np.exp(-18 * time) + 48
	phase = 2 * np.pi * np.cumsum(frequency) / SR
	return np.sin(phase) * np.exp(-15 * time)


def _whoosh(seed: int = 17) -> np.ndarray:
	length = int(0.62 * SR)
	time = np.arange(length) / SR
	rng = np.random.RandomState(seed)
	noise = rng.normal(0, 1, length)
	noise = np.convolve(noise, np.ones(12) / 12, mode="same")
	sweep = np.sin(2 * np.pi * (220 + 1500 * time**1.7) * time)
	envelope = np.sin(np.pi * np.clip(time / time[-1], 0, 1)) ** 1.4
	return (0.65 * noise + 0.35 * sweep) * envelope


def _bell() -> np.ndarray:
	time = np.arange(int(0.42 * SR)) / SR
	return (
		0.65 * np.sin(2 * np.pi * 880 * time)
		+ 0.25 * np.sin(2 * np.pi * 1760 * time)
	) * np.exp(-7 * time)


def generate(events: list[dict], duration: float) -> np.ndarray:
	length = max(1, int(np.ceil(float(duration) * SR)))
	left = np.zeros(length)
	right = np.zeros(length)
	for index, event in enumerate(events):
		start = float(event.get("start", 0.0))
		kind = str(event.get("kind", ""))
		if kind == "broll":
			whoosh = _whoosh(index + 17)
			_put(left, start, whoosh, 0.075)
			_put(right, start + 0.018, whoosh, 0.065)
			click = _click()
			_put(left, start + 0.52, click, 0.085)
			_put(right, start + 0.535, click, 0.070)
		elif kind == "checklist":
			items = event.get("params", {}).get("items", [])
			for item_index in range(min(3, len(items))):
				click = _click()
				click_start = start + 0.62 + item_index * 0.55
				_put(left, click_start, click, 0.075)
				_put(right, click_start + 0.012, click, 0.062)
		elif kind == "stamp":
			thump = _thump()
			_put(left, start + 0.22, thump, 0.10)
			_put(right, start + 0.235, thump, 0.085)
			bell = _bell()
			_put(left, start + 0.28, bell, 0.045)
			_put(right, start + 0.30, bell, 0.04)
	peak = max(float(np.abs(left).max()), float(np.abs(right).max()), 1e-9)
	if peak > 0.55:
		left *= 0.55 / peak
		right *= 0.55 / peak
	return np.column_stack((left, right))


def write_sfx(output: Path, events: list[dict], duration: float) -> None:
	pcm = np.clip(generate(events, duration) * 32767, -32768, 32767).astype(np.int16)
	output.parent.mkdir(parents=True, exist_ok=True)
	with wave.open(str(output), "wb") as stream:
		stream.setnchannels(2)
		stream.setsampwidth(2)
		stream.setframerate(SR)
		stream.writeframes(pcm.tobytes())


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("events", type=Path, help="含 start/kind/params 的 JSON")
	parser.add_argument("output", type=Path)
	parser.add_argument("--duration", type=float, required=True)
	args = parser.parse_args()
	events = json.loads(args.events.read_text(encoding="utf-8"))
	write_sfx(args.output, events, args.duration)
	print(f"✅ SFX: {args.output} ({args.duration:.1f}s)")


if __name__ == "__main__":
	main()

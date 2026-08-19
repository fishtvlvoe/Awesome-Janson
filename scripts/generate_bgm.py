#!/usr/bin/env python3
"""產生剪神可用的合成 BGM；不下載音樂、不含第三方取樣。"""
from __future__ import annotations

import argparse
import wave
from pathlib import Path

import numpy as np

SR = 48_000
BPM = 108
BEAT = 60.0 / BPM
BAR = BEAT * 4
PROG = [
	(65.41, (261.63, 329.63, 392.00)),
	(98.00, (246.94, 293.66, 392.00)),
	(110.00, (261.63, 329.63, 440.00)),
	(87.31, (261.63, 349.23, 440.00)),
]


def _put(buffer: np.ndarray, start: float, signal: np.ndarray, gain: float = 1.0) -> None:
	index = int(start * SR)
	if index >= len(buffer):
		return
	count = min(len(signal), len(buffer) - index)
	buffer[index : index + count] += signal[:count] * gain


def _adsr(length: int, attack: float, decay: float, sustain: float, release: float) -> np.ndarray:
	envelope = np.ones(length)
	attack_i, decay_i, release_i = int(attack * SR), int(decay * SR), int(release * SR)
	if attack_i:
		envelope[:attack_i] = np.linspace(0, 1, attack_i)
	if decay_i:
		envelope[attack_i : attack_i + decay_i] = np.linspace(1, sustain, decay_i)
	envelope[attack_i + decay_i :] = sustain
	if release_i and release_i < length:
		envelope[-release_i:] *= np.linspace(1, 0, release_i)
	return envelope


def _pluck(frequency: float, duration: float, amplitude: float = 0.25) -> np.ndarray:
	length = int(duration * SR)
	time = np.arange(length) / SR
	signal = (
		np.sin(2 * np.pi * frequency * time)
		+ 0.35 * np.sin(4 * np.pi * frequency * time)
		+ 0.15 * np.sin(6 * np.pi * frequency * time)
	)
	return signal * np.exp(-6.0 * time) * amplitude


def _pad(frequency: float, duration: float, amplitude: float = 0.12) -> np.ndarray:
	length = int(duration * SR)
	time = np.arange(length) / SR
	signal = (
		np.sin(2 * np.pi * frequency * time)
		+ 0.5 * np.sin(2 * np.pi * frequency * 1.005 * time)
		+ 0.3 * np.sin(2 * np.pi * frequency * 0.995 * time)
	)
	return signal * _adsr(length, 0.18, 0.10, 0.85, 0.22) * amplitude


def _bass(frequency: float, duration: float, amplitude: float = 0.30) -> np.ndarray:
	length = int(duration * SR)
	time = np.arange(length) / SR
	signal = np.sin(2 * np.pi * frequency * time) + 0.25 * np.sin(4 * np.pi * frequency * time)
	return signal * _adsr(length, 0.008, 0.06, 0.75, 0.09) * amplitude


def _kick(amplitude: float = 0.55) -> np.ndarray:
	length = int(0.16 * SR)
	time = np.arange(length) / SR
	frequency = 130 * np.exp(-28 * time) + 46
	return np.sin(2 * np.pi * np.cumsum(frequency) / SR) * np.exp(-24 * time) * amplitude


def _shaker() -> np.ndarray:
	length = int(0.055 * SR)
	signal = np.random.RandomState(7).randn(length)
	signal = np.convolve(signal, [1, -0.92], mode="same")
	return signal * np.exp(-45 * np.arange(length) / SR) * 0.10


def _bell(frequency: float, duration: float = 1.6, amplitude: float = 0.22) -> np.ndarray:
	length = int(duration * SR)
	time = np.arange(length) / SR
	signal = (
		np.sin(2 * np.pi * frequency * time)
		+ 0.5 * np.sin(2 * np.pi * frequency * 2.76 * time)
		+ 0.25 * np.sin(2 * np.pi * frequency * 5.4 * time)
	)
	return signal * np.exp(-2.6 * time) * amplitude


def generate(duration: float) -> np.ndarray:
	duration = max(8.0, float(duration))
	length = int(np.ceil(duration * SR))
	left = np.zeros(length)
	right = np.zeros(length)
	shaker = _shaker()
	bars = int(np.ceil(duration / BAR))
	for bar in range(bars):
		bass_frequency, chord = PROG[bar % len(PROG)]
		start = bar * BAR
		for beat in (0, 2):
			_put(left, start + beat * BEAT, _bass(bass_frequency, BEAT * 1.9), 0.9)
			_put(right, start + beat * BEAT, _bass(bass_frequency, BEAT * 1.9), 0.9)
		for index, frequency in enumerate(chord):
			pad = _pad(frequency, BAR * 0.98)
			_put(left, start, pad, 1.0 - 0.25 * index)
			_put(right, start, pad, 0.75 + 0.25 * index)
		for beat in range(8):
			frequency = chord[[0, 1, 2, 1, 0, 1, 2, 1][beat]] * (2.0 if beat in (2, 6) else 1.0)
			pluck = _pluck(frequency, BEAT * 0.62, 0.20 if beat % 2 == 0 else 0.13)
			_put(left, start + beat * BEAT / 2, pluck, 1.05)
			_put(right, start + beat * BEAT / 2, pluck, 0.80)
		for beat in (0, 2):
			kick = _kick()
			_put(left, start + beat * BEAT, kick)
			_put(right, start + beat * BEAT, kick)
		for beat in range(8):
			gain = 1.0 if beat % 2 == 0 else 0.55
			_put(left, start + beat * BEAT / 2, shaker, gain * 0.9)
			_put(right, start + beat * BEAT / 2, shaker, gain * 1.1)

	for frequency, gain in ((1046.50, 1.0), (1567.98, 0.6), (2093.00, 0.35)):
		bell = _bell(frequency)
		_put(left, 0.0, bell, gain)
		_put(right, 0.0, bell, gain * 0.9)
	kick = _kick(0.8)
	_put(left, 0.0, kick)
	_put(right, 0.0, kick)

	fade = int(0.5 * SR)
	left[-fade:] *= np.linspace(1, 0, fade)
	right[-fade:] *= np.linspace(1, 0, fade)
	attack = int(0.02 * SR)
	left[:attack] *= np.linspace(0, 1, attack)
	right[:attack] *= np.linspace(0, 1, attack)
	peak = max(float(np.abs(left).max()), float(np.abs(right).max()), 1e-9)
	left = np.tanh(left / peak * 3.6) / np.tanh(3.6) * 0.89
	right = np.tanh(right / peak * 3.6) / np.tanh(3.6) * 0.89
	return np.column_stack((left, right))


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("output", type=Path)
	parser.add_argument("--duration", type=float, default=90.0)
	args = parser.parse_args()
	pcm = np.clip(generate(args.duration) * 32767, -32768, 32767).astype(np.int16)
	args.output.parent.mkdir(parents=True, exist_ok=True)
	with wave.open(str(args.output), "wb") as stream:
		stream.setnchannels(2)
		stream.setsampwidth(2)
		stream.setframerate(SR)
		stream.writeframes(pcm.tobytes())
	print(f"✅ BGM: {args.output} ({len(pcm) / SR:.1f}s)")


if __name__ == "__main__":
	main()

#!/usr/bin/env python3
"""使用 Gemini 將字幕 cue 翻成自然的英文，保留 cue id 與時間軸。"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"


def parse_json(text: str):
	text = text.strip()
	text = re.sub(r"^```(?:json)?\s*", "", text)
	text = re.sub(r"\s*```$", "", text)
	return json.loads(text)


def translate_batch(items: list[dict], api_key: str) -> list[dict]:
	payload = {
		"contents": [
			{
				"role": "user",
				"parts": [
					{
						"text": (
							"You are a professional Traditional Chinese to English subtitle translator. "
							"Translate each item into concise, natural spoken English. Keep names, BNI, "
							"Power Team, PT, Wi-Fi, AI, and acronyms intact. Do not explain or merge items. "
							"Return only a JSON array of objects with the same id and an en field. "
							"Use no markdown.\n\nINPUT:\n" + json.dumps(
								[{"id": item["id"], "zh": item["zh"]} for item in items],
								ensure_ascii=False,
							)
						)
					}
				]
			}
		],
		"generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
	}
	request = urllib.request.Request(
		API_URL + "?key=" + urllib.parse.quote(api_key),
		data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
		headers={"Content-Type": "application/json"},
		method="POST",
	)
	for attempt in range(4):
		try:
			with urllib.request.urlopen(request, timeout=120) as response:
				body = json.loads(response.read().decode("utf-8"))
			text = body["candidates"][0]["content"]["parts"][0]["text"]
			result = parse_json(text)
			if not isinstance(result, list):
				raise ValueError("Gemini returned a non-array result")
			return result
		except (urllib.error.HTTPError, urllib.error.URLError, KeyError, ValueError, json.JSONDecodeError) as error:
			if attempt == 3:
				raise RuntimeError(f"translation batch failed: {error}") from error
			time.sleep(2**attempt)
	return []


def translate_resilient(items: list[dict], api_key: str) -> list[dict]:
	try:
		return translate_batch(items, api_key)
	except RuntimeError:
		if len(items) <= 10:
			raise
		middle = len(items) // 2
		print(f"   ⚠️ 回應格式異常，拆成 {middle} + {len(items) - middle} 條重試", flush=True)
		return translate_resilient(items[:middle], api_key) + translate_resilient(items[middle:], api_key)


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("cues", type=Path)
	parser.add_argument("output", type=Path)
	parser.add_argument("--batch-size", type=int, default=60)
	args = parser.parse_args()
	api_key = os.environ.get("GEMINI_API_KEY")
	if not api_key:
		raise SystemExit("GEMINI_API_KEY is not set")
	cues = json.loads(args.cues.read_text(encoding="utf-8"))
	translations: dict[str, str] = {}
	if args.output.exists():
		translations = json.loads(args.output.read_text(encoding="utf-8"))
	for offset in range(0, len(cues), args.batch_size):
		batch = cues[offset : offset + args.batch_size]
		if all(str(item["id"]) in translations for item in batch):
			continue
		print(f"🌐 翻譯字幕 {offset + 1}–{offset + len(batch)} / {len(cues)}", flush=True)
		for item in translate_resilient(batch, api_key):
			if "id" in item and "en" in item:
				translations[str(item["id"])] = str(item["en"]).strip()
		args.output.write_text(json.dumps(translations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
	print(f"✅ 完成 {len(translations)} 條英文字幕")


if __name__ == "__main__":
	main()

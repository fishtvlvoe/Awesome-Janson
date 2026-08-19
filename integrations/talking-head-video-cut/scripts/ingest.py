# -*- coding: utf-8 -*-
"""通用轉錄：吃一個資料夾，把裡面所有 mp4 轉成逐字稿 + 精簡稿
用法：python ingest.py "<資料夾路徑>"
已存在的逐字稿會跳過。
"""
import os, sys, json, time, io, re, glob
sp = os.path.join(os.path.dirname(sys.executable), "..", "Lib", "site-packages")
for pat in ("nvidia/cublas/bin", "nvidia/cudnn/bin", "nvidia/cuda_runtime/bin"):
    d = os.path.abspath(os.path.join(sp, *pat.split("/")))
    if os.path.isdir(d):
        os.add_dll_directory(d); os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]
from faster_whisper import WhisperModel
from opencc import OpenCC
CC = OpenCC("s2twp")

PROMPT = ("以下是台灣 Meta 廣告投放課程的錄影逐字稿。內容包含 Facebook 廣告、廣告管理員、"
          "受眾、素材、文案、鉤子、腳本、轉換率、客單價、ROAS、CPM、CPC、CTR、CPA、"
          "Pixel、CAPI、GA4、Looker Studio、再行銷、A/B Test、廣告組合、成效、出價、"
          "預算、學習期、類似受眾、版位、ChatGPT、Gemini、提示詞等行銷與 AI 術語。"
          "請使用繁體中文輸出。")

VD = sys.argv[1]
WORK = os.path.join(VD, "工作暫存")
TR   = os.path.join(WORK, "逐字稿")
os.makedirs(TR, exist_ok=True)
vids = sorted(f for f in os.listdir(VD) if f.lower().endswith((".mp4",".mkv",".mov")))
todo = []
for i, f in enumerate(vids, 1):
    tag = "s%d" % i
    if os.path.exists(os.path.join(TR, tag + ".json")):
        print("skip %s (%s 已存在)" % (f, tag), flush=True); continue
    todo.append((tag, f))
if not todo:
    print("沒有要轉的"); sys.exit(0)
model = WhisperModel("large-v3", device="cuda", compute_type="float16", local_files_only=True)
for tag, f in todo:
    t1 = time.time()
    print(">> %s  %s" % (tag, f), flush=True)
    segs, _ = model.transcribe(os.path.join(VD, f), language="zh", beam_size=5,
                               word_timestamps=True, vad_filter=True,
                               condition_on_previous_text=False, initial_prompt=PROMPT)
    out = []
    for i, s in enumerate(segs):
        out.append(dict(start=s.start, end=s.end, text=s.text,
                        words=[dict(w=w.word, s=w.start, e=w.end) for w in (s.words or [])]))
        if i % 400 == 0: print("   seg %d t=%.0fs" % (i, s.end), flush=True)
    io.open(os.path.join(TR, tag+".json"), "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False))
    # 精簡稿
    lines, buf, t0 = [], "", None
    for s in out:
        if t0 is None: t0 = s["start"]
        buf += CC.convert(s["text"]).strip()
        if s["end"] - t0 >= 40:
            lines.append("[%02d:%02d] %s" % (int(t0//60), int(t0%60), buf)); buf, t0 = "", None
    if buf: lines.append("[%02d:%02d] %s" % (int(t0//60), int(t0%60), buf))
    io.open(os.path.join(WORK, tag+"_compact.txt"), "w", encoding="utf-8").write("\n".join(lines))
    print("%s DONE %d segs -> %d 行  %.1f min" % (tag, len(out), len(lines), (time.time()-t1)/60), flush=True)
print("INGEST_DONE", flush=True)

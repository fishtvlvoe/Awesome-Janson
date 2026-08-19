# -*- coding: utf-8 -*-
"""找出 SPANS 在同一來源檔上非遞增的設定（會踩到舊 remap bug）"""
import sys, os, glob, importlib
sys.path.insert(0, r"C:\videoedit\_whisper")
tags = sorted(os.path.basename(x)[:-7] for x in glob.glob(r"C:\videoedit\_whisper\*_cfg.py"))
bad = []
for t in tags:
    try:
        C = importlib.import_module(t + "_cfg")
        sp = C.SPANS
    except Exception:
        continue
    last = {}
    for src, a, b in sp:
        if src in last and a < last[src] - 1e-6:
            bad.append((t, src, last[src], a)); break
        last[src] = b
for r in bad:
    print("%-6s  src=%s  往回跳: 前段結束 %.2f -> 下段開始 %.2f" % r)
print("---- 共 %d 筆" % len(bad))

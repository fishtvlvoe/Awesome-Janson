# -*- coding: utf-8 -*-
"""用『修正前』的規則檢查所有已產出影片的片頭圖卡，找出文字溢出的"""
import sys, os, glob, importlib
sys.path.insert(0, r"C:\videoedit\_whisper")
from PIL import Image, ImageDraw, ImageFont
FONT_H = r"C:\videoedit\_fonts\GenSenRounded2TW-H.otf"
FONT_B = r"C:\videoedit\_fonts\GenSenRounded2TW-B.otf"
for f in (FONT_H, FONT_B):
    if not os.path.exists(f):
        cand = glob.glob(r"C:\videoedit\_fonts\*.ttf") + glob.glob(r"C:\videoedit\_fonts\*.otf")
        print("FONT MISSING", f, "->", cand); sys.exit(1)
img = Image.new("RGB", (10, 10)); d = ImageDraw.Draw(img)
tags = [os.path.basename(x)[:-7] for x in glob.glob(r"C:\videoedit\_whisper\*_cfg.py")]
bad = []
for t in sorted(tags):
    try:
        C = importlib.import_module(t + "_cfg")
        l1, l2 = C.TITLE
    except Exception:
        continue
    for w, h, nm in ((1080, 1920, "V"), (1920, 1080, "H")):
        big = int(w*0.098) if w < h else int(h*0.115)
        sm = int(big*0.74)
        x1 = int(w*0.10); x2 = x1 + int(w*0.075)
        w1 = d.textlength(l1, font=ImageFont.truetype(FONT_H, big))
        w2 = d.textlength(l2, font=ImageFont.truetype(FONT_B, sm))
        lim = w - int(w*0.03)
        o1, o2 = x1 + w1 > lim, x2 + w2 > lim
        if o1 or o2:
            bad.append((t, nm, l1 if o1 else "", l2 if o2 else "",
                        int(x1+w1) if o1 else 0, int(x2+w2) if o2 else 0, lim))
for r in bad:
    print("%-6s %s  limit=%d  L1超出:%s(%d)  L2超出:%s(%d)" % (r[0], r[1], r[6], r[2], r[4], r[3], r[5]))
print("---- 共 %d 筆" % len(bad))

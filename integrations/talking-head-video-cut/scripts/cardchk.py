# -*- coding: utf-8 -*-
"""量實際產出的片頭圖卡：最右邊的文字像素在哪"""
import glob, os
from PIL import Image
for p in sorted(glob.glob(r"C:\videoedit\adhub\20250902廣告進階\工作暫存\長片片頭\*_直式_9x16.png")):
    im = Image.open(p).convert("RGB"); w, h = im.size; px = im.load()
    rmax, lmin = 0, w
    for y in range(int(h*0.10), int(h*0.95)):
        for x in range(w-1, -1, -1):
            r, g, b = px[x, y]
            if r > 210 and g > 210 and b > 210:
                if x > rmax: rmax = x
                break
    flag = "  <<< 超框" if rmax > w - 20 else ""
    print("%-46s  最右白字 x=%4d / %d%s" % (os.path.basename(p)[:46], rmax, w, flag))

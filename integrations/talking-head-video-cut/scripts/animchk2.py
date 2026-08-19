# -*- coding: utf-8 -*-
import sys, importlib
sys.path.insert(0, r"C:\videoedit\_whisper")
import trim as TRIM
tag = sys.argv[1]
C = importlib.import_module(tag + "_cfg")
raw, rep = TRIM.trim(C.SPANS)
lines, body = TRIM.remap(C.SPANS, raw, C.LINES)
anims = C.ANIM
pts, _ = TRIM.remap(C.SPANS, raw, [(a0, a0 + 0.1, "") for a0, _, _, _ in anims])
out = [(pts[i][0], anims[i][1], anims[i][2]) for i in range(len(anims))]
print("body", round(body, 2))
prev_end = -1
for i, (st, du, kind) in enumerate(out):
    en = st + du
    flag = ""
    if st < prev_end - 0.001:
        flag = "  <<< OVERLAP with previous (prev end %.2f)" % prev_end
    if en > body:
        flag += "  <<< PAST BODY"
    print("%2d  %-10s  %7.2f ~ %7.2f  (dur %5.2f)%s" % (i, kind, st, en, du, flag))
    prev_end = en

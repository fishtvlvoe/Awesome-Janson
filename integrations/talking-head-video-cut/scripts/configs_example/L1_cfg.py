# -*- coding: utf-8 -*-
"""L1 雙11 預算怎麼分、怎麼排、怎麼收｜2 分半長版｜EP2 s2｜漲粉用，無活動宣傳"""
import p3_cfg, p2_cfg, p5_cfg
SUB_SCALE = 1.25
BRAND = "圭話行銷"
INTRO_D, CTA_D = 2.2, 6.5
CTA = ("每週一則 Meta 廣告實戰筆記\\N投放、素材、數據 一次講清楚"
       "\\N\\N覺得有用就追蹤 圭話行銷")
TITLE = ("預算怎麼分、怎麼排", "檔期結束怎麼收")
TOPIC = "Meta 廣告實戰筆記"

MODS = [p3_cfg, p2_cfg, p5_cfg]
SPANS, LINES, CARDS, ANIM = [], [], [], []
_off = 0.0
for _m in MODS:
    SPANS += list(_m.SPANS)
    LINES += [(a + _off, b + _off, t) for a, b, t in _m.LINES]
    CARDS += [(a + _off, b + _off, t) for a, b, t in getattr(_m, "CARDS", [])]
    ANIM  += [(a + _off, d, k, p) for a, d, k, p in getattr(_m, "ANIM", [])]
    _off += sum(b - a for _, a, b in _m.SPANS)

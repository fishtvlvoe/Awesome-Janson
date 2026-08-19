# -*- coding: utf-8 -*-
"""開剪前的設定檔健檢：來源檔存在、時間軸不超出、字幕不重疊、動畫不重疊"""
import os, sys, importlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())
import long_run
ok = True
for tag in sys.argv[1:]:
    C = importlib.import_module(tag + "_cfg")
    body = sum(b-a for _,a,b in C.SPANS)
    i = getattr(C, "INTRO_D", 2.0); c = getattr(C, "CTA_D", 8.0)
    total = body + i + c
    prob = []
    # 1) 來源標籤必須登記過（上一批就是死在這）
    for src,_,_ in C.SPANS:
        if src not in long_run.SRC:
            prob.append("來源 '%s' 沒登記在 SRC" % src); break
        if not os.path.exists(long_run.SRC[src]):
            prob.append("來源檔不存在：%s" % src); break
    # 2) 版面必須存在
    for L in getattr(C, "LAYOUTS", []) or []:
        if L not in long_run.LAY["V"] or L not in long_run.LAY["H"]:
            prob.append("版面 '%s' 不存在" % L)
    # 3) 時間軸
    LN = getattr(C, "LINES", [])
    if [l for l in LN if l[1] > body+0.05]: prob.append("字幕超出片長")
    if sum(1 for k in range(len(LN)-1) if LN[k+1][0] < LN[k][1]-0.001): prob.append("字幕重疊")
    AN = getattr(C, "ANIM", [])
    if [x for x in AN if x[0]+x[1] > body]: prob.append("動畫超出片長")
    if sum(1 for k in range(len(AN)-1) if AN[k][0]+AN[k][1] > AN[k+1][0]): prob.append("動畫重疊")
    for st,en,tx in getattr(C, "CARDS", []):
        if en > body+0.05: prob.append("字卡超出片長"); break
    # 4) 動畫元件與參數
    REQP = {"bars2": ["title", "items"], "donut": ["title"], "count": ["value"],
            "checklist": ["title", "items"], "stamp": ["line1"], "vs": ["left", "right"],
            "formula": ["title", "rows"]}
    for _,_,kind,_p in AN:
        import anim_lib
        if kind not in anim_lib.KIND: prob.append("動畫元件 '%s' 不存在" % kind)
        for _k in REQP.get(kind, []):
            if _k not in _p: prob.append("%s 缺參數 %s" % (kind, _k))
    mx = max((max(len(x) for x in t.split("\\N")) for _,_,t in LN), default=0)
    st = "OK " if not prob else "NG "
    if prob: ok = False
    print("%s%-5s body %6.2f  全長 %5.1f (%d:%02d)  字幕 %2d 最長 %2d  動畫 %d  %s"
          % (st, tag, body, total, int(total//60), int(total%60), len(LN), mx, len(AN),
             "；".join(prob)))
print("ALL_OK" if ok else "有問題，先修再排隊")

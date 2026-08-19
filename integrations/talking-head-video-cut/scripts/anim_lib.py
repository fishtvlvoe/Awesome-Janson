# -*- coding: utf-8 -*-
"""EP4 動畫元件庫 - 由 動畫模板21式.py 收斂成 6 個參數化元件，直橫雙版型"""
import math, os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Awesome-Janson adapter：保留原始動畫元件，但改成跨平台字型解析。
FD = os.environ.get("AWJ_TALKING_HEAD_FONT_DIR", "")
_fc = {}

def _font_candidates(weight):
    names = {
        "B": ["GenSenRounded2TW-B.otf", "SourceHanSansTC-Bold.otf", "SourceHanSansTC-Medium.otf"],
        "H": ["GenSenRounded2TW-H.otf", "SourceHanSansTC-Heavy.otf", "SourceHanSansTC-Bold.otf"],
    }[weight]
    roots = []
    if FD:
        roots.append(Path(FD).expanduser())
    env_font = os.environ.get("AWESOME_JANSON_FONT")
    if env_font:
        roots.append(Path(env_font).expanduser().parent)
    roots.extend([
        Path.home() / "Library/Fonts",
        Path.home() / ".local/share/fonts",
        Path.home() / ".fonts",
        Path("/Library/Fonts"),
        Path("/usr/share/fonts/opentype/noto"),
        Path("/usr/share/fonts/truetype/noto"),
    ])
    for root in roots:
        for name in names:
            path = root / name
            if path.is_file():
                yield path

def F(w, s):
    k = (w, int(s))
    if k not in _fc:
        path = next(_font_candidates(w), None)
        _fc[k] = ImageFont.truetype(str(path), int(s)) if path else ImageFont.load_default()
    return _fc[k]

TEAL=(20,200,190); GOLD=(255,214,0); DARK=(22,24,29)
GREY=(150,150,145); WHITE=(255,255,255); RED=(226,86,74)

def eoc(t): return 1-(1-t)**3
def eio(t): return 0.5-0.5*math.cos(math.pi*t)
def c01(t): return max(0.0, min(1.0, t))
def back(t, s=1.7):
    t -= 1; return 1 + t*t*((s+1)*t + s)

# 直式：面板底邊 1452（兩行字幕最高頂到 1486）
# 橫式：面板底邊 810（兩行字幕最高頂到 ~905），置中在投影片區 x=584
LAYOUT = {
 "V": dict(W=1080, H=1920, CX=540, BOTTOM=1452, PW=880, S=1.00),
 "H": dict(W=1920, H=1080, CX=584, BOTTOM=810,  PW=940, S=0.78),
}

class Ctx:
    def __init__(self, lay):
        self.__dict__.update(LAYOUT[lay]); self.lay = lay
    def s(self, v): return int(v * self.S)
    def panel(self, img, h, tl, t0=0.12):
        h = self.s(h); w = self.PW
        a  = int(238 * c01((tl-t0)/0.30))
        dy = int(22 * (1 - eoc(c01((tl-t0)/0.30))))
        x0 = self.CX - w//2; y0 = self.BOTTOM - h + dy
        d = ImageDraw.Draw(img)
        r = self.s(44)
        d.rounded_rectangle([x0,y0,x0+w,y0+h], radius=r, fill=DARK+(a,))
        d.rounded_rectangle([x0,y0,x0+w,y0+h], radius=r, outline=TEAL+(int(a*0.85),), width=4)
        return x0, y0, w, h, a
    def tx(self, d, cx, y, txt, font, fill, alpha=255):
        w = d.textlength(txt, font=font)
        d.text((cx - w/2, y), txt, font=font, fill=tuple(fill[:3])+(alpha,))

# ---------- 01 兩欄長條對比 ----------
def bars2(c, img, tl, p):
    x0,y0,w,h,a = c.panel(img, 552, tl)
    if a < 10: return
    d = ImageDraw.Draw(img)
    c.tx(d, c.CX, y0+c.s(30), p["title"], F("B", c.s(44)), WHITE, a)
    items = p["items"]                    # [(值, 標籤, 顯示字, 顏色)]
    mx = max(i[0] for i in items)
    bw, gap, maxh = c.s(190), c.s(150), c.s(258)
    bx = x0 + (w - len(items)*bw - (len(items)-1)*gap)//2
    base = y0 + c.s(470)
    d.line([x0+c.s(60), base, x0+w-c.s(60), base], fill=(110,110,110,a), width=3)
    for i,(v,lab,txt,col) in enumerate(items):
        k = eoc(c01((tl-0.5-i*0.35)/0.9))
        bh = maxh * v/mx * k
        x = bx + i*(bw+gap)
        if bh > 2:
            d.rounded_rectangle([x, base-bh, x+bw, base], radius=c.s(14), fill=col+(a,))
            c.tx(d, x+bw/2, base-bh-c.s(58), txt, F("H", c.s(44)), col, a)
        c.tx(d, x+bw/2, base+c.s(14), lab, F("B", c.s(34)), GREY, a)
    k = c01((tl-2.3)/0.35)
    if k > 0 and p.get("note"):
        d.line([bx+bw+c.s(26), base-maxh, bx+bw+gap-c.s(26), base-maxh], fill=GOLD+(int(a*k),), width=5)
        c.tx(d, bx+bw+gap/2, base-maxh+c.s(4), p["note"], F("H", int(c.s(40)*(0.75+0.25*back(k)))), GOLD, int(a*k))

# ---------- 02 圓環百分比 ----------
def donut(c, img, tl, p):
    x0,y0,w,h,a = c.panel(img, 552, tl)
    if a < 10: return
    d = ImageDraw.Draw(img)
    c.tx(d, c.CX, y0+c.s(30), p["title"], F("B", c.s(44)), WHITE, a)
    cx, cy, r, th = c.CX, y0+c.s(300), c.s(142), c.s(40)
    bb = [cx-r, cy-r, cx+r, cy+r]
    d.arc(bb, 0, 360, fill=(58,62,62,a), width=th)
    prog = eio(c01((tl-0.45)/1.5))
    sw = 360 * p["pct"]/100.0 * prog
    if sw > 1: d.arc(bb, -90, -90+sw, fill=TEAL+(a,), width=th)
    c.tx(d, cx, cy-c.s(64), "%d%%" % int(p["pct"]*prog), F("H", c.s(92)), WHITE, a)
    c.tx(d, cx, cy+c.s(44), p["label"], F("B", c.s(32)), GREY, a)
    k = c01((tl-2.1)/0.35)
    if k > 0 and p.get("note"):
        c.tx(d, c.CX, y0+c.s(468), p["note"], F("B", int(c.s(36)*(0.75+0.25*back(k)))), GOLD, int(a*k))

# ---------- 03 數字滾動計數卡 ----------
def count(c, img, tl, p):
    x0,y0,w,h,a = c.panel(img, 430, tl)
    if a < 10: return
    d = ImageDraw.Draw(img)
    c.tx(d, c.CX, y0+c.s(34), p["title"], F("B", c.s(44)), WHITE, a)
    prog = eio(c01((tl-0.45)/1.9))
    step = p.get("step", 100)
    val  = int(p["target"]*prog/step)*step
    c.tx(d, c.CX, y0+c.s(128), p.get("prefix","") + format(val, ",") + p.get("suffix",""),
         F("H", c.s(p.get("size",104))), GOLD, a)
    k = c01((tl-2.6)/0.35)
    if k > 0 and p.get("note"):
        c.tx(d, c.CX, y0+c.s(300), p["note"], F("B", int(c.s(38)*(0.8+0.2*back(k)))), TEAL, int(a*k))

# ---------- 04 逐項打勾清單 ----------
def _wrap_card_text(draw, text, font, max_width, max_lines=2):
    text = " ".join(str(text or "").split())
    lines = []
    current = ""
    for char in text:
        candidate = current + char
        if current and draw.textlength(candidate, font=font) > max_width:
            lines.append(current.strip())
            current = char
        else:
            current = candidate
    if current.strip():
        lines.append(current.strip())
    if len(lines) <= max_lines:
        return lines or [""]
    tail = "".join(lines[1:])
    return [lines[0], tail[:14] + ("…" if len(tail) > 14 else "")]


def checklist(c, img, tl, p):
    items = p["items"]
    d = ImageDraw.Draw(img)
    f = F("B", c.s(34))
    wrapped = [_wrap_card_text(d, item, f, c.PW - c.s(176)) for item in items]
    row_heights = [108 + max(0, len(lines) - 1) * 52 for lines in wrapped]
    x0,y0,w,h,a = c.panel(img, 170 + sum(row_heights), tl)
    if a < 10: return
    c.tx(d, c.CX, y0+c.s(30), p["title"], F("B", c.s(44)), WHITE, a)
    row_top = 108
    for i, lines in enumerate(wrapped):
        k = eoc(c01((tl-0.6-i*0.55)/0.55))
        if k <= 0: 
            row_top += row_heights[i]
            continue
        yy = y0 + c.s(row_top)
        bx = x0 + c.s(80)
        al = int(a*k)
        d.rounded_rectangle([bx, yy, bx+c.s(56), yy+c.s(56)], radius=c.s(14),
                            outline=TEAL+(al,), width=4)
        if k > 0.55:
            kk = c01((k-0.55)/0.45)
            p1=(bx+c.s(14), yy+c.s(30)); p2=(bx+c.s(24), yy+c.s(42)); p3=(bx+c.s(44), yy+c.s(14))
            d.line([p1, (p1[0]+(p2[0]-p1[0])*min(1,kk*2), p1[1]+(p2[1]-p1[1])*min(1,kk*2))],
                   fill=TEAL+(al,), width=6)
            if kk > 0.5:
                k2=(kk-0.5)*2
                d.line([p2, (p2[0]+(p3[0]-p2[0])*k2, p2[1]+(p3[1]-p2[1])*k2)], fill=TEAL+(al,), width=6)
        for line_index, line in enumerate(lines):
            d.text((bx+c.s(88), yy+c.s(2 + line_index*48)), line, font=f, fill=WHITE+(al,))
        row_top += row_heights[i]

# ---------- 05 印章蓋下 ----------
def _fit_stamp_font(draw, text, weight, preferred_size, max_width):
    """進場放大時仍讓文字與外框留在畫布內。"""
    size = max(1, int(preferred_size))
    font = F(weight, size)
    width = draw.textlength(text, font=font) if text else 0
    if width <= max_width:
        return font
    size = max(1, int(size * max_width / width))
    font = F(weight, size)
    while size > 1 and draw.textlength(text, font=font) > max_width:
        size -= 1
        font = F(weight, size)
    return font


def stamp(c, img, tl, p):
    d = ImageDraw.Draw(img)
    k = c01((tl-0.25)/0.45)
    if k <= 0: return
    sc = 1.9 - 0.9*eoc(k) if k < 1 else 1.0
    a  = int(245*c01((tl-0.25)/0.3) * c01((p["dur"]-tl)/0.4))
    pad = c.s(56)*sc
    max_text_width = max(1, c.W - 2*pad - c.s(56))
    f1 = _fit_stamp_font(d, p["line1"], "H", int(c.s(p.get("size",76))*sc), max_text_width)
    f2 = _fit_stamp_font(d, p.get("line2", ""), "B", int(c.s(40)*sc), max_text_width)
    cy = c.BOTTOM - c.s(230)
    tw = max(d.textlength(p["line1"], font=f1),
             d.textlength(p.get("line2",""), font=f2) if p.get("line2") else 0)
    box = [c.CX-tw/2-pad, cy-c.s(30)*sc, c.CX+tw/2+pad, cy+c.s(p.get("line2") and 160 or 110)*sc]
    d.rounded_rectangle(box, radius=int(c.s(24)*sc), outline=GOLD+(a,), width=max(3,int(7*sc)))
    d.rounded_rectangle(box, radius=int(c.s(24)*sc), fill=DARK+(int(a*0.80),))
    c.tx(d, c.CX, cy+c.s(6)*sc, p["line1"], f1, GOLD, a)
    if p.get("line2"):
        c.tx(d, c.CX, cy+c.s(112)*sc, p["line2"], f2, WHITE, a)

# ---------- 06 左右對比卡 ----------
def vs(c, img, tl, p):
    x0,y0,w,h,a = c.panel(img, 500, tl)
    if a < 10: return
    d = ImageDraw.Draw(img)
    c.tx(d, c.CX, y0+c.s(30), p["title"], F("B", c.s(44)), WHITE, a)
    cw = (w - c.s(150))//2
    for i, side in enumerate((p["left"], p["right"])):
        k = eoc(c01((tl-0.5-i*0.3)/0.7))
        if k <= 0: continue
        al = int(a*k)
        dx = int((1-k)*c.s(60)) * (1 if i == 0 else -1)
        cx0 = x0 + c.s(40) + i*(cw+c.s(70)) - dx
        col = TEAL if side["ok"] else RED
        d.rounded_rectangle([cx0, y0+c.s(120), cx0+cw, y0+c.s(400)], radius=c.s(22),
                            fill=(col[0]//6, col[1]//6, col[2]//6, al), outline=col+(al,), width=4)
        c.tx(d, cx0+cw/2, y0+c.s(150), "OK" if side["ok"] else "NG", F("H", c.s(46)), col, al)
        c.tx(d, cx0+cw/2, y0+c.s(226), side["big"], F("H", c.s(60)), WHITE, al)
        c.tx(d, cx0+cw/2, y0+c.s(320), side["label"], F("B", c.s(32)), GREY, al)

KIND = dict(bars2=bars2, donut=donut, count=count, checklist=checklist, stamp=stamp, vs=vs)

def render(lay, kind, params, dur, outdir, fps=30):
    c = Ctx(lay); fn = KIND[kind]
    os.makedirs(outdir, exist_ok=True)
    params = dict(params); params["dur"] = dur
    n = int(dur*fps)
    for f in range(n):
        img = Image.new("RGBA", (c.W, c.H), (0,0,0,0))
        fn(c, img, f/fps, params)
        fade = c01((dur - f/fps)/0.35)
        if fade < 1:
            img.putalpha(img.split()[3].point(lambda v: int(v*fade)))
        img.save(os.path.join(outdir, "ov_%04d.png" % f))
    return n

# ---------- 07 計算式逐行揭露（中長片用） ----------
def formula(c, img, tl, p):
    rows = p["rows"]
    x0,y0,w,h,a = c.panel(img, 170 + 96*len(rows), tl)
    if a < 10: return
    d = ImageDraw.Draw(img)
    c.tx(d, c.CX, y0+c.s(28), p["title"], F("B", c.s(42)), WHITE, a)
    fl = F("B", c.s(40))
    for i, (lab, val, hi) in enumerate(rows):
        k = eoc(c01((tl - 0.55 - i*0.62) / 0.55))
        if k <= 0: continue
        al = int(a*k)
        yy = y0 + c.s(112 + i*96)
        dx = int((1-k) * c.s(40))
        col = GOLD if hi else WHITE
        d.text((x0 + c.s(70) + dx, yy + c.s(8)), lab, font=fl, fill=GREY+(al,))
        sc = 1.0 + 0.22*(1-eoc(min(1.0, k*1.4))) if hi else 1.0
        fv = F("H", int(c.s(52)*sc))
        vw = d.textlength(val, font=fv)
        d.text((x0 + w - c.s(70) - vw - dx, yy), val, font=fv, fill=col+(al,))
        if i < len(rows)-1:
            d.line([(x0+c.s(66), yy+c.s(80)), (x0+w-c.s(66), yy+c.s(80))],
                   fill=(70,74,74,int(al*0.7)), width=2)
    if p.get("note"):
        k = c01((tl - 0.6 - len(rows)*0.62) / 0.4)
        if k > 0:
            c.tx(d, c.CX, y0+h-c.s(58), p["note"],
                 F("B", int(c.s(34)*(0.8+0.2*back(k)))), TEAL, int(a*k))

KIND["formula"] = formula

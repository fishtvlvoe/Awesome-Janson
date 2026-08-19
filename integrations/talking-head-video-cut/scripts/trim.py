# -*- coding: utf-8 -*-
"""去長靜音 + 字幕時間軸重映射（skill #39：GAP 0.80 / PAD_END 0.33 / PAD_START 0.12）"""
import os, re, subprocess
from paths import PROJECT as VD, SRC
GAP, PAD_E, PAD_S, TH = 0.80, 0.33, 0.12, "-38dB"
RS = re.compile(r"silence_start:\s*([-\d.]+)")
RE_ = re.compile(r"silence_end:\s*([-\d.]+)")

def detect(src, a, b, gap=GAP):
    """回傳 [(s,e)] 為來源時間軸上的靜音區間"""
    p = subprocess.run(["ffmpeg","-hide_banner","-ss",str(a),"-to",str(b),"-i",SRC[src],
                        "-af","silencedetect=n=%s:d=%s" % (TH, gap),"-f","null",os.devnull],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    starts = [float(x) for x in RS.findall(p.stderr)]
    ends   = [float(x) for x in RE_.findall(p.stderr)]
    out, n = [], min(len(starts), len(ends))
    for i in range(n): out.append((a + starts[i], a + ends[i]))
    if len(starts) > n: out.append((a + starts[-1], b))       # 尾巴沒收尾的靜音
    return out

def trim(spans, gap=GAP):
    """把 spans 中超過 gap 的死空氣剪掉，回傳實際要切的 pieces"""
    pieces, report = [], []
    for src, a, b in spans:
        cur = a
        for s, e in detect(src, a, b, gap):
            s, e = max(s, a), min(e, b)
            if e - s <= gap: continue
            cf, ct = s + PAD_E, e - PAD_S
            if ct - cf < 0.25: continue
            if cf > cur + 0.4: pieces.append((src, round(cur,3), round(cf,3)))
            report.append((src, round(s,2), round(e,2), round(ct-cf,2)))
            cur = ct
        if b - cur > 0.4: pieces.append((src, round(cur,3), round(b,3)))
    return pieces, report

def _piece_spans(spans, pieces):
    """pieces 依 span 順序產生，逐一指派它屬於哪一個 span 索引"""
    idx, out = 0, []
    for psrc, pa, pb in pieces:
        while idx < len(spans):
            ssrc, sa, sb = spans[idx]
            if ssrc == psrc and sa - 1e-6 <= pa and pb <= sb + 1e-6:
                break
            idx += 1
        out.append(min(idx, len(spans) - 1))
    return out

def remap(spans, pieces, lines):
    """把「未修剪 body 時間軸」的字幕，換算到「修剪後 body 時間軸」"""
    pidx = _piece_spans(spans, pieces)
    starts, cum = [], 0.0
    for k, (src, a, b) in enumerate(pieces):
        starts.append((pidx[k], a, b, cum)); cum += b - a

    def old_to_span(t):
        cur = 0.0
        for i, (src, a, b) in enumerate(spans):
            if t <= cur + (b - a) + 1e-6: return i, a + (t - cur)
            cur += b - a
        return len(spans) - 1, spans[-1][2]

    def src_to_new(i, s):
        last = None
        for si, a, b, c0 in starts:
            if si != i: continue
            if s < a: return c0 if last is None else last
            if s <= b: return c0 + (s - a)
            last = c0 + (b - a)
        if last is not None: return last
        for si, a, b, c0 in starts:          # 這個 span 整段被剪掉
            if si > i: return c0
        return cum

    out, pe = [], -1.0
    for st, en, tx in lines:
        s1 = src_to_new(*old_to_span(st))
        e1 = src_to_new(*old_to_span(en))
        s1 = max(s1, pe + 0.06)
        if e1 - s1 < 0.5: e1 = s1 + 0.5
        out.append((round(s1, 2), round(e1, 2), tx)); pe = e1
    body = round(cum, 2)
    return [(a, min(b, body), t) for a, b, t in out], body

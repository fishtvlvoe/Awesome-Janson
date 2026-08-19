# -*- coding: utf-8 -*-
"""中長片渲染器：中性片頭 + 版面每~18秒交替(#33) + 學員字卡 + CTA(含對象聲明) + BGM"""
import os, sys, subprocess, importlib, shutil
import trim as TRIM
import anim_lib
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from paths import PROJECT as VD, SRC, FONT_B, FONT_H, BGM, CAM, SLIDE, ass_fontsdir
OUT  = os.path.join(VD, "工作暫存", "長片輸出")
CARD = os.path.join(VD, "工作暫存", "長片片頭")
for d in (OUT, CARD): os.makedirs(d, exist_ok=True)

INTRO_D, CTA_D, SEGMAX = 2.0, 8.0, 18.0
BRAND_DEFAULT = "圭話行銷 ‧ adHub"
BRAND  = BRAND_DEFAULT
CTA_DEFAULT = ("想把這套做進你自己的帳號嗎？\\N雙 11 實戰陪跑班\\Nad-hub.net/event_2608"
       "\\N\\N僅收品牌商、電商與企業行銷團隊\\N代理商與代操恕不受理")
TEAL = (20, 163, 160)

def run(a, cwd=None):
    p = subprocess.run(a, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd)
    if p.returncode:
        print("FAIL:", " ".join(str(x) for x in a[:6])); print(p.stderr[-1600:], flush=True)
        raise RuntimeError("ffmpeg")

def ts(t): return "%d:%02d:%05.2f" % (int(t//3600), int(t%3600//60), t%60)

def make_card(path, w, h, l1, l2, topic):
    img = Image.new("RGB", (w, h), (14, 26, 28)); d = ImageDraw.Draw(img)
    for y in range(h):
        k = y/h
        d.line([(0,y),(w,y)], fill=(int(14+TEAL[0]*0.42*(1-k)), int(26+TEAL[1]*0.42*(1-k)), int(28+TEAL[2]*0.42*(1-k))))
    big = int(w*0.098) if w < h else int(h*0.115)
    sm, lab = int(big*0.74), int(big*0.30)
    def fit(txt, fpath, size, maxw, floor=26):
        f = ImageFont.truetype(fpath, size)
        while size > floor and d.textlength(txt, font=f) > maxw:
            size -= 2
            f = ImageFont.truetype(fpath, size)
        return f
    PAD = int(w*0.08)
    x1 = int(w*0.10); y1 = int(h*0.44) if w < h else int(h*0.34)
    x2 = x1 + int(w*0.075)
    f1 = fit(l1, FONT_H, big, w - x1 - PAD)
    f2 = fit(l2, FONT_B, sm,  w - x2 - PAD)
    f3 = fit(max(topic, BRAND, key=len), FONT_B, lab, int(w*0.84))
    def st(xy, t, f, an="la", s=None):
        d.text(xy, t, font=f, fill=(255,255,255), anchor=an,
               stroke_width=s or max(4, f.size//13), stroke_fill=(0,0,0))
    st((w//2, int(h*0.13)), topic, f3, "ma", 3)
    st((x1, y1), l1, f1)
    b1 = d.textbbox((x1,y1), l1, font=f1)
    d.line([(b1[0]-6,b1[3]+14),(b1[2]+6,b1[3]+14)], fill=(255,255,255), width=max(5,f1.size//14))
    y2 = b1[3]+int(f1.size*0.62)
    st((x2, y2), l2, f2)
    b2 = d.textbbox((x2,y2), l2, font=f2)
    d.line([(b2[0]-6,b2[3]+12),(b2[2]+6,b2[3]+12)], fill=(255,255,255), width=max(4,f2.size//15))
    st((w//2, int(h*0.90)), BRAND, f3, "ma", 3)
    over = [t for t, bb in ((l1,b1),(l2,b2)) if bb[2] > w - int(w*0.03)]
    if over: print("    !! \u5716\u5361\u6ea2\u51fa\uff1a%s" % over, flush=True)
    img.save(path)

# 雙畫面錄影（課程／講座）：A 講師上投影片下、B 投影片放大講師縮右上、C 只放講師
# 單機位自錄（商品／產品介紹）：F 全幅、P punch-in 特寫
LAY = {
 "V": {"A": ("[0:v]fps=30,split=3[bg0][s0][c0];[bg0]"+SLIDE+",scale=1080:1920:force_original_aspect_ratio=increase,"
             "crop=1080:1920,boxblur=28:2,eq=brightness=-0.30:saturation=0.7[bg];"
             "[s0]"+SLIDE+",scale=1000:-2,pad=iw+8:ih+8:4:4:0x14a3a0[sl];"
             "[c0]"+CAM+",scale=760:-2,pad=iw+8:ih+8:4:4:0x14a3a0[cm];"
             "[bg][cm]overlay=(W-w)/2:400[t1];[t1][sl]overlay=(W-w)/2:900"),
       "B": ("[0:v]fps=30,split=3[bg0][s0][c0];[bg0]"+SLIDE+",scale=1080:1920:force_original_aspect_ratio=increase,"
             "crop=1080:1920,boxblur=28:2,eq=brightness=-0.30:saturation=0.7[bg];"
             "[s0]"+SLIDE+",scale=1060:-2,pad=iw+8:ih+8:4:4:0x14a3a0[sl];"
             "[c0]"+CAM+",scale=420:-2,pad=iw+8:ih+8:4:4:0x14a3a0[cm];"
             "[bg][sl]overlay=(W-w)/2:760[t1];[t1][cm]overlay=W-w-40:330"),
       "C": ("[0:v]fps=30,split=2[bg0][c0];[bg0]" + SLIDE + ",scale=1080:1920:force_original_aspect_ratio=increase,"
             "crop=1080:1920,boxblur=34:2,eq=brightness=-0.34:saturation=0.6[bg];"
             "[c0]" + CAM + ",scale=980:-2,pad=iw+10:ih+10:5:5:0x14a3a0[cm];"
             "[bg][cm]overlay=(W-w)/2:(H-h)/2-120"),
       # F：全幅（自錄影片用）。來源不是 9:16 時自動 letterbox 到模糊底
       "F": ("[0:v]fps=30,split=2[bg0][c0];[bg0]scale=1080:1920:force_original_aspect_ratio=increase,"
             "crop=1080:1920,boxblur=34:2,eq=brightness=-0.34:saturation=0.6[bg];"
             "[c0]scale=1080:1920:force_original_aspect_ratio=decrease[cm];"
             "[bg][cm]overlay=(W-w)/2:(H-h)/2"),
       # P：punch-in 特寫，等於 F 再放大 1.18 倍（自錄影片單機位靠這個換畫面）
       "P": ("[0:v]fps=30,split=2[bg0][c0];[bg0]scale=1080:1920:force_original_aspect_ratio=increase,"
             "crop=1080:1920,boxblur=34:2,eq=brightness=-0.34:saturation=0.6[bg];"
             "[c0]scale=1274:2266:force_original_aspect_ratio=decrease,"
             "crop=min(iw\\,1080):min(ih\\,1920)[cm];"
             "[bg][cm]overlay=(W-w)/2:(H-h)/2")},
 "H": {"A": ("[0:v]fps=30,split=3[bg0][s0][c0];[bg0]"+SLIDE+",scale=1920:1080:force_original_aspect_ratio=increase,"
             "crop=1920:1080,boxblur=28:2,eq=brightness=-0.30:saturation=0.7[bg];"
             "[s0]"+SLIDE+",scale=1020:-2,pad=iw+8:ih+8:4:4:0x14a3a0[sl];"
             "[c0]"+CAM+",scale=430:-2,pad=iw+8:ih+8:4:4:0x14a3a0[cm];"
             "[bg][sl]overlay=70:216[t1];[t1][cm]overlay=1330:390"),
       "B": ("[0:v]fps=30,split=3[bg0][s0][c0];[bg0]"+SLIDE+",scale=1920:1080:force_original_aspect_ratio=increase,"
             "crop=1920:1080,boxblur=28:2,eq=brightness=-0.30:saturation=0.7[bg];"
             "[s0]"+SLIDE+",scale=1230:-2,pad=iw+8:ih+8:4:4:0x14a3a0[sl];"
             "[c0]"+CAM+",scale=360:-2,pad=iw+8:ih+8:4:4:0x14a3a0[cm];"
             "[bg][sl]overlay=60:150[t1];[t1][cm]overlay=1500:700"),
       "C": ("[0:v]fps=30,split=2[bg0][c0];[bg0]" + SLIDE + ",scale=1920:1080:force_original_aspect_ratio=increase,"
             "crop=1920:1080,boxblur=34:2,eq=brightness=-0.34:saturation=0.6[bg];"
             "[c0]" + CAM + ",scale=880:-2,pad=iw+10:ih+10:5:5:0x14a3a0[cm];"
             "[bg][cm]overlay=(W-w)/2:(H-h)/2-90"),
       "F": ("[0:v]fps=30,split=2[bg0][c0];[bg0]scale=1920:1080:force_original_aspect_ratio=increase,"
             "crop=1920:1080,boxblur=34:2,eq=brightness=-0.34:saturation=0.6[bg];"
             "[c0]scale=1920:1080:force_original_aspect_ratio=decrease[cm];"
             "[bg][cm]overlay=(W-w)/2:(H-h)/2"),
       "P": ("[0:v]fps=30,split=2[bg0][c0];[bg0]scale=1920:1080:force_original_aspect_ratio=increase,"
             "crop=1920:1080,boxblur=34:2,eq=brightness=-0.34:saturation=0.6[bg];"
             "[c0]scale=2266:1274:force_original_aspect_ratio=decrease,"
             "crop=min(iw\\,1920):min(ih\\,1080)[cm];"
             "[bg][cm]overlay=(W-w)/2:(H-h)/2")},
}
ASS = {"V": dict(sub=58, cta=52, topic=32, card=46, suby=1580, topicy=140, ctay=900,
                 brandy=1858, cardy=1300, mg=70, w=1080, h=1920),
       "H": dict(sub=48, cta=44, topic=28, card=40, suby=968, topicy=52, ctay=480,
                 brandy=1046, cardy=760, mg=60, w=1920, h=1080)}

def build_ass(P, body, total, lines, cards, topic):
    head = """[Script Info]
ScriptType: v4.00+
PlayResX: %d
PlayResY: %d
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,GenSenRounded2 TW B,%d,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,%d,2,5,%d,%d,0,1
Style: Topic,GenSenRounded2 TW B,%d,&H00E8E8E8,&H00E8E8E8,&H00201008,&H00000000,0,0,0,0,100,100,3,0,1,3,1,5,%d,%d,0,1
Style: CTA,GenSenRounded2 TW B,%d,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,2,0,1,%d,2,5,%d,%d,0,1
Style: Card,GenSenRounded2 TW B,%d,&H0000D6FF,&H0000D6FF,&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,%d,2,5,%d,%d,0,1
Style: Brand,GenSenRounded2 TW B,%d,&H0099958D,&H0099958D,&H00000000,&H00000000,0,0,0,0,100,100,2,0,1,2,0,5,%d,%d,0,1
Style: Box,Arial,20,&H00000000,&H00000000,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" % (P["w"], P["h"], P["sub"], max(4,P["sub"]//12), P["mg"], P["mg"],
       P["topic"], P["mg"], P["mg"], P["cta"], max(4,P["cta"]//12), P["mg"], P["mg"],
       P["card"], max(4,P["card"]//12), P["mg"], P["mg"], P["topic"], P["mg"], P["mg"])
    ev, cx = [], P["w"]//2
    def add(st, en, sty, tx, x, y, ex=""):
        ev.append("Dialogue: 0,%s,%s,%s,,0,0,0,,{\\pos(%d,%d)%s}%s" % (ts(st), ts(en), sty, x, y, ex, tx))
    add(0.0, body, "Topic", topic, cx, P["topicy"])
    for st, en, tx in lines:
        add(min(st, body), min(en, body), "Sub", tx, cx, P["suby"])
    for st, en, tx in cards:                       # 學員發言改字卡（黃字）
        add(min(st, body), min(en, body), "Card", tx, cx, P["cardy"], "\\fad(180,180)")
    ev.append("Dialogue: 0,%s,%s,Box,,0,0,0,,{\\pos(0,0)\\p1\\c&H120A06&\\alpha&H26&\\bord0\\shad0\\fad(250,0)}"
              "m 0 0 l %d 0 l %d %d l 0 %d{\\p0}" % (ts(body), ts(total), P["w"], P["w"], P["h"], P["h"]))
    add(body, total, "CTA", CTA, cx, P["ctay"], "\\fad(250,0)")
    add(0.0, total, "Brand", BRAND, cx, P["brandy"])
    return head + "\n".join(ev) + "\n"

def split_points(spans, lines, segmax=SEGMAX):
    """把 span 依字幕空隙切成 <=segmax 秒的小段，讓版面每段換一次(#33)"""
    gaps = []
    for i in range(len(lines)-1):
        if lines[i+1][0] - lines[i][1] > 0.12:
            gaps.append((lines[i][1] + lines[i+1][0]) / 2)
    pieces, cur = [], 0.0
    for src, a, b in spans:
        d, off = b - a, cur
        n = max(1, int(round(d / segmax)))
        step, prev = d / n, a
        for k in range(1, n):
            want = off + step*k
            near = min(gaps, key=lambda g: abs(g-want)) if gaps else want
            cut = a + (near - off) if abs(near-want) < 2.5 else a + step*k
            cut = max(prev+3.0, min(cut, b-3.0))
            pieces.append((src, prev, cut)); prev = cut
        pieces.append((src, prev, b)); cur += d
    return pieces

def render(tag, cfg):
    spans, cards = cfg.SPANS, getattr(cfg, "CARDS", [])
    global INTRO_D, CTA_D, CTA, SUBSCALE, BRAND
    INTRO_D = getattr(cfg, "INTRO_D", 2.0)
    CTA_D   = getattr(cfg, "CTA_D", 8.0)
    CTA     = getattr(cfg, "CTA", CTA_DEFAULT)
    SUBSCALE = getattr(cfg, "SUB_SCALE", 1.0)
    BRAND    = getattr(cfg, "BRAND", BRAND_DEFAULT)
    raw, rep = TRIM.trim(spans)                       # skill #39：砍掉 >0.80s 的死空氣
    lines, body = TRIM.remap(spans, raw, cfg.LINES)
    if cards: cards, _ = TRIM.remap(spans, raw, cards)
    anims = getattr(cfg, "ANIM", [])
    if anims:
        pts, _ = TRIM.remap(spans, raw, [(a0, a0+0.1, "") for a0,_,_,_ in anims])
        anims = [(pts[i][0], anims[i][1], anims[i][2], anims[i][3]) for i in range(len(anims))]
    total = round(body + CTA_D, 2)
    pieces = []                                       # 版面以「修剪後的自然段」為單位交替
    for src, a, b in raw:
        d = b - a
        n = max(1, int(round(d / SEGMAX)))
        st = d / n
        for k in range(n):
            pieces.append((src, round(a+st*k,3), round(a+st*(k+1),3)))
    print("    去空氣 %d 處共 %.1fs" % (len(rep), sum(r[3] for r in rep)), flush=True)
    print("--- %s  body=%.2fs  片段=%d  全長=%.2fs" % (tag, body, len(pieces), total+INTRO_D), flush=True)
    parts = []
    for i, (src, a, b) in enumerate(pieces):
        p = os.path.join(OUT, "%s_p%02d.mp4" % (tag, i))
        run(["ffmpeg","-y","-loglevel","error","-ss",str(a),"-to",str(b),"-i",SRC[src],
             "-c:v","libx264","-preset","medium","-crf","16","-c:a","aac","-b:a","192k",
             "-ar","48000","-ac","2","-vsync","cfr","-r","30",p])
        parts.append(p)
    for suf, lay in (("直式_9x16","V"), ("橫式_16x9","H")):
        P = dict(ASS[lay]); name = "%s_%s" % (tag, suf)
        if SUBSCALE != 1.0:
            P["sub"]  = int(round(P["sub"]  * SUBSCALE))
            P["card"] = int(round(P["card"] * SUBSCALE))
            P["mg"]   = 48 if lay == "V" else 60
        # 逐段套版面（交替 A/B）
        subs = []
        for i, p in enumerate(parts):
            o = os.path.join(OUT, "%s_%s_l%02d.mp4" % (tag, lay, i))
            seqv = getattr(cfg, "LAYOUTS", None) or ["A", "B"]
            vf = LAY[lay][seqv[i % len(seqv)]] + "[v]"
            run(["ffmpeg","-y","-loglevel","error","-i",p,"-filter_complex",vf,
                 "-map","[v]","-map","0:a","-c:v","libx264","-preset","medium","-crf","18",
                 "-pix_fmt","yuv420p","-r","30","-c:a","aac","-b:a","192k",o])
            subs.append(o)
        lst = os.path.join(OUT, "%s_%s_list.txt" % (tag, lay))
        open(lst,"w",encoding="utf-8").write("".join("file '%s'\n" % x.replace("\\","/") for x in subs))
        base = os.path.join(OUT, "%s_base.mp4" % name)
        run(["ffmpeg","-y","-loglevel","error","-f","concat","-safe","0","-i",lst,
             "-c:v","libx264","-preset","medium","-crf","18","-c:a","aac","-b:a","192k",base])
        sub = os.path.join(OUT, "sub_%s.ass" % name)
        open(sub,"w",encoding="utf-8-sig").write(build_ass(P, body, total, lines, cards, cfg.TOPIC))
        bodymp4 = os.path.join(OUT, "%s_body.mp4" % name)
        run(["ffmpeg","-y","-loglevel","error","-i",base,"-filter_complex",
             "[0:v]tpad=stop_mode=clone:stop_duration=%s,subtitles='%s':fontsdir='C\\:/videoedit/_fonts'[v]"
             % (CTA_D, os.path.basename(sub), ass_fontsdir()),
             "-filter_complex_threads","1","-map","[v]","-map","0:a",
             "-af","apad=whole_dur=%s,afade=t=out:st=%s:d=1.2" % (total, total-1.2),
             "-t",str(total),"-c:v","libx264","-preset","medium","-crf","18",
             "-pix_fmt","yuv420p","-r","30","-c:a","aac","-b:a","192k",bodymp4], cwd=OUT)
        if anims:
            seqs = []
            for i, (ast, adur, kind, params) in enumerate(anims):
                od = os.path.join(VD, "工作暫存", "動畫", "%s_%s_%d" % (tag, lay, i))
                if not (os.path.isdir(od) and len(os.listdir(od)) == int(adur*30)):
                    if os.path.isdir(od): shutil.rmtree(od)
                    anim_lib.render(lay, kind, params, adur, od)
                seqs.append((od, round(ast, 2), adur))
            aargs = ["ffmpeg","-y","-loglevel","error","-i",bodymp4]
            for od,_,_ in seqs: aargs += ["-framerate","30","-i",os.path.join(od,"ov_%04d.png")]
            fc, prev = [], "0:v"
            for i,(od,st,du) in enumerate(seqs):
                fc.append("[%d:v]setpts=PTS-STARTPTS+%s/TB[o%d]" % (i+1, st, i))
            for i,(od,st,du) in enumerate(seqs):
                lbl = "v" if i == len(seqs)-1 else "av%d" % i
                fc.append("[%s][o%d]overlay=0:0:enable='between(t,%s,%s)'[%s]"
                          % (prev, i, st, round(st+du-0.03,2), lbl))
                prev = lbl
            av = os.path.join(OUT, "%s_anim.mp4" % name)
            aargs += ["-filter_complex",";".join(fc),"-map","[v]","-map","0:a",
                      "-c:v","libx264","-preset","medium","-crf","18","-pix_fmt","yuv420p",
                      "-r","30","-c:a","aac","-b:a","192k",av]
            run(aargs)
            bodymp4 = av
        cd = os.path.join(CARD, name + ".png")
        make_card(cd, P["w"], P["h"], cfg.TITLE[0], cfg.TITLE[1], cfg.TOPIC)
        out = os.path.join(OUT, name + ".mp4")
        run(["ffmpeg","-y","-loglevel","error","-loop","1","-t",str(INTRO_D),"-i",cd,
             "-f","lavfi","-t",str(INTRO_D),"-i","anullsrc=r=48000:cl=stereo",
             "-i",bodymp4,"-i",BGM,"-filter_complex",
             "[0:v]scale=%d:%d,fps=30,setsar=1,format=yuv420p,setpts=PTS-STARTPTS[iv];"
             "[1:a]asetpts=PTS-STARTPTS[ia];[2:v]setpts=PTS-STARTPTS,setsar=1[bv];"
             "[2:a]asetpts=PTS-STARTPTS[ba];[iv][ia][bv][ba]concat=n=2:v=1:a=1[v][a0];"
             "[a0]loudnorm=I=-15:TP=-1.5:LRA=11[voc];"
             "[3:a]loudnorm=I=-32:TP=-9,afade=t=in:st=0:d=0.8,afade=t=out:st=%s:d=1.6[bg];"
             "[voc][bg]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.94[a]"
             % (P["w"], P["h"], round(total+INTRO_D-1.6,2)),
             "-map","[v]","-map","[a]","-c:v","libx264","-preset","medium","-crf","18",
             "-pix_fmt","yuv420p","-r","30","-c:a","aac","-b:a","192k",
             "-movflags","+faststart","-t",str(round(total+INTRO_D,2)),out])
        print("    OK %s  %.1f MB" % (name, os.path.getsize(out)/1048576), flush=True)

if __name__ == "__main__":
    for tag in sys.argv[1:]:
        render(tag, importlib.import_module(tag + "_cfg"))
    print("LONG_DONE", flush=True)

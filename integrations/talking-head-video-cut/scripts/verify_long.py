# -*- coding: utf-8 -*-
import os, sys, json, subprocess, io, re
from PIL import Image
sys.path.insert(0, r"C:\videoedit\_whisper")
O = r"C:\videoedit\adhub\20250902廣告進階\工作暫存\長片輸出"
T = r"C:\videoedit\adhub\20250902廣告進階\工作暫存\驗證"
os.makedirs(T, exist_ok=True)
INTRO, CTA = 2.0, 8.0
RS = re.compile(r"silence_start:\s*([\d.]+)")
BOX = {"V": dict(sub=(70,1500,1010,1690), card=(70,1200,1010,1420)),
       "H": dict(sub=(60,900,1860,1050),  card=(60,700,1860,860))}
res = []
for tag in sys.argv[1:]:
    cfg = __import__(tag + "_cfg")
    for suf, lay in (("直式_9x16","V"), ("橫式_16x9","H")):
        f = os.path.join(O, "%s_%s.mp4" % (tag, suf))
        if not os.path.exists(f): res.append("%s %s 缺檔" % (tag,suf)); continue
        j = json.loads(subprocess.run(["ffprobe","-v","error","-print_format","json","-show_entries",
            "stream=width,height,codec_type,duration:format=duration",f],
            capture_output=True,text=True,encoding="utf-8").stdout)
        v = [s for s in j["streams"] if s["codec_type"]=="video"][0]
        au= [s for s in j["streams"] if s["codec_type"]=="audio"][0]
        d = float(j["format"]["duration"]); ad = float(au.get("duration",0))
        # 長靜音只看內容段（扣掉片頭與 CTA）
        sd = subprocess.run(["ffmpeg","-hide_banner","-ss",str(INTRO),"-to",str(d-CTA),"-i",f,
                             "-af","silencedetect=n=-38dB:d=0.9","-f","null",os.devnull],
                            capture_output=True,text=True,encoding="utf-8",errors="replace")
        sil = [float(x)+INTRO for x in RS.findall(sd.stderr)]
        res.append("%s %-11s %sx%s %6.2fs drift %.2f  內容段長靜音 %d %s"
                   % (tag, suf, v["width"], v["height"], d, abs(d-ad), len(sil),
                      ("@ "+", ".join("%.1f"%x for x in sil[:6])) if sil else ""))
        # 字卡是否出現、有沒有壓到字幕
        for cst, cen, ctx in getattr(cfg, "CARDS", [])[:4]:
            pass
        for t, what in ((1.0,"片頭"), (INTRO+25,"內容a"), (d-CTA-20,"內容b"), (d-4,"CTA")):
            p = os.path.join(T, "%s%s%d.png" % (tag,lay,int(t)))
            subprocess.run(["ffmpeg","-y","-loglevel","error","-ss",str(round(t,2)),"-i",f,"-frames:v","1",p],check=True)
            im = Image.open(p).convert("L")
            px = list(im.crop(BOX[lay]["sub"]).getdata())
            res.append("    t=%6.1f %-5s 字幕帶 白像素=%6d" % (t, what, sum(1 for x in px if x>210)))
io.open(os.path.join(r"C:\videoedit\_whisper","long_verify.txt"),"w",encoding="utf-8").write("\n".join(res))
print("\n".join(r for r in res if not r.startswith("    ")))

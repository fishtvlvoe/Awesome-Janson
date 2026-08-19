# -*- coding: utf-8 -*-
"""========== 只要改這個檔，整套引擎就能搬到任何一台電腦 ==========

Windows 寫法： PROJECT = r"C:\\videoedit\\myproject"
macOS   寫法： PROJECT = "/Users/你的帳號/videoedit/myproject"
路徑一律用 os.path.join 組合，不要自己接斜線。
"""
import os

# 1) 專案資料夾：底下會自動長出 工作暫存/ 與 _成品/
PROJECT = os.environ.get("VE_PROJECT", r"C:\videoedit\adhub\demo")

# 2) 字型資料夾（放 .otf/.ttf）＋兩個字重的完整檔名
FONT_DIR = os.environ.get("VE_FONTS", r"C:\videoedit\_fonts")
FONT_B   = os.path.join(FONT_DIR, "GenSenRounded2TW-B.otf")   # Bold
FONT_H   = os.path.join(FONT_DIR, "GenSenRounded2TW-H.otf")   # Heavy
# ASS 字幕用的「字型完整名稱」，不是家族名稱。用 ffmpeg -loglevel verbose 看 fontselect 確認
FONT_ASS = "GenSenRounded2 TW B"

# 3) 背景音樂（用 bgm_gen.py 產生，或放自己的無版權音樂）
BGM = os.environ.get("VE_BGM", r"C:\videoedit\_bgm\bed_A_upbeat.wav")

# 4) 來源錄影：自己取短代號，設定檔裡的 SPANS 就用這個代號
SRC = {
    "a1": os.path.join(PROJECT, "recording_01.mp4"),
    "a2": os.path.join(PROJECT, "recording_02.mp4"),
}

# 5) 畫面幾何 —— 依你的錄影型態二選一
#
# 【模式一】雙畫面錄影（課程、講座、線上會議側錄：左投影片＋右講師）
#   用 geo 工具量出分隔線 x、講師鏡頭、投影片區，填在這裡。每一場都要重量一次。
#   可用版面：A / B / C
SEPARATOR_X = 1440
CAM   = "crop=472:267:1448:406"     # 講師鏡頭
SLIDE = "crop=1440:900:0:90"        # 投影片區
#
# 【模式二】單機位自錄（商品開箱、產品介紹、手機直拍、對鏡頭說話）
#   沒有投影片，也不用量幾何。把上面三行換成下面三行即可：
#
# SEPARATOR_X = 0
# CAM   = "null"      # ffmpeg 的 null filter = 原封不動通過
# SLIDE = "null"
#
#   可用版面：F（全幅）/ P（punch-in 特寫）。單機位靠 F↔P 交替來滿足
#   「每 10–20 秒換一次畫面」這條規則。詳見 SKILL.md〈模式二〉。

def ass_fontsdir():
    """ffmpeg 的 subtitles filter 需要跳脫過的路徑"""
    p = FONT_DIR.replace("\\", "/")
    if len(p) > 1 and p[1] == ":":
        p = p[0] + "\\:" + p[2:]
    return p

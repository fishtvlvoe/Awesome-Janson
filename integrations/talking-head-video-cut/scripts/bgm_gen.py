# -*- coding: utf-8 -*-
"""EP4 BGM 產生器 - 純合成墊底音樂，零授權疑慮
規格：skill #34 強起（前 3 秒要有力度）／#17 固定音量／風格檔 全程鋪滿
"""
import numpy as np, os, subprocess, wave

SR, BPM = 48000, 108
BEAT = 60.0 / BPM
BAR  = BEAT * 4
BARS = 28                      # 28 小節 ~= 62.2s，比最長影片還長，不用 loop
DUR  = BAR * BARS
N    = int(SR * DUR)
L    = np.zeros(N); R = np.zeros(N)

def put(buf, start, sig, gain=1.0):
    i = int(start * SR)
    if i >= len(buf): return
    m = min(len(sig), len(buf) - i)
    buf[i:i+m] += sig[:m] * gain

def adsr(nlen, a, d, s, r):
    e = np.ones(nlen)
    ai, di, ri = int(a*SR), int(d*SR), int(r*SR)
    if ai: e[:ai] = np.linspace(0, 1, ai)
    if di: e[ai:ai+di] = np.linspace(1, s, di)
    e[ai+di:] = s
    if ri and ri < nlen: e[-ri:] *= np.linspace(1, 0, ri)
    return e

def pluck(f, dur, amp=0.25, decay=6.0):
    nn = int(dur*SR); tt = np.arange(nn)/SR
    y = (np.sin(2*np.pi*f*tt) + 0.35*np.sin(4*np.pi*f*tt) + 0.15*np.sin(6*np.pi*f*tt))
    return y * np.exp(-decay*tt) * amp

def pad(f, dur, amp=0.12):
    nn = int(dur*SR); tt = np.arange(nn)/SR
    y = np.sin(2*np.pi*f*tt) + 0.5*np.sin(2*np.pi*f*1.005*tt) + 0.3*np.sin(2*np.pi*f*0.995*tt)
    return y * adsr(nn, 0.18, 0.10, 0.85, 0.22) * amp

def bass(f, dur, amp=0.30):
    nn = int(dur*SR); tt = np.arange(nn)/SR
    y = np.sin(2*np.pi*f*tt) + 0.25*np.sin(4*np.pi*f*tt)
    return y * adsr(nn, 0.008, 0.06, 0.75, 0.09) * amp

def kick(amp=0.55):
    nn = int(0.16*SR); tt = np.arange(nn)/SR
    f = 130*np.exp(-28*tt) + 46
    return np.sin(2*np.pi*np.cumsum(f)/SR) * np.exp(-24*tt) * amp

def shaker(amp=0.10, dur=0.055):
    nn = int(dur*SR)
    x = np.random.RandomState(7).randn(nn)
    x = np.convolve(x, [1, -0.92], mode="same")          # 高通感
    return x * np.exp(-45*np.arange(nn)/SR) * amp

def bell(f, dur=1.6, amp=0.22):
    nn = int(dur*SR); tt = np.arange(nn)/SR
    y = np.sin(2*np.pi*f*tt) + 0.5*np.sin(2*np.pi*f*2.76*tt) + 0.25*np.sin(2*np.pi*f*5.4*tt)
    return y * np.exp(-2.6*tt) * amp

# I - V - vi - IV in C
PROG = [
    dict(bs=65.41,  ch=[261.63, 329.63, 392.00]),   # C
    dict(bs=98.00,  ch=[246.94, 293.66, 392.00]),   # G/B
    dict(bs=110.00, ch=[261.63, 329.63, 440.00]),   # Am
    dict(bs=87.31,  ch=[261.63, 349.23, 440.00]),   # F
]
SH = shaker()

for b in range(BARS):
    c   = PROG[b % 4]
    t0  = b * BAR
    # 低音：1、3 拍
    for k in (0, 2):
        put(L, t0+k*BEAT, bass(c["bs"], BEAT*1.9), 0.9)
        put(R, t0+k*BEAT, bass(c["bs"], BEAT*1.9), 0.9)
    # 和弦墊：整小節
    for j, f in enumerate(c["ch"]):
        p = pad(f, BAR*0.98)
        put(L, t0, p, 1.0 - 0.25*j)
        put(R, t0, p, 0.75 + 0.25*j)
    # 琶音：8 分音符，稍微偏左
    for k in range(8):
        f = c["ch"][[0,1,2,1,0,1,2,1][k]] * (2.0 if k in (2,6) else 1.0)
        pk = pluck(f, BEAT*0.62, amp=0.20 if k % 2 == 0 else 0.13)
        put(L, t0+k*BEAT/2, pk, 1.05); put(R, t0+k*BEAT/2, pk, 0.80)
    # 鼓：1、3 拍
    for k in (0, 2):
        kk = kick()
        put(L, t0+k*BEAT, kk); put(R, t0+k*BEAT, kk)
    # 沙鈴：8 分
    for k in range(8):
        g = 1.0 if k % 2 == 0 else 0.55
        put(L, t0+k*BEAT/2, SH, g*0.9); put(R, t0+k*BEAT/2, SH, g*1.1)

# 強起：第 0 秒疊鈴聲 + 低音重擊（#34 前 3 秒要有力度）
for f, g in ((1046.50, 1.0), (1567.98, 0.6), (2093.00, 0.35)):
    bl = bell(f)
    put(L, 0.0, bl, g); put(R, 0.0, bl, g*0.9)
put(L, 0.0, kick(0.8)); put(R, 0.0, kick(0.8))

# 收尾 0.5 秒淡出讓 loop 接得順
fo = int(0.5*SR)
for buf in (L, R):
    buf[-fo:] *= np.linspace(1, 0, fo)
    buf[:int(0.02*SR)] *= np.linspace(0, 1, int(0.02*SR))

# 密度處理：先推高再 tanh 軟限幅，把 RMS 拉起來（#34 前 3 秒 mean 約 -10dB 等級）
peak = max(np.abs(L).max(), np.abs(R).max())
L, R = L/peak, R/peak
DRIVE = 3.6
L = np.tanh(L*DRIVE)/np.tanh(DRIVE)
R = np.tanh(R*DRIVE)/np.tanh(DRIVE)
peak = max(np.abs(L).max(), np.abs(R).max())
L, R = L/peak*0.89, R/peak*0.89

OUT = r"C:\videoedit\_bgm"
os.makedirs(OUT, exist_ok=True)
wav = os.path.join(OUT, "bed_A_upbeat.wav")
inter = np.empty(N*2, dtype=np.int16)
inter[0::2] = (L*32767).astype(np.int16)
inter[1::2] = (R*32767).astype(np.int16)
with wave.open(wav, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(inter.tobytes())
print("WAV", wav, round(DUR,2), "s")

mp3 = os.path.join(OUT, "bed_A_upbeat.mp3")
subprocess.run(["ffmpeg","-y","-loglevel","error","-i",wav,"-c:a","libmp3lame","-b:a","192k",mp3],check=True)
print("MP3", mp3, round(os.path.getsize(mp3)/1024), "KB")

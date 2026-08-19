# 操作流程說明

給人看的一份。從「我剛下載這包」到「我交出第一支影片」，中間要做什麼。
（AI 要看的是 `SKILL.md`，不是這一份。）

---

## 一張圖

```
① 選路線 ──→ ② 裝環境 ──→ ③ 放檔案 ──→ ④ 填 paths.py
                                              │
                                              ▼
   ⑧ 交付 ←── ⑦ 驗收 ←── ⑥ 算圖 ←── ⑤ 跟 AI 說第一句話
```

前四步是一次性的，做完就不用再做。第五步之後每支影片重複一次。

---

## ① 先選路線

| 你的情況 | 走這條 | 能不能出 mp4 |
|---|---|---|
| 不想碰終端機，用 Claude 桌面版 | **A：Claude 桌面版 Cowork** | ✅ |
| 習慣終端機，用 Claude | **B：Claude Code** | ✅ |
| 習慣終端機，用 ChatGPT / Codex | **C：Codex CLI** | ✅ |
| 只有網頁版 ChatGPT / Claude | **D：純對話** | ❌ 只能做到設定檔 |

**Claude 和 Codex 在剪片這件事上沒有能力差異**，兩邊都能讀檔、跑 ffmpeg、寫設定檔、
看 log 自己除錯。差別只有「skill 放哪個資料夾」。選你已經在付錢的那一個就好。

路線 D 不是不能用，是分工不同：用它盤點內容、選段落、寫字幕分句，
然後把結果拿到自己電腦上跑。手冊第 1-4 節說明這個混用法為什麼最省錢。

---

## ② 裝環境（一次性）

### macOS

```bash
brew install python ffmpeg
pip3 install faster-whisper opencc-python-reimplemented pillow numpy
ffmpeg -filters | grep subtitles     # 要有輸出
```

### Windows

1. Python 3.10+ 從官網安裝，安裝時**勾選 Add to PATH**
2. ffmpeg 用 Gyan 的 full build，解壓後把 `bin` 資料夾加進 PATH
3. 開 PowerShell：

```powershell
pip install faster-whisper opencc-python-reimplemented pillow numpy
ffmpeg -filters | findstr subtitles   # 要有輸出
```

`subtitles` 沒出現就是 ffmpeg 版本不對（沒帶 libass），換 full build。
**這一條沒過，後面字幕一定燒不上去。**

### 字型

準備一套有 Bold 與 Heavy 兩個字重的中文字型，放進一個資料夾。
我們用 GenSenRounded2 TW（思源柔黑，SIL Open Font License，可商用）。

---

## ③ 放檔案

### 路線 A：Claude 桌面版 Cowork

把 `.skill` 檔交給 Claude，它會問你要不要存起來。
或從桌面版側邊欄的 **Customize** 加入。

> ⚠️ Cowork **不讀**你電腦上的 `~/.claude/skills/`。它讀的是你帳號上啟用的 skill。
> 如果你同時也用 Claude Code，兩邊要各裝一次。

### 路線 B：Claude Code

```bash
# macOS
mkdir -p ~/.claude/skills/talking-head-video-cut
unzip 口播影片工作流_完整包.zip -d ~/.claude/skills/talking-head-video-cut
```

```powershell
# Windows
mkdir "$env:USERPROFILE\.claude\skills\talking-head-video-cut"
Expand-Archive 口播影片工作流_完整包.zip -DestinationPath "$env:USERPROFILE\.claude\skills\talking-head-video-cut"
```

解壓後確認路徑長這樣：`.claude/skills/talking-head-video-cut/SKILL.md`
（如果多包了一層 `skillpkg/`，把裡面的東西搬上來一層）。

### 路線 C：Codex CLI

一模一樣，只是資料夾名稱不同：

```bash
# macOS
mkdir -p ~/.agents/skills/talking-head-video-cut
unzip 口播影片工作流_完整包.zip -d ~/.agents/skills/talking-head-video-cut
```

```powershell
# Windows
mkdir "$env:USERPROFILE\.agents\skills\talking-head-video-cut"
Expand-Archive 口播影片工作流_完整包.zip -DestinationPath "$env:USERPROFILE\.agents\skills\talking-head-video-cut"
```

另外把 `AGENTS.md` 複製到**你的專案根目錄**。

> ⚠️ **不要把 `references/手冊.md` 的內容貼進 `AGENTS.md`。**
> Codex 的 `AGENTS.md` 合計上限約 32 KiB，手冊本身就 30 KB 以上，
> 貼進去會吃光額度、擠掉你其他的專案指示。手冊當一般檔案放著就好，Codex 需要時會自己讀。

### 路線 D：網頁版

把 `SKILL.md` 和 `references/手冊.md` 當附件上傳，或整份貼進對話。

### 懶人做法（任何路線都可以）

整包解壓到專案資料夾，然後跟 AI 說「這裡面有 `SKILL.md` 和 `references/手冊.md`，請先讀完」。

裝成 skill 的好處只有一個：**不用每次提醒 AI 去讀**。
一次性的專案，直接丟資料夾就夠了。

---

## ④ 填 `scripts/paths.py`

整套引擎只有這一個檔案要改。打開它，填五樣：

| 要填什麼 | 說明 |
|---|---|
| `PROJECT` | 你的專案資料夾。底下會自動長出 `工作暫存/` 與 `_成品/` |
| `FONT_DIR` / `FONT_B` / `FONT_H` | 字型資料夾與兩個字重的檔名 |
| `BGM` | 背景音樂檔（或用 `bgm_gen.py` 產一個） |
| `SRC` | 來源錄影，自己取短代號，例如 `"a1"` |
| `CAM` / `SLIDE` | **畫面幾何，依模式二選一** |

畫面幾何是唯一會卡住的地方：

- **模式二（單機位自錄：商品、產品、口播）**：`CAM = SLIDE = "null"`，**不用量任何東西**
- **模式一（雙畫面：課程、講座）**：要量出講師鏡頭與投影片區的 crop。
  這件事讓 AI 幫你做——請它「照手冊第 3 章②量畫面幾何，填進 paths.py」，
  它會抓三個時間點的畫格自己算出來

驗證：

```bash
cd scripts
python -c "import paths, trim, long_run, precheck; print('OK', paths.PROJECT)"
```

看到 `OK` 加上你的路徑就算過了。

---

## ⑤ 跟 AI 說第一句話

```
我要把 <資料夾> 裡的錄影剪成短影音。

請先照 SKILL.md 的〈開場：先做環境判別〉把四題答完，結果講給我聽：
你能不能執行指令、我的作業系統、我用的工具、我的錄影是哪一種模式。

判別完之後，先跑 ingest.py 轉逐字稿，
然後照手冊第 3 章③做內容盤點，輸出 A/B/C 分級表與避雷清單。

先不要動手剪，讓我看過盤點結果再決定。
```

**重點是最後一句。** 直接叫 AI 開剪，你會拿到一批「技術上沒問題但你不想發」的影片。
先看盤點結果，花五分鐘刪掉不能用的段落，比事後重剪省時間得多。

---

## ⑥ 算圖

盤點通過之後，讓 AI 寫設定檔、跑 precheck、算圖。你只要看它回報。

```
python precheck.py p3 p5        # 先健檢
python queue.py   p3 p5         # 再算圖
```

`precheck` NG 就會停下來，這是刻意的——**一支 2.5 分鐘的長片要算 5–9 分鐘，
錯了就是白燒**。看到 NG 不要叫 AI「先跑跑看」。

參考耗時：60 秒短片約 2–3 分鐘，2.5 分鐘長片約 5–9 分鐘。

---

## ⑦ 驗收（三支都要跑）

```
python verify_long.py p3 p5     # 尺寸、時長、音畫 drift、內容段長靜音
python monoaudit.py             # 段落順序有沒有往回跳
python cardchk.py               # 片頭圖卡文字有沒有溢框
```

通過標準：

- 尺寸 1080×1920 / 1920×1080
- 音畫 drift ≤ 0.05 秒
- 內容段長靜音 = 0
- 片頭圖卡最右白字 ≤ 畫面寬 − 60px

後面兩支檢查是踩過坑之後加的：`monoaudit` 抓的是時間軸映射錯位
（症狀是「動畫在某一秒全部擠在一起」，而且字幕也會一起錯），
`cardchk` 抓的是封面文字超出畫面。兩個都不會讓程式報錯，只會默默做出壞片子。

**然後自己看一遍。** 程式檢查不了「這段講得好不好」。

---

## ⑧ 交付

檔名照 `編號_主題_長度_尺寸.mp4`，例如
`13_排程刊登與旺季加碼_60秒_直式_9x16.mp4`。

同時更新 `_成品/00_影片清單.md`，把**這支為什麼這樣剪、剪掉了什麼**寫進去。

這一步看起來多餘，但它是整套流程能長期跑下去的關鍵——三個月後你不會記得
為什麼某段沒用，然後你會重新評估一次、再得出同樣的結論、再浪費一次時間。

---

## 工時參考

| 項目 | 時間 |
|---|---|
| 環境安裝（一次性） | 20–40 分鐘 |
| 2 小時錄影轉逐字稿（有 GPU） | 約 16 分鐘 |
| 內容盤點（AI 協助） | 20–30 分鐘 |
| **一支 60 秒短影音** | **約 30 分鐘**（模式二約 20–25 分鐘） |
| **一支 2–3 分鐘中長片** | **約 1.5–2 小時** |

中長片工時是短影音的 6–8 倍，差在字幕句數（60–90 句 vs 8–13 句）、
切點數量（20–40 刀 vs 2–4 刀）、以及每 10–20 秒要換一次畫面。

**排程請用這個比例估，不要用「長度比」估。**

---

## 卡住的時候

| 症狀 | 先看這裡 |
|---|---|
| AI 找不到 skill | 手冊 13-5 排除表 |
| 字幕燒不上去 / 字重不對 | 手冊 2-2（`Fontname` 要填完整名稱） |
| 動畫全部擠在一起 | 手冊第 9 章第 1 條，跑 `monoaudit.py` |
| 封面文字超出框 | 跑 `cardchk.py` |
| 影片超過 60 秒 | 手冊第 9 章第 9 條 |
| AI 說它在算圖但沒有檔案 | 它其實不能執行指令，回到 ⑤ 重做環境判別 |
| 投影片畫面完全沒換 | 改用版面 `C` + 補動畫 |

---

## 一句話原則

**所有剪輯參數照手冊，不要自己發明；字幕分句手寫，不要程式自動斷句；
`precheck` NG 就停；交付前三支檢查全跑過。**

做商品／產品片的人多一條：**不准幫商品補任何你沒講過的數字或功效**。

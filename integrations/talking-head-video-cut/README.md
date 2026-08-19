# 口播影片剪片工作流｜可攜版

一段長錄影 → 一批帶字幕、動畫、圖卡、BGM 的短影音與長片。
Python + ffmpeg，**Windows 與 macOS 都能跑**。

適用前提只有一個：**畫面上有人在講話，而且講的內容本身有價值。**

| | **模式一　雙畫面錄影** | **模式二　單機位自錄** |
|---|---|---|
| 典型來源 | 課程、講座、線上會議側錄 | 商品開箱、產品介紹、口播、客戶見證 |
| 要量畫面幾何？ | 要 | 不用 |
| 版面 | `A` / `B` / `C` | `F` / `P` |
| 範例設定檔 | `configs_example/p3_cfg.py` | `configs_example/prod_cfg.py` |

兩種模式共用同一套引擎與同一套剪輯參數，切換只要改 `paths.py` 三行。

## 這包裡面有什麼

```
SKILL.md              ← 規則總表（給 Claude 讀；也可直接存成 Claude 的 Skill）
AGENTS.md             ← 給 Codex CLI 的指示（放在專案根目錄會被自動讀取）
references/手冊.md     ← 完整手冊：工具比較、安裝、九步驟、踩坑紀錄、可貼 prompt
scripts/              ← 引擎本體，直接可跑
  paths.py            ← ★ 唯一要改的檔案
  configs_example/    ← 5 個真實設定檔範例
```

## 三分鐘上手

### 1. 裝環境

**Windows**

```powershell
# Python 3.10+ 官網安裝（勾 Add to PATH）
# ffmpeg 用 Gyan full build，解壓後把 bin 加入 PATH
pip install faster-whisper opencc-python-reimplemented pillow numpy
ffmpeg -filters | findstr subtitles     # 要有輸出，沒有就是版本不對
```

**macOS**

```bash
brew install python ffmpeg
pip3 install faster-whisper opencc-python-reimplemented pillow numpy
ffmpeg -filters | grep subtitles
```

### 2. 改 `scripts/paths.py`

填五樣：專案資料夾、字型資料夾與檔名、BGM 檔、來源錄影代號（`SRC`）、畫面幾何。

畫面幾何依模式二選一：

- **模式一（雙畫面）**：量出 `CAM` / `SLIDE` 的 crop 填進去（手冊第 3 章②教你怎麼量）
- **模式二（單機位自錄）**：`CAM = SLIDE = "null"`，設定檔用 `LAYOUTS = ["F","P"]`，
  不用量任何東西

也可以用環境變數覆蓋，不動程式碼：

```bash
export VE_PROJECT="/Users/me/videoedit/myproject"     # Windows: set VE_PROJECT=...
export VE_FONTS="/Users/me/videoedit/_fonts"
export VE_BGM="/Users/me/videoedit/_bgm/bed_A.wav"
```

驗證：

```bash
cd scripts && python -c "import paths, trim, long_run, precheck; print('OK', paths.PROJECT)"
```

### 3. 交給你的 AI

**Claude Code / Claude 桌面版 Cowork**

把 `SKILL.md` 存成 Skill（或整包附給對話），然後說：

> 讀完 SKILL.md 與 references/手冊.md，先跑 `ingest.py` 轉逐字稿，
> 然後照手冊第 3 章③做內容盤點，輸出 A/B/C 分級表與避雷清單。
> 先不要動手剪，讓我看過盤點結果再決定。

**Codex CLI**

把整包放進專案根目錄，`AGENTS.md` 會自動被讀取。然後說：

> 照 SKILL.md 第 6 章的規格，把 `選段/p3_alloc.txt` 寫成 `p3_cfg.py`，
> 寫完先跑 `precheck.py p3`，OK 再問我要不要算圖。

**ChatGPT / Claude 網頁版**（不能執行本機指令）

只能做「想」的部分：盤點、選段、寫字幕分句、產設定檔內容給你複製。
算圖必須在你自己的電腦跑。手冊第 10-3 節有可直接貼的 prompt。

## 授權

MIT License — 可自用、修改、再散布，商業使用也可以。
唯一的條件是保留 `LICENSE` 裡的著作權聲明。詳見同資料夾的 `LICENSE`。

## 一句話原則

**所有剪輯參數照手冊，不要自己發明；字幕分句手寫，不要程式自動斷句；
`precheck` NG 就停；交付前三支檢查全跑過。**

做商品／產品片的人多一條：**不准幫商品補任何你沒講過的數字或功效**——
手冊第 12-6 節有完整的廣告用語避雷表。

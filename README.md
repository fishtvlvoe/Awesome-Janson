# 🎬【剪神 / Awesome-Janson】全能 AI 影片剪輯 Agent

> **長片精修 & 短影音雙模式 · 跨平台 · 全開源 · 零配置降級 · 支援任何 AI Agent 即插即用**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows%20%7C%20Linux-green.svg)]()

「剪神 (Awesome-Janson)」是專為現代創作者、講師與開發者打造的 **AI 影片剪輯全能 Agent**。目前已完成長片語意精修、`shorts-master` 與 `talking-head-video-cut` 本地短影音 adapter；電影級 **`video-shotcraft`**、Pixel2Motion、GSAP、Remotion 與 LottieFiles motion-design 作為進階動畫技能路由。HyperFrames 專案另可選用官方本機 CLI，既有 FFmpeg 路線不受影響。


---

<!-- GODS-FAMILY:START -->
## 👑 「神」系列家族：彼此怎麼接力合作？

「神」系列不是各自為政的工具，而是一條從**商務接案、工程開發到成果交付**的完整流水線：

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                       👑 「神」系列家族完整協同接力鏈                         │
└─────────────────────────────────────────────────────────────────────────┘

【第一棒：接案與商務需求】
  📋 案神 (Awesome-Anson) ➔ 丟進客戶會議逐字稿與資料，自動拆解需求、產出報價單與簡報。
         │
         ▼ (客戶成交，需求確認，交棒給工程總管)
【第二棒：自動化工程開發】
  🏗️ 蓋神 (Awesome-Gason) ➔ 把需求轉成 Spectra 規格，指揮多 Agent 在隔離房間寫碼與驗收。
         │
         ├─► 🗣️ 譯神 (Awesome-Eason) ➔ 過程中遇到看不懂的技術名詞？對外文案太假？
         │                               隨時叫「譯神」出來翻譯成白話、去 AI 味。
         │
         ├─► ⌨️ Key神 (Awesome-Keyson) ➔ 專案需註冊第三方平台、申請 API Key、填寫繁瑣企業表單？
         │                               貼上網址交給「Key神」安全自動填表，不用手打。
         │
         ▼ (系統開發完成，功能已驗收上線)
【第三棒：產品交付與行銷宣傳】
  🎬 剪神 (Awesome-Janson) ➔ 錄好的系統操作教學、發表會影片，一鍵自動精修成長片與爆款短影音。
```

### 家族成員倉庫速查

* 📋 **[案神 Awesome-Anson](https://github.com/fishtvlvoe/Awesome-Anson)**：接案分析、商務報價、合約拆解與提案簡報架構
* 🏗️ **[蓋神 Awesome-Gason](https://github.com/fishtvlvoe/Awesome-Gason)**：Spectra SDD 全自動開發總管（規格→TDD→多代理派工→CR→驗收）
* 🗣️ **[譯神 Awesome-Eason](https://github.com/fishtvlvoe/Awesome-Eason)**：小白技術降維、台灣繁中去 AI 味與翻譯急救
* ⌨️ **[Key神 Awesome-Keyson](https://github.com/fishtvlvoe/Awesome-Keyson)**：自動 Key 單、智慧語意對齊與跨平台表單自動填寫
* 🎬 **[剪神 Awesome-Janson](https://github.com/fishtvlvoe/Awesome-Janson)**（本倉庫）：全能 AI 影片剪輯 Agent（長片精修、爆款短影音與動效）
<!-- GODS-FAMILY:END -->

---
## 🌟 兩大核心交付模式 (Two Output Modes)

面對 1~3 小時的演講、工作坊或課程長錄影，剪神支援兩種截然不同的出片模式：

1. 📱 **模式一：精華短影音（Shorts Mode）**
   * 自動提煉出 3–5 支約 60~90 秒獨立金句短片。
   * 1.1~1.3x 節奏變速、情境 B-roll、6 款動態字卡、繁中單語字幕、BGM 與轉場音效。
2. 🎓 **模式二：完整長影片精修版（Full-Length Master Clean Cut）**
   * 保留完整 1.5~2 小時知識演講架構。
   * 先由「譯神」依上下文修正逐字稿、自然分句，再由「剪神」依 word-level 時間碼剪除贅詞與重複。
   * 保守處理「嗯、呃、欸、喔、啊」及明顯重來句；「這個、那個、然後」有語意時不刪。
   * 加上「章節進度條、知識點重點字卡、中英雙語階層字幕（主次分明）」。

---

## ✨ 核心能力

* 📱 **短影音口播精剪 (Shorts)**：語音字詞級自動去除「口誤重錄、發呆贅字」、1.1~1.3x 智慧節奏變速、6 款動態字卡。
* 🎓 **長影片去廢話精修 (Master Cut)**：2 小時以上工作坊全片去冗長停頓，保留完整脈絡並自動加章節字卡。
* 🧠 **語意級字幕與贅詞編輯**：譯神負責上下文分句、ASR 錯字修正、自然英文翻譯；剪神負責把被核准的贅詞從聲音與畫面一起剪掉。
* 💻 **電影級產品宣傳片 (Showcase)**：152 張 Remotion 鏡頭配方卡、2.5D 頁面運鏡、149 款電影級音效卡點、剪映工程草稿導出。
* 🌐 **長片中英雙語／短片繁中單語字幕**：長片保留「繁中主字亮白 + 英文副字淡灰」階層式排版；短片針對中文市場關閉英文，避免干擾。
* 🛡️ **全平台零門檻 (Zero-Config)**：支援 macOS (M系列/Intel) 與 Windows，本地開源 FFmpeg + faster-whisper 即可完成 80% 核心交付。

---

## 🚀 快速安裝

### 方式 1：直接將倉庫網址貼給你的 AI Agent（最推薦）
在 Claude Code、Codex 或任何支援 Skill 的 AI 對話框輸入：
```text
幫我安裝這個剪輯 Skill：https://github.com/fishtvlvoe/Awesome-Janson
```

### 方式 2：使用一鍵安裝腳本 (macOS / Linux)
```bash
git clone https://github.com/fishtvlvoe/Awesome-Janson.git
cd Awesome-Janson
chmod +x install.sh && ./install.sh
```

---

## 🛠️ 環境相容性診斷

執行內建診斷腳本，自動檢查本地 FFmpeg、Python 與 Node.js：
```bash
python3 scripts/doctor.py
```

---

## 🧠 語意編輯測試

長片字幕採「語意先、時間軸後」：不再用固定字數把一句話切碎。語言編輯結果會保留來源 word id，讓剪神能同時處理字幕與影片剪接。字幕使用思源黑體；1280×720 預設中文 50px、英文 30px，中文每行最多 22 個視覺字元、英文每行最多 60 個字元，各自最多兩行，超過就拆成有獨立時間碼的 cue。畫面底部加入灰階字幕層、低濃度漸層與文字陰影，避免白底投影片造成字幕看不清楚。

```bash
python3 scripts/semantic_edit.py transcript.json semantic_edit.json \\
  --start 0 --end 600 --batch-seconds 150 --raw-response semantic_raw.json
# 短影音用中文單語片審規則，避免英文與碎句 cue
python3 scripts/semantic_edit.py transcript.json shorts_semantic_edit.json \\
  --start 0 --end 600 --batch-seconds 150 --shorts
python3 scripts/render_semantic.py semantic_edit.json \\
  --source PT工作坊.mp4 --output-dir semantic_sample --render
```

預設是保守贅詞剪輯；不確定的「這個、那個、然後、就是」會保留。`--subtitle-only` 僅適合檢查文字，不適合直接交付，因為聲音仍會說出被刪掉的字。

完整長片自動輸出時，可把語意贅詞剪輯與既有等待區間一起合併：

```bash
python3 scripts/render_full.py semantic_full/semantic_edit.json \\
  --source PT工作坊.mp4 \\
  --base-edl edl_master.json \\
  --chapters chapters.json \\
  --output-dir auto_master --render
```

輸出包含 `auto_master_edl.json`、`auto_master_bilingual.ass` 與 `PT工作坊_auto_clean_bilingual.mp4`；自動剪輯仍採保守規則，不會任意刪除內容詞。

### 📱 短影音模式（shorts-master + talking-head adapter）

已接入 `shorts-master` 與 `talking-head-video-cut` 的本地路線：自動挑選 3 段候選、9:16 重排、1.15x 變速，先產出口白時間碼分鏡表供人工決定；未核准時畫面只保留說話者，核准後才插入真人情境 B-roll、人物／關係圖、流程表、清單或印章卡，並加入 BGM、whoosh／check／stamp 音效、CTA 與繁中單語 ASS 字幕。三支短片共用同一種視覺模板，但各自只帶出一個不同重點；字幕會先合併碎句、最多兩行並在動畫之後疊加，避免只剩單字或被卡片蓋掉。短片與長片共用同一份語意 JSON／word-level 時間軸：

```bash
python3 scripts/select_short_segments.py semantic_full/semantic_edit.json shorts/short_segments.json \\
  --chapters chapters.json --count 3
python3 scripts/render_shorts.py semantic_full/semantic_edit.json shorts/short_segments.json \\
  --source PT工作坊.mp4 --output-dir shorts --speed 1.15 --style editorial --render

# 先產出分鏡表：所有段落皆是 pending/talking-head，請先人工決定時間與畫面。
python3 scripts/build_short_storyboard.py semantic_full/semantic_edit.json shorts/short_segments.json \\
  --output shorts/storyboard.json --speed 1.15

# 使用者核准 storyboard.json 後，才渲染其中核准的動畫／B-roll。
python3 scripts/render_shorts.py semantic_full/semantic_edit.json shorts/short_segments.json \\
  --source PT工作坊.mp4 --output-dir shorts/talking_head --speed 1.15 \\
  --animation talking-head --storyboard shorts/storyboard.json --broll local \\
  --generate-bgm --generate-sfx --cta "追蹤剪神" --render
```

短影音片審規則固定在 `prompts/shorts-review.md`：中文市場預設只顯示繁中、字幕先合併碎句，先用 `build_short_storyboard.py` 產出時間分鏡，再以 `--storyboard` 只渲染使用者核准的視覺事件；三支短片共用第一版 B-roll／動畫／BGM／音效／CTA 模板但各自帶出不同重點。`--broll local` 是不依賴外部 API 的 Image2-style 情境圖卡 fallback；`--reuse-broll-media` 可優先重用已核准的本機 B-roll，不會發出遠端請求。外部 AI B-roll、素材搜尋與臉部保真服務仍是可選 provider，沒有服務時仍可完成本地短片輸出。完整 provider 選項與模型串接方式見 [`docs/broll-providers.md`](docs/broll-providers.md)；文字 → 本地動態圖卡／生圖鏡頭動畫／文字生影片／fal GPT Image 2 → image-to-video 的分層流程見 [`docs/text-to-dynamic-broll.md`](docs/text-to-dynamic-broll.md)。

### 🧩 fal.ai B-roll（選用）

`fal-image` 已支援 fal queue 的直式生圖 B-roll；`fal-video` 支援使用者指定的文字轉影片 endpoint；`fal-image-to-video` 可用 fal 的 `openai/gpt-image-2` 產生情境首幀，再接 image-to-video endpoint。遠端呼叫必須同時選擇 fal 模式與加上 `--allow-remote-broll`，否則自動回退 local，不會意外扣款。API key 只放在本機 `.env`／環境變數，不可貼進聊天或 git。

```bash
# 在本機 .env 設定 FAL_KEY 後；預設使用 fal-ai/flux/schnell。
python3 scripts/render_shorts.py edit.json segments.json \
  --source input.mp4 --output-dir shorts/fal-image \
  --broll fal-image --allow-remote-broll --remote-broll-limit 2 --render

# 影片模型需明確選擇 endpoint，避免預設啟用高成本模型。
AWJ_FAL_VIDEO_MODEL=fal-ai/kling-video/v3/standard/text-to-video \
python3 scripts/render_shorts.py edit.json segments.json \
  --source input.mp4 --output-dir shorts/fal-video \
  --broll fal-video --allow-remote-broll --remote-broll-limit 1 --render
```

生成媒體會快取於輸出目錄的 `.fal-cache/`，只作無音軌視覺 overlay；原始口白與最終字幕仍保留。key、簽名下載 URL 不會進 manifest。參數、回退與模型相容性請看 [`docs/broll-providers.md`](docs/broll-providers.md)。

### 🧩 B-roll 與模型擴充（optional providers）

剪神核心不綁任何雲端模型。除了本地圖卡，也可以選擇 Pexels／Pixabay 素材、OpenAI Images、Gemini／Imagen、FLUX、Runway、Veo、Kling、Luma 或本地 ComfyUI；這些 provider 都是可插拔擴充，沒有 API 時會回退到 local。請先讀 [`docs/broll-providers.md`](docs/broll-providers.md) 再決定是否接入。

### 🧠 主題生成模式（MoneyPrinterTurbo provider）

如果沒有現成長錄影，只有主題／腳本，需要 AI 旁白、素材、BGM 與自動成片，剪神會路由到可選的 `moneyprinterturbo-video`。若使用者已有錄影，仍優先使用剪神的語意剪輯，不會把原始口白改成合成旁白。

```text
integrations/moneyprinterturbo/
```

MPT 的完整 WebUI、Docker 與 345MB 資源包不會被硬塞進剪神；需要時由 provider 自己安裝，API key 也只由使用者明確設定。

### 📝 文字剪輯審稿器

Filmora 類型的「從逐字稿選句子剪片」現在由內建的無依賴審稿頁支援。它會把 AI 建議、人工核准與保留分開；未核准的贅詞不會進入 EDL，也可直接預覽原始影片的句子時間碼。

```bash
python3 scripts/open_review.py \
  --edit /path/to/semantic_edit.json \
  --video /path/to/input.mp4
```

也可以直接開啟 `review/index.html`。在頁面載入完整 `semantic_edit.json` 與原始影片後，逐句選擇「保留整句」、「採用贅詞建議」或「刪除整句」，並可分別調整中文／英文字幕大小、切換英文副字幕，再匯出審核檔與已套用 JSON：

```bash
python3 scripts/apply_review.py semantic_edit.json semantic_edit_review.json reviewed_edit.json
python3 scripts/render_semantic.py reviewed_edit.json \\
  --source input.mp4 --output-dir reviewed_output --render
```

## 💡 常用對話指令範例

* **長片精修完整版**：「剪神，幫我把這支 2 小時工作坊影片 `PT工作坊.mp4` 精修成完整長片，去除廢話與設備測試，加上章節重點字卡與中英雙語字幕！」
* **長片拆短影音**：「剪神，幫我把這支 2 小時工作坊影片 `PT工作坊.mp4` 拆成 3 支 60 秒重點短影片。」
* **產品展示片**：「剪神，用 2.5D 頁面運鏡鏡頭卡為我的網頁產出一支 30 秒電影感宣傳片。」

---

## 📄 開源授權

本專案採用 [MIT License](LICENSE) 開源授權。

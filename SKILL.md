---
name: awesome-janson
description: "【剪神 / Awesome-Janson】全能 AI 影片剪輯 Agent。支援長影片（1~3小時工作坊/課程/演講）與短影音的雙模式剪輯。具備「完整長片精剪去廢話」與「精華短影音拆剪」兩大模式。支援自動逐字稿去贅詞口誤、1.1-1.3x 智能變速、章節重點字卡、長片中英雙語／短片繁中單語字幕、2.5D 畫面運鏡與廣播級音訊美化。觸發詞包含：幫我剪片、剪神、awesome-janson、剪長影片、短影音剪輯、做產品宣傳片、長影片拆短影音、工作坊精華剪輯、加字卡字幕、去贅詞廢話、中英雙語字幕。"
---

# 【剪神 / Awesome-Janson】全能 AI 影片剪輯 Agent

## 🎬 兩大核心交付模式 (Two Output Modes)

當你丟進一支長錄影（如 1~3 小時的 Google Meet / Zoom 工作坊、演講或課程）：

```text
┌─────────────────────────────────────────────────────────────┐
│                    來源長錄影 (1 ~ 3 小時)                   │
└──────────────┬───────────────────────────────┬──────────────┘
               │                               │
       【 模式 1：短影音精華 】            【 模式 2：完整長影片精修 】
               │                               │
┌──────────────▼──────────────┐ ┌──────────────▼──────────────┐
│  • 提取 3–5 支 60~90s 金句   │ │  • 保留完整演講/教學脈絡    │
│  • 9:16 直式或 1:1 滿版      │ │  • 自動切除開場等待與設備測試 │
│  • 1.1~1.3x 節奏變速        │ │  • 自動剃除口誤贅字與長停頓 │
│  • 6 款熱門爆款動態字卡      │ │  • 章節大綱導航 + 重點提示卡 │
│  • 繁中單語字幕 + B-roll/BGM  │ │  • 繁中 / 中英雙語階層字幕   │
│  • 產出：shorts_01.mp4 ...   │ │  • 產出：master_clean.mp4   │
└─────────────────────────────┘ └─────────────────────────────┘
```

---

## 🚀 三大核心工作流 (Pipelines)

### 🎓 路線 1：Long-form 長影片精修（完整長片模式）
適用於：1~3 小時工作坊、線上課程、演講、訪談。
1. **譯神語意編輯 → 剪神時間軸剪輯**：
   - 先保留 word-level 原始逐字稿，不用固定字數硬切字幕。
   - 由譯神（Awesome-Eason）依上下文修正 ASR 錯字、按完整語意分句、產生自然英文。
   - 保守標記可刪除的獨立贅詞（嗯、呃、欸、喔、啊）、明顯重複與失敗重來句。
   - 「這個、那個、就是、然後、所以」必須經過語境判斷；有實際意思時保留。
   - 剪神依 word id 時間碼真的剪除語音與畫面，並重新映射字幕，不只把文字藏掉。
2. **章節與重點字卡**：
   - 自動生成章節段落標題卡（Chapter Cards / Lower-Thirds）。
   - 關鍵知識點自動浮出「重點提示框」。
3. **語意級中英雙語字幕**：
   - 以完整意思分 cue，不拆開主詞、動詞、名詞片語或專有名詞。
   - 中文主字亮白 100%，英文副字淡灰 60%；英文依英文語序自然翻譯。
   - 使用思源黑體（Source Han Sans TC）；1280×720 預設中文 50px、英文 30px，中文每行最多 22 個視覺字元、英文每行最多 60 個字元，且每種語言最多兩行。
   - 超過上限時拆成多個有獨立時間碼的字幕 cue，不只把字縮小或硬塞在同一段。
   - 畫面底部疊加低濃度黑灰漸層，讓白底投影片也能看清字幕，但不壓暗內容。
   - 每個 cue 保留來源 word ids、刪除標記、信心分數，方便人工審核與回溯。
   - 文字剪輯審稿器（`review/index.html`）模擬 Filmora 的逐字稿剪輯：未核准的 AI 建議不會實際剪除；使用者可逐句保留、採用贅詞或刪除整句，並可分別調整中文／英文字幕大小與英文顯示，再匯出 reviewed edit JSON。
4. **無損導出**：保持 16:9 原畫質，切點加 30ms 音訊淡入淡出（防爆音），輸出流暢且緊湊的完整成片。

### 📱 路線 2：Shorts 短影音精剪（短影音模式）
適用於：從長影片中提取精華金句，或直式口播短影音。
1. **金句萃取**：自動識別整場活動「觀點最犀利、含金量最高」的 3~5 個獨立段落。
2. **節奏變速**：1.1x–1.3x 變速壓縮至 60~90 秒黃金長度。
3. **情境 B-roll**：每 6～8 秒安排一次 B-roll、流程圖、關係圖或字卡變化；只有簡報來源時使用本地 Image2-style 圖卡，不依賴外部 API。
4. **動態字卡**：6 種風格（大字報 editorial / 綜藝爆字 variety / 白板筆記 whiteboard 等），並加入 whoosh／check／stamp 輕音效。
5. **繁中單語字幕**：短影音不顯示英文；短句 96 級強調、長句 76 級最多兩行，字幕最後疊加避免被 B-roll 蓋住。
6. **第一版視覺模板固定**：動畫卡、B-roll、BGM、音效、簡單轉場與 CTA 經片審通過後，批次短片共用同一套呈現，只更換各支的核心重點。
7. **字幕／切點閘門**：合併 ASR／模型碎句，禁止「麼？」「。」「到。」等孤兒字幕；字幕 cue 必須覆蓋完整語意與聲音，不在詞中間切畫面。詳見 `prompts/shorts-review.md`。

### 💻 路線 3：Showcase 電影級產品宣傳片
適用於：軟體 Demo、功能發佈片、官網 Hero Video。
1. **152 張鏡頭配方卡**：2.5D 頁面運鏡、卡片飛入、聚光燈特寫。
2. **Remotion 確定性渲染**：60fps 絲滑過渡。
3. **149 款電影 SFX 音效**：自動卡點轉場與音效。
4. **剪映草稿導出**：直接轉出剪映工程檔供後續調整。

---

## 🧩 已接入的動畫與短影音技能

剪神現在把外部技能當成可選 provider／方法庫，不把任何第三方服務當成硬依賴：

| 技能 | 用途 | 剪神接法 |
| --- | --- | --- |
| `shorts-master` | 短片順剪、變速、字卡、字幕與 B-roll 方法 | `select_short_segments.py` + `render_shorts.py`；無雲端服務時走本地 fallback |
| `motion-design` | 情緒、時序、easing、choreography 與 QA 原則 | 短片標題／字幕動畫與長片章節卡共用 |
| `video-shotcraft` | Remotion 電影感鏡頭卡、2.5D、轉場與聲音設計 | 產品宣傳片與進階動效 provider |
| `HyperFrames`／`GSAP`／`Remotion` | 字卡、時間軸、字幕與程式動畫實作規範 | 產生動效工程時由 Agent 路由載入 |
| `Pixel2Motion` | Logo／品牌開場動畫 | Logo reveal provider |
| `story-to-handdrawn-video` | 中文故事手繪動畫 | 故事型短片 provider |
| `LottieFiles motion-design` | 通用 motion design 方法論 | 已安裝至全域 Skill SSOT，並同步保留在 `integrations/motion-design/` |
| `MoneyPrinterTurbo` | 主題／腳本 → TTS、素材、BGM、成片 | 只作 optional topic-video provider；不取代既有錄影的語意剪輯 |
| `Pexels`／`Pixabay` | 真實情境 B-roll 素材 | optional；需各自 API／授權，沒有設定時回退 local |
| `fal.ai` | Marketplace 圖片與文字轉影片 B-roll | `--broll fal-image`／`fal-video` 加 `--allow-remote-broll`；缺 key／模型／遠端失敗回退 local |
| AI 生圖／圖生影片 | OpenAI Images、Gemini／Imagen、FLUX、Runway、Veo、Kling、Luma 等 | optional provider 設計；fal.ai queue adapter 已可用，其餘不作核心硬依賴 |

短片與長片共用語意 JSON、word-level 時間軸與字幕布局；長片使用 `render_full.py`，短片使用 `render_shorts.py`。B-roll／模型 provider 的完整擴充矩陣見 `docs/broll-providers.md`；這些都是 optional，不是剪神核心依賴。

### MoneyPrinterTurbo 路由規則

- 使用者已有長錄影、課程、口播或工作坊：走剪神現有流程，必要時加 `talking-head-video-cut` 動畫 adapter。
- 使用者只有主題、關鍵字或完整腳本，要自動旁白／素材／BGM 短片：才載入 `moneyprinterturbo-video`。
- MPT 的 LLM、TTS、素材 API、BGM 與跨平台發布全部是 opt-in；沒有 key 時不會偷偷呼叫。
- 不把 MPT 345MB 完整 WebUI／Docker／資源包塞進剪神；只保留 Agent Skill 與安全安裝 helper。

### 瀏覽器控制（ego-browser）

`ego-browser` 是 Agent 的 optional 操作層，不是剪輯核心依賴：

- 有 ego：Agent 可以自動開剪神審稿器、MPT WebUI 或本地預覽頁，協助載入素材與驗收。
- 沒有 ego：客戶仍可用一般 Chrome／Edge／Safari、CLI 與 FFmpeg 完整剪片。
- 不把 ego runtime 或瀏覽器權限寫進成片 pipeline，避免客戶因缺少 ego 而無法使用剪神。

## 🛠️ 跨平台環境診斷 (Doctor)

執行內建診斷腳本：

```bash
python3 scripts/doctor.py
```

| 工具 | 檢查項目 | 缺了怎辦 |
| :--- | :--- | :--- |
| **FFmpeg** | `ffmpeg -filters \| grep subtitles` | Mac: `brew install ffmpeg` / Win: `winget install Gyan.FFmpeg` |
| **Python** | Python 3.10+、`faster-whisper`、Pillow（本地／fal B-roll） | `pip install faster-whisper Pillow` |
| **Node.js** | Node 20+ & Remotion | `npx remotion --version` |

### B-roll Provider 原則

- 有現成錄影時，預設保留原始人聲與剪神本地 B-roll，不自動呼叫外部模型。
- LLM 只產生受限制的 `scene_plan.json`；素材／圖片／圖生影片 provider 仍須 opt-in。
- ChatGPT／Codex／Claude Code／Kimi 網頁訂閱通常不能直接代替第三方 API key。
- API key 不寫入 skill、git 或 log；fal remote 呼叫必須同時有 `FAL_KEY` 與 `--allow-remote-broll`，缺少 key、影片模型或遠端失敗時必須退回本地路線。
- fal 下載媒體只作無音軌 overlay，原始口白與字幕最後一層不變；manifest 不得記錄 key 或簽名 URL。
- Provider 類型、設定名稱與目前完成度見 `docs/broll-providers.md`；文字 → 本地動態圖卡／生圖鏡頭動畫／文字生影片與未來 image-to-video 的分層規則見 `docs/text-to-dynamic-broll.md`。

---

## 🧠 語意編輯工作流

長片模式不能只把逐字稿按秒數切成字幕；正確順序是：

```text
原始 word timestamps
        ↓
譯神：修正錯字、語意分句、標記贅詞與重複
        ↓
剪神：依 word id 剪除聲音／畫面，重新計算輸出時間軸
        ↓
字幕：繁中主字幕 + 英文副字幕 + 章節字卡
```

目前提供兩個可重複使用的本地工具：

```bash
# 產生長片語意 cue 與保守贅詞標記（需要 GEMINI_API_KEY）
python3 scripts/semantic_edit.py transcript.json semantic_edit.json \\
  --start 0 --end 600 --batch-seconds 150 --raw-response semantic_raw.json

# 短影音語意 cue：中文市場、en 欄位留空、禁止孤兒字幕／碎句切點
python3 scripts/semantic_edit.py transcript.json shorts_semantic_edit.json \\
  --start 0 --end 600 --batch-seconds 150 --shorts --raw-response shorts_semantic_raw.json

# 若分別處理不同時間範圍，可先合併多個 semantic_edit 結果
python3 scripts/merge_semantic.py semantic_edit.json part_0_300.json part_300_600.json

# 產生語意版 EDL／ASS；預設會真的剪掉標記的語音贅詞
python3 scripts/render_semantic.py semantic_edit.json \\
  --source input.mp4 --output-dir semantic_sample --render

# 合併既有等待剪輯與完整語意剪輯，輸出長片
python3 scripts/render_full.py semantic_full/semantic_edit.json \\
  --source input.mp4 --base-edl edl_master.json --chapters chapters.json \\
  --output-dir auto_master --render

# 短片：同一份語意 JSON → 3 段直式短影音
python3 scripts/select_short_segments.py semantic_full/semantic_edit.json shorts/short_segments.json \\
  --chapters chapters.json --count 3
python3 scripts/render_shorts.py semantic_full/semantic_edit.json shorts/short_segments.json \\
  --source input.mp4 --output-dir shorts --speed 1.15 --style editorial --render

# 口播動畫版：沿用 talking-head-video-cut 的 checklist／stamp，另加本地 BGM 與 CTA
python3 scripts/render_shorts.py semantic_full/semantic_edit.json shorts/short_segments.json \\
  --source input.mp4 --output-dir shorts/talking_head --speed 1.15 \\
  --animation talking-head --broll local --generate-bgm --generate-sfx \\
  --cta "追蹤剪神" --render

# fal 生圖 B-roll（須由使用者先在本機 .env／環境變數設定 FAL_KEY）
python3 scripts/render_shorts.py semantic_full/semantic_edit.json shorts/short_segments.json \
  --source input.mp4 --output-dir shorts/fal --speed 1.15 \
  --broll fal-image --allow-remote-broll --remote-broll-limit 2 --render
```

不確定的詞一律保留。長片預設採保守模式；短影音才使用較積極的節奏清理。短片預設只顯示繁中；`prompts/shorts-review.md` 是短影音片審與 Agent 的固定規則。`--broll local` 會產生不依賴外部 API 的情境圖卡，`--generate-sfx` 會產生本地轉場／打勾／印章音效。若只想檢查字幕，可加 `--subtitle-only`，但那會讓字幕與原始語音不完全一致，不應直接當成最終成片。

### 📝 文字剪輯審稿

先開啟審稿器，再載入譯神輸出的完整語意 JSON 與原始影片：

```bash
python3 scripts/open_review.py --edit semantic_edit.json --video input.mp4
```

審核完成後可直接匯出 `reviewed_edit.json`，或用審核檔搭配原始語意結果重建：

```bash
python3 scripts/apply_review.py semantic_edit.json semantic_edit_review.json reviewed_edit.json
python3 scripts/render_semantic.py reviewed_edit.json --source input.mp4 --output-dir reviewed_output --render
```

`reviewed_edit.json` 會標記 `review.mode=manual-review`。此模式只剪人工核准的單字或整句，不會沿用尚未確認的 AI 贅詞建議。

## 📌 快速調用指令範例

- **模式 1（短影音）**：`剪神，幫我把這支長影片 /path/to/video.mp4 拆成 3 支 60 秒重點短影片`
- **模式 2（完整長片）**：`剪神，幫我把這支 2 小時工作坊影片 /path/to/video.mp4 精修成完整長片，去除廢話贅詞，加上章節字卡與中英雙語字幕！`
- **宣傳片**：`剪神，用 2.5D 運鏡鏡頭卡為我的軟體做一支 30 秒產品宣傳片`

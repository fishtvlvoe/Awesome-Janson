# 文字 → 動態 B-roll

本文件定義剪神把逐字稿的「完整語意 cue」轉成動態 B-roll 的做法。它不依賴 Codex、Claude、Kimi 或任一特定對話訂閱；LLM 只負責提出受限制的畫面描述，實際產圖／產片由可替換 provider 完成。

## 原則

- **時間軸優先**：B-roll 只能安排在既有 cue 時段，不能改寫口白、成效數字或客戶承諾。
- **字幕優先**：字幕永遠最後燒錄；B-roll 的 lower third 保持簡單，不能遮住字幕。
- **漸進升級**：預設先用本地動畫；只有人工確認需要真實動態時才用遠端影片模型。
- **Provider 與 LLM 分離**：Codex／Claude／Kimi／本地 LLM 都可產生同一份 `scene_plan.json`；沒有 LLM 或 API 時則使用既有字幕 cue 產生本地事件。
- **成本明示**：每次 fal 遠端工作都必須先確認 endpoint、輸出秒數、單價和最大事件數；未帶 `--allow-remote-broll` 不得送出工作。

## 四層交付路線

### A. 本地動態圖卡（現在可用、零雲端成本）

```text
cue → checklist／流程／關係圖卡 → 本地 frame 動畫 → FFmpeg 合成
```

- 使用 `--broll local --animation talking-head`。
- 流程、漏斗、網路與迴圈圖卡會依事件時段生成動態 PNG frames。
- 最適合知識型口播、課程與工作坊；畫面有節奏，但不假裝是真實拍攝影片。

### B. 文字 → 圖片 → 本地鏡頭動畫（現在可用、低成本）

```text
cue → provider-neutral prompt → fal-image → 緩慢推近／景深／淡入淡出 → FFmpeg 合成
```

- 使用 `--broll fal-image --allow-remote-broll`。
- 預設模型是 `fal-ai/flux/schnell`；短片最多兩個遠端事件，其餘維持本地圖卡。
- 生成圖片只作無音軌 overlay，原始口白與字幕不變。
- 適合抽象概念、品牌情境或沒有可用實拍素材的段落。

### C. 文字 → 動態影片 B-roll（現在可用，但必須選模型）

```text
cue → provider-neutral prompt → fal text-to-video queue → 無音軌影片 overlay → FFmpeg 合成
```

- 使用 `--broll fal-video --allow-remote-broll`。
- 必須明確設定 `AWJ_FAL_VIDEO_MODEL` 或 `--fal-video-model`；剪神不提供影片模型預設值，避免意外使用高成本 endpoint。
- 每段只生成 3–6 秒，且 `--remote-broll-limit` 預設為 2。
- 只用於需要真正鏡頭運動、物件運動或 cinematic 氛圍的少數重點段落；不使用模型輸出的音軌。

### D. 圖片 → 動態影片（規劃中，尚未宣告 CLI 可用）

```text
approved image → upload to an image-to-video endpoint → motion prompt → 無音軌影片 overlay
```

未來採用此路線時必須：

1. 保留原圖與 provider 的非敏感 request metadata 在輸出目錄 cache；不得寫入 key 或簽名 URL。
2. 明確選擇支援 image-to-video 的 endpoint，並先取得該 endpoint 的 input schema、輸出秒數和成本估算。
3. 先用一個 3–6 秒鏡頭人工片審，再允許批次生成。
4. 上傳來源圖前取得使用者同意；含人物、客戶素材或商標時，需確認授權與 provider 條款。
5. queue／下載／解碼失敗或超時時取消遠端工作並回退 B 路線或 A 路線。

## Provider-neutral `scene_plan.json`

LLM 輸出只能描述既有口白，禁止虛構數字、成果或客戶背書：

```json
{
  "start": 23.1,
  "duration": 4.8,
  "source_cue_ids": ["cue-12", "cue-13"],
  "visual_type": "conceptual-pipeline",
  "prompt": "A vertical editorial visual about a partner referral workflow; no readable text, logos, statistics, or identifiable people.",
  "requires_remote_media": false
}
```

剪神仍負責驗證時長、來源 cue、lower-third 安全區與輸出格式；provider 不可自行決定剪點或字幕文字。

## 選擇規則

| 畫面需求 | 路線 | 建議 |
| --- | --- | --- |
| 流程、概念、課程重點 | A | 預設；最快且完全本地 |
| 情境插圖、品牌氛圍 | B | 只生成少量靜態圖，讓本地鏡頭動畫承接 |
| 真正的人物／物件／鏡頭運動 | C | 只用 1–2 個重點鏡頭，先確認成本與片審 |
| 已核准主視覺需要延伸動態 | D | 等 image-to-video adapter 和 endpoint 成本核對完成後再使用 |

## 執行範例

```bash
# A：本地動態 B-roll，零雲端成本
python3 scripts/render_shorts.py edit.json segments.json \
  --source input.mp4 --output-dir shorts/local-motion \
  --animation talking-head --broll local \
  --generate-bgm --generate-sfx --render

# B：文字生圖後用本地鏡頭動畫；會產生付費遠端工作
python3 scripts/render_shorts.py edit.json segments.json \
  --source input.mp4 --output-dir shorts/fal-image \
  --animation talking-head --broll fal-image \
  --allow-remote-broll --remote-broll-limit 2 --render

# C：文字生影片；先明確指定模型、模型單價與最多事件數
AWJ_FAL_VIDEO_MODEL=<confirmed-text-to-video-endpoint> \
python3 scripts/render_shorts.py edit.json segments.json \
  --source input.mp4 --output-dir shorts/fal-video \
  --animation talking-head --broll fal-video \
  --allow-remote-broll --remote-broll-limit 1 --render
```

`fal-video` 或未來 image-to-video 的實際呼叫前，操作 Agent 必須向使用者說明模型、預估費用和鏡頭數量並取得確認；未設定 key、模型或 opt-in 時，剪神必須輸出 A 路線的本地 fallback。

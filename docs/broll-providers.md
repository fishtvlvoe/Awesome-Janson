# 剪神 B-roll 與模型 Provider

## 核心與擴充的界線

剪神的核心功能不依賴任何雲端服務：

- 逐字稿、語意剪輯、字幕、FFmpeg 時間軸
- `--broll local` 本地情境圖卡
- talking-head 動畫、BGM、SFX、CTA

以下全部是**可選擴充**，不會影響核心剪輯：

| Provider 類型 | 例子 | 用途 | 目前狀態 |
|---|---|---|---|
| 本地程式圖卡 | PIL、SVG、FFmpeg、Remotion、GSAP、Lottie | 漏斗、流程、關係圖、UI 卡片 | 已可用／方法路由 |
| 素材搜尋 | Pexels、Pixabay、其他授權素材庫 | 真實情境 B-roll | MPT 可選路線；非核心 |
| AI 生圖 | OpenAI Images、Gemini／Imagen、FLUX、Stable Image | 依主題產生情境插圖 | 可規劃的 optional provider |
| AI 圖生影片 | Runway、Veo、Kling、Luma、Pika 等 | 將情境圖變成 3～8 秒動態片段 | 可規劃的 optional provider |
| fal.ai 圖片／影片 | fal Marketplace 的圖片與文字轉影片 endpoint | 依既有 cue 產生直式 AI 情境 B-roll | 已接入 optional queue adapter；需明確 opt-in 與自有 key |
| 本地生成 | ComfyUI、FLUX、SDXL、Wan、AnimateDiff | 不上傳素材的 AI B-roll | 需要本機 GPU／額外安裝 |
| 主題成片 | MoneyPrinterTurbo | 主題／腳本 → 旁白、素材、BGM、成片 | 已整合 optional provider |

> 外部模型的名稱、API、價格與可用地區會變動；真正接入前要再次核對官方文件與授權條款。

## 模型串接方式

模型不直接取代剪神的時間軸。完整的「文字 → 圖片／動態影片 B-roll」分層、成本確認與 image-to-video 規劃見 [`text-to-dynamic-broll.md`](text-to-dynamic-broll.md)。建議採用：

```text
逐字稿／主題
   ↓
LLM：產生受限制的 scene_plan.json
   ↓
圖片／素材／圖生影片 Provider：產生 B-roll 素材
   ↓
剪神：依 cue 時間軸安排素材、字幕、動畫、BGM、SFX、CTA
   ↓
FFmpeg／Remotion：輸出成片
```

`scene_plan.json` 必須只包含：

- cue 的開始／結束時間
- 已在逐字稿出現的關鍵詞
- B-roll 類型與畫面描述
- 是否允許使用外部素材
- 授權／來源資訊

禁止模型自行補上客戶成果、百分比、業績數字或未說過的承諾。

## 建議設定介面

以下是 provider 設計名稱；沒有設定時一律回退到本地路線：

```bash
AWJ_BROLL_PROVIDER=local
# local | pexels | pixabay | image | image-to-video | mpt | fal-image | fal-video

AWJ_IMAGE_PROVIDER=
# openai | gemini-imagen | flux | stable-image | comfyui

AWJ_VIDEO_PROVIDER=
# runway | veo | kling | luma | pika | comfyui
```

這些 `AWJ_*` 變數不代表每個外部服務都已完成直接 adapter；現階段除了 local 與 MoneyPrinterTurbo 外，也可使用 fal.ai 的 queue adapter：

```bash
# 不需要外部 API
python3 scripts/render_shorts.py edit.json segments.json \
  --source input.mp4 --output-dir shorts \
  --animation talking-head --broll local \
  --generate-bgm --generate-sfx --render

# fal 生圖 B-roll：FAL_KEY 只放本機 .env／環境變數；未帶 --allow-remote-broll 時仍會回退 local。
python3 scripts/render_shorts.py edit.json segments.json \
  --source input.mp4 --output-dir shorts \
  --broll fal-image --allow-remote-broll --remote-broll-limit 2 --render

# fal 的 GPT Image 2 → Kling image-to-video：只需 FAL_KEY，無須 OPENAI_API_KEY。
AWJ_FAL_IMAGE_MODEL=openai/gpt-image-2 \
AWJ_FAL_VIDEO_MODEL=fal-ai/kling-video/o3/standard/image-to-video \
python3 scripts/render_shorts.py edit.json segments.json \
  --source input.mp4 --output-dir shorts \
  --broll fal-image-to-video --allow-remote-broll \
  --remote-broll-limit 2 --remote-broll-seconds 2 --render

# 已核准的 B-roll 可離線重用：不重送 fal request，manifest 不記錄本機路徑。
python3 scripts/render_shorts.py edit.json segments.json \
  --source input.mp4 --output-dir shorts \
  --animation talking-head --visual-cadence 2 --broll local \
  --reuse-broll-media shorts/.fal-cache/approved-01.mp4 \
  --generate-bgm --generate-sfx --render

# fal 影片 B-roll：需自行選擇目前可用的文字轉影片 endpoint。
AWJ_FAL_VIDEO_MODEL=fal-ai/kling-video/v3/standard/text-to-video \
python3 scripts/render_shorts.py edit.json segments.json \
  --source input.mp4 --output-dir shorts \
  --broll fal-video --allow-remote-broll --remote-broll-limit 1 --render

# 主題／腳本才走 MoneyPrinterTurbo
python3 scripts/moneyprinterturbo_provider.py --subject "你的主題"
```

### fal.ai 設定與安全界線

複製 [`.env.example`](../.env.example) 的欄位到本機 `.env`，或以程序環境變數設定；當專案位於此 Development 工作區時，adapter 只會讀取白名單的 `FAL_*`／`AWJ_FAL_*` 欄位。不要用 `source .env` 執行未知內容，也不要把 key 貼進聊天、log、manifest 或 git。

```bash
FAL_KEY=你的_fal_key
# fal-image 預設為 fal-ai/flux/schnell；GPT Image 2 可設為 openai/gpt-image-2，仍只需要 FAL_KEY。
AWJ_FAL_IMAGE_MODEL=
# fal-video 沒有預設，避免意外選到高成本模型；可填 /text-to-video 或 /image-to-video endpoint。
AWJ_FAL_VIDEO_MODEL=
# 選用：不同模型的額外欄位，只接受 JSON object。
# AWJ_FAL_IMAGE_INPUT_JSON={"output_format":"jpeg"}
# AWJ_FAL_VIDEO_INPUT_JSON={"cfg_scale":0.5}
```

- 每個遠端要求都走 `queue.fal.run`，有 queue timeout、逾時／輪詢失敗時的 best-effort cancel、模型 ID 驗證、下載大小限制與最終輸出目錄內 `.fal-cache`。
- 短片預設最多生成兩個遠端 B-roll；其餘核准事件使用本地卡。talking-head 短片必須先產出人工核准的時間分鏡，未核准段落只保留說話者；影片模式沒有預設模型，避免意外扣款。
- `--reuse-broll-media` 會優先用已核准的本機影片填入最早的 B-roll slot，不呼叫遠端 provider；manifest 只記錄 `reused-local-media`、媒體類型與 cache 狀態。
- 下載的 fal 媒體只作無音軌的視覺 overlay，原始人聲與最後燒錄的字幕仍保留；畫面會標示為 `AI 情境示範 · fal.ai`。
- key 缺失、未明確 opt-in、模型設定不完整、queue／下載／解碼失敗都會回退 `local`；manifest 僅記錄 provider、model、request ID／cache 狀態，絕不記錄 key 或簽名媒體 URL。

## API 與訂閱

- ChatGPT、Codex、Claude Code 或 Kimi 網頁版訂閱，通常不能直接當成第三方 API key。
- LLM API、素材 API、圖片模型與圖生影片服務通常各自計費／各自發 key。
- 本地圖卡、FFmpeg、Remotion、ComfyUI 不一定需要雲端 API。
- API key 只放在本機環境變數或 provider 自己的安全設定，不寫入 git、不輸出到 log。

## 推薦路線

1. 已有工作坊／口播影片：`local`，保留原始人聲，最穩定。
2. 需要真實情境：選 Pexels／Pixabay，先人工確認素材授權。
3. 需要品牌化插圖：選 AI 生圖，再用 Ken Burns／Remotion 做動態，不必每次直接生成影片。
4. 需要電影感短鏡頭：最後才接圖生影片，並限制每個鏡頭 3～8 秒與人工片審。

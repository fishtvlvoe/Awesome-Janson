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
| 本地生成 | ComfyUI、FLUX、SDXL、Wan、AnimateDiff | 不上傳素材的 AI B-roll | 需要本機 GPU／額外安裝 |
| 主題成片 | MoneyPrinterTurbo | 主題／腳本 → 旁白、素材、BGM、成片 | 已整合 optional provider |

> 外部模型的名稱、API、價格與可用地區會變動；真正接入前要再次核對官方文件與授權條款。

## 模型串接方式

模型不直接取代剪神的時間軸。建議採用：

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
# local | pexels | pixabay | image | image-to-video | mpt

AWJ_IMAGE_PROVIDER=
# openai | gemini-imagen | flux | stable-image | comfyui

AWJ_VIDEO_PROVIDER=
# runway | veo | kling | luma | pika | comfyui
```

這些 `AWJ_*` 變數目前是擴充設計約定，不代表每個外部服務都已完成直接 adapter。現階段可用的是：

```bash
# 不需要外部 API
python3 scripts/render_shorts.py edit.json segments.json \
  --source input.mp4 --output-dir shorts \
  --animation talking-head --broll local \
  --generate-bgm --generate-sfx --render

# 主題／腳本才走 MoneyPrinterTurbo
python3 scripts/moneyprinterturbo_provider.py --subject "你的主題"
```

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

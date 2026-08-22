# Awesome-Janson integrations

這裡保留剪神實際使用的第三方方法庫副本與授權檔，方便離線查閱；全域 Agent Skill 則統一安裝在 `/Users/fishtv/Development/.skills-ssot/live/`。

## 已接入

- `shorts-master/` — 短影音七階段方法、字卡樣式、字幕模板與時間軸映射 helper。剪神的本地 adapter 是 `scripts/select_short_segments.py` + `scripts/render_shorts.py`。
- `motion-design/` — LottieFiles motion design 方法論；短片與長片的動效決策共用。
- `talking-head-video-cut/` — MIT 授權的本機口播引擎參考與動畫元件；剪神 adapter 會使用其 checklist／stamp 元件，不直接使用硬編碼 Windows 主流程。
- `moneyprinterturbo/` — optional 主題／腳本成片 provider，只保留 Agent Skill 與安裝 helper，不 vendoring 完整 345MB 應用程式。
- `hyperframes/` — optional HyperFrames 本機 HTML-to-video provider；支援 `npx hyperframes` 與各種 coding agents。
- `../scripts/fal_broll_provider.py` — optional fal.ai queue adapter；不 vendoring SDK，使用標準 HTTP queue API，輸出仍回到既有 PNG overlay contract。

## 全域已安裝的動畫技能

來源與安全掃描結果見：

```text
/Users/fishtv/Development/.skills-ssot/live/animation-skill-install-manifest.json
```

## Provider 分層

- **核心**：FFmpeg、faster-whisper、既有語意 JSON、local B-roll、talking-head 動畫。
- **素材 optional**：Pexels／Pixabay 等搜尋 API；需自行確認授權與流量限制。
- **圖片 optional**：OpenAI Images、Gemini／Imagen、FLUX、Stable Image、ComfyUI。
- **圖像／影片 optional**：fal.ai Marketplace endpoint（`fal-image`／`fal-video`）已接入；Runway、Veo、Kling、Luma、Pika 或本地 ComfyUI 工作流仍可後續擴充。
- **主題成片 optional**：MoneyPrinterTurbo，負責主題／腳本 → 旁白、素材與成片。
- **HyperFrames 渲染 optional**：HyperFrames CLI，負責 HTML／CSS／JS 動態影片；可在 macOS、Windows、Linux 本機使用，沒有 CLI 時不影響既有 FFmpeg fallback。

這些 provider 不是剪神主要功能；沒有設定 API 或模型時，一律回退本地 FFmpeg／PIL／Remotion 路線。完整狀態與設定約定見 `../docs/broll-providers.md`。

本地 adapter 不會自動呼叫 Higgsfield、ElevenLabs、OpenRouter 或其他付費 provider；未設定服務時仍可用 FFmpeg + faster-whisper／既有語意 JSON 完成本地輸出。

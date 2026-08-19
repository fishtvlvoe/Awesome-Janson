# Awesome-Janson integrations

這裡保留剪神實際使用的第三方方法庫副本與授權檔，方便離線查閱；全域 Agent Skill 則統一安裝在 `/Users/fishtv/Development/.skills-ssot/live/`。

## 已接入

- `shorts-master/` — 短影音七階段方法、字卡樣式、字幕模板與時間軸映射 helper。剪神的本地 adapter 是 `scripts/select_short_segments.py` + `scripts/render_shorts.py`。
- `motion-design/` — LottieFiles motion design 方法論；短片與長片的動效決策共用。
- `talking-head-video-cut/` — MIT 授權的本機口播引擎參考與動畫元件；剪神 adapter 會使用其 checklist／stamp 元件，不直接使用硬編碼 Windows 主流程。
- `moneyprinterturbo/` — optional 主題／腳本成片 provider，只保留 Agent Skill 與安裝 helper，不 vendoring 完整 345MB 應用程式。

## 全域已安裝的動畫技能

來源與安全掃描結果見：

```text
/Users/fishtv/Development/.skills-ssot/live/animation-skill-install-manifest.json
```

本地 adapter 不會自動呼叫 Higgsfield、ElevenLabs、OpenRouter 或其他付費 provider；未設定服務時仍可用 FFmpeg + faster-whisper／既有語意 JSON 完成本地輸出。

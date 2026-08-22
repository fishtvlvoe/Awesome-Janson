# HyperFrames provider

剪神把官方 [HyperFrames](https://github.com/heygen-com/hyperframes) 接成 optional 本機 HTML-to-video provider。它可以在 macOS、Windows、Linux 本機使用，不要求用戶準備 Linux 主機。

## 使用方式

```bash
# 直接使用官方 CLI
npx hyperframes init my-video --example blank
cd my-video
npx hyperframes preview
npx hyperframes lint
npx hyperframes render --output final.mp4
```

從剪神呼叫同一條路線：

```bash
python3 scripts/hyperframes_provider.py doctor /path/to/project
python3 scripts/hyperframes_provider.py lint /path/to/project
python3 scripts/hyperframes_provider.py check /path/to/project
python3 scripts/hyperframes_provider.py render /path/to/project --output final.mp4
```

需要跨機器一致輸出時，HyperFrames 自己提供 `--docker` 路線；這仍然是 HyperFrames 的一般 Docker 模式，不等於必須使用 `xiaotianfotos/HyperFrames-RenderKit`。

## 讓各種 LLM 都能使用

HyperFrames 的 Agent Skills 可用官方 installer 安裝：

```bash
npx skills add heygen-com/hyperframes --full-depth
```

Skills 是給 Claude、Cursor、Gemini CLI、Codex、GitHub Copilot CLI 等 coding agents 讀的操作規則；真正執行出片的核心仍是 `npx hyperframes` CLI。沒有支援 Skills 的 LLM，也可以依照本文件直接呼叫 CLI。

## 與 RenderKit 的關係

`xiaotianfotos/HyperFrames-RenderKit` 是另一個 Linux x86_64 專用的實驗渲染器。它不是剪神的一般必要依賴；剪神預設使用 HyperFrames 本機 CLI，RenderKit 只保留為未來的進階 optional 路線。

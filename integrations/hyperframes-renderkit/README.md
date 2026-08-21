# HyperFrames RenderKit provider

剪神把 [HyperFrames-RenderKit](https://github.com/xiaotianfotos/HyperFrames-RenderKit) 接成 optional HyperFrames 渲染 provider。它不取代剪神既有的 FFmpeg／PIL／Remotion 路線，也不把 upstream 的 Electron／Chromium runtime vendoring 進來。

## 適用範圍

- HyperFrames 專案需要 deterministic rendering、interval routing 與 final-file verification。
- 執行環境是 Linux x86_64，具備 Node.js 22、FFmpeg／FFprobe、Chromium-compatible display session。
- RenderKit checkout 保留在剪神之外，並由 `hf-render check → plan → run` fail-closed 驗證。

目前的 macOS／Windows／Linux 非 x86_64 剪神流程不受影響，繼續使用既有本地渲染器。

## 設定與使用

```bash
export AWJ_HYPERFRAMES_RENDERKIT_ROOT=/opt/HyperFrames-RenderKit
python3 scripts/hyperframes_renderkit_provider.py check /path/to/hyperframes-project
python3 scripts/hyperframes_renderkit_provider.py plan /path/to/hyperframes-project \
  --config /path/to/delivery.json
python3 scripts/hyperframes_renderkit_provider.py run /path/to/hyperframes-project \
  --config /path/to/delivery.json --report /path/to/report
```

也可用 `AWJ_HYPERFRAMES_RENDERKIT_CLI=/absolute/path/to/hf-render` 直接指定 CLI。provider 不會自動 clone、build、安裝 Electron，也不會把 unsupported fallback 當成成功。

官方 runtime 建置成本很高，請依 upstream 的 pinned Electron／Chromium 與 Linux VAAPI 文件，在獨立主機完成；剪神只負責路由與保護既有 fallback。

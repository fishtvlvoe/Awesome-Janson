# AGENTS.md — 給 Codex CLI / 其他 agent 的指示

這個資料夾是一套「口播長錄影 → 短影音／長片」的剪片工作流。
課程講座、商品開箱、產品介紹、自錄口播、客戶見證都適用。

**開工前必讀：`SKILL.md`（規則總表）。需要細節時再讀 `references/手冊.md`。**

> ⚠️ 這份 `AGENTS.md` 刻意寫得短。Codex 的 `AGENTS.md` 合計有大小上限（預設約 32 KiB），
> `references/手冊.md` 超過 30 KB，**不要把它的內容搬進這個檔案**——
> 它是一般檔案，你需要時自己去讀就好。

## 開場先做環境判別，四題答完才動手

1. **我能不能執行本機指令？** 跑 `ffmpeg -version` 測。
   不能就老實說「我沒辦法在這裡算出 mp4」，只做到設定檔為止，**不要假裝在渲染**。
2. **使用者的作業系統？** `python -c "import platform; print(platform.system())"`
3. **使用者用哪個 AI 工具？** 影響的只有「檔案放哪」，不影響能做什麼：
   Claude Code → `~/.claude/skills/`＋`CLAUDE.md`；
   Claude 桌面版 Cowork → 帳號層級的 Customize，不讀本機資料夾；
   Codex CLI → `~/.agents/skills/`＋`AGENTS.md`。
4. **錄影是模式一還是模式二？**（見下表）判斷不出來就問，不要猜。

| | 模式一 雙畫面錄影 | 模式二 單機位自錄 |
|---|---|---|
| 來源 | 課程、講座、會議側錄（左投影片＋右講師） | 商品開箱、產品介紹、口播、見證 |
| `paths.py` 的 `CAM`/`SLIDE` | 量出來的 crop | 都填 `"null"` |
| 版面 | `A` / `B` / `C` | `F` / `P` |
| 要量幾何 | 要 | 不用，跳過 |
| 額外必讀 | 手冊第 8 章（立場衝突） | **手冊第 12 章（選段模板 ＋ 廣告用語避雷）** |

## 你可以直接執行的指令

```bash
cd scripts
python ingest.py "<專案資料夾>"      # 錄影 → 逐字稿
python precheck.py <tags>            # 算圖前健檢
python queue.py   <tags>             # 算圖
python verify_long.py <tags>         # 成品驗收
python monoaudit.py                  # 段落順序檢查
python cardchk.py                    # 片頭圖卡溢框檢查
```

`<tags>` 是設定檔前綴，例如 `p3` 對應 `p3_cfg.py`。

## 硬規定

1. **先改 `scripts/paths.py`**，這是唯一的環境設定檔（專案路徑、字型、BGM、來源錄影代號、畫面幾何）。
   沒填完就別往下跑。
2. **所有剪輯參數照 `SKILL.md`**，不要自己調整靜音門檻、留白、字幕長度、動畫節奏。
3. **字幕分句逐句手寫**，不准用程式自動斷句。程式只負責簡轉繁與術語校正。
4. **`precheck.py` NG 就停**。一支長片算 5–9 分鐘，錯了就是白燒。
5. **算完一定跑 `verify_long.py` + `monoaudit.py` + `cardchk.py` 三項**，全過才算交付。
6. **內容安全清單（手冊第 8 章）逐條檢查**，有疑慮先問人，不要自己判斷「應該還好」。
7. **不要把錄影檔上傳到任何雲端服務**——裡面有客戶資料與後台畫面。
8. **模式二額外**：不准幫商品補任何使用者沒講過的數字或功效；
   療效用語、最高級用語、沒有出處的數字一律不能留。有疑慮就標記起來問人，
   **不要自己改寫成模糊講法就放行**。詳見手冊第 12-6 節。

## 常見誤區

- 改了 `SPANS` 忘了同步位移 `LINES`／`CARDS`／`ANIM` → 字幕整段偏移。
- `ANIM` 元件缺必填參數 → 算到一半 KeyError。查 `SKILL.md` 的元件表。
- ASS 字幕的 `Fontname` 要填**字型完整名稱**（例：`GenSenRounded2 TW B`），不是家族名。
- 同一支錄影被非遞增取用時（74 分 → 19 分 → 40 分），先跑 `monoaudit.py` 確認。

## macOS 注意事項

- `brew install ffmpeg python`，確認 `ffmpeg -filters | grep subtitles` 有輸出。
- 沒有 CUDA，`ingest.py` 用 `device="cpu", compute_type="int8"`。
- 路徑一律用 `os.path.join`，不要自己接斜線。

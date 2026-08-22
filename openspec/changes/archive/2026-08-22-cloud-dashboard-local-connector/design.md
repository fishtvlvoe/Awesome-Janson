## Context

既有狀態分成兩邊：

- `https://awesome-janson-dashboard.pages.dev/` 目前只提供靜態 Dashboard 與功能說明。
- Awesome-Janson 的影片、字幕、分鏡、FFmpeg 與 HyperFrames 都在使用者本機執行。

固定網址不是租戶識別。所有人載入相同的前端程式，但每次安裝都必須有不可猜測的安裝身分、獨立的狀態空間與只對該安裝有效的憑證。第一版採匿名 capability-based access：持有該次安裝核發的有效能力憑證，才能存取該租戶；不建立使用者帳號資料庫。

Cloudflare 官方架構允許 Pages Functions 綁定由獨立 Worker 建立的 Durable Object。Durable Object 適合把同一安裝的 Dashboard 與 Connector 放在同一個強一致、可接受 WebSocket 的房間；Hibernation API 可在閒置時保留 WebSocket 而不依賴記憶體狀態。

## Goals / Non-Goals

**Goals:**

- 使用者不需要 Cloudflare 帳號，也不需要 Google 登入。
- 安裝完成後 Connector 自動開啟 Dashboard 並完成首次配對，不要求貼 token、開 port、設定 IP 或路由器。
- 所有人可共用固定 Dashboard 網址，但不同安裝的命令、狀態與工作階段絕不互通。
- 本機只建立 outbound HTTPS／WebSocket 連線，雲端不能任意掃描或直接連入 localhost。
- 第一版用 `connector.health` 與 `job.echo` 證明雲端與本機可雙向連線、回傳結果與處理斷線。
- 原始影片、輸出影片、API key、本機絕對路徑與任意 shell 指令不進入第一版雲端協定。

**Non-Goals:**

- 第一版不支援跨電腦同步、帳號復原、團隊成員、邀請或共用專案。
- 第一版不支援 Google OAuth、Cloudflare Access 或終端使用者 Cloudflare 帳號。
- 第一版不傳輸影片檔、不執行正式剪輯、不建立雲端影片佇列。
- 第一版不把 Dashboard 直接連到 `localhost`，也不建立 Cloudflare Tunnel 到每台使用者電腦。
- 第一版不允許雲端傳送任意命令、任意參數或任意檔案路徑。
- 第一版先以 macOS 開發與 E2E 驗證；Windows 安全儲存與安裝包屬後續相容工作。

## Decisions

### 終端使用者免 Cloudflare 與 Google 帳號

**選擇**：Cloudflare 帳號只屬於 Awesome-Janson 服務營運方。終端使用者以安裝時核發的匿名 capability credential 存取自己的連線空間。

**理由**：第一版的核心是把一台本機與一個瀏覽器安全連起來，不需要先引入個人資料、OAuth consent screen、帳號合併與復原流程。

**替代方案**：Google OAuth。它適合後續跨裝置與團隊功能，但會把「本機能不能連上」和「帳號系統是否正常」綁在一起，因此不納入第一版。

### 租戶身分來自每次安裝而不是固定網址

**選擇**：首次啟動由服務端建立至少 128-bit 隨機 `installation_id` 與至少 256-bit 隨機 `connector_secret`。租戶鍵為 `installation_id`；固定網址只載入共用 UI。

Pages Functions 只有在驗證 credential 或 session 後，才能用 token 內的 `installation_id` 呼叫 `idFromName(installation_id)` 取得對應 Durable Object。不得採用 query string、IP、瀏覽器自行提交的 tenant 名稱或可連續猜測的數字 ID 來選擇租戶。

**理由**：網址相同不會造成資料碰撞；每個 Durable Object 都是該次安裝的獨立房間與儲存邊界。

**替代方案**：每位使用者一個子網域。它仍需要身分核發與驗證，還增加 DNS、憑證與名稱碰撞問題，因此不採用。

### 一次性配對票券建立瀏覽器工作階段

**選擇**：Connector 已有有效 credential 時，向 `/api/v1/pair-tickets` 取得兩分鐘內有效、只可使用一次的 `pair_ticket`。Connector 用系統預設瀏覽器開啟 `https://awesome-janson-dashboard.pages.dev/#/connect?ticket=<ticket>`。

票券放在 URL fragment，避免出現在 HTTP request、CDN access log 與 Referer。Dashboard 立即以 POST `/api/v1/pair/exchange` 交換票券；成功後服務端設定 `HttpOnly; Secure; SameSite=Strict` 的 `janson_session` cookie，前端用 `history.replaceState` 清除 fragment。後續直接開固定網址時，以 cookie 恢復同一安裝。

票券只保存雜湊、到期時間與 consumed 狀態。重複交換一律回傳 `PAIR_TICKET_USED`，過期回傳 `PAIR_TICKET_EXPIRED`。

**理由**：使用者不需複製代碼，也不讓公開網頁直接探測 localhost。

**替代方案**：Dashboard fetch `http://127.0.0.1`。它受瀏覽器 CORS、Private Network Access 與本機 CSRF 風險影響，且會讓任何遠端頁面有機會攻擊本機服務，因此不採用。

### Pages Functions 與 Durable Object 組成同源雲端閘道

**選擇**：保留現有 Cloudflare Pages 作為 UI。新增同源 `/api/v1/*` Pages Functions，負責 schema 驗證、cookie、票券交換與 WebSocket upgrade；Durable Object class 由獨立 Worker 部署，再以 `script_name` binding 提供 Pages Functions 使用。

每個 `installation_id` 對應一個 `ConnectorRoom` Durable Object。重要狀態存入 DO storage；每條 WebSocket 的 `role`、`installation_id` 與 connection ID 寫入 serialized attachment，以便 Hibernation 後恢復。

**理由**：同源 API 避免額外 CORS 與第三方 cookie；Durable Object 提供每租戶的強一致票券消耗與即時雙向轉送。

**替代方案**：單一共享 Worker 記憶體 Map。Worker isolate 會重啟且多地執行，無法作為租戶真相來源，因此不採用。

### Connector 只建立 outbound WebSocket 並自動重連

**選擇**：Connector 使用 `wss://.../api/v1/socket?role=connector` 主動向外連線。Dashboard 以 session cookie 連接同一路徑的 `role=dashboard`。DO 僅在兩端憑證屬於同一 `installation_id` 時轉送訊息。

Connector 斷線後使用 1、2、4、8、16、30 秒上限的 exponential backoff，加入 0–20% jitter；恢復後先送 `connector.ready`。第一版不離線排隊，Dashboard 在 Connector 不在線時立即收到 `CONNECTOR_OFFLINE`。

**理由**：使用者不必開放 inbound port，NAT 與家用路由器不需要設定；失敗狀態可預測。

**替代方案**：為每位使用者建立 Cloudflare Tunnel。Tunnel 的安裝、憑證、生命週期與權限遠超過第一版需求，因此不採用。

### 命令白名單與本機資料邊界

**選擇**：v1 只接受 `connector.health` 與 `job.echo`。Worker 與 Connector 都要對 envelope 及每個 command payload 做 allowlist 驗證；未知 command 回傳 `COMMAND_NOT_ALLOWED`。

雲端訊息最大 32 KiB。payload 不得包含二進位檔、API key、簽名媒體 URL、本機絕對路徑或 shell command。Connector 不提供 `eval`、`exec`、任意 subprocess 或任意檔案讀取入口。

**理由**：先驗證連線模型，不讓測試 relay 變成遠端程式執行入口。

### 匿名租戶限制與未來帳號升級

**選擇**：匿名註冊端點限制建立頻率；每個租戶同時最多一條 Connector WebSocket 與三條 Dashboard WebSocket。新 Connector 連線取代舊 Connector，並向舊連線送出 `REPLACED_BY_NEW_CONNECTION`。

匿名租戶沒有帳號復原：若本機 credential 遺失或 Connector 重裝，就建立新的 `installation_id`；舊瀏覽器 session 只會顯示離線，不得自動認領新安裝。後續若增加 Google 登入，帳號只是把多個既有 `installation_id` 掛到同一 owner，不改變 DO 的租戶邊界。

**理由**：限制共享狀態與濫用範圍，同時保留未來加入帳號層的升級路徑。

## Implementation Contract

### Behavior

1. 首次啟動 Connector 時，自動註冊匿名安裝、保存 credential、取得一次性票券並開啟 Dashboard。
2. Dashboard 交換票券後顯示「本機已連線」與非敏感裝置標籤；重新整理或再次開啟固定網址可由安全 cookie 恢復。
3. Dashboard 發送 `connector.health`，Connector 回傳版本、平台與能力名稱；不得回傳主機名稱、使用者名稱或路徑。
4. Dashboard 發送 `job.echo`，Connector 原樣回傳允許的 UTF-8 `message` 與同一 `command_id`。
5. 不同 `installation_id` 的 Dashboard 與 Connector 不得互看狀態、接收命令或交換票券。
6. Connector 離線時 Dashboard 顯示離線，命令立即失敗；連線恢復後不重播離線期間的命令。

### Interface / data shape

`POST /api/v1/installations`

```json
{
  "client_version": "0.1.0",
  "platform": "darwin-arm64"
}
```

成功回應只出現一次完整 credential：

```json
{
  "installation_id": "ins_<random>",
  "connector_credential": "<installation_id>.<secret>",
  "pair_ticket": "<installation_id>.<one-time-secret>",
  "dashboard_url": "https://awesome-janson-dashboard.pages.dev/#/connect?ticket=<ticket>",
  "expires_in": 120
}
```

`POST /api/v1/pair-tickets` 需要 `Authorization: Bearer <connector_credential>`，核發新的單次票券。

`POST /api/v1/pair/exchange` 接受 `{ "ticket": "..." }`，成功設定 `janson_session` cookie，回傳 `{ "installation_id", "status" }`；回應不得包含 Connector secret。

WebSocket command envelope：

```json
{
  "v": 1,
  "type": "command",
  "command_id": "<uuid>",
  "command": "connector.health",
  "issued_at": "<ISO-8601 UTC>",
  "expires_at": "<ISO-8601 UTC>",
  "payload": {}
}
```

WebSocket result envelope：

```json
{
  "v": 1,
  "type": "result",
  "command_id": "<same uuid>",
  "status": "completed",
  "payload": {},
  "error": null
}
```

標準錯誤格式：

```json
{
  "error": {
    "code": "PAIR_TICKET_EXPIRED",
    "message": "配對連結已過期，請從本機剪神重新開啟。",
    "request_id": "<uuid>"
  }
}
```

### Failure modes

- Credential 無效或已撤銷：HTTP 401 `INVALID_CONNECTOR_CREDENTIAL`，不得洩漏 installation 是否存在。
- 票券過期：HTTP 410 `PAIR_TICKET_EXPIRED`。
- 票券已使用：HTTP 409 `PAIR_TICKET_USED`。
- Dashboard session 不屬於目標租戶：HTTP 403 `TENANT_MISMATCH` 並關閉 WebSocket。
- Connector 不在線：命令結果 `CONNECTOR_OFFLINE`，不得排隊。
- 命令未知、payload 超限或 schema 錯誤：`COMMAND_NOT_ALLOWED`、`PAYLOAD_TOO_LARGE` 或 `INVALID_MESSAGE`，不得轉送本機。
- WebSocket 中斷：UI 顯示離線；Connector 自動重連；未完成命令標記 `CONNECTION_LOST`。
- 雲端不可用：本機剪輯 CLI 仍可獨立使用；Connector 顯示連線失敗但不得阻止本機工作。

### TDD 失敗矩陣（Phase 2 確認後才寫紅燈測試）

| 失敗點 | 紅燈測試名稱 | 預期錯誤／行為 |
| --- | --- | --- |
| 兩個租戶互相送命令 | `tenant_a_cannot_reach_tenant_b` | `TENANT_MISMATCH`，B 不收到訊息 |
| 同一票券交換兩次 | `pair_ticket_is_single_use` | 第二次 `PAIR_TICKET_USED` |
| 過期票券交換 | `expired_pair_ticket_is_rejected` | `PAIR_TICKET_EXPIRED` |
| 偽造 Connector credential | `forged_connector_credential_is_rejected` | `INVALID_CONNECTOR_CREDENTIAL` |
| 未知命令 | `unknown_command_never_reaches_connector` | `COMMAND_NOT_ALLOWED` |
| payload 超過 32 KiB | `oversized_payload_is_rejected` | `PAYLOAD_TOO_LARGE` |
| Connector 離線送命令 | `offline_connector_fails_without_queueing` | `CONNECTOR_OFFLINE`，重連後不重播 |
| WebSocket 斷線重連 | `connector_reconnects_with_bounded_backoff` | delay 依序增加且上限 30 秒 |
| 新 Connector 取代舊連線 | `new_connector_replaces_old_connection` | 舊連線收到 `REPLACED_BY_NEW_CONNECTION` |
| 雲端失效 | `local_cli_remains_usable_when_cloud_is_down` | 本機 CLI 行為不受阻擋 |

### Acceptance criteria

- 單元測試覆蓋 credential、票券生命週期、命令 schema、租戶路由與重連 backoff。
- 本機整合測試同時啟動兩個 installation fixture，證明 A/B 雙向隔離。
- Cloudflare staging E2E：Connector 註冊 → 自動開頁 → 顯示 online → `connector.health` → `job.echo` → 中斷 → offline → 重連 → online。
- 瀏覽器網路記錄與 Worker log 不出現 Connector secret、完整 pair ticket、API key、本機路徑或影片資料。
- `spectra validate cloud-dashboard-local-connector` 與 `spectra analyze cloud-dashboard-local-connector --json` 無 Critical／High findings。

### Scope boundaries

- Phase 2 只建立測試與 fixture，不部署 production、不新增正式影片命令。
- 第一版實作只完成匿名安裝、配對、租戶隔離、WebSocket relay、`connector.health` 與 `job.echo`。
- Google 登入、跨裝置復原、團隊、多租戶帳號管理、R2、Queue 與影片傳輸全部延後。

## Risks / Trade-offs

- [風險] 無帳號代表 credential 遺失後無法找回舊租戶 → Mitigation：安裝時明確說明重新安裝會重新配對；未來以 owner account 掛接既有 installation。
- [風險] 一次性票券被瀏覽器擴充套件讀取 → Mitigation：放 URL fragment、兩分鐘到期、單次消耗、交換後立即清除。
- [風險] 匿名註冊被大量濫用 → Mitigation：註冊 endpoint 使用 Cloudflare rate limiting、限制同租戶連線數、未連線租戶依 retention policy 清理。
- [風險] Durable Object Hibernation 清除記憶體 → Mitigation：重要狀態存 DO storage，連線角色放 serialized attachment，不依賴 constructor 記憶體。
- [風險] 固定 Pages 網址讓使用者誤以為資料已上雲 → Mitigation：UI 持續標示「影片留在本機」，協定阻擋二進位與本機路徑。
- [取捨] 第一版不做離線命令佇列 → Mitigation：UI 立即回報離線，避免過期剪輯命令在重連後意外執行。
- [取捨] 第一版先驗證 macOS → Mitigation：credential storage 與 browser opener 定義 adapter interface，Windows 實作後補，不混入核心協定。

## Migration Plan

1. 建立 staging Durable Object Worker 與 Pages Functions binding，不改 production Dashboard 行為。
2. 以 fixture Connector 跑完兩租戶隔離與 WebSocket E2E。
3. 在 Dashboard 加入 feature flag，只對測試安裝顯示連線狀態。
4. 完成安全審查後部署 production Worker，再部署 Pages Functions 與 Dashboard UI。
5. 發布 Connector 安裝更新；既有使用者首次啟動時建立匿名 installation。
6. 回滾時關閉 Dashboard feature flag 與 Connector 雲端連線；本機剪輯功能維持可用。DO migration 不執行 `deleted_classes`，保留資料供修復。

## Open Questions

第一版沒有阻擋實作的開放問題。自訂網域、Windows 安裝包、匿名租戶保存期限與未來 Google 帳號層，另開 change 決策。

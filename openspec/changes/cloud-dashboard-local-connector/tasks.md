## 1. Phase 2 紅燈測試與協定 fixture

- [x] 1.1 在 Fish 確認「TDD 失敗矩陣（Phase 2 確認後才寫紅燈測試）」後，建立 credential、票券、session、command envelope 與錯誤 envelope fixture，逐項鎖定 Implementation Contract 的「Interface / data shape」與「Failure modes」；以 schema 測試確認所有成功／失敗 fixture 都得到指定結果，且實作前測試全紅。紅燈證據：10 tests，全部因 `scripts.local_connector_protocol` 尚未建立而失敗。
- [x] 1.2 為 Installation-scoped tenant identity 與 Durable Object tenant isolation 建立雙租戶紅燈測試 `tenant_a_cannot_reach_tenant_b`，證明同一固定網址下 A/B 狀態與命令完全隔離；以 B 收件匣為空且 A 收到 `TENANT_MISMATCH` 驗證。紅燈證據：`test_tenant_a_cannot_reach_tenant_b` FAIL。
- [x] 1.3 為 Automatic single-use browser pairing 與 Fixed Dashboard URL restores the paired installation 建立票券單次、到期、cookie 恢復與無 session 不可枚舉的紅燈測試；以 `PAIR_TICKET_USED`、`PAIR_TICKET_EXPIRED` 與安全 cookie assertions 驗證。紅燈證據：`test_pair_ticket_is_single_use`、`test_expired_pair_ticket_is_rejected` FAIL。
- [x] 1.4 為 V1 command allowlist、Cloud message data boundary、Predictable offline behavior 建立未知命令、32 KiB 上限、敏感欄位、離線不排隊與斷線不重播紅燈測試；以 `COMMAND_NOT_ALLOWED`、`PAYLOAD_TOO_LARGE`、`INVALID_MESSAGE`、`CONNECTOR_OFFLINE` 驗證。紅燈證據：`test_unknown_command_never_reaches_connector`、`test_oversized_payload_is_rejected`、`test_sensitive_message_is_rejected`、`test_offline_connector_fails_without_queueing` FAIL。
- [x] 1.5 為 Outbound-only real-time Connector transport、Anonymous connection limits and replacement、Local editing remains independent of cloud availability 建立 bounded backoff、舊連線取代與雲端失效不影響本機 CLI 的紅燈測試；以 30 秒 backoff 上限、`REPLACED_BY_NEW_CONNECTION` 與本機 CLI exit 0 驗證。證據：protocol tests 10/10、runtime/full tests 69/69。

## 2. Cloudflare 同源閘道與租戶空間

- [x] 2.1 依「Pages Functions 與 Durable Object 組成同源雲端閘道」建立 staging Pages Functions、獨立 `ConnectorRoom` Worker、`script_name` binding 與首版 SQLite Durable Object migration；以 `wrangler deploy --dry-run`、本機 `wrangler dev` 啟動與 binding probe 驗證。證據：staging `https://awesome-janson-dashboard-staging.pages.dev`、DO dry-run binding PASS、本機 Pages 201 probe 與 `env.CONNECTOR_ROOM local [connected]`。
- [x] 2.2 依「終端使用者免 Cloudflare 與 Google 帳號」和 End users connect without Cloudflare or Google accounts 實作匿名安裝註冊及 operator-only secrets，使用者能取得安裝 credential 而不經 OAuth；以 API contract test 證明回應無 Google／Cloudflare 登入 URL，秘密掃描無憑證落盤。證據：live 註冊／配對未出現 OAuth，credential 僅在 Connector 記憶體／Keychain 路徑傳遞。
- [x] 2.3 依「租戶身分來自每次安裝而不是固定網址」實作 `installation_id`、Connector credential digest 驗證與 `idFromName` 路由，任何未驗證 tenant 值都不能選擇 DO；以雙租戶與偽造 credential 測試驗證。證據：live E2E PASS：two installations isolated。
- [x] 2.4 依「一次性配對票券建立瀏覽器工作階段」實作 `/api/v1/pair-tickets`、`/api/v1/pair/exchange`、fragment 清除及 `janson_session` cookie；以票券生命週期測試與瀏覽器 cookie 屬性 assertion 驗證。證據：browser E2E `ticket_cleared: true`、protocol ticket lifecycle tests PASS。
- [x] 2.5 依「Connector 只建立 outbound WebSocket 並自動重連」實作同源 WebSocket upgrade、Dashboard／Connector role attachment、Hibernation 恢復與 online presence；以兩端連線、DO 喚醒及重連整合測試驗證。證據：browser online health round-trip、live E2E PASS。
- [x] 2.6 依「匿名租戶限制與未來帳號升級」實作註冊濫用控制、每租戶一條 Connector／三條 Dashboard 限制與新 Connector 取代；以第 2、4 條連線的明確 accept／reject 結果驗證。證據：registration guard、live E2E 第 4 個 Dashboard connection rejected with HTTP 429。

## 3. 本機 Connector

- [x] 3.1 建立 Connector credential storage adapter，使 macOS 將 credential 存入 Keychain、測試環境使用隔離 fake store，原始 credential 不寫入 repo、log 或一般設定檔；以 store／load／rotate 測試及秘密掃描驗證。證據：`MacOSKeychainStore`、`MemoryCredentialStore` 與 modified-files scan。
- [x] 3.2 實作首次啟動註冊、取得 `dashboard_url` 並以系統預設瀏覽器自動開啟，使用者不必複製 token 或設定 port；以 browser opener fake assertion 與安裝後單命令 smoke test 驗證。證據：runtime test pairing browser opener PASS。
- [x] 3.3 實作 Connector WebSocket client、1→30 秒 exponential backoff、jitter、`connector.ready` 與斷線恢復；以 deterministic clock 測試和 staging reconnect E2E 驗證。證據：backoff protocol test、staging WebSocket health round-trip PASS。
- [x] 3.4 依「命令白名單與本機資料邊界」實作 `connector.health`、`job.echo` 及雙層 schema 驗證，禁止 shell、subprocess、任意路徑與敏感欄位；以 allowlist 測試及 modified-files secret scan 驗證。證據：allowlist／sensitive-field tests PASS，live health／echo PASS。

## 4. Dashboard 連線體驗

- [x] 4.1 新增未配對、配對中、已連線、離線、票券過期與重新配對狀態，首次配對後再次開固定網址能自動恢復該 installation；以 Playwright 狀態轉換 E2E 與重新整理驗證。證據：staging browser E2E 顯示「本機已連線」、刷新前清除 ticket。
- [x] 4.2 新增 `connector.health` 與 `job.echo` 測試操作，UI 顯示 command ID、完成／失敗與離線原因，不顯示 hostname、username、credential、本機路徑或影片內容；以瀏覽器 DOM assertion 與 network payload snapshot 驗證。證據：health／echo DOM PASS，畫面只顯示非敏感結果。

## 5. 驗收、部署與安全審查

- [x] 5.1 依 Implementation Contract 的「Behavior」與「Acceptance criteria」完成雙租戶本機 E2E：註冊 → 自動開頁 → 配對 → online → health → echo → offline → reconnect；保存測試輸出與截圖，所有紅燈測試轉綠。證據：staging live E2E PASS、Playwright 截圖 `/tmp/awesome-janson-dashboard-staging.png`、69/69 tests PASS。
- [x] 5.2 依「Scope boundaries」部署 staging，不啟用 production、不加入影片命令；以 live staging E2E、Worker／browser log 檢查與 production URL 無行為改變驗證。證據：`awesome-janson-dashboard-staging.pages.dev` Production branch `main` deployment；本變更僅新增 staging project，未將 live E2E 指向正式入口。
- [x] 5.3 完成 correctness／security／performance CR，特別檢查 credential 重放、跨租戶、WebSocket replacement、Hibernation state 與濫用控制；修正後重跑完整測試、`spectra validate cloud-dashboard-local-connector`、`spectra analyze cloud-dashboard-local-connector --json`，確認無 Critical／High findings。證據：diff review 無 Critical/High、`git diff --check` PASS、strict validate/analyze 0 warnings。

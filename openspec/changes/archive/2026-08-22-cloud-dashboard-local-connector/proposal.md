## Why

目前 Cloudflare Pages 上的剪神 Dashboard 與使用者本機的 Awesome-Janson 是兩個互不相連的入口。若沒有明確的安裝身分、配對與租戶隔離機制，所有人雖然共用同一個網址，卻無法安全地只看到並控制自己的本機工作台。

這個變更要讓使用者安裝 Janson Connector 後，由本機自動開啟固定的 Dashboard 網址並完成免帳號配對；使用者不需要 Cloudflare 帳號，也不需要先建立 Google 帳號登入流程、開 port、設定 IP、貼 token 或調整路由器。

## What Changes

- 新增本機 Janson Connector 的安裝身分：首次啟動產生隨機 `installation_id` 與裝置金鑰，私密資料只存放於作業系統安全儲存區。
- 新增一次性配對流程：Connector 向雲端取得短效配對票券後，自動開啟剪神 Dashboard；Dashboard 交換票券後，只能連到該次安裝所屬的租戶空間。
- 新增免帳號瀏覽器工作階段：首次配對後，固定 Dashboard 網址可在同一瀏覽器自動恢復對應的本機連線；票券過期、撤銷或換瀏覽器時重新配對。
- 新增本機主動向外建立的 WebSocket 長連線，不要求使用者開放本機連入 port；Dashboard 與 Connector 透過同一個 Cloudflare Durable Object 交換小型指令與狀態事件。
- 新增租戶隔離規則：每個 `installation_id` 對應獨立 Durable Object；Worker 只接受伺服器核發、綁定安裝身分與角色的短效憑證，不以固定網址、IP 或前端傳入的任意 tenant 值判斷租戶。
- 新增第一版安全命令白名單，只提供 `connector.health` 與 `job.echo` 測試，不允許任意 shell、任意檔案路徑、影片上傳或正式剪輯。
- 新增連線狀態 UI：顯示未安裝、配對中、已連線、離線、票券過期與重新配對；不把原始影片、API key 或本機路徑送到雲端。

## Capabilities

### New Capabilities

- `dashboard-local-connector`: 定義免帳號安裝身分、一次性配對、瀏覽器工作階段、Cloudflare 即時轉送、租戶隔離、命令白名單與第一版連線測試。

### Modified Capabilities

無。

## Impact

- Cloudflare：既有 Pages Dashboard 增加同源 API 入口；新增 Pages Functions gateway、獨立 Durable Object Worker、WebSocket Hibernation 與伺服器端簽章 secret。
- 本機：新增可常駐的 Connector 程序、作業系統安全儲存、瀏覽器啟動與 WebSocket 重連能力。
- Dashboard：新增配對票券交換、瀏覽器工作階段、裝置狀態與測試命令 UI。
- 安全：新增一次性票券、角色分離、短效權杖、撤銷、重放保護、命令 schema 驗證、租戶隔離與匿名註冊流量限制。
- 部署：終端使用者不需要 Cloudflare 帳號；Cloudflare 帳號、專案、網域與服務端秘密只由 Awesome-Janson 服務營運方管理。

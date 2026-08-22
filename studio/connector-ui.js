(() => {
  "use strict";

  const $ = (selector) => document.querySelector(selector);
  const statusEl = $("#connector-status");
  const cardEl = $("#connector-panel");
  const labelEl = $("#connector-status-label");
  const detailEl = $("#connector-status-detail");
  const badgeEl = $("#connector-badge");
  const copyEl = $("#connector-copy");
  const resultEl = $("#connector-result");
  const healthButton = $("#connector-health");
  const echoButton = $("#connector-echo");
  const state = { name: "local", online: false, apiAvailable: true, socket: null, pending: new Map() };

  const statusCopy = {
    local: { label: "本機模式", detail: "等待連線", badge: "本機模式", copy: "這頁目前是本機預覽。部署到 Dashboard 後，啟動本機 Connector 就會自動配對。" },
    unpaired: { label: "尚未配對", detail: "啟動本機 Connector", badge: "尚未配對", copy: "啟動本機 Connector 後，瀏覽器會自動完成一次性配對。" },
    pairing: { label: "正在配對", detail: "建立本機工作階段", badge: "配對中", copy: "正在建立這台電腦的工作階段，請稍候。" },
    online: { label: "本機已連線", detail: "可以執行測試工作", badge: "已連線", copy: "本機 Connector 已在線。影片、金鑰與本機路徑不會傳到 Dashboard。" },
    offline: { label: "本機離線", detail: "重新啟動 Connector", badge: "離線", copy: "Dashboard 還在，但本機 Connector 沒有在線；重新啟動即可恢復。" },
    expired: { label: "配對已失效", detail: "請重新啟動 Connector", badge: "需要重新配對", copy: "這次配對連結已過期或使用過，請重新啟動本機 Connector。" },
  };

  function setState(name, detail = "") {
    state.name = name;
    state.online = name === "online";
    const copy = statusCopy[name] || statusCopy.local;
    statusEl.dataset.state = name;
    cardEl.dataset.state = name;
    labelEl.textContent = copy.label;
    detailEl.textContent = detail || copy.detail;
    badgeEl.textContent = copy.badge;
    copyEl.textContent = copy.copy;
    healthButton.disabled = !state.online;
    echoButton.disabled = !state.online;
  }

  function showResult(message, isError = false) {
    resultEl.hidden = false;
    resultEl.classList.toggle("is-error", isError);
    resultEl.textContent = message;
  }

  async function request(path, options = {}) {
    const response = await fetch(path, {
      credentials: "same-origin",
      ...options,
      headers: { accept: "application/json", ...(options.headers || {}) },
    });
    const contentType = response.headers.get("content-type") || "";
    const body = contentType.includes("application/json") ? await response.json() : {};
    if (!response.ok) throw new Error(body.error?.code || `HTTP_${response.status}`);
    return body;
  }

  function pairingTicket() {
    if (!location.hash.startsWith("#/connect")) return "";
    return new URLSearchParams(location.hash.split("?")[1] || "").get("ticket") || "";
  }

  async function exchangeTicket() {
    const ticket = pairingTicket();
    if (!ticket) return;
    setState("pairing");
    try {
      await request("/api/v1/pair/exchange", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ ticket }),
      });
      history.replaceState(null, "", `${location.pathname}${location.search}#top`);
    } catch (error) {
      setState(error.message === "PAIR_TICKET_EXPIRED" || error.message === "PAIR_TICKET_USED" ? "expired" : "local");
      showResult(`配對未完成：${error.message}`, true);
    }
  }

  function closeSocket() {
    if (!state.socket) return;
    state.socket.close();
    state.socket = null;
  }

  function receiveResult(message) {
    if (!message || message.type !== "result" || !state.pending.has(message.command_id)) return;
    const pending = state.pending.get(message.command_id);
    state.pending.delete(message.command_id);
    if (message.status !== "completed") {
      showResult(`測試失敗：${message.error?.code || "UNKNOWN_ERROR"}`, true);
      return;
    }
    const suffix = pending.name === "connector.health" ? "本機健康檢查完成" : `本機回應：「${message.payload?.message || "收到"}」`;
    showResult(`${suffix} · 指令 ${message.command_id.slice(-8)}`);
  }

  function openSocket() {
    if (!state.online || state.socket || !/^https?:$/.test(location.protocol)) return;
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    state.socket = new WebSocket(`${protocol}//${location.host}/api/v1/socket`);
    state.socket.addEventListener("message", (event) => {
      try { receiveResult(JSON.parse(event.data)); } catch { showResult("收到無法辨識的連線訊息。", true); }
    });
    state.socket.addEventListener("close", () => { state.socket = null; });
    state.socket.addEventListener("error", () => { state.socket?.close(); });
  }

  async function refreshStatus() {
    try {
      const session = await request("/api/v1/session");
      state.apiAvailable = true;
      if (!session.paired) {
        closeSocket();
        setState("unpaired");
        return;
      }
      if (session.online) {
        setState("online", `${session.connector_connections || 1} 台本機在線`);
        openSocket();
      } else {
        closeSocket();
        setState("offline");
      }
    } catch (error) {
      state.apiAvailable = false;
      closeSocket();
      setState("local", "此頁只供本機預覽");
    }
  }

  function commandId() {
    return window.crypto?.randomUUID?.() || `cmd_${Date.now()}_${Math.random().toString(16).slice(2)}`;
  }

  async function sendCommand(name, payload) {
    if (!state.online) return;
    const id = commandId();
    state.pending.set(id, { name });
    showResult(`測試已送出 · 指令 ${id.slice(-8)}`);
    try {
      await request("/api/v1/command", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ v: 1, type: "command", command_id: id, command: name, payload }),
      });
    } catch (error) {
      state.pending.delete(id);
      showResult(`測試未送出：${error.message}`, true);
      await refreshStatus();
    }
  }

  healthButton.addEventListener("click", () => sendCommand("connector.health", {}));
  echoButton.addEventListener("click", () => sendCommand("job.echo", { message: "Dashboard 連線正常" }));

  async function start() {
    setState("local");
    await exchangeTicket();
    await refreshStatus();
    window.setInterval(refreshStatus, 5000);
  }

  start();
})();

const encoder = new TextEncoder();

function json(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", ...headers },
  });
}

async function digest(value) {
  const bytes = await crypto.subtle.digest("SHA-256", encoder.encode(value));
  return [...new Uint8Array(bytes)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function randomSecret() {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return [...bytes].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function safeEqual(left, right) {
  if (left.length !== right.length) return false;
  let result = 0;
  for (let index = 0; index < left.length; index += 1) result |= left.charCodeAt(index) ^ right.charCodeAt(index);
  return result === 0;
}

export class ConnectorRoom {
  constructor(state) {
    this.ctx = state;
  }

  async state() {
    return (await this.ctx.storage.get("state")) || {
      installationId: null,
      credentialHash: null,
      tickets: {},
      sessions: {},
    };
  }

  async save(state) {
    await this.ctx.storage.put("state", state);
  }

  async fetch(request) {
    const url = new URL(request.url);
    const state = await this.state();

    if (url.pathname === "/register" && request.method === "POST") {
      if (state.credentialHash) return json({ error: { code: "INSTALLATION_EXISTS" } }, 409);
      const body = await request.json();
      state.installationId = String(body.installation_id || "");
      state.credentialHash = String(body.credential_hash || "");
      if (!state.installationId || !state.credentialHash) return json({ error: { code: "INVALID_REGISTRATION" } }, 400);
      await this.save(state);
      return json({ installation_id: state.installationId }, 201);
    }

    if (url.pathname === "/registration-guard" && request.method === "POST") {
      const now = Date.now();
      const clientIp = request.headers.get("x-client-ip") || "unknown";
      const recent = (state.registrationEvents || []).filter((event) => now - event.at < 60000);
      const attempts = recent.filter((event) => event.ip === clientIp).length;
      if (attempts >= 20) {
        return json({ error: { code: "REGISTRATION_RATE_LIMITED" } }, 429, { "retry-after": "60" });
      }
      recent.push({ at: now, ip: clientIp });
      state.registrationEvents = recent;
      await this.save(state);
      return json({ allowed: true });
    }

    if (url.pathname === "/pair-ticket" && request.method === "POST") {
      if (!(await this.authorizeConnector(request, state))) return json({ error: { code: "INVALID_CONNECTOR_CREDENTIAL" } }, 401);
      const ticketSecret = randomSecret();
      state.tickets[await digest(ticketSecret)] = { expiresAt: Date.now() + 120000, used: false };
      await this.save(state);
      return json({ ticket_secret: ticketSecret, expires_in: 120 });
    }

    if (url.pathname === "/pair-exchange" && request.method === "POST") {
      const body = await request.json();
      const ticketHash = await digest(String(body.ticket_secret || ""));
      const ticket = state.tickets[ticketHash];
      if (!ticket || ticket.used || Date.now() > ticket.expiresAt) {
        return json({ error: { code: ticket?.used ? "PAIR_TICKET_USED" : "PAIR_TICKET_EXPIRED" } }, ticket?.used ? 409 : 410);
      }
      ticket.used = true;
      const sessionSecret = randomSecret();
      state.sessions[await digest(sessionSecret)] = { expiresAt: Date.now() + 7 * 24 * 60 * 60 * 1000 };
      await this.save(state);
      return json({ installation_id: state.installationId, session_secret: sessionSecret });
    }

    if (url.pathname === "/status" && request.method === "GET") {
      if (!(await this.authorizeDashboard(request, state))) return json({ error: { code: "INVALID_DASHBOARD_SESSION" } }, 401);
      return json({ installation_id: state.installationId, online: this.connections("connector").length > 0, dashboard_connections: this.connections("dashboard").length, connector_connections: this.connections("connector").length });
    }

    if (url.pathname === "/command" && request.method === "POST") {
      if (!(await this.authorizeDashboard(request, state))) return json({ error: { code: "INVALID_DASHBOARD_SESSION" } }, 401);
      const connector = this.connections("connector")[0];
      if (!connector) return json({ error: { code: "CONNECTOR_OFFLINE" } }, 503);
      const body = await request.json();
      connector.send(JSON.stringify(body));
      return json({ accepted: true, command_id: body.command_id });
    }

    if (request.headers.get("Upgrade")?.toLowerCase() === "websocket" && url.pathname === "/socket") {
      const role = request.headers.get("x-room-role");
      const roomAuth = request.headers.get("x-room-auth") || "";
      const authorized = role === "connector"
        ? await this.authorizeConnectorValue(roomAuth, state)
        : role === "dashboard" && await this.authorizeDashboardValue(roomAuth, state);
      if (!authorized) return json({ error: { code: "INVALID_SOCKET_AUTH" } }, 401);
      if (role === "dashboard" && this.connections("dashboard").length >= 3) {
        return json({ error: { code: "DASHBOARD_CONNECTION_LIMIT" } }, 429, { "retry-after": "10" });
      }
      const pair = new WebSocketPair();
      const client = pair[0];
      const server = pair[1];
      if (role === "connector") {
        for (const old of this.connections("connector")) {
          old.send(JSON.stringify({ type: "error", code: "REPLACED_BY_NEW_CONNECTION" }));
          old.close(4001, "replaced");
        }
      }
      server.serializeAttachment({ installationId: state.installationId, role });
      this.ctx.acceptWebSocket(server, [role]);
      return new Response(null, { status: 101, webSocket: client });
    }

    return json({ error: { code: "NOT_FOUND" } }, 404);
  }

  async authorizeConnector(request, state) {
    return this.authorizeConnectorValue(request.headers.get("x-connector-secret") || "", state);
  }

  async authorizeConnectorValue(secret, state) {
    if (!state.credentialHash || !secret) return false;
    return safeEqual(await digest(secret), state.credentialHash);
  }

  async authorizeDashboard(request, state) {
    return this.authorizeDashboardValue(request.headers.get("x-dashboard-session") || "", state);
  }

  async authorizeDashboardValue(secret, state) {
    if (!secret) return false;
    const session = state.sessions[await digest(secret)];
    return Boolean(session && Date.now() <= session.expiresAt);
  }

  connections(role) {
    return this.ctx.getWebSockets(role);
  }

  async webSocketMessage(socket, message) {
    const attachment = socket.deserializeAttachment() || {};
    let parsed;
    try {
      parsed = JSON.parse(message);
    } catch {
      socket.send(JSON.stringify({ type: "error", code: "INVALID_MESSAGE" }));
      return;
    }
    if (attachment.role === "connector") {
      for (const dashboard of this.connections("dashboard")) dashboard.send(JSON.stringify(parsed));
    }
  }

  async webSocketClose() {}
  async webSocketError() {}
}

export default {
  async fetch() {
    return json({ error: { code: "ROOM_WORKER_ONLY" } }, 404);
  },
};

// Cloudflare Pages Advanced mode entrypoint.
const encoder = new TextEncoder();
const forbiddenKeys = new Set(["api_key", "apikey", "credential", "secret", "token", "signed_url", "path", "local_path", "shell", "subprocess"]);

function json(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json; charset=utf-8", ...headers } });
}

async function digest(value) {
  const bytes = await crypto.subtle.digest("SHA-256", encoder.encode(value));
  return [...new Uint8Array(bytes)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function randomId(prefix) {
  return `${prefix}${crypto.randomUUID().replaceAll("-", "")}`;
}

function credentialParts(value) {
  const [installationId, secret] = String(value || "").split(".", 2);
  if (!installationId || !secret) return null;
  return { installationId, secret };
}

function bearer(request) {
  const value = request.headers.get("authorization") || "";
  return value.startsWith("Bearer ") ? value.slice(7) : "";
}

function cookie(request, name) {
  const values = (request.headers.get("cookie") || "").split(";").map((part) => part.trim());
  const match = values.find((part) => part.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : "";
}

function room(env, installationId) {
  return env.CONNECTOR_ROOM.get(env.CONNECTOR_ROOM.idFromName(installationId));
}

async function forward(env, installationId, path, init = {}) {
  return room(env, installationId).fetch(new Request(`https://connector-room${path}`, init));
}

function validateCommand(command) {
  let encoded;
  try {
    encoded = encoder.encode(JSON.stringify(command));
  } catch {
    return { code: "INVALID_MESSAGE", status: 400 };
  }
  if (encoded.byteLength > 32 * 1024) return { code: "PAYLOAD_TOO_LARGE", status: 413 };
  if (!command || command.v !== 1 || command.type !== "command" || typeof command.command_id !== "string") return { code: "INVALID_MESSAGE", status: 400 };
  if (!new Set(["connector.health", "job.echo"]).has(command.command)) return { code: "COMMAND_NOT_ALLOWED", status: 403 };
  if (!command.payload || typeof command.payload !== "object" || Array.isArray(command.payload)) return { code: "INVALID_MESSAGE", status: 400 };
  const walk = (value) => {
    if (Array.isArray(value)) return value.every(walk);
    if (!value || typeof value !== "object") return true;
    return Object.entries(value).every(([key, child]) => !forbiddenKeys.has(key.toLowerCase()) && walk(child));
  };
  if (!walk(command.payload || {})) return { code: "INVALID_MESSAGE", status: 400 };
  if (command.command === "connector.health" && Object.keys(command.payload).length) return { code: "INVALID_MESSAGE", status: 400 };
  if (command.command === "job.echo" && typeof command.payload?.message !== "string") return { code: "INVALID_MESSAGE", status: 400 };
  return null;
}

async function api(request, env) {
  const url = new URL(request.url);
  const path = url.pathname;

  if (path === "/api/v1/installations" && request.method === "POST") {
    const registrationGuard = env.CONNECTOR_ROOM.get(env.CONNECTOR_ROOM.idFromName("__registration_gate__"));
    const guardResponse = await registrationGuard.fetch(new Request("https://connector-room/registration-guard", {
      method: "POST",
      headers: { "x-client-ip": request.headers.get("cf-connecting-ip") || "unknown" },
    }));
    if (!guardResponse.ok) return guardResponse;
    const installationId = randomId("ins_");
    const secret = randomId("");
    const registered = await forward(env, installationId, "/register", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ installation_id: installationId, credential_hash: await digest(secret) }),
    });
    if (!registered.ok) return registered;
    return json({ installation_id: installationId, connector_credential: `${installationId}.${secret}`, dashboard_url: `${url.origin}/#/connect`, expires_in: 0 }, 201);
  }

  if (path === "/api/v1/pair-tickets" && request.method === "POST") {
    const parts = credentialParts(bearer(request));
    if (!parts) return json({ error: { code: "INVALID_CONNECTOR_CREDENTIAL" } }, 401);
    const response = await forward(env, parts.installationId, "/pair-ticket", { method: "POST", headers: { "x-connector-secret": parts.secret } });
    if (!response.ok) return response;
    const result = await response.json();
    return json({ ticket: `${parts.installationId}.${result.ticket_secret}`, dashboard_url: `${url.origin}/#/connect?ticket=${parts.installationId}.${result.ticket_secret}`, expires_in: result.expires_in });
  }

  if (path === "/api/v1/pair/exchange" && request.method === "POST") {
    const body = await request.json();
    const parts = credentialParts(body.ticket);
    if (!parts) return json({ error: { code: "PAIR_TICKET_EXPIRED" } }, 410);
    const response = await forward(env, parts.installationId, "/pair-exchange", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ ticket_secret: parts.secret }) });
    if (!response.ok) return response;
    const result = await response.json();
    return json({ installation_id: result.installation_id, status: "paired" }, 200, { "set-cookie": `janson_session=${encodeURIComponent(`${parts.installationId}.${result.session_secret}`)}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=604800` });
  }

  const session = credentialParts(cookie(request, "janson_session"));
  if (path === "/api/v1/session" || path === "/api/v1/status") {
    if (!session) return json({ paired: false, online: false });
    const response = await forward(env, session.installationId, "/status", { headers: { "x-dashboard-session": session.secret } });
    if (!response.ok) return json({ paired: false, online: false });
    const status = await response.json();
    return json({ paired: true, ...status });
  }

  if (path === "/api/v1/command" && request.method === "POST") {
    if (!session) return json({ error: { code: "INVALID_DASHBOARD_SESSION" } }, 401);
    const command = await request.json();
    const validationError = validateCommand(command);
    if (validationError) return json({ error: validationError }, validationError.status);
    return forward(env, session.installationId, "/command", { method: "POST", headers: { "content-type": "application/json", "x-dashboard-session": session.secret }, body: JSON.stringify(command) });
  }

  if (path === "/api/v1/socket" && request.headers.get("upgrade")?.toLowerCase() === "websocket") {
    const connector = credentialParts(bearer(request));
    const dashboard = session;
    const role = connector ? "connector" : dashboard ? "dashboard" : "";
    const identity = connector || dashboard;
    if (!role || !identity) return json({ error: { code: "INVALID_SOCKET_AUTH" } }, 401);
    const proxy = new Request("https://connector-room/socket", request);
    proxy.headers.set("x-room-role", role);
    proxy.headers.set("x-room-auth", identity.secret);
    return room(env, identity.installationId).fetch(proxy);
  }

  return json({ error: { code: "NOT_FOUND" } }, 404);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname.startsWith("/api/")) return api(request, env);
    return env.ASSETS.fetch(request);
  },
};

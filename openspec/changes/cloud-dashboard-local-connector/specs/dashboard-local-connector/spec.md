## ADDED Requirements

### Requirement: End users connect without Cloudflare or Google accounts
The system SHALL allow an end user to install and pair a local Janson Connector without owning a Cloudflare account or signing in with Google. Cloudflare project ownership and server secrets MUST remain operator-only concerns.

#### Scenario: First launch requires no account
- **WHEN** a newly installed Connector starts for the first time
- **THEN** the system SHALL create an anonymous installation identity and open the Dashboard pairing URL without presenting a Cloudflare or Google login requirement

##### Example: Clean macOS installation
- **GIVEN** Connector version `0.1.0` has no stored credential and no Google or Cloudflare environment variables
- **WHEN** the user launches `janson connector start`
- **THEN** the Connector receives an `ins_` installation identifier and opens the returned `https://awesome-janson-dashboard.pages.dev/#/connect?ticket=...` URL

### Requirement: Installation-scoped tenant identity
The system SHALL assign every Connector installation an unguessable `installation_id` and separate credential. The API gateway MUST derive the Durable Object tenant from a verified credential or browser session and MUST NOT trust an IP address, fixed Dashboard URL, sequential identifier, or caller-provided tenant value as tenant authority.

#### Scenario: Two installations use the same Dashboard URL
- **WHEN** installation A and installation B open the same public Dashboard origin
- **THEN** each Dashboard SHALL connect only to the Durable Object derived from its own verified installation session

##### Example: A and B share the public origin
- **GIVEN** installation A is `ins_A7f2` and installation B is `ins_B9c4`
- **WHEN** both browsers load `https://awesome-janson-dashboard.pages.dev/`
- **THEN** A resolves only to room `ins_A7f2` and B resolves only to room `ins_B9c4`

#### Scenario: Caller supplies another tenant identifier
- **WHEN** a valid installation A session submits installation B's identifier in a query parameter or payload
- **THEN** the gateway SHALL reject the request with `TENANT_MISMATCH` and SHALL NOT route it to installation B

### Requirement: Automatic single-use browser pairing
The Connector SHALL request a pairing ticket and open the system browser with a Dashboard URL containing that ticket in the URL fragment. The pairing ticket MUST expire within 120 seconds, MUST be stored server-side only as a digest, and MUST be consumed at most once. Successful exchange SHALL establish an `HttpOnly`, `Secure`, `SameSite=Strict` Dashboard session and SHALL remove the fragment from browser history.

#### Scenario: Fresh ticket is exchanged
- **WHEN** the Dashboard exchanges an unexpired and unused pairing ticket
- **THEN** the system SHALL mark the ticket consumed, establish a session for the same `installation_id`, and report the Connector connection state

#### Scenario: Ticket is exchanged twice
- **WHEN** a consumed pairing ticket is submitted again
- **THEN** the system SHALL return `PAIR_TICKET_USED` and SHALL NOT create another session

#### Scenario: Ticket expires
- **WHEN** a pairing ticket is submitted after its expiry
- **THEN** the system SHALL return `PAIR_TICKET_EXPIRED` and instruct the user to reopen the Dashboard from the local Connector

### Requirement: Fixed Dashboard URL restores the paired installation
The Dashboard SHALL restore the previously paired installation from its secure same-origin session when the user revisits the fixed Dashboard URL in the same browser. A browser without a valid session SHALL remain unpaired and MUST NOT enumerate installations.

#### Scenario: Paired browser revisits the root URL
- **WHEN** the user opens the fixed Dashboard URL with a valid `janson_session` cookie
- **THEN** the Dashboard SHALL restore only that session's installation status without asking for an account

#### Scenario: Unpaired browser visits the root URL
- **WHEN** a browser without a valid session opens the fixed Dashboard URL
- **THEN** the Dashboard SHALL show an unpaired state and SHALL NOT reveal installation identifiers or online status

##### Example: Private browsing window
- **GIVEN** a private browsing window has no `janson_session` cookie
- **WHEN** it requests the Dashboard root and `/api/v1/session`
- **THEN** the API returns the unpaired state without an `installation_id`, device count, or presence value

### Requirement: Outbound-only real-time Connector transport
The local Connector SHALL establish an outbound secure WebSocket connection to the Cloudflare gateway and SHALL NOT require an inbound port, public IP, router configuration, or per-user Cloudflare Tunnel. The Connector SHALL reconnect with exponential backoff capped at 30 seconds and bounded jitter.

#### Scenario: Connector establishes its first connection
- **WHEN** the Connector has a valid credential and internet access
- **THEN** it SHALL open the outbound WebSocket, authenticate as role `connector`, and publish `connector.ready`

#### Scenario: Connection drops
- **WHEN** the Connector WebSocket closes unexpectedly
- **THEN** the Connector SHALL retry with increasing delay capped at 30 seconds and SHALL return to online state after a successful reconnect

### Requirement: Durable Object tenant isolation
The Cloudflare gateway SHALL route each verified `installation_id` to a distinct `ConnectorRoom` Durable Object. Each room MUST accept messages only from Dashboard and Connector sessions bound to that same installation. Critical tenant state MUST survive hibernation in Durable Object storage, and connection role metadata MUST survive in serialized WebSocket attachments.

#### Scenario: Cross-tenant command injection is attempted
- **WHEN** a Dashboard session for installation A attempts to send a command to a Connector session for installation B
- **THEN** the system SHALL return `TENANT_MISMATCH`, and installation B SHALL receive no message

#### Scenario: Durable Object wakes from hibernation
- **WHEN** a message wakes a hibernated ConnectorRoom
- **THEN** the room SHALL recover the connection roles and installation binding without relying on stale in-memory state

##### Example: Connector message wakes the room
- **GIVEN** room `ins_A7f2` hibernated with serialized attachments `{role: "connector"}` and `{role: "dashboard"}`
- **WHEN** the Connector sends a valid `result` message
- **THEN** the room forwards it only to the attached Dashboard connections in `ins_A7f2`

### Requirement: V1 command allowlist
The first release SHALL accept only `connector.health` and `job.echo`. Both the gateway and Connector MUST validate the command envelope and command-specific payload before forwarding or execution. The system MUST NOT expose arbitrary shell execution, subprocess invocation, expression evaluation, or unrestricted file access.

#### Scenario: Health command succeeds
- **WHEN** a paired Dashboard sends a valid `connector.health` command to an online Connector
- **THEN** the Connector SHALL return the same `command_id` with version, platform, and capability names and SHALL NOT return hostname, username, secrets, or local paths

#### Scenario: Echo command succeeds
- **WHEN** a paired Dashboard sends a valid UTF-8 `message` using `job.echo`
- **THEN** the Connector SHALL return the same allowed message and `command_id`

#### Scenario: Unknown command is submitted
- **WHEN** a Dashboard submits any command outside the allowlist
- **THEN** the gateway SHALL return `COMMAND_NOT_ALLOWED` and SHALL NOT forward it to the Connector

### Requirement: Cloud message data boundary
Every cloud message MUST be valid JSON and MUST be no larger than 32 KiB. The protocol MUST reject binary media, API keys, signed media URLs, absolute local paths, and shell command fields. Original videos, rendered videos, subtitles, and local project files SHALL remain on the local machine in V1.

#### Scenario: Oversized payload is submitted
- **WHEN** a message exceeds 32 KiB
- **THEN** the gateway SHALL return `PAYLOAD_TOO_LARGE` and SHALL NOT forward or persist the message

#### Scenario: Sensitive field is submitted
- **WHEN** a message contains a forbidden secret, media, path, or shell field
- **THEN** schema validation SHALL reject it with `INVALID_MESSAGE` before tenant relay

### Requirement: Predictable offline behavior
The system SHALL report Connector presence from the installation's Durable Object connections. Commands sent while no Connector is online MUST fail immediately with `CONNECTOR_OFFLINE` and MUST NOT be queued or replayed after reconnection. Commands interrupted by a lost connection MUST end with `CONNECTION_LOST`.

#### Scenario: Dashboard sends a command while Connector is offline
- **WHEN** the installation has no authenticated Connector WebSocket
- **THEN** the Dashboard SHALL receive `CONNECTOR_OFFLINE`, and the command SHALL NOT execute after a later reconnect

### Requirement: Anonymous connection limits and replacement
The system SHALL apply registration abuse controls and SHALL limit each installation to one active Connector WebSocket and at most three active Dashboard WebSockets. A newly authenticated Connector connection SHALL replace the previous Connector connection for that installation.

#### Scenario: Second Connector connects with the same installation credential
- **WHEN** a new Connector WebSocket authenticates for an installation that already has an active Connector
- **THEN** the old Connector SHALL receive `REPLACED_BY_NEW_CONNECTION` and be closed before the new Connector becomes authoritative

### Requirement: Local editing remains independent of cloud availability
Cloud connection failure MUST NOT block existing local Awesome-Janson commands, transcription, rendering, or file access. The Connector SHALL surface cloud connection status separately from local editing readiness.

#### Scenario: Cloud gateway is unavailable
- **WHEN** the Connector cannot reach the Cloudflare gateway
- **THEN** local Janson CLI operations SHALL remain usable and the Connector SHALL report cloud offline without changing local files

##### Example: DNS failure during local storyboard build
- **GIVEN** the gateway hostname cannot be resolved and a local video fixture is available
- **WHEN** the user runs the existing storyboard command
- **THEN** the command exits successfully with its local artifact while Connector status reports cloud offline

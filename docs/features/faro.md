# Connecting Faro

CachiBot can use [Faro](https://github.com/jhd3197/Faro) — a desktop
SFTP/SSH/S3 client — as a connection for a bot. Faro's **Agent Bridge** is a
localhost HTTP server that lends the user's already-authenticated sessions to
a local agent. When a bot is connected, it gets live `faro_*` tools (list,
read, search, upload, download, sync, exec, and the rest of the bridge's own
catalogue) that act on the user's Faro sessions.

---

## How it works

1. Open Faro and turn on the **Agent Bridge**. While it is on, Faro writes a
   discovery file `agent-endpoint.json` — `{url, port, token, pid, version}`,
   mode `0600` — into its data dir (`FARO_DATA_DIR` when set, otherwise the OS
   data dir: `%APPDATA%\com.juandenis.faro` on Windows,
   `~/Library/Application Support/com.juandenis.faro` on macOS,
   `$XDG_DATA_HOME/com.juandenis.faro` or `~/.local/share/com.juandenis.faro`
   on Linux).
2. CachiBot finds that file, accepts only `127.0.0.1`/`localhost` URLs,
   checks the recorded pid, and confirms `GET /health` answers
   `name = "faro-agent-bridge"`. This detection is re-checked with a short
   TTL; when the file cannot be seen (Docker, a remote server) the
   integration is simply unavailable and every Faro surface stays hidden.
3. In the bot's settings, **Connections → Faro → Connect** (editor access or
   the bot owner; a running bridge is required). The flag is stored per bot
   and is not secret.
4. The bot's tools come from the bridge's live MCP `tools/list`. Reads are
   marked safe; writes and transfers carry side effects; execution tools are
   marked dangerous — so CachiBot's own tool-approval policy applies to them
   exactly as to any other tool. The tools exist only while the bot is
   connected **and** the bridge is running; otherwise the model sees no
   `faro_*` tools at all.

## Credentials never leave Faro

- The bridge token is read from the discovery file for **every** connection
  and call, and is never stored in CachiBot: no database column, no config
  file, no log line, no API response, no websocket payload. (It changes on
  every Faro launch; on a `401` or a connection error CachiBot re-reads the
  file once and retries once.)
- Your Faro credentials — SSH keys, passwords, S3 keys — stay inside Faro.
  CachiBot only ever talks to the local bridge, and only ever sees what the
  tool answers say.
- Tool arguments may contain secrets, so CachiBot logs only the tool name
  and its outcome.

## Approvals happen in Faro

Every side-effecting call is approved by **you in Faro's own UI**; the MCP
call blocks until you approve, deny, or it times out (120 s). While a call is
in flight, CachiBot shows the pending approvals — kind, session, command
summary — in the chat status line, the bot inspector, and the bot settings
card, delivered only to users who can see that bot. CachiBot can offer
**Deny** and nothing else: there is deliberately no approve route, no approve
button, and no flag for it, anywhere. Approving only ever happens in Faro.

The approvals line needs a Faro build that includes `GET /approvals`; older
Faro builds still work for tools — CachiBot detects the missing route and
shows a plain "waiting on Faro" line instead (and nothing when idle).

## Minimum version

Any Faro build with the Agent Bridge works for tools. For the pending-
approvals line (list + Deny from CachiBot), use a Faro build that includes
`GET /approvals`. CachiBot reports `supportsApprovals` in
`GET /api/integrations/faro/status` and the UI adapts.

## API

| Endpoint | Access | Purpose |
| --- | --- | --- |
| `GET /api/integrations/faro/status` | any signed-in user | bridge detection (available/version/features; no secrets) |
| `GET /api/bots/{id}/faro` | bot viewer+ | connection flag + status + pending approvals |
| `POST /api/bots/{id}/faro/connect` | bot editor+ | connect (requires a running bridge) |
| `POST /api/bots/{id}/faro/disconnect` | bot viewer+ | disconnect (always allowed) |
| `POST /api/bots/{id}/faro/approvals/{requestId}/deny` | bot operator+ | deny one pending approval |

State changes are pushed over the `faro_update` websocket event, scoped to
users who can see the bot.

## Troubleshooting

- **The Faro card does not appear anywhere.** The bridge was not detected:
  open Faro, turn on the Agent Bridge, and make sure CachiBot runs on the
  same machine as Faro (same user, so the discovery file is readable). In
  Docker or on a remote server the file is not visible — the integration is
  unavailable there by design.
- **"Faro is not running" on a connected bot.** Faro (or just the bridge)
  was closed. Open Faro and turn the Agent Bridge back on — the tools and
  the approvals line come back on their own; nothing needs reconnecting. To
  stop using Faro with the bot, Disconnect.
- **A tool says the user denied or did not respond.** You (or the timeout)
  declined the approval in Faro. The model is told exactly that; rerun the
  tool after approving, or ask the bot to take a different approach.
- **The approvals line never shows.** You are on a Faro build without
  `GET /approvals` (CachiBot says `supportsApprovals: false` in the status);
  update Faro to a build that includes it.
- **A call fails right after a Faro update/restart.** The token rotates on
  every launch; the next call re-reads the file. If failures persist, check
  that the bridge is on and the discovery file exists and is readable.

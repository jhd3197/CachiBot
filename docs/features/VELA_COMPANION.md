# Vela companion

CachiBot can register itself as a **companion app** with a Vela running on the same computer. While the CachiBot server runs, it offers Vela two desk widgets — **Needs you** and **Runs** — plus an **Approve** and a **Deny** button for the one thing that is waiting. Once you connect CachiBot in Vela, the widgets show on every device signed in to that Vela, including phones.

The whole integration is file- and loopback-based: Vela always calls CachiBot; CachiBot never calls Vela, never learns Vela's address, and never holds a Vela credential. The only auth is the protocol's own random bearer token, minted fresh on every start, which Vela sends to the loopback endpoint.

---

## How it works

1. The CachiBot server detects a local Vela (the `VELA_DATA_DIR` directory, or `~/.vela`, already exists). It never creates that directory.
2. It starts a loopback-only HTTP server on an ephemeral port and writes `<vela home>/companions/cachibot.json` (atomically, with a per-start token and this process's pid).
3. Vela shows **CachiBot** under *Marketplace → Found on this computer*. Press **Connect** and review the two widgets and two actions once.
4. From then on Vela polls the widgets and calls the actions until CachiBot stops, the setting is turned off, or Vela goes away — then the registration files are removed again.

## What is shown

**Needs you** lists real, current items, each labelled by bot:

- pending tool approvals from a chat (tool + what it wants to do),
- a bot computer's needs-you (e.g. a needs-person pause or an approval on the desktop),
- side tasks in `needs_you` status (display only; resolve them in CachiBot).

With nothing waiting it says so, and it does not flag attention. While something waits it carries a count badge and an attention dot.

**Runs** is a small key/value read of live counts: side tasks running and waiting, running executions, and awake bot computers. Only numbers with a real source are shown; a source that errors is left out, not faked.

## What Approve and Deny do — and don't

Buttons appear on the Needs-you widget only when **exactly one actionable item** is waiting. An action then re-reads the current items and acts **only** on that exact item (it is pinned by identity, never "the oldest" and never "all"). If anything changed since the widget was drawn, the action answers with a conflict and touches nothing — open CachiBot to review it.

- **Approve** resolves the pending tool approval so the run continues.
- **Deny** refuses the pending tool approval.
- A bot computer's needs-you offers **Deny only**: it applies CachiBot's existing "skip" answer (an approval is denied; a needs-person pause stops the run). **Approve** on a computer item is refused — approving a pause happens in CachiBot, which is the only place with that flow.

## Settings

The integration is on by default. Admins find a **Vela** section in *Settings* (it only appears while a local Vela is present):

- **Connected to Vela** — Vela called the loopback server within the last minute.
- **Waiting for you to connect CachiBot in Vela > Marketplace > Found on this computer** — registered, but Vela has not called yet.
- **Turned off** — disabled.

The toggle persists to `~/.cachibot.toml` (`[vela_companion] enabled = …`) and applies immediately. The environment variable `CACHIBOT_VELA_COMPANION=0` (also `false`/`no`) disables the integration and wins over the saved setting.

## Caveat

Vela belongs to whoever runs it on that computer. On a multi-user CachiBot server, the widgets show **all** bots' items to that Vela's owner, so this is meant for a personal/local install.

## Deferred

- Answering computer take-overs from a widget (only skip/deny is exposed).
- Side-task resolution actions (needs-you side tasks are display only).
- A per-bot scope: the protocol has one registration per app, not per person.

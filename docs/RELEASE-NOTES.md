Nexo 7 v0.19.1 preview — Telegram setup and connection diagnostics

- Reject the bot ID in Allowed chats before starting; select actual private/group IDs from discovery buttons.
- Keep discovery results visible instead of overwriting them with the periodic status refresh.
- Keep the consent checkbox selected; explicitly explain why the token field clears after starting.
- Mark running only after Telegram authentication and initial polling succeed. Show reconnection errors including token rejection and polling conflicts.
- Display session-only received, replied and blocked-by-allowlist counters, plus generation/reply failure status. No message content or tokens in diagnostics.
- Preserve v0.19 memory, persona, drafts, chips, mobile and local inference.

Extract the complete Windows/Linux archive and run Nexo7. Stop the bridge, enter the current token and consent, send your bot a private Telegram message, click Read recent chat IDs, click Allow beside the private ID, then Start and send a new message.

Tests simulate Telegram API events; no real bot credentials or messages were used. The user's live connection still requires a post-update check. Telegram group membership and allowed group IDs remain explicit. Local inference still depends on PC resources.

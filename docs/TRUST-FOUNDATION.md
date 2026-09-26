# Local trust foundation (Phase 0)

Nexo 0.17 adds local identity, permission checks and an activity viewer. It does
not install avatars, voice modules, Google OAuth connectors, a chip marketplace,
mobile sync or arbitrary plugin execution. Existing inference, image generation,
workspace, music, documents and memory use the same engines and formats.

## Where to find it

Open **Settings → Trust and permissions**. Your Navi ID is a SHA-256 fingerprint
of an Ed25519 public key. No account, registration, cloud upload or extra model is
needed. The private key is never exposed by the HTTP API or sent to a provider.

The first run creates `trust.sqlite3` beside `nexo.sqlite3` in your user data
folder. Windows protects the private key with current-user DPAPI; Linux restricts
the database to mode 0600 (the key is not encrypted at rest on Linux). Protect
backups and your OS account. Do not put this file in GitHub. Windows identity
files cannot simply be moved to a different login; encrypted pairing/export is
a later phase. Keep a trusted backup while Nexo is closed. A corrupt identity or
invalid signed log stops startup instead of silently creating a different ID.

## Permissions

The fixed `SCOPES`, `ACTIONS` and `ROUTES` registries in `nexo7/trust.py` declare
built-in capabilities. Existing features are enabled initially to preserve the
installation's behavior. This does **not** enable networking by itself: existing
per-message research choices, Telegram consent and chat allowlists still apply.
Unknown tool names and unregistered API routes never execute. Future connectors
and chips must be declared explicitly; a model cannot grant itself permission.

Checks cover authenticated API actions, model-requested tools, direct chat math
and creation commands, saved-memory access, workspace tasks, web/PubMed lookup,
Telegram reads/sends/downloads, image jobs, and desktop model startup. Cached
answers include the permission state in their key. Library helper functions are
not an OS sandbox: trusted Python code can call low-level functions, and nothing
in this release allows loading untrusted Python plugins.

Permission updates require the same local access token and Host/Origin checks as
other owner controls. The owner can always restore permissions, even after
turning off settings changes. Turning a permission off blocks subsequent action
starts, including Telegram requests already running in a bridge. Already admitted
operations may finish. Revoking image generation/model management requests image
cancellation; revoking model management cancels setup; revoking Telegram requests
bridge shutdown. Read-only status and stop/cancel controls remain accessible.
Disabling memory access can prevent conversations which require saved history;
reenable it in Settings to resume those features.

## Audit receipts

Each admitted action writes a signed `started` receipt before running and a
`completed`, `failed`, or `accepted` receipt afterward. Denials are recorded too.
Background image jobs and desktop model setup also record worker outcomes.
`accepted` on an HTTP request means queued, not completed. A crash can leave a
started action with no finish receipt; that is not proof it completed or failed.

Receipts contain only timestamp, sequence, Navi ID, declared action, outcome,
random call ID and the preceding receipt's hash. They exclude prompts, answers,
message text, filenames, document bodies, credentials and raw exception text.
Private conversations still produce these activity metadata receipts. Opening
saved data can itself produce read receipts; status polling is omitted.

SQLite serializes appends across threads/processes. Transactions and update/delete
triggers make the log append-only through the application. Ed25519 signatures and
hash chaining detect modified records, reordered records and missing interior
records. Verification runs on startup and on demand. Pages show 50 receipts, and
verification streams records rather than loading the entire log into RAM.

**Limits:** this is local tamper evidence, not immutable remote attestation. It
cannot detect restoring an entire older backup, removing the final records, or
replacing the whole identity plus log. Someone who controls your OS account can
bypass app checks or steal/use the key. Receipts sign action metadata, not the
arguments or a future portable authorization token. No audit deletion or automatic
rotation is offered in this phase; the database grows with usage. If it cannot
write an admission receipt, the action is blocked. If completion logging fails,
work may already have happened and should not be assumed undone.

## Authenticated endpoints

- `GET /api/trust`: public identity, declared actions and effective permissions.
- `POST /api/trust/permissions`: `{ "scope": "math.use", "enabled": false }`.
- `GET /api/trust/audit?before=123`: newest receipts before an optional sequence.
- `GET /api/trust/verify`: signature/chain verification and current head digest.

The private key has no API route. Trust data is independent of the existing memory
database, and updating Nexo does not erase saved notes or downloaded models.

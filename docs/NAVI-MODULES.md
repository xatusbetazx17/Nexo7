# Nexo Navi modules — 0.18 preview

Open **Navi** in the desktop sidebar. All new optional permissions start off, including when upgrading. Existing chat, inference, memory, workspace, image creation and Telegram settings are preserved. No account is needed for local use.

## Avatar and voice

Enable **Desktop avatar** for a native, always-on-top 2D face. It shows idle, listening, thinking, happy and sleeping states, with an unread reminder count. These are interface states, not emotions or consciousness. Closing the avatar disables it. Linux needs a graphical desktop (X11 or XWayland); headless sessions cannot display it.

Enable **Local voice**, choose English or Spanish, and download the recognition model (~40 MB). Record up to 30 seconds in Chat. Review the transcript before sending. Browser microphone permission is required. Vosk runs in a separate, short-lived process with a 1.25 GB guard; at least 1.4 GB free memory is checked first. Recognition shares the existing model-operation lock. It does not train the model. Close other applications if memory is low.

**Read last reply** uses the bundled eSpeak NG renderer, entirely offline, with a deliberately synthetic voice. Speech synthesis accepts up to 1,500 characters. API voices include English, Spanish, French, German, Italian and Portuguese; the simple UI follows the recognition language. Audio is temporary. Model downloads require internet once; microphone content is not sent online. Cancel recording by leaving/closing the page; no always-listening wake word.

## Your day

Enable reminders, add a local date/time, and optionally enable a morning briefing. Choose an IANA time zone, a saved note or Library overview, and optional connected Calendar/Gmail summaries. Delivery happens while Nexo is running; overdue reminders are caught on resume. Browser notifications need separate browser permission. The in-app list works without it. This does not wake a powered-off PC or provide a background OS service.

External titles and snippets are displayed as plain, untrusted data. They are never interpreted as tool instructions. Briefings are assembled locally without an LLM. Reading Google data requires the connector permission, enabled connection and unlocked vault.

## Google Calendar and Gmail

1. In Google Cloud, create a project, enable **Google Calendar API** and **Gmail API**, and configure the OAuth consent screen. For testing, add your account as a test user.
2. Create an OAuth client with application type **Desktop app**. Download its JSON. Do not use a web client, mobile client or service account.
3. In Navi → Google connections, create/unlock a vault using a passphrase of at least 16 characters. Upload the Desktop client JSON.
4. Click **Connect read only** for each service. Continue in your browser, consent, then return and refresh connections.
5. Read recent items, disable a connection, or use **Revoke access**. Revoke attempts Google revocation and always removes the local token; if offline, also revoke at https://myaccount.google.com/permissions.

Calendar asks only for `calendar.events.readonly`; Gmail asks only for `gmail.readonly`. The flow uses PKCE S256, random state, a single-use five-minute loopback callback and an external browser. A connector base class declares scopes, refreshes expiring tokens and audits reads. Gmail returns up to ten inbox snippets and attachment filenames; attachment bytes are never downloaded. There is no send/delete API. The security-watch chip flags suspicious wording and risky filename extensions. It is a heuristic, not malware detection or proof of safety.

Tokens and OAuth client details are encrypted with AES-256-GCM and a key derived from the vault passphrase (PBKDF2-SHA256, 600,000 iterations). The key stays in process memory only while unlocked. Unlock after each restart. Keep a secure backup and phrase: there is no recovery service. Locking prevents subsequent token access; an already-dispatched request may finish.

A shared public OAuth client may need Google verification, particularly for Gmail’s restricted read scope. Testing-mode grants may expire. This release supplies the implementation, not a pre-verified public Google app. Automated tests use a fake Google transport and actual local callback handling; account consent still requires your client and account.

## Chips

Built-ins: **math**, **web-memory**, **security-watch**. The existing math API/panel and reviewed-source saver dispatch through the signed built-ins. Existing chat math tools retain their own permission checks.

A `.nexochip` is a ZIP containing exactly `manifest.json`, `program.json`, `signature.json`. Manifest fields: `format` (`nexo-chip-v1`), `name`, `version`, `author`, `permissions`, `entry_point` (`program.json`). Program contains one `operation`: `math.solve`, `memory.reviewed-save`, or `security.email-check`. Permission declarations must exactly match the registry. The Ed25519 signature covers the canonical manifest and program. Built-ins also have pinned archive hashes.

Preview the archive, verify the publisher fingerprint through a trusted channel, approve permissions, and install. A signature proves possession of a key; the author name is not independently verified. Third-party execution needs its separate permission. Every run rechecks signatures and operation scopes. Maximum 30 installed chips, 100 KB archive, 20 KB per member and bounded inputs. No Python, JavaScript, shell, dynamic imports, unrestricted filesystem or network access is permitted. This is a restricted declarative interpreter, not an OS sandbox for arbitrary plugins or a marketplace.

Create your own chip with `python -m scripts.make_chip --key PRIVATE_32_BYTE_SEED --name my-math --operation math.solve --author "Your name" --output my-math.nexochip`. Keep the key out of Git. The module does not generate or upload private keys.

## Encrypted transfer and mobile

Export bundles include the Navi private identity key, selected personality/language preferences, all saved documents (including reviewed examples and provenance), and pending reminders. They exclude OAuth tokens, API keys, chat history, audit history, model weights and executable chips. Use a strong, separate pairing phrase; anyone with the file and phrase can clone the identity. This is an offline transfer, not remote revocation, device attestation or synchronization.

Imports decrypt and validate before creating a separate profile. **Switch to imported profile and restart** activates it; the previous directory stays intact. Default launches follow `profile-choice.json` to its validated child profile. To restore the old profile, quit Nexo and remove that choice file from the original data directory. The imported profile starts with optional permissions and scheduler off. It downloads its own model unless you arrange a local cache separately.

**Nexo-Mobile** is a standalone installable web app, not a signed Android/iOS store binary. Serve the release ZIP’s files from a trusted HTTPS static host, or build with `cd mobile && npm ci --ignore-scripts && npm run build`. The host must serve `.wasm` as `application/wasm`. Open on the phone, choose Install / Add to Home Screen, and import the encrypted `.nexo` file. Current browsers with WebCrypto Ed25519 and WebAssembly SIMD are required. Safari/iOS compatibility depends on browser version; physical-device performance has not been benchmarked.

Mobile can create a fresh identity, chat with an optional pinned SmolLM2-135M q4 model (~185 MB download plus ~33 MB app/runtime), use saved notes as bounded reference, change personality, save notes, and deliver reminders while open. All inference is CPU WASM on the phone; no desktop server/account/cloud inference is required. This small English model is limited and can be wrong. Model downloads contact Hugging Face only when loading; cached app/model files support offline reuse. Use Free model memory to stop/unload. Browser storage is managed by the OS and can be evicted.

Profiles are encrypted in IndexedDB; an unlocked profile and pairing phrase reside in memory. Lock clears the UI and model worker. Returning after five minutes in the background locks the app. Keep encrypted exports: there is no recovery account. No background push or full sync is included; missed reminders appear after unlock. A hosting operator can change the JavaScript, so use a host you control for sensitive profiles.

## Validation and boundaries

The new tests cover default-off permissions, encrypted vault tamper/wrong-passphrase rejection, OAuth state/PKCE/replay, token refresh, permission revocation between Gmail reads, signed-chip mutation, deterministic math, reminder deduplication, and profile round trips. Release gates run real local TTS→STT, packaged application checks, desktop browser tests and mobile CPU inference/offline reload. Live Google account consent and physical Dell/phone performance are separate activation/validation steps.

Application grants and signed audit receipts do not replace an OS sandbox. No connector content can automatically send, delete, share or run code. Existing explicit review/confirmation remains required for sensitive workspace and sharing actions. No new telemetry or collective upload is enabled.

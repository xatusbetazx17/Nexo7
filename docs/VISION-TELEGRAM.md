# Local images and optional Telegram

Nexo7 0.12.0 adds the requested LiquidAI checkpoint as an optional **vision**
model. Existing automatic Qwen profiles, documents, math, reviewed learning,
optional web search and workspace tasks remain available. This integration
loads published weights; it does not merge models or train new weights.

## Use images on Windows or Linux

1. Open **Setup → Local model choice → LiquidAI LFM2-VL 450M**.
2. Click **Switch to selected model** (or start local setup on first launch).
3. Open chat, attach a JPEG, PNG, WebP or GIF, and ask a short question.
4. Switch back to **Automatic** when you want the existing general chat model.

The switch unloads the current model before loading another. It rechecks memory
and retains the OS process guard. A failed switch leaves the app available for
another setup attempt; it does not start an unbounded fallback process. Both
weights and projector are pinned to revision and SHA-256. Together they download
323,197,440 bytes; download size is not runtime RAM usage.

- One image per model request; the interface sequences at most two attachments.
- Each input is at most 4 MB and 16 million pixels. A separate 512 MB worker
  converts the first frame to RGB PNG, removes metadata and resizes to fit 512×512.
- The runtime uses 64–256 image tokens, 4096 context, CPU, at most 256 output
  tokens per image, and the existing adaptive model-process memory guard.
- Requests are stateless: no saved chats, documents, learning, search or tools
  are attached. Image bytes and answers are not automatically saved. You can
  explicitly export the conversation or turn a reviewed answer into a file.
- Large screenshots and tiny writing lose detail when resized. Crop the relevant
  area yourself before attaching it. This is not reliable document OCR.
- The checkpoint officially supports English. Spanish and other languages can
  produce seriously incorrect answers. Keep the other chat models available.

The guard applies to the model process (Windows worker/job committed memory;
Linux virtual address space), not the whole app, browser, OS or disk. The image
worker exits before inference. No claim is made that the entire desktop uses
only 1.5 GB, or that speed measured on CI matches a Dell N5030.

## What the tests actually showed

`reports/vision-4gb-smoke.json` records a real Linux desktop/API run with simulated
4 GB installed / 2.5 GB available and an enforced 1.5 GB model-process limit.
The model identified a red rectangle and a blue circle separately. Reload and
stateless text requests passed. The release workflow repeats this on Windows and
Linux, including packaged executables.

An earlier simultaneous two-image trial confused their colors and shapes. This
is why the app analyzes attachments **separately and labels each answer**.
Cross-image comparisons are not implemented. Telegram albums follow the same
rule. This change does not prove accuracy for general photographs or screenshots.

The same small text diagnostic used in v0.11 produced 3/8 strict automatic passes
for this checkpoint (`reports/quality-lfm2-vl.json`). It returned correct JSON and
a simple square function, but made errors in ordering and an English arithmetic
problem, failed exact output formatting, and falsely described a Spanish
"gallina" as a fish. Two failures were formatting failures despite useful content:
it calculated 34 in the Spanish word problem and admitted an unknown population.
The English definition was brief and imprecise. This is not a general chat upgrade.

Reproduce the checks from source:

```sh
python -m pip install -r requirements-runtime.txt
python scripts/smoke_vision.py --simulate-4gb
python scripts/evaluate_quality.py --model lfm2-vl:450m --data-dir ./quality-data --output reports/my-liquid-quality.json
```

## Telegram from the desktop interface

Telegram is optional and uses the Internet. Inference runs on your PC, but
incoming messages, images and outgoing answers pass through Telegram's service.
It is not an offline/private transport. Nexo never starts it automatically.

1. Create a bot with the official **@BotFather** in Telegram and copy its token.
2. Start a local model in Nexo; select LiquidAI if you want image replies.
3. Open **Setup → Optional Telegram access**, enter the token and review the
   Telegram-access checkbox. The token is held in memory, not saved in preferences.
4. Send a message to your new bot in Telegram. Click **Read recent chat IDs from
   Telegram** in Nexo, then copy only your intended numeric ID into Allowed chats.
   This reads recent bot updates and returns chat IDs/types; it saves no messages
   and sends no reply. It does not automatically select every discovered chat.
5. Click **Start Telegram bridge**. The token field clears after successful start.
   Send a new message: old pre-start messages are deliberately skipped.
6. Click **Stop Telegram bridge** or quit Nexo when finished. An in-flight local
   request may finish, but the stop flag blocks subsequent Telegram sends.

Only allowlisted chats are processed. Private chats need no mention; groups
require a bot mention or reply. Mentions use Telegram's UTF-16 entity offsets,
including text with emoji. Replying to an image and mentioning the bot works.
Albums buffer briefly and keep up to two images, analyzed sequentially.
Replies are split into Telegram-sized chunks. Inference is serialized by Nexo;
if chat/setup/tasks are busy, Telegram receives a generic local-request error.

The relay has **no access to saved notes, chat history, workspace files, tools,
web search or learning**. It calls only the stateless native endpoint. Group
members in an allowed group can request replies, but cannot retrieve your local
knowledge through the bridge. It never uploads training data or posts to GitHub.

Telegram setup is optional at install time. No Telegram account was connected
and no real messages were sent during development. Allowlist, album, mention,
stop and reaction behavior is verified with mocked Telegram calls; real local
inference is verified separately. Live account behavior still needs your test.

## Optional command-line bridge and reaction rules

The GUI leaves passive image scanning off. Advanced users can run one bridge
from source instead. Start Nexo first and stop any GUI bridge before doing so:

PowerShell:

```powershell
$env:TELEGRAM_BOT_TOKEN = "YOUR_BOTFATHER_TOKEN"
$env:NEXO_TELEGRAM_CHAT_IDS = "YOUR_NUMERIC_CHAT_ID"
python -m nexo7.telegram_bridge
```

Linux:

```sh
export TELEGRAM_BOT_TOKEN='YOUR_BOTFATHER_TOKEN'
export NEXO_TELEGRAM_CHAT_IDS='YOUR_NUMERIC_CHAT_ID'
python -m nexo7.telegram_bridge
```

The packaged executable also accepts `--telegram`, using the same environment
variables. The Windows package is a windowed executable; the GUI controls are
more convenient. `NEXO_ACCESS_FILE` can point to another Nexo data directory's
`access.json`; only an authenticated `http://127.0.0.1` address is accepted.
Do not put tokens in source files, chat prompts, shared scripts or GitHub.

To enable custom image rules in the command-line bridge, set
`NEXO_TELEGRAM_SCAN_IMAGES=true` and `NEXO_TELEGRAM_RULES` to a JSON file:

```json
[
  {"name":"FLOWER","description":"A clearly visible flower","reply":"This may be a flower."}
]
```

At most eight rules, with unique uppercase names, a short description, and a
reply and/or emoji. Invalid rule files fail without activating default rules.
Classification must return exact names; substring matches do not trigger actions.
Classifications can be wrong, so use reactions only for noncritical purposes.
There are no built-in social scores. Each image can use one extra local call
when rules are enabled, increasing latency. Unsupported Telegram emoji fail
without a fallback text action. Restart the command-line bridge after edits.

Leave Telegram group privacy mode enabled for ordinary use. Passive scanning in
an allowed group requires intentionally disabling it with BotFather and making
participants aware that the bot receives images. Enable that only if intended.

## Sources and licenses

- [Requested LiquidAI model and pinned assets](https://huggingface.co/LiquidAI/LFM2-VL-450M-GGUF/tree/7cf9679aa137039135e342aa77014f7b5f2bef73)
- [Original model card](https://huggingface.co/LiquidAI/LFM2-VL-450M)
- [Liquid license](../nexo7/licenses/LIQUID-LFM-1.0.txt): LFM Open License v1.0,
  including Section 5 commercial-use conditions and its $10 million revenue threshold.
  It is separate from Nexo's source-code license; read it before commercial use.
- [Telegram Bot API](https://core.telegram.org/bots/api)
- The user's pasted Telegram bot supplied the PNG normalization, mention/reply,
  album and custom-reaction design. Nexo adapts it with smaller limits, an
  allowlist, a stateless local endpoint, exact classification matching, bounded
  buffers and opt-in scanning; it uses no third-party bot framework.
- [Emir Code](https://github.com/daristanapeyvan/emircode): HTML acceptance criteria
  are adapted to Python in `task_contracts.py`, retaining its MIT notice. Nexo
  retains its own task engine and interface, without adding Electron or Node
  as desktop runtime requirements.

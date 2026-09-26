# v0.16.0 — Optional offline diffusion images

- Adds a separate CPU image-generation engine: pinned stable-diffusion.cpp, DreamShaper 8 LCM Q4 and TAESD. LFM2-VL and other chat weights remain unchanged.
- Create → AI images offers explicit model installation, styles, 256/512px output, 2/4/8 steps, cancellation and PNG download. Installed images can also be requested through chat.
- Unloads the owned chat model before generation and restores it afterward. A separate worker enforces a memory cap of at most 4 GB; admission uses currently available RAM.
- Automatically selects a faster AVX2 CPU engine where supported; retains a baseline engine for Pentium-class hardware. Defaults to 4 steps with CPU-adaptive size (256px baseline / 512px AVX2). Small 2-step drafts remain optional and can be very blurry.
- About 1.64 GB of optional downloads; generation then works offline. CPU jobs can take minutes. Quality, anatomy, lettering and prompt accuracy remain imperfect.
- Adds real image release checks on Windows/Linux, packaged execution and a simulated 4 GB available-memory budget. Existing chat, simple drawings, music and document features remain.

See [AI images setup and limits](AI-IMAGES.md).

# v0.15.0 — Create files directly in chat

- Ordinary English/Spanish drawing requests reach the renderer before the conversation model can refuse or search the web.
- Exact simple chicken/hand requests use labeled built-in illustrations; other subjects use a bounded, validated model-generated scene. This is simple shape art, not diffusion or photorealistic generation.
- Images appear in chat with PNG and SVG downloads. Short music requests can return WAV previews and MIDI downloads.
- Document/letter/report requests draft content and export DOCX plus plain text. Existing replies have a Download Word action.
- No new model weights or GPU requirement; existing context/output/memory limits remain. Invalid or truncated designs produce a visible failure, not a fake image.
- Download attachments before closing or reloading: chat history stores text only. No automatic file uploads or filesystem writes.
- Added routing, valid-file and failure tests; browser chat-preview checks; real LiquidAI creation checks in Windows/Linux release gates.

# v0.14.1 — Laptop layout refinement

- Keeps imagined-scenario answers concise to reduce truncation on small models.
- Keeps the initial Send button visible at 1366 × 768, with a Chromium regression check.
- Clarifies that scenario replies use the configured model, which may be local or remote.
- Includes the v0.14 features listed below.

# v0.14.0 — Everyday chat and what-if questions

- New light/dark interface with Chat, Create, Library and Settings; technical controls and response diagnostics are expandable.
- Online search and literature modes now apply to one message, returning to Automatic afterward.
- Common hypothetical English/Spanish prompts use a scenario discussion path, including when an old Web mode is selected. Explicit online-search requests are preserved.
- Scenario prompts distinguish fictional assumptions from real claims; incomplete stories do not establish injuries, damage or repair prices.
- Offline What-if calculator computes toy projectile motion and decimal paint/labor subtotals from explicit inputs, with formulas and limitations visible.
- Simpler creative controls and direct transfer of drawing/score JSON responses to the preview editor.
- Added routing/math regression tests, real Chromium layout checks and native-model scenario smoke coverage. Model weights are unchanged; general reasoning accuracy is not guaranteed.

See [Everyday chat and what-if questions](SCENARIOS-AND-INTERFACE.md).

# v0.13.0 — Offline drawing and music

- Fixed compact low-memory web prompts skipping source-synthesis instructions before returning. A small model can still produce incomplete or inaccurate answers.
- Creative Studio in My workspace renders simple shape illustrations to PNG and SVG.
- Short instrumental scores render to playable WAV and editable MIDI, with soft, bell and synth sounds.
- Includes a superhero cloud drawing and a melody example; optional chat drafting prepares an editable JSON design.
- Previews, explicit downloads, validation errors and a reset example work without a model or GPU.
- Rendering performs no network requests and uses no AI tokens. Existing model, memory, Telegram and task features remain available.
- Bounded canvas, score length and polyphony; one creative render at a time. No generated code execution or automatic uploading.
- Functional tests cover files, UI and packaged rendering. Small-model creative quality is not guaranteed; no photorealistic images or vocals are included.

See [Creative Studio](CREATIVE-STUDIO.md) for instructions and limits.

# v0.12.0 — local vision and optional Telegram

- Add the requested LiquidAI LFM2-VL 450M Q4_0 model with a verified Q8_0 projector and its license. Keep existing automatic chat profiles.
- Report setup ready only after the model operation lock is released, preventing a first-request busy error.
- Switch models after unloading the old process; recheck memory and preserve OS guards.
- Analyze bounded image attachments locally, one at a time. A separate decoder worker resizes and removes metadata. Images are not automatically saved.
- Add opt-in desktop Telegram start/stop, chat-ID discovery, explicit chat allowlists, mention/reply/album support and a stateless local endpoint. Command-line users can enable custom image reaction rules. No Telegram messages were sent in development.
- Adapt Emir Code's HTML acceptance criteria, add task templates, manual proposal correction and feedback without resetting budgets.
- Preserve existing chat, tools, documents, learning and contribution features. This release integrates existing weights; it does not train a stronger universal model.
- Include real image smoke tests and raw text diagnostics. LiquidAI recognized simple colors separately but failed multiple text tasks and simultaneous-image interpretation; batches are therefore analyzed separately. See VISION-TELEGRAM.md for scope and limitations.

# Nexo 7 0.11.0 — persistent workspace tasks and measured model comparison

- Model-assisted draft plans, persistent 1–4 step tasks, bounded retries and compact file ledger.
- Full proposed-file/diff review; conditional atomic edits, read-back verification and reverse rollback that refuses to overwrite newer work.
- Syntax/content checks plus optional numeric Python function cases using a restricted AST interpreter, with no arbitrary code execution.
- Published three-model diagnostic with raw answers, failures and manual definition review. Existing default retained; optional pinned Qwen2.5 1.5B Instruct candidate requires a 3 GB model budget.
- Disabled native server prompt-cache and context-checkpoint defaults after a longer low-memory task sequence exposed excess memory use.
- Existing features and low-memory profiles preserved. No general intelligence, universal correctness or superiority claim.

# Nexo 7 0.10.0 — local companion controls and smaller memory profile

- Native low-memory profile for 4 GB installed / at least 2.5 GB available; bounded batches, shorter context and one model call. New native requests pause below 512 MB available. Process guards do not cover the whole PC.
- Local personality/tone preferences with explicit simulated-emotion and factual/permission boundaries.
- Source-linked reviewed learning with provenance and expiry, separate from raw excerpts, public contributions and actual weight training.
- Privacy preflight before external searches/cloud model calls; conservative pattern matching, not guaranteed de-identification.
- Local macro-free Word DOCX export of reviewed text and headings.
- No newly trained weights, universal accuracy claim, frontier-model parity, voice or arbitrary device control.

# Nexo 7 0.9.0 — reviewed search-note contributions and offline math

- Source-linked original-note editor, explicit rights/privacy/CC0/training consent, conservative copying/private-data screens, exact GitHub draft preview and JSON download. User signs in and submits through GitHub; no token storage or background uploads.
- Separate maintainer review-to-training conversion verifies contribution hashes and keeps imported notes in the training split. No model is automatically trained or promoted.
- Offline Decimal linear systems, real/complex quadratic roots, statistics and bounded scientific calculator functions; available through UI and commands. Existing model and RAM guards remain.

# Nexo 7 0.8.0 — bounded local companion

- Local-first request routing, exact reviewed-answer reuse without model generation, and one optional research follow-up for expressed uncertainty.
- Per-request Internet permission resets after sending. Source metadata is visible; factual truth and source independence are not automatically verified.
- Read-only device checks, reviewed file creation with syntax/statistics checks, and one bounded Python/JSON repair proposal without execution or overwriting.
- Existing RAM guards and optional separate training pipeline remain. Routing heuristics currently recognize English/Spanish signals; general multilingual responses depend on the model.

# Nexo 7 0.7.1 — lighter everyday chat

- Default Chat mode uses a compact prompt without search, saved-source retrieval or model-selected tools; native answers are capped at 128 tokens.
- Clearer labels distinguish everyday conversation, saved knowledge/tools, web lookup and PubMed research. New chat returns to everyday Chat.
- Local timeouts identify the model on this computer and suggest recovery steps. Failed attempts are not saved as conversation turns, do not receive citation warnings, and do not offer Create file.
- The Send button shows elapsed waiting time. Model weights and RAM guards are unchanged.
- Added real native English typo/Spanish definition checks to both Windows and Linux release tests. The Dell Pentium N5030 has not been directly benchmarked; no response-time guarantee is made.

# Nexo 7 0.7.0 — opt-in Internet lookup and reusable web memory

- Search Wikipedia without a key or connect your own Brave Search API key for broader web results.
- Save retrieved excerpts locally with source URLs, retrieval times and a seven-day reuse window; repeated matching lookups can work offline without another search.
- Refresh explicitly, inspect expired entries, and delete individual/all saved web sources. Private chat never saves new web sources.
- Excerpts-only mode avoids model calls. Web explanation uses a single model round without tool schemas; context packing shortens excerpts before removing sources.
- Search keys stay in application memory. Brave storage requires a plan granting storage rights; no key is provided. No conversations or retrieved web data are automatically uploaded to GitHub.
- Windows/Linux 4 GB available-memory admission and platform memory guards remain.

This adds retrieval and reuse, not weight training or new model intelligence. Wikipedia is not general web search; Brave live operation requires your key. Search snippets are unverified excerpts, not full articles. See WEB-RESEARCH.md for limits, privacy and setup.

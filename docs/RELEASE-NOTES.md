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

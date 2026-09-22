# Architecture — native edition

The desktop launcher creates a per-user database/workspace, takes an instance lock and starts an authenticated loopback UI. Setup and chat share an operation lock. Demo stays active until the native model is healthy.

native_catalog.json pins model revisions, engine release b11093, exact file sizes and SHA-256 hashes. native_runtime.py downloads and verifies files, safely extracts the engine, selects a profile, launches a supervisor and checks the authenticated health endpoint. native_worker.py enforces OS-specific memory limits before model startup and watches the parent's lifetime. Runtime credentials/ownership are in memory, never exported as reusable config.

NativeProvider maps the existing bounded tool loop to llama.cpp's OpenAI-compatible local chat endpoint. Engine bounds context, output and tool rounds; validates declared tool arguments; retrieves saved document excerpts and marks unsupported citations. Tools are calculator, memory search, date differences, workspace read/inspection and explicit PubMed research. There is no generated-code execution.

PDF/DOCX/text imports run in a separate memory-limited process with a timeout, returning text to an editor for explicit saving. CSV summaries use decimal arithmetic; Python inspection uses AST parsing without executing imports or code. Workspace files have filename/type/size/count quotas. File metadata enters exact-cache keys to invalidate changed-file answers.

SQLite stores preferences, explicitly approved examples, FTS5 chunks, history and bounded cache entries. This is retrieval/personalization, not online weight training. Native model intelligence remains that of downloaded Qwen weights. Legacy Ollama and optional cloud provider code remain separate.

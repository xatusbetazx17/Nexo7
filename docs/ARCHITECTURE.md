# Architecture

`desktop.py` selects a per-user data directory, takes an operating-system instance lock, starts the authenticated loopback server and opens the user's browser. The setup controller remains in demo mode until a guarded local model has loaded successfully. Chat and setup use the same operation lock.

`hardware.py` measures available memory, applies visible Linux cgroup ceilings when present and recommends a supported model. `local_runtime.py` manages only Nexo's labeled container, disables swap, checks daemon support and verifies actual cgroup limits before model calls. It never switches to an unbounded runtime when checks fail.

`engine.py` admits bounded context, retrieves relevant saved excerpts, calls a configured model and validates advertised tool requests. Arithmetic can bypass the model entirely. Language is included in instructions and cache keys. Research requires retrieved PubMed records; missing records do not become invented evidence.

`store.py` provides SQLite FTS5 document search, bounded history and exact-response caching. `providers.py` adapts local Ollama and optional OpenAI responses. `tools.py` exposes only calculation and constrained source retrieval. `net.py` bounds response sizes and refuses redirects.

The desktop application is orchestration code; language understanding comes from externally downloaded model weights. Better retrieval, deterministic calculations and reduced repeated work can improve particular workflows, but do not establish a generally better model.

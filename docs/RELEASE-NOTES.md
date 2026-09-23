# Nexo 7 0.7.0 — opt-in Internet lookup and reusable web memory

- Search Wikipedia without a key or connect your own Brave Search API key for broader web results.
- Save retrieved excerpts locally with source URLs, retrieval times and a seven-day reuse window; repeated matching lookups can work offline without another search.
- Refresh explicitly, inspect expired entries, and delete individual/all saved web sources. Private chat never saves new web sources.
- Excerpts-only mode avoids model calls. Web explanation uses a single model round without tool schemas; context packing shortens excerpts before removing sources.
- Search keys stay in application memory. Brave storage requires a plan granting storage rights; no key is provided. No conversations or retrieved web data are automatically uploaded to GitHub.
- Windows/Linux 4 GB available-memory admission and platform memory guards remain.

This adds retrieval and reuse, not weight training or new model intelligence. Wikipedia is not general web search; Brave live operation requires your key. Search snippets are unverified excerpts, not full articles. See WEB-RESEARCH.md for limits, privacy and setup.

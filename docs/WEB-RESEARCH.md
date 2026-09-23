# Internet lookup and reusable local knowledge (0.7)

## Workflow

1. Select **Web lookup** in the conversation mode menu, or use **Look up this topic online** after an answer without saved sources. That button only prepares the query; Send initiates lookup.
2. Select **Wikipedia** for encyclopedia topics without a key, or **Brave Search** for broader web search with your own API key. Select the search language separately from the response language. Review the short query before sending: this exact query, not the chat history or personal documents, is sent to the provider.
3. Optionally check **Remember retrieved excerpts** to save sources locally. Private chat never saves new web excerpts. Uncheck **Explain with the connected model** to retrieve excerpts with no model calls.
4. Repeat the same topic later. Saved matching searches can be reused for seven days without another Internet request, even after restarting. Ordinary local chat also searches unexpired saved excerpts. This is lexical retrieval, not perfect semantic recall.
5. Check **Refresh now** for changing information. A small English/Spanish keyword heuristic also requests refresh for obvious current-news/price queries, but it cannot detect every time-sensitive question or language. Seven days is a reuse policy, not a truth or freshness guarantee.
6. Open **My knowledge → Saved web sources** to inspect dates, original links and excerpts, or delete them. Expired entries remain visible there but are not automatically reused. Deleting excerpts does not erase previously saved chat history; clear that separately.

## Providers and data

Wikipedia provides short introductory extracts, not full articles or a general web index. The supported search-language list is deliberately bounded. Results retain their original URL and are labeled as encyclopedia excerpts; see each article for its attribution, history and applicable license. Do not automatically redistribute retrieved text as community learning data.

Brave Search returns web-search descriptions, not pages downloaded by Nexo. Enter your own key in My knowledge or set `BRAVE_SEARCH_API_KEY` before launch. The interface keeps the key in process memory until exit; it is not written to SQLite, logs, learning packs or browser storage. Remove key clears it for that run. Search can be subject to the provider's charges and limits. No key or subscription is supplied by this project.

Brave states that saving results requires a plan explicitly granting storage rights: https://brave.com/search/api/ (FAQ). Check the storage-rights box only if your plan allows it. Otherwise Brave lookup runs without history persistence, and Remember is rejected. Private chat can still use previously stored references, but never saves new ones.

Official API references:
- https://www.mediawiki.org/wiki/Extension:TextExtracts
- https://www.mediawiki.org/wiki/API:Search
- https://api-dashboard.search.brave.com/api-reference/web/search/get

## Limits and efficiency

Each lookup uses at most one provider request, three result excerpts and 1,000 characters per excerpt. Queries are limited to 500 characters / 75 words. Transport has a 20-second timeout and 500 KB response cap, with no redirects or implicit retries. Only fixed Wikipedia/Brave API endpoints are contacted; result URLs are never downloaded automatically. Source links open only when the user clicks them.

Storage is bounded to 100 search groups / 300 excerpts, with oldest-group eviction, duplicate-query replacement and explicit deletion. Keys, complete webpages and model-generated summaries are not stored in the web-source database. Excerpts remain unverified data, not new instructions, authorization or model weights. Actual third-party correctness is not established by retrieval. Internet lookup obeys the existing `research_network` switch and tool-call limit.

Web explanation uses one local generation round without advertising additional tools. Context packing shortens excerpts before dropping an entire source. Model-free lookup and exact saved-query reuse avoid unnecessary generation or network requests; neither makes a weak model a stronger general reasoner. Existing 4 GB available-RAM admission and OS memory guards remain.

## What this release does not implement

This is not continuous weight training, distillation, a new inference architecture, arbitrary web browsing, automatic knowledge-gap detection, or a guarantee of more accurate answers. Model compression/training changes need a separate compatible dataset, compute and held-out accuracy/latency/memory comparisons. It does not autonomously search every time the model is uncertain. Each Web lookup request is user-selected; ordinary chat stays offline except explicitly selected literature research or a configured cloud generation provider.

## Verification

Run `python -m unittest discover -s tests -v` for consent/private behavior, persistence, expiry, refresh, invalid URLs, credential isolation, bounded eviction and context packing. `python scripts/smoke_web.py path/to/Nexo7` checks live Wikipedia retrieval through a packaged app, then zero-request reuse. Brave uses protocol fixtures in tests; it is not live-tested without a user-provided key. These checks are engineering tests, not broad model accuracy benchmarks.

# Nexo starter guide

Nexo 7 is an independent assistant around downloaded Qwen weights, not a newly trained frontier model.
The native desktop setup needs no Docker or WSL. It verifies downloads and applies OS memory limits.
Choose Fast for the smallest model. Windows can attempt NVIDIA/Vulkan; native Linux uses CPU in this release.
Chat in English, Spanish or another selected language; quality depends on the base model.
Use /calc 24.50 * 40 and /date 2024-02-28 2024-03-01 for deterministic results without model tokens.
Import PDF, DOCX or text in My knowledge, review it, then save. Scanned PDFs need OCR, which is not included.
Save CSV, JSON, Python or text in My workspace; Analyze checks data/syntax without executing code.
Use /inspect sales.csv for workspace statistics or ask the model to read a saved file by name/ID.
Native memory budgets are normally at most 12 decimal GB with a 16 GB configuration ceiling.
Linux limits virtual address space; Windows limits job committed memory. OS, app/browser, VRAM and disk are separate.
Models do not execute shell commands, install software or train themselves from conversations.
PubMed searches send the requested topic to the Internet. Local chat and document tools can work offline after setup.
Documents/history are local and unencrypted. Private mode avoids saving the current conversation, not explicitly saved files.

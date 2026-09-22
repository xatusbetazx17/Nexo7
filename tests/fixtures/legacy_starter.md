# Nexo starter guide

Nexo 7 is an independent assistant application, not a newly trained frontier model.
Use /calc 24.50 * 40 for an exact arithmetic result without model tokens.
Add a text document in My knowledge, then ask about it or use /search followed by keywords.
The local setup wizard checks Docker, available memory and the supported model profiles.
CPU inference is supported. Compatible GPU acceleration is optional; speed depends on hardware.
Chat answers can follow English, Spanish or another selected language. Language quality depends on the model.
The inference container uses a verified RAM ceiling, normally at most 12 decimal GB and never above 16 GB.
This ceiling excludes the operating system, browser, app, Docker virtual machine overhead and dedicated GPU VRAM.
A supported model download is checked against its profile size; cumulative Docker storage is not capped at 16 GB.
Literature search sends the search topic to PubMed. Do not include personal medical information.
Local documents and history are stored on this computer without encryption. Use private mode to avoid saving a conversation.

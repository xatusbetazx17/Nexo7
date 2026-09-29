Nexo 7 v0.20.0 preview — local short-video maker across devices

- New "Short video" mode in the shared Create tools (standalone browser app, desktop Windows/Linux interface, LAN companion, mobile companion).
- Script beats: up to 8 narration lines (140 characters each), one animated scene and color palette per beat; or paste a paragraph and split it into beats automatically.
- Word-count timings at about 150 words per minute (3–12 seconds per beat, 60 seconds total), with a live preview of each beat and a running total.
- Vertical 9:16 (360×640) recording through the browser encoder: MP4 or WebM depending on encoder support, with burned-in captions, a progress bar and a beat counter.
- Microphone voiceover mixed with the procedural instrumental soundtrack while recording (the browser asks permission; earphones avoid echo). No AI narration voice is included.
- Captions export as .srt with the same timings burned into the video; silent animated-GIF fallback (180×320) for browsers without a supported encoder.
- One recording at a time, cancellation, hidden-tab cancellation, 16 MB output cap. No network requests from the studio.

Limits: this is not arbitrary prompt-to-video; the studio uses template/procedural graphics, instrument synthesis and your own microphone narration. No AI vocals. Safari/iOS and other browsers must expose canvas recording, a supported encoder and microphone access to export narrated shorts; unsupported browsers display an explanation and retain the GIF fallback. Physical Apple-device testing is still needed. Telegram remains a chat/image-analysis bridge, not a media-generation command interface.

Browser use: https://xatusbetazx17.github.io/Nexo7/ — Create tab. Existing visitors: close all Nexo tabs and reopen to activate an updated offline cache.
Desktop use: run the new Windows/Linux package, choose Create, then Create on this device. No additional model is needed for these lightweight tools. Optional DreamShaper neural image generation remains a separate desktop download with its own RAM requirements.

Video compatibility: browsers without canvas recording or a supported encoder fall back to a **silent animated GIF** (180×320, 8 frames/second, first 20 seconds). All versions also offer an explicit GIF button. GIF has no audio. WebKit on Linux was verified for this fallback, not MP4/WebM recording or physical iPhone hardware.

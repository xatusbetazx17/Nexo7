Nexo 7 v0.19.3 preview — local creative studio across devices

- Shared Create tools in the standalone browser app, desktop Windows/Linux interface, and LAN companion.
- Local template illustrations (landscape, space, chicken, abstract), captions, colors, freehand drawing and optional imported pictures. Export PNG.
- Procedural instrumental music: mood, tempo, length, variation and instrument controls. Play and export WAV/MIDI, with no model download.
- Short animated clips (4, 8 or 12 seconds), with optional synthesized soundtrack. Exports MP4 or WebM depending on browser encoder support. Imported pictures produce captioned still-image clips.
- One recording at a time, cancellation, hidden-tab cancellation, 16 MB output cap and bounded 640×360 rendering. Browser profile lock clears the creative session.
- No network requests from the studio. Existing desktop neural image generation and chat/document tools remain available.

Limits: this is not arbitrary prompt-to-image or generative video; the browser studio uses template/procedural graphics and instrument synthesis. No vocals. Safari/iOS and other browsers must expose canvas recording and a supported encoder to export clips; unsupported browsers display an explanation and retain image/music export. Physical Apple-device testing is still needed. Telegram remains a chat/image-analysis bridge, not a media-generation command interface.

Browser use: https://xatusbetazx17.github.io/Nexo7/ — Create tab. Existing visitors: close all Nexo tabs and reopen to activate an updated offline cache.
Desktop use: run the new Windows/Linux package, choose Create, then Create on this device. No additional model is needed for these lightweight tools. Optional DreamShaper neural image generation remains a separate desktop download with its own RAM requirements.

Video compatibility: browsers without canvas recording or a supported encoder fall back to a **silent animated GIF** (320×180, 8 frames/second). All versions also offer an explicit GIF button. GIF has no audio; export WAV separately. WebKit on Linux was verified for this fallback, not MP4/WebM recording or physical iPhone hardware.

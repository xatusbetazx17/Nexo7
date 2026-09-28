# Nexo on each device — no app installation

The standalone browser app runs its model **on the device opening the page**. It works independently of the Windows/Linux desktop app. It is different from the optional LAN companion, which sends questions to a PC.

Open the project's deployed HTTPS page in a current browser on Mac, iPhone, iPad, Windows, Linux or Android. Creating a home-screen icon is optional. Create a local profile with a pairing phrase, or import an encrypted `.nexo` profile, then choose **Download / load local chat**. No account, Python, Docker, desktop bridge or app-store installation is required.

**No installation does not mean no download.** The page caches its application/runtime files (~24 MB) and, when you ask, the pinned LiquidAI LFM2.5-350M Q4_K_M model (~230 MB). After the first successful load, chat can run offline while these files remain in browser storage. Profiles are encrypted on this device; conversations stay in the tab. Export a profile before clearing browser data. Your pairing phrase has no recovery service.

## What runs locally

- Short multilingual chat using CPU WebAssembly in a worker; no cloud or PC inference fallback.
- Notes, reminders while open, personality, reviewed experiences and encrypted profile transfer.
- Five color palettes, light/dark appearance and a name-initial, robot, cat or orb avatar.
- Manual image editing: rotate, mirror, center square crop, grayscale, undo/reset, finger/mouse eraser and transparent PNG export. Images are not uploaded, are not placed in saved memory and are cleared on lock. Work on a resized copy (maximum 1024 pixels); PNG/JPEG/WebP files up to 8 MB and 24 megapixels. This is **not** automatic background removal, generative editing, subject recognition or Qwen image generation.
- Optional local voice features only when the browser exposes installed on-device support; no silent remote fallback.

For WebKit, Wllama uses the shared IndexedDB cache instead of requiring OPFS. The pinned runtime is bundled with guarded adapters for real Memory64 feature detection and safe abort-error reporting; its MIT license is included.

The download checks browser storage, displays progress and verifies the model's size and SHA-256. The model retains a 2,048-token context, single CPU thread and bounded input/output. **Free model memory** and **Stop** terminate the worker.

Safari does not report available RAM to this application. Browser estimates are not an OS memory limit; there is no guarantee of a fixed total RAM ceiling on every phone. The 230 MB download is not the model's total runtime memory. Larger desktop models and native image generation remain separate features.

On iOS, background tabs may be suspended. Keep the page open during generation. This web app cannot act as a continuously running Telegram bot, access other apps freely, or guarantee background reminders. The existing Windows/Linux Telegram bridge is unchanged.

## About the shared Qwen video

The referenced [video](https://www.youtube.com/shorts/_a0r6lQKc28) describes **Qwen-Image-2.1**, an image generator/editor, not a replacement chat model. Its official model card describes transparency, local edits and up to ten reference images. Its larger pipeline and native runtimes do not fit this browser app's low-memory design. Qwen-Image-2.1 weights have **not** been embedded, ported to Safari, downloaded automatically, or relabeled as Nexo's own model.

The [Unsloth guide](https://unsloth.ai/docs/models/qwen-image-2.1) describes a 7B visual generator plus an 8B encoder and gives estimated CPU/unified-memory starting configurations of 12–16 GB. Those are not tested minimums for Nexo. The [official model card](https://huggingface.co/Qwen/Qwen-Image-2.1) documents the separate Qwen Research License. Adding that complete native engine would need separate integration, license review and real hardware tests; it is not promised for a 4 GB browser budget.

## Publishing the static app

The **Local browser app** workflow builds and tests the app in Chromium, the Safari compatibility runtime, and Playwright WebKit, including actual WASM inference and offline reload. A compatibility user agent alone is not a Safari test; Playwright WebKit is also not a physical iPhone/Mac benchmark. All three browser gates passed in [validation run 36371902229](https://github.com/xatusbetazx17/Nexo7/actions/runs/36371902229), including real local generation after the origin server was stopped and external HTTPS requests were denied. Physical Safari validation is still needed.

For GitHub Pages, select **Settings → Pages → Source → GitHub Actions** once in this repository. The workflow deploys only `mobile/dist` after its validation gates. It does not publish profiles, keys, notes or model weights. The project site is then `https://xatusbetazx17.github.io/Nexo7/`.

Alternatively, build with `npm ci --prefix mobile --ignore-scripts` and `npm run build --prefix mobile`, and publish `mobile/dist` on a trusted HTTPS static host with `.wasm` served as `application/wasm`. Use the same origin/path to retain existing encrypted profiles and cached models. Do not import sensitive data into an untrusted host: the host can change JavaScript.

Small-model factual accuracy is still limited. Browser execution and offline tests do not establish ChatGPT-level reasoning or the image quality shown in the video.

## Creative studio (v0.19.3)

Open **Create** to make template illustrations or freehand drawings (PNG), procedural instrumental tunes (WAV/MIDI), and 4–12 second animated clips (MP4/WebM when the browser supports recording). All rendering happens in the tab without a model or uploads. Optional pictures are resized and kept in memory. Keep the tab visible for recording; locking the profile clears the studio. These are bounded graphics/music tools, not neural image/video generation or vocals. The desktop and LAN companion include the same tools. The desktop's optional DreamShaper AI-image engine remains separate.

After updates, close all Nexo tabs and reopen so the waiting offline cache can activate.

# Start Nexo 7 — native edition 0.10.0

1. Extract the archive into a folder you own. Windows: open Nexo7.exe. Linux: run ./Nexo7 (chmod +x Nexo7 if needed).
2. The local browser interface opens. Python and the PDF reader are included. No Docker or WSL required.
3. In Setup, select Fast for the smallest model or Balanced/Larger model for resource-based selection. Choose Check requirements.
4. Choose Download & start local AI. Internet is needed for the first engine/model download. Both downloads are pinned and SHA-256 verified. Smallest model is about 580 MB; larger choices need more disk and memory.
5. Start chatting in your preferred language. Saved documents and text generation run locally. Literature research contacts PubMed; the optional cloud provider must be configured explicitly.
6. Use Quit Nexo to stop the app and its model. Closing only the browser tab leaves the app running. Saved preferences can enable automatic startup on future launches.

Supported desktop builds: Windows x86-64 and modern glibc Linux x86-64. A supported CPU, sufficient free disk and free memory are needed even on a nominal 8 GB PC. Native Linux uses CPU in this release. Windows can try NVIDIA/Vulkan with suitable drivers and measured VRAM, falling back to CPU. AMD/Intel GPU support is not promised. No additional driver installation occurs automatically.

## Documents and local tools

My knowledge imports PDF, DOCX and UTF-8 text/code/CSV/JSON files. Review the extracted text, then Save knowledge. Limits: 5 MB input, 100 PDF pages, 200000 characters. Scanned images need OCR, which is not included. PDF/DOCX extraction discards layout, images and macros. Extraction is isolated in a worker with a 1 GB memory budget and a 25-second timeout.

My workspace lets you review and save generated documents/code, or load a text/CSV/JSON/code file into the editor. Click Analyze to calculate CSV statistics, validate JSON or inspect Python syntax. Syntax checks do not execute code or establish correctness/security. Ask about file makes its name/ID available to chat; the model only receives bounded excerpts or tool results. Duplicate filenames require a unique file ID.

Direct chat commands work without model inference:
- /calc 24.5 * 40
- /date 2024-02-28 2024-03-01
- /inspect sales.csv (file must already be saved in My workspace)
- /search your saved topic

Approved examples are searchable references, not model training. Incorrect feedback clears cached answers. Private chat avoids history/cache; explicitly saving a document or file is a separate action.

## Memory and privacy

Nexo normally budgets at most 12 decimal GB for native inference; the configuration ceiling is 16 GB. Linux enforces virtual address space per model process. Windows uses aggregate job committed memory and disables model mmap. These are different memory measures, not a guarantee of whole-PC RAM or disk usage. OS, app/browser, dedicated VRAM and downloaded files are separate. Swap remains an OS setting. RAM/VRAM recommendations are rechecked on setup/launch, not live resized during an answer.

Local data is not encrypted: %LOCALAPPDATA%\Nexo7 on Windows; $XDG_DATA_HOME/Nexo7 or ~/.local/share/Nexo7 on Linux. The native engine is not a security sandbox. No model-generated code runs automatically. Do not expose the local server to a network.

This is an independent assistant around Qwen, not official GPT-7. Quality varies, and neither universal task competence nor clinical capability is claimed.

Upgrading from 0.4: quit the old application before opening the new one. Personal notes/preferences remain in the same data folder. Only the exact bundled old starter guide is automatically replaced with native instructions; user-authored notes are preserved. Old Docker downloads are not deleted automatically.

## Starting with about 4 GB available RAM

On native Windows and Linux, 4 decimal GB **available** gives a 3 GB model budget plus 1 GB additional headroom. Available RAM is measured after OS/application usage; it is not installed RAM. The smallest 0.8B model is selected at this budget. Below 3.5 GB available the planner still refuses to load. No system services need to be disabled. Actual model loading must also succeed inside the platform-specific memory guard.

Fast always selects the smallest native model. Balanced / Larger model can select larger supported models when memory permits; compatible Windows NVIDIA acceleration is optional. More RAM alone does not guarantee faster responses: CPU/GPU capability and the selected model also matter. Long documents, complex reasoning and unsupported tasks remain limited. This is not a promise of good performance for every task on a 4 GB installed-memory PC.

## Look up and remember new information

Select Web lookup, choose Wikipedia (no key) or your configured Brave Search account, and enter a short topic. Check Remember to store retrieved excerpts for later local reuse; check Refresh for changing information. Uncheck model explanation for model-free excerpts. Manage saved sources and optional Brave credentials in My knowledge. See WEB-RESEARCH.md. Search is optional and does not train model weights.

## Everyday questions

Choose **Chat · everyday questions** for questions such as “What is a chicken?” or “¿Qué es una gallina?”. It uses a short prompt and no Internet search. Use **New chat** to leave research mode and return to Companion with Internet permission off. For the Dell with 8 GB installed RAM, select **Fast** in setup. Longer replies are available in **Detailed**, and saved documents/examples in **Saved knowledge & tools**.

If an older version repeatedly waited about 180 seconds, install v0.10.0 in a new folder after quitting Nexo. Open the new executable and start a New chat. Existing downloaded models and saved data remain in the usual per-user data directory. This update reduces prompt and output work but cannot guarantee a specific speed on an untested CPU.

See [Companion workflow](COMPANION.md) for reviewed memory, per-request research, device observations and bounded syntax repairs.

Open **Offline math** above the chat box for numerical equations/statistics. In **My knowledge → Saved web sources**, choose **Contribute a note** to prepare an original, reviewed public GitHub submission. See CONTRIBUTIONS.md before sharing.

See [COMPANION.md](COMPANION.md) for personality settings, source-linked learning, Word export and the 4 GB installed / 2.5 GB available memory profile.

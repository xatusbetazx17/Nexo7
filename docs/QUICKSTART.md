# Start Nexo 7

1. Extract this archive to a folder you own. Keep the included files together.
2. Windows: double-click `Nexo7.exe`. Linux: run `./Nexo7` (or open it in a file manager that supports executable files). If execute permission is missing, run `chmod +x Nexo7` first.
3. Your browser opens the Nexo interface. Keep the application running while you use it.
4. Choose **Check requirements**. Local inference requires a running local Docker engine with Linux containers and cgroups v2. Follow the official Docker links in the setup screen if it is missing. Installing Docker may require OS configuration, permissions and a restart.
5. Choose **Download & start local AI**. Initial image/model downloads can use several GB. Setup verifies the RAM guard and loads a supported model. GPU support is optional; you can select CPU only.
6. When setup finishes, start a conversation. Choose a response language in chat. English and Spanish are supported by the selected base model; quality varies by model and language.
7. Use **Quit Nexo** to close the application and stop its model. Closing the browser tab alone keeps Nexo running. Downloads and your notes are retained for next time. Each launch checks resources again; already downloaded model layers are reused.

**Try it immediately:** choose **Explore demo without a model** for calculations and saved-document lookup. Demo does not generate AI answers.

The portable app includes Python. It does not bundle Docker, GPU drivers or model weights. No API key or paid AI account is required for local mode. Internet is needed for first downloads and PubMed searches; local chat can work offline after its dependencies and model have been downloaded.

Windows builds target x86-64 Windows with a supported Docker Desktop/WSL 2 installation (Docker currently specifies at least 8 GB system RAM). Linux CI builds target x86-64 glibc systems using Ubuntu 22.04; actual compatibility depends on host libraries and Docker support. ARM and 32-bit builds are not provided. Unsigned preview binaries may require normal operating-system trust decisions; no code-signing certificate is bundled.

## Memory and data

The selected model download is checked against a profile cap of 1.5–7.5 decimal GB. Its inference container normally receives at most 12 GB RAM and can never be configured above 16 decimal GB. The launcher reserves room for other applications and refuses to run if the guard cannot be verified. This is not a 16 GB limit on total installation size or whole-computer memory. The OS, browser, app, Docker VM overhead and dedicated GPU VRAM are separate. Model fallback downloads and Docker images can accumulate on disk.

Your notes and chat history are stored locally without encryption: `%LOCALAPPDATA%\Nexo7` on Windows, `$XDG_DATA_HOME/Nexo7` or `~/.local/share/Nexo7` on Linux. Private mode avoids saving a conversation. Saved documents are still searchable in private mode. PubMed receives the topic you search; do not include patient identifiers.

The application is an independent assistant built around an existing model, not official GPT-7. It has no demonstrated superiority to frontier models and is not clinically validated.

## Preferences, examples and files

In Setup, choose **Fast** for a smaller model and shorter generation budgets, **Balanced**, or **Larger model when it fits**. Save preferences; hardware changes take effect at the next local start. You can enable automatic local startup after the dependencies have been installed. Free NVIDIA VRAM is measured for selection, but is not hard-limited. AMD support remains conservative and depends on drivers.

After a reply, **Save as useful example** asks permission to add that question and answer to searchable memory. It does not retrain the model or establish truth. Remove examples through **My knowledge**. **Mark incorrect** clears the answer cache but does not erase conversation history or guarantee the mistake will not recur. Private replies do not offer the example-saving control.

Choose **Create file** after a reply, review/edit its contents and filename in **My workspace**, then save. Supported formats are txt, md, csv, json, html, css, js, py and sql. Files stay in the `workspace` folder under the app data directory; download or delete them in the interface. Limits: 200 files, 20 MB total, 200 KB each. Saving a file is explicit even for a private conversation. No generated code is executed automatically.

Local generation still consumes tokens, time and electricity; there is no per-token API bill in local mode. Only direct tools and cache hits can avoid model inference. Model weights and dependencies must be downloaded separately.

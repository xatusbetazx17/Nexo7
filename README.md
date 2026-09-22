# Nexo 7

An independent local assistant with an English setup interface, multilingual chat, personal document retrieval and a verified inference-container RAM limit.

**Early preview · v0.4.0.** Nexo is an application around an existing model. It is not official ChatGPT/GPT-7, does not contain proprietary OpenAI weights, and has no demonstrated superiority over Astra or other local models. It is not clinically validated.

## Get started

Download the archive for your operating system from [Releases](https://github.com/xatusbetazx17/Nexo7/releases). The first v0.4.0 release appears after both native build jobs succeed; track progress in [Actions](https://github.com/xatusbetazx17/Nexo7/actions). Extract it and open **Nexo7.exe** on Windows or **Nexo7** on Linux. Python is bundled in portable builds.

The setup screen checks the computer, recommends a model and shows download progress. Local AI requires **Docker with Linux containers and cgroups v2**. Use the official installation links in the interface, start Docker, then choose **Check requirements → Download & start local AI**. Docker setup can require OS changes, permissions and a restart; the application does not silently install drivers or accept third-party terms.

Choose **Explore demo without a model** to immediately try calculations and document lookup. Demo does not generate AI responses. See [START HERE](docs/QUICKSTART.md) for requirements and data locations.

## What it does

- Adapts a supported Qwen3.5 model profile to available host/Docker RAM and measured free NVIDIA VRAM. Offers Fast, Balanced and Larger-model preferences.
- Remembers language, answer style and optional automatic local startup; resources are checked again on launch.
- Saves explicitly approved answers as searchable examples, with deletion through My knowledge. This does not retrain weights or verify answers.
- Creates reviewed text, code, CSV and JSON files in My workspace, with download and deletion. Generated code is never automatically executed.
- Uses CPU inference or attempts compatible NVIDIA/AMD acceleration, with CPU fallback during setup.
- Lets the user select a response language, including English and Spanish. Quality depends on the base model.
- Runs arithmetic directly, with no model tokens, and retrieves relevant excerpts from saved text using SQLite FTS5.
- Keeps optional chat history and a bounded exact-response cache on the computer.
- Retrieves PubMed records for literature questions and displays sources, tool usage and elapsed time.
- Restricts model tools to arithmetic, saved-document search and opt-in literature search. Models cannot run shell commands or install software.

## Resource limits

| Resource | Policy |
| --- | --- |
| Inference-container RAM | Adaptive, normally at most 12 decimal GB; configuration rejects more than 16 GB |
| Swap for the model container | Disabled; actual cgroup limits checked before inference |
| Local models loaded | One, with one concurrent inference request |
| Selected model file size | Checked against a profile maximum of 1.5–7.5 GB |
| Context and output | Local context at most 8192 tokens; output at most 1024 per call |
| Other memory and storage | OS, app/browser, Docker VM overhead, dedicated GPU VRAM, images and accumulated downloads are separate |

VRAM measurements guide profile selection; they are not a hard VRAM cap. Resources are rechecked at startup, not continuously resized during a conversation. On a hypothetical 8 GB machine with 7 GB free, the planner selects 2B in Balanced or 0.8B in Fast; Docker memory may reduce that further.

This does **not** guarantee that every PC can run every model, that the whole computer uses under 16 GB, or that total installation storage stays below 16 GB. Low-memory or unsupported systems receive an explanation and can use demo mode. Admission thresholds are engineering estimates, followed by a real load attempt within the enforced budget. See [resource policy](docs/RESOURCES.md).

The root-level v0.3.0 binary archives and `Nexo7-Source.zip` are retained historical uploads. The current source is the expanded project in this repository; use Releases for new binaries.

## Run from source

Python 3.11+ is required for source use. The core application has no third-party Python runtime dependencies.

```bash
python -m nexo7.desktop
```

Or run `start_windows.cmd` / `start_linux.sh`. The launcher opens a local browser interface and stores data in the operating system's per-user application directory. Use **Quit Nexo** in the interface to stop the application and its model; downloaded layers are retained.

Advanced CLI commands remain available:

```bash
python -m nexo7 local-plan --cpu
python -m nexo7 serve --open
python -m nexo7 chat "/calc 24.5 * 40"
python -m nexo7 local --cpu --open --language es
```

`serve` uses `config.toml` when present and defaults to demo. Copy `config.example.toml` for advanced settings. An optional OpenAI provider uses `OPENAI_API_KEY` from the environment and an explicit model identifier; those requests may incur charges. The desktop wizard uses local inference and never silently falls back to a paid API.

## Build Windows and Linux applications

Build on each target OS; PyInstaller is not a cross-compiler.

```bash
python -m venv .venv
# Activate the environment for your shell, then:
python -m pip install -r requirements-build.txt
python scripts/build_desktop.py
```

This produces a portable archive and SHA-256 checksum in `release/`. Each build must pass an executable smoke test before packaging. The release workflow builds on Windows Server 2022 and Ubuntu 22.04 runners with x86-64 Python. Windows binaries are unsigned. Linux compatibility depends on glibc and system libraries; the local development build's host is recorded in the validation report.

The first push to `main` builds and publishes the v0.4.0 prerelease after both platforms succeed. A `v*` tag can publish a later version; existing releases are preserved. Manual workflow runs produce downloadable Actions artifacts without publishing. See [release process](docs/RELEASING.md).

### Windows portable preview assembled without a Windows runner

An additional `windows-x86_64-preview.zip` can be assembled on Linux. It contains a cross-compiled Windows GUI launcher and the official CPython 3.14.7 embeddable distribution, with a pinned download checksum. This is **not** a PyInstaller cross-build and has **not been executed on Windows** in this environment. It is a preliminary download, pending native validation.

```bash
python -m pip install ziglang==0.15.2
python scripts/build_windows_portable.py
```

Extract all files and open `Nexo7.exe`. The executable starts the adjacent bundled runtime without using a shell. A build manifest records runtime provenance and file hashes. Native Windows CI remains the primary tested release route.

## Verification and limits

```bash
python -m unittest discover -s tests -v
python scripts/evaluate.py --output reports/evaluation-demo.json
```

A standalone CPU check with Qwen3.5-0.8B Q4_K_M ran four short prompts using two threads, with approximately 0.92 GB peak resident memory and 28.8–37.1 generated tokens/second on an AMD EPYC server. The model answered the arithmetic prompt incorrectly. This is not an end-to-end desktop test or a benchmark of a physical 8 GB PC; see the complete [validation record](docs/VALIDATION.md).

Tests check memory-policy decisions, guard failures, tool boundaries, provider contracts, private history, citations and the web API. They do not establish model intelligence, medical efficacy or real GPU performance. `evals/multilingual.jsonl` and `scripts/measure_local.py` support subsequent real-model evaluation; fluent answers still need human review. See [validation](docs/VALIDATION.md).

The optional `experiments/tiny_transformer.py` is an educational byte-level Transformer requiring a separate PyTorch installation. It is unrelated to production inference and its weights are not included in the desktop application.

## Privacy and security

The web server binds to loopback and requires a random access token for API requests. Host/origin checks, bounded requests and restrictive content policy are enabled. Model containers use a local-only published port and restricted privileges. Local processes with sufficient access can still reach local services; this is not protection from malware or a compromised OS.

Notes and chat history are not encrypted. Private mode avoids saving the current conversation and its answer cache. PubMed receives search topics. The optional cloud provider receives queries and relevant excerpts. The model does not grant itself new tools or permissions. Do not expose the local service to a network. See [SECURITY.md](SECURITY.md).

## License

Original project code is MIT licensed. Docker, Ollama, model weights, bundled runtime dependencies and publications retain their own licenses; see [third-party components](THIRD-PARTY.md) and [official sources](docs/SOURCES.md).

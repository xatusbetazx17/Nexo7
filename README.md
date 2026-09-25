# Nexo 7

An independent local assistant with an English setup interface, multilingual chat, personal document retrieval and a OS-specific native memory controls.

**Early preview · v0.14.0.** Nexo is an application around an existing model. It is not official ChatGPT/GPT-7, does not contain proprietary OpenAI weights, and has no demonstrated superiority over Astra or other local models. It is not clinically validated.

## Get started — no Docker

Download the Windows or Linux x86-64 archive from [Releases](https://github.com/xatusbetazx17/Nexo7/releases), extract it and open **Nexo7.exe** or **Nexo7**. Python and the document reader are bundled. The setup screen downloads a pinned native llama.cpp engine and Qwen3.5 GGUF model, checks SHA-256 hashes, applies an OS memory limit and starts local chat. Neither Docker nor WSL is required by the desktop application.

Select **Fast** for the 0.8B model (~580 MB). Balanced/Larger-model preferences choose among supported profiles according to free resources. Initial engine/model downloads require Internet; subsequent chat, document lookup, file inspection and calculations can run offline. PubMed and the explicitly configured optional cloud provider still require Internet.

Windows can attempt NVIDIA/Vulkan acceleration when VRAM is measurable, with CPU fallback. **This Linux native release uses CPU** because GPU drivers may reserve more virtual address space than its strict address-space budget allows. AMD/Intel GPU acceleration and general native Linux GPU support are not promised in this release. See [START HERE](docs/QUICKSTART.md).

## Optional model training and research

The source repository now includes a separate [model improvement workflow](docs/MODEL-RESEARCH.md): reviewed datasets with held-out splits, local-teacher sequence distillation, actual LoRA training, baseline/candidate evaluation, adapter merging and small architecture experiments. Start with `python -m research --help`. These developer tools require optional dependencies and a suitable training computer; they add no training dependencies to the desktop application. The distributed desktop weights remain unchanged until a candidate is independently evaluated, quantized and approved. No general capability gain is claimed.

## Shared notes and offline math

Saved web sources now offer **Contribute a note**: write an original explanation, review rights/privacy/public-training consent, inspect the exact payload, then submit through your own GitHub account. Maintainers can convert approved notes into training-only records. No automatic upload or live weight update occurs. See [contributions](docs/CONTRIBUTIONS.md).

The offline math panel computes linear systems (up to 8 unknowns), quadratic roots including complex roots, and statistics using 50-digit Decimal arithmetic. `/calc` also supports bounded scientific functions; trigonometric arguments are radians. This is not a general symbolic algebra engine or proof of model-level intelligence.

## Companion mode

Default Companion routes everyday requests locally, reuses reviewed answers, and can research fresh information or expressed uncertainty when you enable Internet for that request. It exposes its steps, supports read-only `/device` checks and bounded `/repair filename.py` or `.json` proposals, and checks saved artifacts. See [Companion](docs/COMPANION.md) for commands, permissions and limits. Source metadata is not truth verification. No autonomous operating-system modification or unlimited learning is claimed.

## Everyday chat

Select **Chat · everyday questions** for definitions, explanations and conversation. It runs locally without Internet lookup, saved-source retrieval or model-selected tools. It uses a compact prompt and caps native replies at 128 tokens to reduce work on modest CPUs. Select **Detailed** for longer answers or **Saved knowledge & tools** to use saved documents and examples. **New chat** clears the active conversation and returns to Companion with Internet permission off. Search modes are explicit. Real speed still depends on your CPU; the Pentium N5030 has not been benchmarked directly.

## What it does

- Adapts a supported Qwen3.5 model profile to available host RAM and measured free NVIDIA VRAM. Offers Fast, Balanced and Larger-model preferences.
- Remembers language, answer style and optional automatic local startup; resources are checked again on launch.
- Saves explicitly approved answers as searchable examples, with deletion through My knowledge. This does not retrain weights or verify answers.
- Creates reviewed text, code, CSV and JSON files in My workspace, with download and deletion. Generated code is never automatically executed.
- Uses native CPU inference; Windows can attempt compatible NVIDIA/Vulkan acceleration with CPU fallback.
- Lets the user select a response language, including English and Spanish. Quality depends on the base model.
- Runs arithmetic directly, with no model tokens, and retrieves relevant excerpts from saved text using SQLite FTS5.
- Keeps optional chat history and a bounded exact-response cache on the computer.
- Retrieves PubMed records for literature questions and displays sources, tool usage and elapsed time.
- Imports text-based PDFs, DOCX and UTF-8 text/code files for review before adding them to memory. Extraction runs in a separate limited process. Scanned PDFs need OCR, which is not included.
- Reads explicitly saved workspace files, computes CSV statistics, checks JSON and Python syntax, and calculates date differences.
- Restricts tools to a fixed read-only/calculation set and opt-in literature search. Models cannot run shell commands or install software.

## Resource limits

| Resource | Native policy |
| --- | --- |
| Planned memory budget | At most 12 decimal GB by default; configuration rejects more than 16 GB |
| Linux enforcement | Per-process virtual address-space limit via RLIMIT_AS, inherited before model launch |
| Windows enforcement | Aggregate worker/model committed-memory limit via a verified Job Object; model mmap disabled |
| GPU memory | Admission estimate only; no hard VRAM cap |
| Concurrency | One model and one model request at a time |
| Context / output | Context at most 6144 tokens; Fast output 256/call, other desktop profiles 512/call |
| Imports | 5 MB file, 100 PDF pages, 200000 extracted characters; worker memory budget 1 GB and timeout 25 seconds |
| Workspace | 200 files, 20 MB total, 200 KB per file |

These OS limits measure different things. Windows committed memory does not cap every file-backed mapping or whole-machine RAM; Linux address space is stricter than resident RAM and can reject a process that has enough physical RAM. Neither includes the app/browser, OS, dedicated VRAM or accumulated downloads. Native swap is controlled by the OS; unlike legacy Docker mode, it is not disabled by Nexo. Free RAM is checked at startup, not continuously resized during a response. Unsupported/low-memory systems fail with an explanation.

A nominal 8 GB PC still needs enough free memory, disk and a supported CPU/OS. Tests do not establish universal PC compatibility. See [resource policy](docs/RESOURCES.md).

The root-level v0.3.0 archives and Nexo7-Source.zip are historical uploads. Use current Releases for binaries and the expanded repository for source.

## Run from source

Python 3.11+ is required for source use. Install the document reader dependency first.

```bash
python -m pip install -r requirements-runtime.txt
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

`serve` uses `config.toml` when present and defaults to demo. Copy `config.example.toml` for advanced settings. An optional OpenAI provider uses `OPENAI_API_KEY` from the environment and an explicit model identifier; those requests may incur charges. The desktop wizard uses native local inference and never silently falls back to a paid API.

## Build Windows and Linux applications

Build on each target OS; PyInstaller is not a cross-compiler.

```bash
python -m venv .venv
# Activate the environment for your shell, then:
python -m pip install -r requirements-build.txt
python scripts/build_desktop.py
```

This produces a portable archive and SHA-256 checksum in `release/`. Each build must pass an executable smoke test before packaging. The release workflow builds on Windows Server 2022 and Ubuntu 22.04 runners with x86-64 Python. Windows binaries are unsigned. Linux compatibility depends on glibc and system libraries; the local development build's host is recorded in the validation report.

A push to `main` builds and publishes the v0.7.0 prerelease after native builds and real-model smoke tests succeed on both platforms. A `v*` tag can publish a later version; existing releases are preserved. Manual workflow runs produce downloadable Actions artifacts without publishing. See [release process](docs/RELEASING.md).

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

Tests check real memory-allocation rejection, native process cleanup, memory-policy decisions, archive/download integrity, tool boundaries, document imports, provider contracts, private history, citations and the web API. They do not establish model intelligence, medical efficacy or real GPU performance. `scripts/smoke_native.py --binary dist/Nexo7` exercises the actual native model through the packaged app; fluent answers still need human review. See [validation](docs/VALIDATION.md).

The optional `experiments/tiny_transformer.py` is an educational byte-level Transformer requiring a separate PyTorch installation. It is unrelated to production inference and its weights are not included in the desktop application.

## Privacy and security

The web server binds to loopback and requires a random access token for API requests. Host/origin checks, bounded requests and restrictive content policy are enabled. The native model binds to loopback with a random API key. It runs as your user with memory limits; this is not a filesystem/network security sandbox. Built-in llama agent/shell/MCP tools are disabled. Local processes with sufficient access can still reach local services; this is not protection from malware or a compromised OS.

Notes and chat history are not encrypted. Private mode avoids saving the current conversation and its answer cache. PubMed receives search topics. The optional cloud provider receives queries and relevant excerpts. The model does not grant itself new tools or permissions. Do not expose the local service to a network. See [SECURITY.md](SECURITY.md).

## License

Original project code is MIT licensed. llama.cpp, model weights, bundled runtime dependencies and publications retain their own licenses; see [third-party components](THIRD-PARTY.md) and [official sources](docs/SOURCES.md).

## Reviewed learning (0.6)

Open **My knowledge → Learning workshop** to save corrections and reusable procedures, import/export selected learning packs and preview community examples bundled with a release. Learning persists in your local data directory across updates. References are retrieved when relevant; model weights do not change.

Community sharing is voluntary: edit the example, approve public sharing, then open and submit a GitHub issue draft. No automatic conversation upload or GitHub token storage. Maintainers review contributions before shipping them in a future pack. Optional local performance totals contain no prompt text and are not uploaded. See [learning and privacy](docs/LEARNING.md).

## Internet lookup and reusable web memory (0.7)

Choose **Web lookup** to search Wikipedia without a key, or connect your own Brave Search API key for broader results. **Remember retrieved excerpts** saves dated references locally for reuse; **Refresh now** bypasses saved results. Uncheck model explanation for excerpts without model calls. Saved sources can be inspected/deleted in My knowledge. Private chat never saves new web excerpts. Ordinary chat can retrieve saved, unexpired references without accessing the Internet.

This is bounded source retrieval, not automatic model training or infallible knowledge. Search providers receive the submitted topic. Brave may incur provider charges and requires storage rights to remember results. See [web research](docs/WEB-RESEARCH.md).

## Local companion controls

Version 0.10 adds a smaller native profile (4 GB installed **and at least 2.5 GB available**), personality preferences, source-linked reviewed notes with expiry, outbound privacy checks and offline Word export. These are application features, not new trained model weights or a guarantee of accuracy. See [local companion guide](docs/COMPANION.md) for resource scopes, privacy limits and usage.

## Persistent workspace agent

Version 0.11 adds local model-assisted task planning, bounded generation/correction, persistent steps, reviewed diffs, conditional atomic edits, file verification and rollback. Optional tests check pure scalar Python functions without executing arbitrary code. Existing learning, documents, search and memory guards remain. See [task-agent guide and model comparison](docs/TASK-AGENT.md). An optional Qwen2.5 1.5B candidate is available when a 3 GB model budget fits; it is not a universal quality upgrade.

## Local images and optional Telegram (v0.12)

Choose **LiquidAI LFM2-VL 450M** in Setup for bounded local image questions, and
switch back to automatic chat models when needed. Two attachments are analyzed
separately. Telegram can be started and stopped from Setup with explicit allowed
chat IDs; it cannot read your saved knowledge or workspace.

Task templates, editable proposals and declared HTML checks extend the reviewed
workspace workflow. See [images, Telegram, measured limits and licenses](docs/VISION-TELEGRAM.md)
and [task editing](docs/TASK-AGENT.md). These features do not establish superior
reasoning or factual accuracy; the new checkpoint officially supports English.

## Offline drawing and music

Version 0.13 adds [Creative Studio](docs/CREATIVE-STUDIO.md): editable simple drawings with PNG/SVG downloads and short synthesized instrumental music with WAV/MIDI downloads. Open My workspace to preview a working example without a model or GPU. Chat can draft the editable JSON, with quality depending on the loaded model. This does not add photorealistic image generation or sung vocals.

## Everyday chat and what-if questions

[Version 0.14](docs/SCENARIOS-AND-INTERFACE.md) simplifies navigation and separates imagined scenarios from online searches. The offline What-if calculator uses explicit inputs for toy flight paths and paint/labor subtotals. These features improve routing and provide checked formulas; they do not retrain the underlying model or guarantee correct reasoning.

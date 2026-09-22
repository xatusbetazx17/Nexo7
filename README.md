# Nexo 7

An independent local assistant with an English setup interface, multilingual chat, personal document retrieval and a OS-specific native memory controls.

**Early preview · v0.5.0.** Nexo is an application around an existing model. It is not official ChatGPT/GPT-7, does not contain proprietary OpenAI weights, and has no demonstrated superiority over Astra or other local models. It is not clinically validated.

## Get started — no Docker

Download the Windows or Linux x86-64 archive from [Releases](https://github.com/xatusbetazx17/Nexo7/releases), extract it and open **Nexo7.exe** or **Nexo7**. Python and the document reader are bundled. The setup screen downloads a pinned native llama.cpp engine and Qwen3.5 GGUF model, checks SHA-256 hashes, applies an OS memory limit and starts local chat. Neither Docker nor WSL is required by the desktop application.

Select **Fast** for the 0.8B model (~580 MB). Balanced/Larger-model preferences choose among supported profiles according to free resources. Initial engine/model downloads require Internet; subsequent chat, document lookup, file inspection and calculations can run offline. PubMed and the explicitly configured optional cloud provider still require Internet.

Windows can attempt NVIDIA/Vulkan acceleration when VRAM is measurable, with CPU fallback. **This Linux native release uses CPU** because GPU drivers may reserve more virtual address space than its strict address-space budget allows. AMD/Intel GPU acceleration and general native Linux GPU support are not promised in this release. See [START HERE](docs/QUICKSTART.md).

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

A push to `main` builds and publishes the v0.5.0 prerelease after native builds and real-model smoke tests succeed on both platforms. A `v*` tag can publish a later version; existing releases are preserved. Manual workflow runs produce downloadable Actions artifacts without publishing. See [release process](docs/RELEASING.md).

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

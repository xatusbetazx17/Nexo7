# Validation record — 0.4.0

## Application checks

- Core suite: 70 tests completed, 69 passed and one optional PyTorch test skipped. Added coverage for 8 GB planning, VRAM pressure fallback, preference persistence, approved examples and bounded workspace files, including traversal and symlink rejection.
- Demo engineering evaluation: 6/6 fixed calculation/retrieval cases passed; no model tokens. This is not an intelligence benchmark.
- JSDOM integration with a real local HTTP server: setup prerequisites, demo calculation, document import, literal HTML, saved preferences, explicit example approval, authenticated artifact API and workspace creation/read/deletion. No JavaScript errors. This is not rendered-browser visual QA.
- Linux packaged executable: PyInstaller 6.22.0/Python 3.12, executed on x86-64 Linux with glibc 2.39. Smoke test covers startup, English assets, API authentication, calculator, bundled knowledge, preferences, workspace and clean shutdown. Compatibility with older system libraries is not established by this build.
- Windows portable preview: x86-64 PE GUI launcher cross-compiled with Zig; official embeddable CPython 3.14.7 archive pinned by SHA-256. Structure and hashes checked. **Not executed on Windows.**

## Standalone real-model CPU check

Official llama.cpp b11093, Qwen3.5-0.8B Q4_K_M, two CPU threads, context 2048, output cap 192 tokens, reasoning disabled, seed 42. Model file: 579,615,840 bytes. Pinned revision and SHA-256 are in reports/real-cpu-provenance.json. Full answers and metrics are in reports/real-cpu.json.

Host CPU: AMD EPYC 9V74. Host container limit: 20 GiB. Each inference process was additionally restricted to **8,000,000,000 bytes of virtual address space** using RLIMIT_AS. That is not a physical 8 GB PC test or the production Docker RAM guard.

| Case | Wall time including loading | Generation tokens/s | Peak RSS KiB | Observed answer |
| --- | ---: | ---: | ---: | --- |
| Spanish file tips | 4.734 s | 37.1 | 895508 | Two tips; second includes an awkward invented phrase |
| English file tips | 3.457 s | 35.2 | 895484 | Two relevant tips |
| Python square function | 3.815 s | 31.1 | 896484 | Returns n*n; inspected, not executed |
| 24.5 * 40 | 1.921 s | 28.8 | 896320 | Incorrect: 100; expected 980 |

The Nexo deterministic calculator returns 980.0 for `/calc 24.5 * 40` with zero model calls (separate application test). That illustrates one useful tool-routing improvement, not superiority to other models. No repetitions/statistical confidence, multilingual benchmark score or large-model comparison is claimed. The standalone llama.cpp runtime is a development check and is not bundled or used as an alternative that bypasses the desktop guard.

## Outstanding validation

- Full Docker/Ollama inference, GPU acceleration and a live stress test of the production RAM ceiling: Docker/GPU unavailable here.
- Native Windows execution, rendered-browser layout review and physical low-spec PC performance.
- Broad language/knowledge/reasoning benchmarks and any clinical evaluation.
- Native GitHub Actions results for this imported source are reported by the repository workflow. Local validation above predates publication and does not establish a successful CI run.

## Reproduce

```bash
python -m unittest discover -s tests -v
python scripts/evaluate.py --output reports/evaluation-demo.json
npm install
npm run test:ui
python scripts/benchmark_cpu.py --runtime /path/to/llama --model /path/to/model.gguf
python -m pip install -r requirements-build.txt
python scripts/build_desktop.py
```

The standalone CPU script requires Linux/resource.RLIMIT_AS and separately obtained, license-compliant runtime/model files. Do not extrapolate server token rates to every PC. Training and knowledge remain those of the selected base model; saved examples provide retrieval, not autonomous weight updates.

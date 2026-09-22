# Validation record — 0.5.0 native edition

## Completed locally

- Core suite: 88 tests, 87 passed and one optional PyTorch test skipped. Coverage includes real OS memory-allocation rejection, native supervisor cleanup, hash mismatch/cancellation, archive traversal, low-memory planning, bounded imports, CSV/date/syntax tools and exact bundled-guide migration without changing personal notes.
- Demo evaluation: six fixed arithmetic/retrieval cases; this is not an intelligence benchmark.
- JSDOM integration: setup, low-memory feedback, preferences, explicit examples, authenticated workspace, file creation/deletion, bounded text import and CSV statistics. This is not rendered-browser layout QA.
- Native Linux source and packaged executable both completed actual Qwen3.5-0.8B Q4_K_M inference through the application's HTTP API without Docker. Spanish greeting and English Python-function prompts generated visible answers; arithmetic, CSV totals, isolated text import and clean shutdown also passed. Reports: reports/native-source-linux.json and reports/native-packaged-linux.json.
- Local development host: x86-64 Linux/glibc 2.39, visible container RAM 20 GiB. Native limit selected 12 decimal GB; this run is not a physical 8 GB PC test. Explicit 8 GB planning uses fixtures, while allocation rejection uses a real 1 GB OS limit in a separate test process.

The workflow builds native Windows and Ubuntu 22.04 packages and requires scripts/smoke_native.py on each packaged executable before publishing. Consult Actions for results of the release commit; local results above do not assert Windows/GPU validation.

## Limits of evidence

Short successful responses do not establish broad accuracy, intelligence, universal compatibility or performance superiority. The historical 0.4 standalone model check in reports/real-cpu.json includes an incorrect arithmetic answer. Deterministic tools reduce specific errors; the model still decides whether to call them for ordinary natural-language questions.

Native memory guards differ: Linux limits virtual address space; Windows limits committed memory across the worker/model job with model mmap disabled. Neither guarantees total-machine RAM, disk or dedicated VRAM. Allocation failure may stop the model. Native GPU paths, physical low-spec PCs, scanned-PDF OCR, rendered-browser visual review and clinical capability have not been validated locally. This is not a sandbox for untrusted executable code, which the assistant does not run automatically.

## Reproduce

```bash
python -m pip install -r requirements-runtime.txt
python -m unittest discover -s tests -v
python scripts/evaluate.py --output reports/evaluation-demo.json
npm install
npm run test:ui
python -m pip install -r requirements-build.txt
python scripts/build_desktop.py
python scripts/smoke_native.py --binary dist/Nexo7
```

On Windows pass dist/Nexo7.exe. The real smoke test downloads a pinned engine and ~580 MB model unless cached, then runs actual inference. No paid API is used. The first-run download path needs Internet; subsequent local chat does not.

## 0.6.0 reviewed-learning validation

- Local Python suite: 100 tests, 99 passed and one optional PyTorch skip.
- Learning regression: 2/2 bundled exact questions retrieve their reviewed examples after import (0/2 before import in an empty store); 3/3 calculator cases unchanged. This measures retrieval plumbing, not general intelligence or unseen-question accuracy.
- Authenticated API tests cover consent, preview without mutation, selected export, deletion, private metrics exclusion, credential-pattern rejection, Unicode persistence and capacity failure without partial import.
- JSDOM interaction checks cover the workshop, public draft preparation, consent reset on editing, community pack preview/import and literal HTML handling. This is not a rendered-browser visual inspection.
- Release gates run Windows/Linux native builds, packaged learning import/export and actual model generation with a reviewed reference admitted into context. Consult the 0.6 release Actions run for platform results; local tests alone do not establish Windows execution.
- No GPU benchmark, physical 8 GB device test, continuous training or broad multilingual quality benchmark was performed.

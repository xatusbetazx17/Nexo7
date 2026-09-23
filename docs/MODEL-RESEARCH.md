# Model improvement workflow

This is an optional **developer workflow**, separate from the Windows/Linux desktop app.
It implements reviewed datasets, sequence distillation, actual LoRA weight updates,
held-out evaluation, adapter merging, and controlled small architecture experiments.
It does not ship a newly capable model or claim improvement over Qwen or ChatGPT.

## Hardware and installation

Run from a source checkout with Python 3.12. Create a separate environment:

```sh
python -m venv .venv-research
```

Activate with `.venv-research\Scripts\activate` on Windows Command Prompt, or
`source .venv-research/bin/activate` on Linux. For CPU research:

```sh
python -m pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-research.txt
python scripts/smoke_research.py
```

Use an appropriate PyTorch CUDA wheel for a compatible NVIDIA training host and
pass `--device cuda`. CPU and CUDA paths use float32; this initial workflow is not
QLoRA, distributed training or mixed precision. CUDA has not been validated here.
Qwen3.5's optional fast training kernels are not installed; reference operations
can be slow. Training and merging need substantially more memory than quantized
inference. **Do not assume they fit the Dell's approximately 4 GB free RAM.**
There is no hard memory limiter on these explicit research commands. Use a separate
machine with sufficient RAM, then evaluate a compressed candidate on the target PC.
No research dependencies are imported or bundled by the desktop app.

Community notes can be admitted through the separately reviewed [contribution workflow](CONTRIBUTIONS.md). Its converter emits training-only rows; independent held-out splits are still required.

## 1. Prepare approved data

Input is JSONL: one object per line with these required fields:

```json
{"id":"sample-1","group":"one-source-document","split":"train","prompt":"Your question","answer":"Reviewed answer","language":"en","source":"Owned document and version","license":"Your applicable license","approved":true,"training_allowed":true}
```

Supply nonempty `train`, `validation` and `test` splits. Keep translations,
paraphrases, examples from the same document and closely related questions in one
group and one split. Choose groups before looking at model results. Duplicate
normalized prompts and cross-split groups are rejected. Semantic leakage still
requires human review. Permission booleans record your review; they do not verify
copyright or remove personal data. Do not include secrets or private conversations
without explicit contributor permission. Nothing is automatically uploaded.

```sh
python -m research prepare reviewed.jsonl research-runs/dataset-v1
```

The manifest records hashes and counts; changed data is rejected. Make a new
dataset version for changes. The bundled `tests/research_fixtures/reviewed.jsonl`
is original CC0 synthetic test data: six tiny English/Spanish examples, **not a
useful training corpus or intelligence benchmark**. To check the CLI, substitute
that fixture for `reviewed.jsonl`.

## 2. Optional sequence distillation

Start a stronger, separately licensed teacher on a local OpenAI-compatible HTTP
server. This command sends only the training prompts, never held-out prompts:

```sh
python -m research distill research-runs/dataset-v1 teacher-drafts.jsonl --teacher YOUR_TEACHER --revision YOUR_EXACT_TEACHER_VERSION --output-license YOUR_PERMITTED_OUTPUT_LICENSE --limit 20
```

Default endpoint is `http://127.0.0.1:8080/v1/chat/completions`; use `--endpoint`
for another numeric loopback port. Remote endpoints, redirects and proxy routing
are blocked. The server itself may proxy requests: run a teacher you control.
Teacher identity/version are operator declarations, not cryptographically verified.
Use only a teacher whose terms permit this use of its outputs. This is
**sequence distillation** (learning from answers), not teacher-logit KL distillation.

Every generated record starts with `approved:false` and `training_allowed:false`.
Check correctness, provenance, licensing and privacy; edit or reject each draft.
Replace the corresponding training rows in your source JSONL, retain the untouched
validation/test rows, and prepare a new dataset. Do not append duplicate prompts.
Generated answers and web excerpts are not automatically considered ground truth.
There is no automatic path from web cache or user history into training.

## 3. Train an adapter

Use a pinned Hugging Face revision (40-character commit) or a local safetensors
model directory. Remote model loading disables custom repository code. Example:

```sh
python -m research train --model Qwen/Qwen3.5-0.8B --revision 2fc06364715b967f1860aea9cf38778875588b17 --dataset research-runs/dataset-v1 --output research-runs/adapter-v1 --steps 100 --rank 8 --max-length 512
```

This trains LoRA adapters on `q_proj` and `v_proj` with batch size one, deterministic
example shuffling, answer-only loss and gradient clipping. Base weights, including
Qwen3.5's vision tower, remain frozen. It is text training; it does not add vision
or audio skills. Overlength examples and incompatible chat-template boundaries
fail explicitly instead of silently dropping answer tokens. Validation loss is
reported before and after training. Test answers do not enter the optimizer or
validation-loss computation. A dataset integrity check reads all splits.

Each output has safetensors adapter weights, tokenizer files and `run.json` with
the base identity, dataset hash, settings, dependency versions, training losses,
timing and adapter checksums. Outputs never overwrite an existing run directory.
Seeded runs are reproducible in configuration, not guaranteed bit-identical across
devices. This version does not resume interrupted optimizer state; failed runs
must restart. Keep the source commit and full environment lock for archival use.

## 4. Evaluate the baseline and candidate

Run each command in a **fresh process on the same idle machine**. First use
`--split validation` while choosing settings. After freezing a candidate, use test:

```sh
python -m research evaluate --model Qwen/Qwen3.5-0.8B --revision 2fc06364715b967f1860aea9cf38778875588b17 --dataset research-runs/dataset-v1 --split test --output research-runs/baseline.json
python -m research evaluate --model Qwen/Qwen3.5-0.8B --revision 2fc06364715b967f1860aea9cf38778875588b17 --dataset research-runs/dataset-v1 --split test --adapter research-runs/adapter-v1 --output research-runs/candidate.json
python -m research compare research-runs/baseline.json research-runs/candidate.json research-runs/comparison.json --memory-gb 3 --max-slowdown 1.1
```

Evaluation uses normalized exact match, deterministic decoding, per-example timing,
sampled process peak RSS including loading and PyTorch peak allocated CUDA memory.
This scorer is for short tasks with one expected answer; it cannot judge essays,
reasoning validity, medical correctness or general usefulness. Add representative
multilingual tasks and independent human evaluation before any capability claim.
Reports contain generated answers and must be reviewed before sharing.

Comparison rejects mismatched base, dataset, settings, dependency versions,
environment or examples. It requires higher test accuracy, no language regression,
the chosen mean-latency budget and memory budgets before recommending human review.
It **never authorizes an automatic release**. Memory is measured, not enforced;
sampled RSS can miss brief peaks and CUDA allocated bytes exclude driver memory.
Unquantized research memory results do not predict GGUF memory. Repeat timing runs
and benchmark final GGUF separately with the native process guards. A few successful
examples do not establish statistical significance. Repeatedly tuning against the
test split invalidates it; reserve new test cases for subsequent releases.

## 5. Merge and prepare a deployment candidate

```sh
python -m research merge --model Qwen/Qwen3.5-0.8B --revision 2fc06364715b967f1860aea9cf38778875588b17 --adapter research-runs/adapter-v1 --output research-runs/merged-v1
```

This checks base identity and adapter hashes and saves a merged safetensors model.
It **does not replace the desktop model**. The desktop still downloads its existing
pinned, verified catalog weights. Model distribution is a separate review step:

1. Use a pinned compatible llama.cpp conversion tool to convert the merged model
   to GGUF, then `llama-quantize` to make a Q4_K_M candidate. Install converter
   dependencies in a separate environment. Consult the upstream instructions below.
2. Re-evaluate the actual quantized file for regressions and multilingual quality.
3. Measure startup, peak memory, time to first token and generation on Windows and
   Linux, including the 4 GB available / 3 GB model-budget configuration and the Dell.
4. Publish licensed weights and a model card recording data provenance, limitations,
   metrics, SHA-256 and the rollback model. Only then update `native_catalog.json`
   through normal source review and desktop smoke tests.

No trained weights are uploaded by these commands. Quantization/conversion and a
new desktop catalog entry are not performed automatically by this initial workflow.

## 6. Architecture research

```sh
python -m research.architecture --train owned-train.txt --validation owned-validation.txt --output research-runs/architecture.json --steps 100
```

This runs three small byte-level Transformer configurations with the same seed,
training steps and held-out corpus, reporting parameters, loss, time and sampled
memory. It provides a repeatable experimental starting point; it is not a new
competitive architecture, Qwen compression, or transfer of Qwen's knowledge.
Models share a process, so allocator retention affects memory comparisons. Use
isolated runs for serious memory conclusions. Broader architecture advances require
additional experiments, training data, compute and independent evaluation.

## Upstream references

- [PEFT LoRA workflow](https://huggingface.co/docs/peft/quicktour)
- [Qwen3.5 Transformers support](https://huggingface.co/docs/transformers/model_doc/qwen3_5)
- [llama.cpp conversion and quantization](https://github.com/ggml-org/llama.cpp/blob/master/tools/quantize/README.md)

The reproducible workflow is implemented. An improved production checkpoint,
frontier-model parity, unlimited learning and a general accuracy gain remain unproven.

## Recorded validation (2026-09-23)

- Core suite: 127 tests, 126 passed and one optional PyTorch test skipped in the
  ordinary desktop-development environment.
- Separate CPU research environment: the tiny random Qwen3.5 smoke performed real
  optimizer updates, preserved base weights, evaluated both models, saved/reloaded
  the adapter and verified merged logits against the unmerged adapter.
- Actual pretrained Qwen3.5-0.8B: two LoRA steps completed with 79,872 trainable
  parameters. Baseline and adapter were evaluated in separate processes on two
  held-out synthetic cases with a 16-token output cap. Both scored 0/2 on strict
  exact match; these small, capped tests do not characterize general quality.
- The adapter failed the improvement, latency and 3 GB process-RAM gates. Its
  unquantized research run reached about 5.74 decimal GB sampled RSS. No model
  replacement or trained-weight release was approved.
- All three tiny architecture configurations completed a two-step CPU smoke.

See the [machine-readable record](validation/model-research-smoke.json). These are
development-machine measurements, not Dell measurements. Windows/Linux research
CI runs the offline tiny model smoke without downloading pretrained weights.

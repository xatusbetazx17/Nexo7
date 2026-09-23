"""Single-device text LoRA training, evaluation and safetensors merge.

Training is deliberately separate from Nexo7's inference RAM budget.
"""
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import random
import re
import threading
import time
from .data import digest, load_dataset, normalized, write_json


def identity(model, revision):
    path = Path(model)
    if path.is_dir():
        hashes = {str(p.relative_to(path)): digest(p) for p in sorted(path.rglob("*"))
                  if p.is_file() and p.suffix in (".json", ".safetensors", ".jinja", ".txt", ".model")}
        if not any(name.endswith(".safetensors") for name in hashes):
            raise ValueError("Local model requires safetensors weights")
        return {"local_sha256": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()}
    if not revision or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Remote models require an immutable 40-character commit revision")
    return {"repository": model, "revision": revision}


def versions():
    return {p: importlib.metadata.version(p) for p in ("torch", "transformers", "peft", "psutil")}


def load(args):
    import torch
    from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer, Qwen3_5ForConditionalGeneration
    base = identity(args.model, args.revision)
    if not 1 <= args.threads <= 64:
        raise ValueError("threads must be 1–64")
    if args.device == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA unavailable; select CPU or use an NVIDIA training host")
    torch.set_num_threads(args.threads)
    torch.manual_seed(getattr(args, "seed", 42))
    kwargs = {"revision": args.revision, "trust_remote_code": False}
    config = AutoConfig.from_pretrained(args.model, **kwargs)
    # Official Qwen3.5 checkpoints contain a vision tower; it stays frozen in text LoRA.
    cls = Qwen3_5ForConditionalGeneration if config.model_type == "qwen3_5" else AutoModelForCausalLM
    model = cls.from_pretrained(args.model, **kwargs, use_safetensors=True,
                               dtype=torch.float32, attn_implementation="eager").to(args.device)
    tokenizer = AutoTokenizer.from_pretrained(args.model, **kwargs)
    if not tokenizer.chat_template:
        raise ValueError("A model chat template is required")
    model.config.use_cache = False
    return model, tokenizer, base


def encode(tokenizer, row, max_length):
    prompt = [{"role": "user", "content": row["prompt"]}]
    prefix = tokenizer.apply_chat_template(prompt, tokenize=True, return_dict=False, add_generation_prompt=True, enable_thinking=False)
    complete = tokenizer.apply_chat_template(prompt + [{"role": "assistant", "content": row["answer"]}],
                                              tokenize=True, return_dict=False, enable_thinking=False)
    if complete[:len(prefix)] != prefix:
        raise ValueError("Chat template prefix mismatch; use an explicitly compatible text template")
    if not 2 <= len(complete) <= max_length or len(complete) <= len(prefix):
        raise ValueError("Example exceeds token budget or has no answer; curate instead of silently truncating")
    return complete, [-100] * len(prefix) + complete[len(prefix):]


def tensors(item, device):
    import torch
    ids, labels = item
    return {"input_ids": torch.tensor([ids], device=device),
            "attention_mask": torch.ones((1, len(ids)), dtype=torch.long, device=device),
            "labels": torch.tensor([labels], device=device)}


def loss_on(model, examples, device):
    import torch
    model.eval()
    total, count = 0.0, 0
    with torch.no_grad():
        for item in examples:
            n = sum(x != -100 for x in item[1][1:])
            value = model(**tensors(item, device)).loss.item()
            if not math.isfinite(value):
                raise ValueError("Nonfinite evaluation loss")
            total += value * n
            count += n
    return total / count


def fit(model, examples, validation, *, steps, learning_rate, device, seed):
    import torch
    rng = random.Random(seed)
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=learning_rate)
    before = loss_on(model, validation, device)
    model.train()
    order = list(range(len(examples)))
    losses = []
    for step in range(steps):
        if step % len(order) == 0:
            rng.shuffle(order)
        optimizer.zero_grad(set_to_none=True)
        loss = model(**tensors(examples[order[step % len(order)]] , device)).loss
        if not torch.isfinite(loss):
            raise ValueError("Nonfinite training loss")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        losses.append(float(loss.detach()))
    return {"validation_loss_before": before, "validation_loss_after": loss_on(model, validation, device),
            "training_loss_first": losses[0], "training_loss_last": losses[-1]}


def attach(model, adapter, base, dataset=None):
    from peft import PeftModel
    record = json.loads((Path(adapter) / "run.json").read_text(encoding="utf-8"))
    if record["base"] != base or (dataset is not None and record["dataset"] != dataset):
        raise ValueError("Adapter base model or evaluation dataset mismatch")
    for name in ("adapter_config.json", "adapter_model.safetensors"):
        if digest(Path(adapter) / name) != record["artifacts"][name]:
            raise ValueError("Adapter artifact changed")
    return PeftModel.from_pretrained(model, adapter, is_trainable=False), record


def train(args):
    from peft import LoraConfig, get_peft_model
    if not (1 <= args.steps <= 100000 and 1 <= args.rank <= 128
            and 0 < args.learning_rate <= .01 and 32 <= args.max_length <= 4096):
        raise ValueError("Invalid training limits")
    splits, manifest = load_dataset(args.dataset)
    output = Path(args.output)
    if output.exists():
        raise ValueError("Use a new output directory")
    model, tokenizer, base = load(args)
    examples = [encode(tokenizer, r, args.max_length) for r in splits["train"]]
    validation = [encode(tokenizer, r, args.max_length) for r in splits["validation"]]
    model = get_peft_model(model, LoraConfig(r=args.rank, lora_alpha=2 * args.rank,
        lora_dropout=0.0, target_modules=["q_proj", "v_proj"], task_type="CAUSAL_LM"))
    started = time.perf_counter()
    results = fit(model, examples, validation, steps=args.steps, learning_rate=args.learning_rate,
                  device=args.device, seed=args.seed)
    output.mkdir(parents=True)
    model.save_pretrained(output, safe_serialization=True)
    tokenizer.save_pretrained(output)
    write_json(output / "run.json", {"schema": "nexo-adapter-v1", "base": base, "dataset": manifest,
        "settings": vars(args), "versions": versions(), "results": results,
        "elapsed_seconds": time.perf_counter() - started,
        "trainable_parameters": sum(p.numel() for p in model.parameters() if p.requires_grad),
        "artifacts": {n: digest(output / n) for n in ("adapter_config.json", "adapter_model.safetensors")},
        "status": "experimental; not approved for desktop distribution"})


class PeakMemory:
    """Sample process RSS including loading; not a hard limit or whole-PC measurement."""
    def __init__(self):
        import psutil
        self.process = psutil.Process()
        self.peak = 0
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.sample, daemon=True)

    def sample(self):
        while not self.stop.is_set():
            self.peak = max(self.peak, self.process.memory_info().rss)
            self.stop.wait(.01)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.peak = max(self.peak, self.process.memory_info().rss)
        self.stop.set()
        self.thread.join()


def evaluate(args):
    import torch
    import psutil
    if not 32 <= args.max_length <= 4096 or not 1 <= args.max_new_tokens <= 1024:
        raise ValueError("Invalid evaluation token limits")
    splits, manifest = load_dataset(args.dataset)
    if Path(args.output).exists():
        raise ValueError("Use a new report path")
    with PeakMemory() as memory:
        model, tokenizer, base = load(args)
        adapter_id = None
        if args.adapter:
            model, _ = attach(model, args.adapter, base, manifest)
            adapter_id = digest(Path(args.adapter) / "run.json")
        model.eval()
        if args.device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        results = []
        for row in splits[args.split]:
            inputs = tokenizer.apply_chat_template([{"role": "user", "content": row["prompt"]}],
                tokenize=True, return_dict=False, add_generation_prompt=True, enable_thinking=False)
            if len(inputs) + args.max_new_tokens > args.max_length:
                raise ValueError("Evaluation prompt plus output exceeds context budget")
            ids = torch.tensor([inputs], device=args.device)
            if args.device == "cuda":
                torch.cuda.synchronize()
            start = time.perf_counter()
            with torch.no_grad():
                output = model.generate(ids, attention_mask=torch.ones_like(ids), do_sample=False,
                    max_new_tokens=args.max_new_tokens, use_cache=True,
                    pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id)
            if args.device == "cuda":
                torch.cuda.synchronize()
            elapsed = time.perf_counter() - start
            answer = tokenizer.decode(output[0, len(inputs):], skip_special_tokens=True).strip()
            results.append({"id": row["id"], "language": row["language"], "answer": answer,
                "correct": normalized(answer) == normalized(row["answer"]), "seconds": elapsed,
                "tokens": int(output.shape[1] - len(inputs))})
        gpu_peak = torch.cuda.max_memory_allocated() if args.device == "cuda" else 0
    environment = {"os": platform.platform(), "processor": platform.processor(), "cpu_count": psutil.cpu_count(),
                   "ram": psutil.virtual_memory().total, "device": args.device, "threads": args.threads,
                   "gpu": torch.cuda.get_device_name() if args.device == "cuda" else None}
    write_json(args.output, {"schema": "nexo-evaluation-v1", "base": base, "adapter": adapter_id,
        "dataset": manifest, "split": args.split, "settings": {k: getattr(args, k) for k in
            ("seed", "max_length", "max_new_tokens")}, "environment": environment, "versions": versions(),
        "peak_rss_bytes": memory.peak, "peak_cuda_allocated_bytes": gpu_peak, "results": results,
        "accuracy": sum(r["correct"] for r in results) / len(results),
        "mean_seconds": sum(r["seconds"] for r in results) / len(results),
        "limitations": "Exact-match tasks only. RSS is sampled, GPU metric excludes driver allocations. No factuality judge."})


def merge(args):
    output = Path(args.output)
    if output.exists():
        raise ValueError("Use a new output directory")
    model, tokenizer, base = load(args)
    model, record = attach(model, args.adapter, base)
    merged = model.merge_and_unload(safe_merge=True)
    merged.save_pretrained(output, safe_serialization=True)
    tokenizer.save_pretrained(output)
    write_json(output / "nexo-provenance.json", {"adapter_run": record,
        "status": "unquantized research candidate; desktop catalog unchanged"})

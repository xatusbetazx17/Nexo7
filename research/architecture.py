"""Controlled tiny architecture experiments; not assistant-quality pretrained models."""
import argparse
from dataclasses import asdict
from pathlib import Path
import time
from .data import digest, write_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--train", required=True, help="Owned/licensed UTF-8 corpus")
    p.add_argument("--validation", required=True, help="Separate held-out corpus")
    p.add_argument("--output", required=True)
    p.add_argument("--steps", type=int, default=100)
    args = p.parse_args()
    if not 1 <= args.steps <= 1000 or Path(args.output).exists():
        raise ValueError("Use 1–1000 steps and a new output path")
    import torch
    from torch.nn import functional as F
    from experiments.tiny_transformer import ModelConfig, TinyTransformer
    from .training import PeakMemory
    raw = [Path(x).read_bytes() for x in (args.train, args.validation)]
    if any(not 1024 <= len(x) <= 1_000_000 for x in raw) or raw[0] == raw[1]:
        raise ValueError("Provide distinct 1KB–1MB corpora; keep related documents in one split")
    # Exact shared chunks catch obvious leakage, not semantic duplication.
    chunks = [{x[i:i+128] for i in range(0, len(x)-127, 128)} for x in raw]
    if chunks[0] & chunks[1]:
        raise ValueError("Shared 128-byte corpus chunks; review split leakage")
    torch.set_num_threads(4)
    datasets = [torch.tensor(list(x), dtype=torch.long) for x in raw]
    results = []
    for width, layers in ((32, 2), (64, 2), (64, 4)):
        torch.manual_seed(42)
        cfg = ModelConfig(context=64, width=width, heads=4, layers=layers)
        with PeakMemory() as memory:
            model = TinyTransformer(cfg)
            opt = torch.optim.AdamW(model.parameters(), lr=3e-4)
            rng = torch.Generator().manual_seed(73)
            start = time.perf_counter()
            for _ in range(args.steps):
                indices = torch.randint(len(datasets[0])-65, (4,), generator=rng)
                x = torch.stack([datasets[0][i:i+64] for i in indices])
                y = torch.stack([datasets[0][i+1:i+65] for i in indices])
                opt.zero_grad(set_to_none=True)
                loss = F.cross_entropy(model(x).reshape(-1, 256), y.reshape(-1))
                loss.backward(); opt.step()
            seconds = time.perf_counter()-start
            model.eval()
            with torch.no_grad():
                losses = [F.cross_entropy(model(datasets[1][i:i+64][None]).reshape(-1, 256),
                    datasets[1][i+1:i+65]).item() for i in range(0, len(datasets[1])-65, 64)]
            count = sum(x.numel() for x in model.parameters())
            del model, opt
        results.append({"config": asdict(cfg), "parameters": count, "validation_loss": sum(losses)/len(losses),
                        "training_seconds": seconds, "sampled_process_peak_rss": memory.peak})
    write_json(args.output, {"schema": "nexo-architecture-v1", "steps": args.steps, "seed": 42,
        "corpora": {"train": digest(args.train), "validation": digest(args.validation)}, "results": results,
        "limitations": "Toy byte models trained from scratch; no Qwen transfer or assistant capability. "
        "Same process allocator may retain memory between candidates; use fresh processes for memory conclusions."})


if __name__ == "__main__":
    main()

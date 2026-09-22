"""Train a small causal Transformer from scratch. Educational, not a capable assistant.

Optional dependency: PyTorch >= 2.6. No downloaded weights, no remote training jobs.
This experiment is separate from the model providers used by the Nexo 7 application.
"""
import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import time

try:
    import torch
    from torch import nn
    from torch.nn import functional as F
except ImportError:
    raise SystemExit("Instala la dependencia opcional PyTorch: python -m pip install 'torch>=2.6,<3'")


@dataclass
class ModelConfig:
    context: int = 128
    width: int = 64
    heads: int = 4
    layers: int = 2


class Block(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        self.heads = cfg.heads
        self.norm1, self.norm2 = nn.LayerNorm(cfg.width), nn.LayerNorm(cfg.width)
        self.qkv, self.projection = nn.Linear(cfg.width, cfg.width*3), nn.Linear(cfg.width, cfg.width)
        self.mlp = nn.Sequential(nn.Linear(cfg.width, cfg.width*4), nn.GELU(), nn.Linear(cfg.width*4, cfg.width))

    def forward(self, x):
        b, t, c = x.shape
        q, k, v = self.qkv(self.norm1(x)).chunk(3, dim=-1)
        def split(a):
            return a.reshape(b, t, self.heads, c//self.heads).transpose(1, 2)
        attention = F.scaled_dot_product_attention(split(q), split(k), split(v), is_causal=True)
        x = x + self.projection(attention.transpose(1, 2).contiguous().reshape(b, t, c))
        return x + self.mlp(self.norm2(x))


class TinyTransformer(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.token = nn.Embedding(256, cfg.width)
        self.position = nn.Embedding(cfg.context, cfg.width)
        self.blocks = nn.Sequential(*[Block(cfg) for _ in range(cfg.layers)])
        self.norm = nn.LayerNorm(cfg.width)
        self.head = nn.Linear(cfg.width, 256, bias=False)
        self.head.weight = self.token.weight
        self.apply(self._init)

    @staticmethod
    def _init(module):
        if isinstance(module, (nn.Linear, nn.Embedding)):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if isinstance(module, nn.Linear) and module.bias is not None:
                nn.init.zeros_(module.bias)

    def forward(self, tokens):
        if tokens.shape[1] > self.cfg.context:
            raise ValueError("La secuencia supera la ventana de contexto")
        positions = torch.arange(tokens.shape[1], device=tokens.device)
        return self.head(self.norm(self.blocks(self.token(tokens) + self.position(positions))))

    @torch.no_grad()
    def generate(self, prefix, count=100, temperature=0.8):
        self.eval()
        for _ in range(count):
            logits = self(prefix[:, -self.cfg.context:])[:, -1] / max(temperature, .05)
            new = torch.multinomial(F.softmax(logits, dim=-1), 1)
            prefix = torch.cat((prefix, new), dim=1)
        return prefix


def train(args):
    if not 1 <= args.steps <= 100000 or not 1 <= args.batch <= 128:
        raise ValueError("steps or batch exceeds the limit")
    torch.manual_seed(42)
    torch.set_num_threads(4)
    raw = Path(args.data).read_bytes()
    cfg = ModelConfig()
    if len(raw) < cfg.context*12:
        raise ValueError("Usa al menos 1536 bytes de texto propio o autorizado")
    data = torch.tensor(list(raw), dtype=torch.long, device=args.device)
    split = int(.9*len(data))
    training, validation = data[:split], data[split:]
    model = TinyTransformer(cfg).to(args.device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4)

    def batch(source):
        starts = torch.randint(len(source)-cfg.context, (args.batch,), device=args.device)
        x = torch.stack([source[i:i+cfg.context] for i in starts])
        y = torch.stack([source[i+1:i+cfg.context+1] for i in starts])
        return x, y

    losses = []
    started = time.perf_counter()
    for step in range(args.steps):
        model.train()
        x, y = batch(training)
        loss = F.cross_entropy(model(x).reshape(-1, 256), y.reshape(-1))
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        if step % 50 == 0 or step == args.steps-1:
            model.eval()
            with torch.no_grad():
                vx, vy = batch(validation)
                val = F.cross_entropy(model(vx).reshape(-1, 256), vy.reshape(-1)).item()
            entry = {"step": step+1, "training_loss": loss.item(), "validation_loss": val}
            losses.append(entry)
            print(json.dumps(entry), flush=True)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    torch.save({"config": asdict(cfg), "state_dict": model.cpu().state_dict(), "steps": args.steps,
                "tokenizer": "utf8-bytes-256", "purpose": "educational-only"}, temporary)
    temporary.replace(output)
    metrics = {"parameters": sum(p.numel() for p in model.parameters()), "seconds": time.perf_counter()-started,
               "losses": losses, "note": "Loss on a small corpus; does not measure general intelligence or clinical capability."}
    output.with_suffix(".metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    t = sub.add_parser("train")
    t.add_argument("--data", required=True)
    t.add_argument("--out", default="data/tiny.pt")
    t.add_argument("--steps", type=int, default=200)
    t.add_argument("--batch", type=int, default=16)
    t.add_argument("--device", default="cpu", choices=["cpu", "cuda", "mps"])
    s = sub.add_parser("sample")
    s.add_argument("--checkpoint", required=True)
    s.add_argument("--prompt", default="Technology")
    s.add_argument("--bytes", type=int, default=120)
    s.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    if args.command == "train":
        train(args)
    else:
        torch.manual_seed(args.seed)
        torch.set_num_threads(4)
        checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
        model = TinyTransformer(ModelConfig(**checkpoint["config"]))
        model.load_state_dict(checkpoint["state_dict"])
        prefix = torch.tensor([list(args.prompt.encode("utf-8")) or [32]])
        generated = model.generate(prefix, min(max(args.bytes, 1), 2000))
        print(bytes(generated[0].tolist()).decode("utf-8", errors="replace"))


if __name__ == "__main__":
    main()

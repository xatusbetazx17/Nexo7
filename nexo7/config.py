from dataclasses import dataclass, fields
from pathlib import Path
import tomllib
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Config:
    provider: str = "demo"
    model: str = ""
    fast_model: str = ""
    deep_model: str = ""
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_context_tokens: int = 8192
    local_container_id: str = ""
    local_ram_limit_bytes: int = 12_000_000_000
    local_threads: int = 2
    local_backend: str = "cpu"
    response_language: str = "auto"
    database: str = "data/nexo.sqlite3"
    max_output_tokens: int = 800
    max_total_output_tokens: int = 2400
    max_model_calls: int = 3
    max_tool_calls: int = 4
    max_context_chars: int = 22000
    history_messages: int = 8
    cache_seconds: int = 600
    timeout_seconds: int = 90
    research_network: bool = True
    persist_history: bool = True
    input_price_per_million: float = -1.0
    cached_input_price_per_million: float = -1.0
    output_price_per_million: float = -1.0

    def __post_init__(self):
        if self.provider not in {"demo", "openai", "ollama"}:
            raise ValueError("provider must be demo, openai or ollama")
        if self.provider != "demo" and not self.model.strip():
            raise ValueError("Set a real model identifier")
        import re
        if type(self.local_ram_limit_bytes) is not int or not 1_000_000_000 <= self.local_ram_limit_bytes <= 16_000_000_000:
            raise ValueError("Local RAM limit must be between 1 and 16 decimal GB")
        if type(self.local_threads) is not int or not 1 <= self.local_threads <= 32:
            raise ValueError("local_threads must be between 1 and 32")
        if self.local_backend not in {"cpu", "nvidia", "amd"}:
            raise ValueError("Unknown local backend")
        if self.local_container_id and not re.fullmatch(r"[a-f0-9]{64}", self.local_container_id):
            raise ValueError("Invalid local container identifier")
        if self.response_language != "auto" and not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z]{2,8})?", self.response_language):
            raise ValueError("response_language must be auto or a language code such as en or es")
        if self.provider == "ollama":
            from .hardware import PROFILES
            if self.model not in {p.model for p in PROFILES}:
                raise ValueError("Bounded local mode only accepts the supported Qwen model profiles")
            if any(value and value != self.model for value in (self.fast_model, self.deep_model)):
                raise ValueError("All modes share one local model to control memory use")
            if self.ollama_context_tokens > 8192 or self.max_output_tokens > 1024:
                raise ValueError("Bounded mode supports context up to 8192 and output up to 1024 tokens")
        limits = {"max_output_tokens": (64, 8192), "max_total_output_tokens": (64, 24576),
                  "max_model_calls": (1, 5), "max_tool_calls": (0, 8),
                  "max_context_chars": (6000, 100000), "history_messages": (0, 20),
                  "cache_seconds": (0, 86400), "timeout_seconds": (1, 180), "ollama_context_tokens": (1024, 131072)}
        for name, (low, high) in limits.items():
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{name} must be between {low} and {high}")
        if self.max_total_output_tokens < self.max_output_tokens:
            raise ValueError("max_total_output_tokens must cover at least one response")
        for name in ("research_network", "persist_history"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be a boolean")
        for name in ("input_price_per_million", "cached_input_price_per_million", "output_price_per_million"):
            import math
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or value < -1:
                raise ValueError(f"Invalid rate: {name}")
        u = urlsplit(self.ollama_url)
        if (u.scheme != "http" or u.hostname not in {"localhost", "127.0.0.1", "::1"}
                or u.username or u.password or u.path not in {"", "/"} or u.query or u.fragment):
            raise ValueError("Ollama must use a loopback HTTP address without credentials")

    def select_model(self, mode):
        if mode == "eco":
            return self.fast_model or self.model
        if mode in {"deep", "research"}:
            return self.deep_model or self.model
        return self.model


def load_config(path=None):
    path = Path(path) if path else Path("config.toml")
    raw = tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    extra = set(raw) - {f.name for f in fields(Config)}
    if extra:
        raise ValueError("Unknown options: " + ", ".join(sorted(extra)))
    raw["database"] = str((path.resolve().parent / raw.get("database", "data/nexo.sqlite3")).resolve())
    return Config(**raw)

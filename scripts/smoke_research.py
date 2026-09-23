"""Offline real optimizer/save/reload/merge smoke on a tiny random Qwen3.5.

No pretrained intelligence or accuracy improvement is implied by this fixture.
"""
import json
import gc
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import torch
    from tokenizers import Tokenizer
    from tokenizers.models import WordLevel
    from tokenizers.pre_tokenizers import Whitespace
    from transformers import (PreTrainedTokenizerFast, Qwen3_5Config, Qwen3_5TextConfig,
                              Qwen3_5VisionConfig, Qwen3_5ForConditionalGeneration)
    from research.data import prepare, digest
    torch.manual_seed(42)
    torch.set_num_threads(2)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        model_dir = root / "base"
        tokens = ["[UNK]", "[EOS]", "[USER]", "[ASSISTANT]", "5", "gatos", "12", "abajo", "hello", "3"]
        tokenizer = Tokenizer(WordLevel(dict(zip(tokens, range(len(tokens)))), unk_token="[UNK]"))
        tokenizer.pre_tokenizer = Whitespace()
        tokenizer = PreTrainedTokenizerFast(tokenizer_object=tokenizer, unk_token="[UNK]", eos_token="[EOS]", pad_token="[EOS]")
        tokenizer.chat_template = "{% for m in messages %}{{ '[USER] ' if m['role'] == 'user' else '[ASSISTANT] ' }}{{ m['content'] }}{{ ' [EOS] ' }}{% endfor %}{% if add_generation_prompt %}{{ '[ASSISTANT] ' }}{% endif %}"
        config = Qwen3_5Config(text_config=Qwen3_5TextConfig(vocab_size=32, hidden_size=32,
            intermediate_size=64, num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=2,
            head_dim=8, linear_key_head_dim=8, linear_value_head_dim=8, linear_num_key_heads=2,
            linear_num_value_heads=4, layer_types=["linear_attention", "full_attention"], eos_token_id=1,
            rope_parameters={"rope_type": "default", "rope_theta": 10000, "partial_rotary_factor": 1,
                             "mrope_section": [1, 1, 2]}),
            vision_config=Qwen3_5VisionConfig(depth=1, hidden_size=32, intermediate_size=64,
                                            num_heads=4, out_hidden_size=32))
        model = Qwen3_5ForConditionalGeneration(config)
        model.save_pretrained(model_dir, safe_serialization=True)
        tokenizer.save_pretrained(model_dir)
        base_hash = digest(model_dir / "model.safetensors")
        prepare(ROOT / "tests/research_fixtures/reviewed.jsonl", root / "data")

        def run(command, *options):
            subprocess.run([sys.executable, "-m", "research", command, "--model", str(model_dir),
                            "--threads", "2", *map(str, options)], cwd=ROOT, check=True)

        run("train", "--dataset", root / "data", "--output", root / "adapter", "--steps", 4,
            "--rank", 2, "--max-length", 128)
        self_report = json.loads((root / "adapter/run.json").read_text())
        from safetensors.torch import load_file
        weights = load_file(root / "adapter/adapter_model.safetensors")
        assert any("lora_B" in name and torch.count_nonzero(value) for name, value in weights.items())
        assert digest(model_dir / "model.safetensors") == base_hash
        for name, extra in (("baseline", []), ("candidate", ["--adapter", root / "adapter"])):
            run("evaluate", "--dataset", root / "data", "--output", root / f"{name}.json",
                "--split", "test", "--max-length", 128, "--max-new-tokens", 4, *extra)
        subprocess.run([sys.executable, "-m", "research", "compare", str(root / "baseline.json"),
                        str(root / "candidate.json"), str(root / "comparison.json")], cwd=ROOT, check=True)
        run("merge", "--adapter", root / "adapter", "--output", root / "merged")
        from peft import PeftModel
        base = Qwen3_5ForConditionalGeneration.from_pretrained(model_dir)
        adapted = PeftModel.from_pretrained(base, root / "adapter").eval()
        merged = Qwen3_5ForConditionalGeneration.from_pretrained(root / "merged").eval()
        with torch.no_grad():
            ids = torch.tensor([[2, 4, 3]])
            torch.testing.assert_close(adapted(input_ids=ids).logits, merged(input_ids=ids).logits, atol=1e-5, rtol=1e-4)
        print(json.dumps({"status": "passed", "model": "tiny random Qwen3.5 fixture", "weights_updated": True,
            "base_unchanged": True, "merged_logits_match": True, "results": self_report["results"],
            "capability_improvement_demonstrated": False}, indent=2))
        # Windows cannot unlink safetensors while their mapped tensors remain live.
        del weights, adapted, merged, base, model
        gc.collect()


if __name__ == "__main__":
    main()

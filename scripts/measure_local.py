"""Measure a running bounded model. Requires python -m nexo7 local in another terminal."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nexo7.config import load_config
from nexo7.local_runtime import runtime_metrics, verify_runtime
from evaluate import evaluate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.local.toml")
    parser.add_argument("--cases", default="evals/multilingual.jsonl")
    parser.add_argument("--output", default="reports/local-measurement.json")
    args = parser.parse_args()
    config = load_config(args.config)
    if config.provider != "ollama":
        raise ValueError("This measurement requires the bounded local provider")
    verify_runtime(config)
    before = runtime_metrics(config)
    cases = [json.loads(line) for line in Path(args.cases).read_text(encoding="utf-8").splitlines() if line.strip()]
    result = evaluate(args.config, cases, True)
    verify_runtime(config)
    after = runtime_metrics(config)
    report = {"timestamp": datetime.now(timezone.utc).isoformat(), "model": config.model,
              "guard_verified_before_and_after": True, "before": before, "after": after,
              "evaluation": result, "human_language_review_required": True,
              "scope": "RAM charged to this model container only. Peak is cumulative since container creation. Regex matches do not validate fluency or general intelligence."}
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(path), "passed": result["passed"], "total": result["total"], "peak_bytes": after["ram_peak_bytes"]}))


if __name__ == "__main__":
    main()

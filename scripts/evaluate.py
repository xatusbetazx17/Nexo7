"""Run identical fixed tasks on one or two configurations. No hidden API model defaults."""
import argparse
import json
from pathlib import Path
import re
import statistics
import sys
import tempfile
from dataclasses import replace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nexo7.config import load_config
from nexo7.engine import Engine
from nexo7.store import Store


def evaluate(config_path, cases, optimized):
    config = replace(load_config(config_path), persist_history=False, cache_seconds=0)
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp)/"evaluation.sqlite3")
        store.add_document("Evaluation fixture", "The test router name is Faro. The test network identifier is NEXO-LAB-42.")
        engine = Engine(config, store)
        results = []
        try:
            for case in cases:
                try:
                    result = engine.chat(case["prompt"], session="evaluation", mode=case.get("mode", "balanced"), optimized=optimized, language=case.get("language"))
                    passed = result["status"] == "completed" and bool(re.search(case["expected_regex"], result["answer"], re.I))
                    results.append({"id": case["id"], "passed": passed, "answer": result["answer"], "status": result["status"], "stats": result["stats"]})
                except Exception as exc:
                    results.append({"id": case["id"], "passed": False, "error": str(exc)})
        finally:
            store.close()
    valid = [r for r in results if "stats" in r]
    return {"provider": config.provider, "model": config.model or "none", "optimized": optimized,
            "passed": sum(r["passed"] for r in results), "total": len(results),
            "mean_ms": statistics.mean(r["stats"]["elapsed_ms"] for r in valid) if valid else None,
            "reported_tokens": sum(r["stats"]["input_tokens"]+r["stats"]["output_tokens"] for r in valid),
            "results": results}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", default="config.example.toml")
    p.add_argument("--baseline", help="Optional second configuration; its implicit arithmetic shortcut is disabled")
    p.add_argument("--cases", default="evals/cases.jsonl")
    p.add_argument("--output", default="reports/evaluation.json")
    args = p.parse_args()
    cases = [json.loads(line) for line in Path(args.cases).read_text(encoding="utf-8").splitlines() if line.strip()]
    report = {"scope": "Fixed engineering smoke tasks, not a general-intelligence or clinical benchmark. Regex checks require human review.",
              "candidate": evaluate(args.config, cases, True)}
    if args.baseline:
        report["baseline"] = evaluate(args.baseline, cases, False)
        report["comparison_note"] = "Same tasks and memory. No superiority claim; compare only these measurements. API runs may incur charges."
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"file": str(path), "passed": report["candidate"]["passed"], "total": len(cases)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

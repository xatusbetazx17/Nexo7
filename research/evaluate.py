"""Conservative comparison of matching, independently executed evaluation runs."""
import json
import math
from pathlib import Path
from .data import write_json


def compare(baseline, candidate, output, memory_gb=3.0, max_slowdown=1.1):
    if not math.isfinite(memory_gb) or not math.isfinite(max_slowdown) or memory_gb <= 0 or max_slowdown < 1:
        raise ValueError("Invalid comparison budgets")
    b, c = [json.loads(Path(p).read_text(encoding="utf-8")) for p in (baseline, candidate)]
    for key in ("schema", "base", "dataset", "split", "settings", "environment", "versions"):
        if b[key] != c[key]:
            raise ValueError(f"Incomparable runs: {key}")
    if b["schema"] != "nexo-evaluation-v1" or b["adapter"] is not None or not c["adapter"]:
        raise ValueError("Compare an unmodified baseline with a trained adapter")
    if not b["results"] or [r["id"] for r in b["results"]] != [r["id"] for r in c["results"]]:
        raise ValueError("Different or empty evaluation cases")
    if len({r["id"] for r in b["results"]}) != len(b["results"]):
        raise ValueError("Duplicate evaluation IDs")
    if [r["language"] for r in b["results"]] != [r["language"] for r in c["results"]]:
        raise ValueError("Evaluation language labels changed")
    scores, latency = [], []
    for report in (b, c):
        for r in report["results"]:
            if type(r["correct"]) is not bool or not math.isfinite(r["seconds"]) or r["seconds"] <= 0:
                raise ValueError("Invalid measurement")
        for key in ("peak_rss_bytes", "peak_cuda_allocated_bytes"):
            if not isinstance(report[key], int) or report[key] < 0:
                raise ValueError("Invalid memory measurement")
        if report["peak_rss_bytes"] == 0:
            raise ValueError("Missing process memory measurement")
        scores.append(sum(r["correct"] for r in report["results"]) / len(report["results"]))
        latency.append(sum(r["seconds"] for r in report["results"]) / len(report["results"]))
    language_scores = {}
    for language in {r["language"] for r in b["results"]}:
        values = []
        for report in (b, c):
            rows = [r for r in report["results"] if r["language"] == language]
            if not rows:
                raise ValueError("Language mismatch")
            values.append(sum(r["correct"] for r in rows) / len(rows))
        language_scores[language] = values
    checks = {"held_out_test": b["split"] == "test", "accuracy_improved": scores[1] > scores[0],
        "no_language_regression": all(v[1] >= v[0] for v in language_scores.values()),
        "latency_budget": latency[1] <= latency[0] * max_slowdown,
        "process_ram_budget": c["peak_rss_bytes"] <= memory_gb * 1e9,
        "cuda_allocations_budget": c["peak_cuda_allocated_bytes"] <= memory_gb * 1e9}
    write_json(output, {"checks": checks, "baseline_accuracy": scores[0], "candidate_accuracy": scores[1],
        "language_scores": language_scores, "candidate_for_human_review": all(checks.values()),
        "automatic_release": False,
        "limitations": "Small exact-match tests do not establish general intelligence or statistical significance. "
        "Repeat on representative tasks and the target PC; benchmark the final quantized artifact separately."})

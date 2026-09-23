"""Reviewed JSONL datasets, explicit group splits and tamper-evident manifests."""
import hashlib
import json
from pathlib import Path
import unicodedata

SPLITS = ("train", "validation", "test")


def normalized(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def read_rows(path):
    path = Path(path)
    if path.stat().st_size > 50_000_000:
        raise ValueError("Dataset exceeds 50 MB; curate a bounded experiment")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not 1 <= len(rows) <= 10000:
        raise ValueError("Expected 1–10000 records")
    return rows


def validate(rows, require_all=True):
    ids, prompts, groups = set(), {}, {}
    counts = dict.fromkeys(SPLITS, 0)
    for row in rows:
        for key in ("id", "group", "split", "prompt", "answer", "language", "source", "license"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise ValueError(f"Missing text field: {key}")
        if row["split"] not in SPLITS:
            raise ValueError("Invalid split")
        if row.get("approved") is not True or row.get("training_allowed") is not True:
            raise ValueError("Every example needs explicit review and training permission")
        if len(row["prompt"]) > 8000 or len(row["answer"]) > 16000:
            raise ValueError("Example too long")
        if row["id"] in ids:
            raise ValueError("Duplicate example ID")
        ids.add(row["id"])
        prompt = normalized(row["prompt"])
        if prompt in prompts:
            raise ValueError("Duplicate normalized prompt; deduplicate before splitting")
        prompts[prompt] = row["split"]
        group = normalized(row["group"])
        if group in groups and groups[group] != row["split"]:
            raise ValueError("Related examples cross split boundaries")
        groups[group] = row["split"]
        counts[row["split"]] += 1
    if require_all and not all(counts.values()):
        raise ValueError("Provide nonempty train, validation and test splits")
    return counts


def prepare(source, output):
    rows = read_rows(source)
    counts = validate(rows)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for split in SPLITS:
        path = output / f"{split}.jsonl"
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows if r["split"] == split), encoding="utf-8")
        hashes[split] = digest(path)
    write_json(output / "manifest.json", {"schema": "nexo-research-v1", "counts": counts, "sha256": hashes,
        "warning": "Group labels require human review; automated checks cannot detect semantic paraphrases."})


def load_dataset(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != "nexo-research-v1":
        raise ValueError("Unsupported dataset manifest")
    splits = {}
    for split in SPLITS:
        path = directory / f"{split}.jsonl"
        if digest(path) != manifest["sha256"][split]:
            raise ValueError("Dataset changed since preparation")
        splits[split] = read_rows(path)
        if any(r["split"] != split for r in splits[split]):
            raise ValueError("Record in incorrect split")
    counts = validate(sum(splits.values(), []))
    if counts != manifest["counts"]:
        raise ValueError("Incorrect manifest counts")
    return splits, digest(directory / "manifest.json")

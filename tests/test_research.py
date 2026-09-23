import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from research.data import prepare, load_dataset, validate, write_json
from research.distill import generate
from research.evaluate import compare


def rows():
    return [dict(id=str(i), group=str(i), split=s, prompt=f"Question {i}", answer=str(i),
                 language="en", source="original fixture", license="CC0-1.0", approved=True,
                 training_allowed=True) for i, s in enumerate(("train", "validation", "test"))]


class ResearchTests(unittest.TestCase):
    def test_permissions_and_group_leakage(self):
        for field in ("approved", "training_allowed"):
            data = rows(); data[0][field] = False
            with self.assertRaises(ValueError): validate(data)
        data = rows(); data[1]["group"] = data[0]["group"]
        with self.assertRaises(ValueError): validate(data)
        data = rows(); data[1]["prompt"] = " QUESTION   0 "
        with self.assertRaises(ValueError): validate(data)

    def test_manifest_roundtrip_and_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / "input.jsonl"
            source.write_text("\n".join(json.dumps(r) for r in rows()), encoding="utf-8")
            prepare(source, root / "data")
            splits, fingerprint = load_dataset(root / "data")
            self.assertEqual(len(fingerprint), 64)
            self.assertEqual(splits["test"][0]["id"], "2")
            with (root / "data/train.jsonl").open("a") as target: target.write("\n")
            with self.assertRaises(ValueError): load_dataset(root / "data")

    def test_teacher_never_sees_validation_or_test_and_is_unapproved(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "teacher.jsonl"
            with patch("research.distill.load_dataset", return_value=({"train": rows()[:1]}, "hash")), \
                 patch("research.distill.build_opener") as opener:
                opener.return_value.open.return_value.__enter__.return_value.read.return_value = json.dumps(
                    {"choices": [{"message": {"content": "teacher answer"}}]}).encode()
                generate("unused", target, "http://127.0.0.1:8080/v1/chat/completions", "teacher", "revision", "CC0")
                request = opener.return_value.open.call_args.args[0]
                sent = json.loads(request.data)
                self.assertEqual(sent["messages"], [{"role": "user", "content": "Question 0"}])
                result = json.loads(target.read_text())
                self.assertFalse(result["approved"])
                self.assertFalse(result["training_allowed"])
                with self.assertRaises(ValueError): validate([result], require_all=False)

    def test_teacher_blocks_remote_and_redirect_style_urls(self):
        for url in ("https://example.com/v1/chat/completions", "http://localhost/v1/chat/completions",
                    "http://127.0.0.1/v1/chat/completions?redirect=x"):
            with self.assertRaises(ValueError): generate("unused", "unused", url, "t", "r", "CC0")

    def test_comparison_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = dict(schema="nexo-evaluation-v1", base="b", dataset="d", split="test", settings={},
                        environment={}, versions={}, adapter=None, peak_rss_bytes=100, peak_cuda_allocated_bytes=0,
                        results=[dict(id="1", language="en", correct=False, seconds=1)])
            candidate = dict(base, adapter="a", results=[dict(id="1", language="en", correct=True, seconds=1)])
            write_json(root / "b", base); write_json(root / "c", candidate)
            compare(root / "b", root / "c", root / "out")
            self.assertTrue(json.loads((root / "out").read_text())["candidate_for_human_review"])
            candidate["peak_rss_bytes"] = 4_000_000_000
            write_json(root / "c", candidate)
            compare(root / "b", root / "c", root / "out")
            self.assertFalse(json.loads((root / "out").read_text())["candidate_for_human_review"])
            candidate["dataset"] = "different"
            write_json(root / "c", candidate)
            with self.assertRaises(ValueError): compare(root / "b", root / "c", root / "out")

    def test_answer_only_labels_and_no_silent_truncation(self):
        from research.training import encode
        class Tokenizer:
            def apply_chat_template(self, messages, **kwargs):
                return [1, 2] if len(messages) == 1 else [1, 2, 3, 4]
        self.assertEqual(encode(Tokenizer(), rows()[0], 10), ([1, 2, 3, 4], [-100, -100, 3, 4]))
        with self.assertRaises(ValueError): encode(Tokenizer(), rows()[0], 3)


if __name__ == "__main__":
    unittest.main()

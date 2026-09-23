"""Sequence distillation: local teacher responses awaiting human review.

No cloud requests, credentials, conversation export or automatic approval.
"""
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from .data import load_dataset


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def generate(dataset, output, endpoint, teacher, revision, license_name, limit=20):
    parsed = urlsplit(endpoint)
    if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "::1")
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path.rstrip("/") != "/v1/chat/completions"):
        raise ValueError("Use a numeric loopback HTTP /v1/chat/completions endpoint")
    if not all(x.strip() for x in (teacher, revision, license_name)) or not 1 <= limit <= 1000:
        raise ValueError("Teacher identity, revision, permitted output license and bounded limit required")
    splits, manifest = load_dataset(dataset)
    opener = build_opener(ProxyHandler({}), NoRedirect())
    # Exclusive creation prevents silently overwriting reviewed data. Partial files stay unapproved.
    with Path(output).open("x", encoding="utf-8") as target:
        for row in splits["train"][:limit]:
            payload = {"model": teacher, "messages": [{"role": "user", "content": row["prompt"]}],
                       "temperature": 0, "max_tokens": 512, "stream": False}
            request = Request(endpoint, json.dumps(payload).encode(), {"Content-Type": "application/json"})
            with opener.open(request, timeout=120) as response:
                body = response.read(1_000_001)
            if len(body) > 1_000_000:
                raise ValueError("Teacher response exceeds limit")
            answer = json.loads(body)["choices"][0]["message"]["content"]
            if not isinstance(answer, str) or not answer.strip() or len(answer) > 16000:
                raise ValueError("Invalid teacher response")
            candidate = dict(row, answer=answer, approved=False, training_allowed=False,
                             source=f"teacher:{teacher}@{revision}; prompt source: {row['source']}",
                             license=license_name, teacher_dataset=manifest)
            target.write(json.dumps(candidate, ensure_ascii=False) + "\n")
            target.flush()

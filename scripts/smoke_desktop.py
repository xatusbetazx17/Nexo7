"""Exercise the packaged executable through its authenticated local HTTP interface."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit, parse_qs
from urllib.request import Request, urlopen


def main():
    binary = str(Path(sys.argv[1]).resolve())
    with tempfile.TemporaryDirectory(prefix="nexo-desktop-") as tmp:
        process = subprocess.Popen([binary, "--no-open", "--data-dir", tmp],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 45
            access = Path(tmp) / "access.json"
            while not access.exists():
                if process.poll() is not None:
                    raise AssertionError("Packaged application exited during startup: " + process.stderr.read().decode(errors="replace")[-1000:])
                if time.monotonic() > deadline:
                    raise AssertionError("Desktop startup timed out")
                time.sleep(0.1)
            url = json.loads(access.read_text())["url"]
            parsed = urlsplit(url)
            base = f"http://127.0.0.1:{parsed.port}"
            token = parse_qs(parsed.fragment)["token"][0]
            def request(path, body=None, authenticated=True):
                headers = {"Content-Type": "application/json"}
                if authenticated:
                    headers["X-Nexo-Key"] = token
                data = json.dumps(body).encode() if body is not None else None
                with urlopen(Request(base + path, data=data, headers=headers), timeout=20) as response:
                    return response.read()
            html = request("/").decode()
            assert 'lang="en"' in html and 'id="setup-view"' in html
            assert b"download" in request("/app.js").lower()
            try:
                request("/api/setup", authenticated=False)
                raise AssertionError("Setup endpoint accepted an unauthenticated request")
            except HTTPError as exc:
                assert exc.code == 401
            status = json.loads(request("/api/status"))
            assert status["desktop"] and status["provider"] == "demo"
            result = json.loads(request("/api/chat", {"message": "/calc 24.5 * 40", "language": "en"}))
            assert result["answer"] == "980.0" and result["stats"]["model_calls"] == 0
            math_result = json.loads(request("/api/math", {"operation":"quadratic","a":"1","b":"-5","c":"6"}))
            assert sorted(math_result["result"]["roots"]) == ["2", "3"]
            try:
                request("/api/contributions/prepare", {})
                raise AssertionError("Contribution accepted without consent")
            except HTTPError as exc:
                assert exc.code == 400
            exported = json.loads(request('/api/export/document', {'title':'Local report','content':'# Summary\nWorks offline.'}))
            import base64
            assert base64.b64decode(exported['data']).startswith(b'PK')
            task = json.loads(request('/api/tasks', {'goal':'Write a guide','steps':[{'name':'guide.md','instruction':'Write a guide'}]}))
            assert task['state']=='ready'
            assert any(j['id']==task['id'] for j in json.loads(request('/api/tasks'))['tasks'])
            request('/api/tasks/'+task['id']+'/cancel', {})
            docs = json.loads(request("/api/documents"))["documents"]
            assert any(d["title"] == "Nexo starter guide" for d in docs)
            preferences = json.loads(request("/api/preferences", {"performance": "fast"}))
            assert preferences["performance"] == "fast"
            artifact = json.loads(request("/api/artifacts", {"name": "smoke.md", "content": "Local file"}))
            assert json.loads(request("/api/artifacts/" + artifact["id"]))["content"] == "Local file"
            imported = json.loads(request("/api/import", {"name":"sample.txt", "data":"TG9jYWwgaW1wb3J0"}))
            assert imported["content"] == "Local import"
            pack = json.loads(request("/api/learning/community"))
            assert pack["format"] == "nexo-learning-v1"
            preview = json.loads(request("/api/learning/preview", {"pack":pack}))
            assert len(preview["entries"]) > 0
            imported = json.loads(request("/api/learning/import", {"pack":pack,"consent":True}))
            assert imported["added"] == len(pack["entries"])
            learned = json.loads(request("/api/learning"))["entries"]
            exported = json.loads(request("/api/learning/export", {"ids":[learned[0]["id"]]}))
            assert len(exported["entries"]) == 1
            state = json.loads(request("/api/setup"))
            assert state["phase"] == "idle" and not state["ready"]
            request("/api/shutdown", {})
            process.wait(timeout=25)
            assert process.returncode == 0
            print("Packaged executable passed: startup, English setup assets, authentication, calculator, bundled knowledge, preferences, workspace and clean shutdown.")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            process.stderr.close()


if __name__ == "__main__":
    main()

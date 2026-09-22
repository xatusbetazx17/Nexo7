"""Small bounded HTTP transport. No redirect following or implicit retries."""
import json
import urllib.error
import urllib.request


class TransportError(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url, *, payload=None, headers=None, timeout=30, max_bytes=2_000_000):
    hdr = {"User-Agent": "Nexo7/0.1 (personal research assistant)", **(headers or {})}
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        hdr["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=hdr)
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise TransportError("Remote response exceeds the size limit")
        return body
    except urllib.error.HTTPError as exc:
        raise TransportError(f"Remote service returned HTTP {exc.code}; check access, quota and configuration") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise TransportError("The remote service could not be reached within the time limit") from None


def fetch_json(url, **kwargs):
    try:
        result = json.loads(fetch(url, **kwargs))
    except (ValueError, UnicodeError):
        raise TransportError("The service did not return valid JSON") from None
    if not isinstance(result, dict):
        raise TransportError("Unexpected JSON response")
    return result

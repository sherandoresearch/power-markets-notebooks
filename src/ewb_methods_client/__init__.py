"""Transport only. No private methods, numerical fallback or dependency."""

import json
import math
from pathlib import Path
from urllib.parse import urlsplit
import httpx


class MethodsError(RuntimeError):
    pass


class MethodsClient:
    def __init__(self, base_url, api_key, *, allow_loopback_http=False, read_timeout=180.0):
        if (isinstance(read_timeout, bool) or not isinstance(read_timeout, (int, float))
                or not math.isfinite(read_timeout) or read_timeout <= 0):
            raise ValueError("read_timeout must be finite and positive")
        url = urlsplit(base_url)
        if url.username or url.password or url.query or url.fragment:
            raise ValueError("Use a plain service origin")
        if url.scheme != "https" and not (
            allow_loopback_http
            and url.scheme == "http"
            and url.hostname in {"127.0.0.1", "localhost", "::1"}
        ):
            raise ValueError("HTTPS is required")
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"X-API-Key": api_key},
            follow_redirects=False,
            verify=True,
            timeout=httpx.Timeout(75.0, read=read_timeout),
            trust_env=False,
        )

    def __repr__(self):
        return "MethodsClient(credentials=<redacted>)"

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _request(self, method, path, **kwargs):
        try:
            response = self._http.request(method, path, **kwargs)
        except httpx.HTTPError:
            raise MethodsError("Methods transport failed") from None
        if response.status_code != 200:
            raise MethodsError(
                "Methods request refused (HTTP " + str(response.status_code) + ")"
            )
        try:
            return response.json()
        except ValueError:
            raise MethodsError("Invalid service response") from None

    def catalog(self):
        return self._request("GET", "/v1/methods")

    def describe(self, method_id, version):
        self._validate_version(method_id, version)
        return self._request("GET", f"/v1/methods/{method_id}/versions/{version}")

    @staticmethod
    def _validate_version(method_id, version):
        import re

        if not re.fullmatch("[a-z][a-z0-9_]*", method_id) or not re.fullmatch(
            r"\d+\.\d+\.\d+", version
        ):
            raise ValueError("Explicit method and version required")

    def execute(self, method_id, version, request):
        self._validate_version(method_id, version)
        return self._request(
            "POST", f"/v1/methods/{method_id}/versions/{version}/execute", json=request
        )

    @staticmethod
    def save_result(path, result):
        Path(path).write_text(json.dumps(result, allow_nan=False, indent=2) + "\n")

    @staticmethod
    def read_result(path):
        """Explicit offline access; makes no remote request."""
        return json.loads(Path(path).read_text())

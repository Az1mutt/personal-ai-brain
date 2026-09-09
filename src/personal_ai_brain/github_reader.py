from __future__ import annotations

import base64
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class GitHubReadError(RuntimeError):
    """Raised when a GitHub file cannot be read."""


class GitHubReader:
    """Minimal read-only GitHub Contents API client.

    A token is optional for public repositories and required for private ones.
    The client intentionally exposes no write methods.
    """

    def __init__(
        self,
        token: str | None = None,
        api_base: str = "https://api.github.com",
        timeout_seconds: int = 20,
    ) -> None:
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.api_base = api_base.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def get_text(self, repository: str, path: str, ref: str = "main") -> str:
        safe_path = quote(path, safe="/")
        safe_ref = quote(ref, safe="")
        url = f"{self.api_base}/repos/{repository}/contents/{safe_path}?ref={safe_ref}"

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "personal-ai-brain-core-agent",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        request = Request(url, headers=headers)

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.load(response)
        except HTTPError as exc:
            raise GitHubReadError(
                f"GitHub returned HTTP {exc.code} for {repository}:{path}@{ref}"
            ) from exc
        except URLError as exc:
            raise GitHubReadError(
                f"Could not reach GitHub for {repository}:{path}@{ref}: {exc.reason}"
            ) from exc

        if payload.get("type") != "file":
            raise GitHubReadError(
                f"Expected file at {repository}:{path}@{ref}, got {payload.get('type')!r}"
            )

        if payload.get("encoding") != "base64":
            raise GitHubReadError(
                f"Unsupported GitHub content encoding: {payload.get('encoding')!r}"
            )

        try:
            return base64.b64decode(payload["content"]).decode("utf-8")
        except (KeyError, ValueError, UnicodeDecodeError) as exc:
            raise GitHubReadError(
                f"Could not decode {repository}:{path}@{ref}"
            ) from exc

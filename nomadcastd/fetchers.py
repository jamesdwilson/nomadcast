from __future__ import annotations

"""Fetcher abstraction for Reticulum resources.

README requires a fetch_bytes(destination_hash, resource_path) interface and
allows a mock implementation for tests while real RNS integration is pending.
"""

import importlib.util
from dataclasses import dataclass


class Fetcher:
    def fetch_bytes(self, destination_hash: str, resource_path: str) -> bytes:
        raise NotImplementedError


@dataclass
class MockFetcher(Fetcher):
    rss_payload: bytes = b""
    media_payload: bytes = b""

    def fetch_bytes(self, destination_hash: str, resource_path: str) -> bytes:
        if resource_path == "rss":
            return self.rss_payload
        return self.media_payload


class ReticulumFetcher(Fetcher):
    """Placeholder for Reticulum integration.

    TODO: Implement Reticulum (RNS) request handling for resource retrieval.
    The interface should resolve the destination hash to an RNS Identity and
    request the provided resource path (rss or media/<filename>).
    """

    def __init__(self, config_dir: str | None = None) -> None:
        if importlib.util.find_spec("RNS") is None:
            raise RuntimeError(
                "Reticulum (RNS) is not installed. Install it before starting nomadcastd."
            )
        self.config_dir = config_dir

    def fetch_bytes(self, destination_hash: str, resource_path: str) -> bytes:
        raise NotImplementedError("Reticulum fetcher not implemented yet.")

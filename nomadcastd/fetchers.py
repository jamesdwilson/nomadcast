from __future__ import annotations

"""Fetcher abstraction for Reticulum resources.

README requires a fetch_bytes(destination_hash, resource_path) interface and
allows a mock implementation for tests while real RNS integration is pending.
"""

import importlib.util
import threading
import time
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
        import RNS  # noqa: N811

        self._rns = RNS
        self._ensure_reticulum(config_dir)
        self.config_dir = config_dir

    def fetch_bytes(self, destination_hash: str, resource_path: str) -> bytes:
        destination_identity = self._resolve_identity(destination_hash)
        destination = self._rns.Destination(
            destination_identity,
            self._rns.Destination.OUT,
            self._rns.Destination.SINGLE,
            "nomadcast",
        )
        link = self._rns.Link(destination)
        try:
            self._await_link(link, resource_path)
            receipt = link.request(resource_path, timeout=self._request_timeout_seconds)
            if not receipt:
                raise RuntimeError(f"Reticulum request for {resource_path} was rejected")
            payload = self._await_request(receipt, resource_path)
            return payload
        finally:
            link.teardown()

    _reticulum_lock = threading.Lock()
    _reticulum_instance = None
    _link_timeout_seconds = 30.0
    _request_timeout_seconds = 120.0

    def _ensure_reticulum(self, config_dir: str | None) -> None:
        cls = type(self)
        with cls._reticulum_lock:
            if cls._reticulum_instance is None:
                cls._reticulum_instance = self._rns.Reticulum(config_dir)

    def _resolve_identity(self, destination_hash: str):
        try:
            destination_bytes = bytes.fromhex(destination_hash)
        except ValueError as exc:
            raise ValueError(f"Destination hash is not valid hex: {destination_hash}") from exc
        identity = self._rns.Identity.recall(destination_bytes, from_identity_hash=True)
        if identity is None:
            identity = self._rns.Identity.recall(destination_bytes)
        if identity is None:
            raise RuntimeError(f"Reticulum identity not found for {destination_hash}")
        return identity

    def _await_link(self, link, resource_path: str) -> None:
        deadline = time.monotonic() + self._link_timeout_seconds
        while time.monotonic() < deadline:
            if link.status == self._rns.Link.ACTIVE:
                return
            if link.status == self._rns.Link.CLOSED:
                raise RuntimeError(f"Reticulum link closed while requesting {resource_path}")
            time.sleep(0.1)
        raise TimeoutError(f"Timed out establishing Reticulum link for {resource_path}")

    def _await_request(self, receipt, resource_path: str) -> bytes:
        deadline = time.monotonic() + self._request_timeout_seconds
        while time.monotonic() < deadline:
            status = receipt.get_status()
            if status == self._rns.RequestReceipt.READY:
                if receipt.response is None:
                    raise RuntimeError(f"Reticulum response missing for {resource_path}")
                return bytes(receipt.response)
            if status == self._rns.RequestReceipt.FAILED:
                raise RuntimeError(f"Reticulum request failed for {resource_path}")
            time.sleep(0.1)
        raise TimeoutError(f"Timed out waiting for Reticulum response for {resource_path}")

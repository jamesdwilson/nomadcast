from __future__ import annotations

"""Fetcher abstraction for Reticulum resources.

README requires a fetch_bytes(destination_hash, resource_path) interface and
allows a mock implementation for tests while real RNS integration is pending.
"""

import importlib
import importlib.util
import logging
import threading
import time
from dataclasses import dataclass
from types import ModuleType
from typing import TYPE_CHECKING, Callable, Protocol, TypeAlias


class IdentityProtocol(Protocol):
    @staticmethod
    def recall(destination_bytes: bytes, from_identity_hash: bool = False) -> "IdentityProtocol | None":
        ...


class RequestReceiptProtocol(Protocol):
    READY: int
    FAILED: int
    SENT: int
    DELIVERED: int
    RECEIVING: int
    response: bytes | None

    def get_status(self) -> int:
        ...


class LinkProtocol(Protocol):
    ACTIVE: int
    CLOSED: int
    status: int

    def request(
        self,
        path: str,
        data: bytes | None = None,
        response_callback: Callable[[RequestReceiptProtocol], None] | None = None,
        failed_callback: Callable[[RequestReceiptProtocol], None] | None = None,
        progress_callback: Callable[[RequestReceiptProtocol], None] | None = None,
        timeout: float | None = None,
    ) -> RequestReceiptProtocol | bool:
        ...

    def teardown(self) -> None:
        ...


class DestinationProtocol(Protocol):
    OUT: int
    SINGLE: int

    def __init__(
        self,
        identity: IdentityProtocol | None,
        direction: int,
        dest_type: int,
        app_name: str,
        *aspects: str,
    ) -> None:
        ...


class ReticulumProtocol(Protocol):
    def __init__(self, config_dir: str | None) -> None:
        ...

if TYPE_CHECKING:
    from RNS import Destination as DestinationType
    from RNS import Identity as IdentityType
    from RNS import Link as LinkType
    from RNS import RequestReceipt as RequestReceiptType
    from RNS import Reticulum as ReticulumType
else:
    DestinationType: TypeAlias = DestinationProtocol
    IdentityType: TypeAlias = IdentityProtocol
    LinkType: TypeAlias = LinkProtocol
    RequestReceiptType: TypeAlias = RequestReceiptProtocol
    ReticulumType: TypeAlias = ReticulumProtocol


class RNSModule(Protocol):
    Reticulum: type[ReticulumType]
    Destination: type[DestinationType]
    Link: type[LinkType]
    Identity: type[IdentityType]
    RequestReceipt: type[RequestReceiptType]


class Fetcher(Protocol):
    def fetch_bytes(self, destination_hash: str, resource_path: str) -> bytes:
        """Fetch a remote resource as raw bytes.

        Inputs:
            destination_hash: Reticulum destination hash in hex string form.
            resource_path: Path requested by the publisher, e.g.
                file/<show>/feed.rss or file/<show>/media/<filename>.

        Outputs:
            Raw bytes for the requested resource.

        Error Conditions:
            Implementations should raise exceptions for network errors,
            timeouts, or invalid destination/resource parameters.

        Thread Safety:
            Implementations should document whether concurrent calls are safe.
        """
        ...


@dataclass
class MockFetcher(Fetcher):
    rss_payload: bytes = b""
    media_payload: bytes = b""

    def fetch_bytes(self, destination_hash: str, resource_path: str) -> bytes:
        """Return canned payloads for RSS or media paths.

        This test helper ignores destination_hash and matches feed paths based
        on README conventions.
        """
        logger = logging.getLogger("nomadcastd.fetchers")
        logger.debug(
            "MockFetcher requested destination=%s resource=%s",
            destination_hash,
            resource_path,
        )
        if resource_path == "rss" or resource_path.endswith("/feed.rss"):
            payload = self.rss_payload
        else:
            payload = self.media_payload
        logger.debug(
            "MockFetcher returning %d bytes for destination=%s resource=%s",
            len(payload),
            destination_hash,
            resource_path,
        )
        if not payload:
            logger.error(
                "MockFetcher payload is empty for destination=%s resource=%s",
                destination_hash,
                resource_path,
            )
        return payload


class ReticulumFetcher(Fetcher):
    """Fetcher implementation backed by Reticulum (RNS).

    Uses the Reticulum configuration directory (config.reticulum_config_dir)
    to initialize RNS and resolves destination hashes to Identities before
    requesting resources.
    """

    def __init__(self, config_dir: str | None = None) -> None:
        """Initialize the Reticulum client.

        Inputs:
            config_dir: Reticulum configuration directory path from the daemon
                config (reticulum_config_dir).

        Error Conditions:
            Raises RuntimeError if Reticulum is not installed or is missing
            required symbols.

        Thread Safety:
            Reticulum initialization is protected by a class-level lock; it is
            safe to construct multiple instances.
        """
        self.logger = logging.getLogger("nomadcastd.fetchers")
        self._rns: RNSModule = self._load_rns()
        self._ensure_reticulum(config_dir)
        self.config_dir = config_dir

    def fetch_bytes(self, destination_hash: str, resource_path: str) -> bytes:
        """Fetch a resource via Reticulum and return its payload.

        Inputs:
            destination_hash: Hex-encoded destination hash.
            resource_path: Resource path such as file/<show>/feed.rss or
                file/<show>/media/<filename>.

        Outputs:
            Raw payload bytes from Reticulum.

        Error Conditions:
            Raises ValueError for invalid destination hashes, RuntimeError for
            rejected/failed requests, and TimeoutError for link or request
            timeouts.

        Thread Safety:
            Link objects are per-call; this method is safe for concurrent use.
        """
        self.logger.debug(
            "Reticulum fetch start destination=%s resource=%s config_dir=%s",
            destination_hash,
            resource_path,
            self.config_dir,
        )
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
                self.logger.error("Reticulum request rejected for %s", resource_path)
                raise RuntimeError(f"Reticulum request for {resource_path} was rejected")
            payload = self._await_request(receipt, resource_path)
            self.logger.debug(
                "Reticulum fetch complete destination=%s resource=%s bytes=%d",
                destination_hash,
                resource_path,
                len(payload),
            )
            return payload
        finally:
            link.teardown()

    _reticulum_lock = threading.Lock()
    _reticulum_instance: ReticulumProtocol | None = None
    _link_timeout_seconds = 30.0
    _request_timeout_seconds = 120.0
    _required_rns_symbols = ("Reticulum", "Destination", "Link", "Identity", "RequestReceipt")

    def _load_rns(self) -> RNSModule:
        """Load the Reticulum module, supporting multiple package layouts."""
        self.logger.debug("Loading Reticulum module")
        rns_spec = importlib.util.find_spec("RNS")
        reticulum_spec = importlib.util.find_spec("reticulum")
        if rns_spec is None and reticulum_spec is None:
            self.logger.error("Reticulum module not found (RNS/reticulum)")
            raise RuntimeError(
                "Reticulum is not installed. Install the 'reticulum' package before starting nomadcastd."
            )
        if rns_spec is not None:
            module = importlib.import_module("RNS")
            self._validate_rns_module(module)
            self.logger.debug("Loaded Reticulum module from RNS")
            return module
        reticulum_module = importlib.import_module("reticulum")
        if hasattr(reticulum_module, "RNS"):
            module = reticulum_module.RNS
            self._validate_rns_module(module)
            self.logger.debug("Loaded Reticulum module from reticulum.RNS attribute")
            return module
        if self._safe_find_spec("reticulum.RNS") is not None:
            module = importlib.import_module("reticulum.RNS")
            self._validate_rns_module(module)
            self.logger.debug("Loaded Reticulum module from reticulum.RNS")
            return module
        self._validate_rns_module(reticulum_module)
        self.logger.debug("Loaded Reticulum module from reticulum root")
        return reticulum_module

    def _validate_rns_module(self, module: ModuleType | RNSModule) -> None:
        """Ensure the Reticulum module exposes required symbols."""
        self._populate_rns_module(module)
        missing = [name for name in self._required_rns_symbols if not hasattr(module, name)]
        if missing:
            missing_list = ", ".join(missing)
            self.logger.error("Reticulum module missing symbols: %s", missing_list)
            raise RuntimeError(
                "Reticulum import does not expose required symbols "
                f"({missing_list}). Ensure the Reticulum Python package is installed correctly."
            )

    def _populate_rns_module(self, module: ModuleType | RNSModule) -> None:
        """Attempt to load missing RNS symbols from known submodules."""
        for symbol in self._required_rns_symbols:
            if hasattr(module, symbol):
                continue
            for candidate in self._candidate_rns_modules(module.__name__, symbol):
                if self._safe_find_spec(candidate) is None:
                    continue
                submodule = importlib.import_module(candidate)
                if hasattr(submodule, symbol):
                    setattr(module, symbol, getattr(submodule, symbol))
                    break

    def _candidate_rns_modules(self, base: str, symbol: str) -> list[str]:
        candidates = [f"{base}.{symbol}"]
        if base != "RNS" and not base.endswith(".RNS"):
            candidates.append(f"{base}.RNS.{symbol}")
        if base != "RNS":
            candidates.append(f"RNS.{symbol}")
        seen: set[str] = set()
        unique: list[str] = []
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            unique.append(candidate)
        return unique

    def _safe_find_spec(self, module_name: str) -> importlib.machinery.ModuleSpec | None:
        """Return a module spec while tolerating missing parent packages."""
        try:
            return importlib.util.find_spec(module_name)
        except ModuleNotFoundError:
            return None

    def _ensure_reticulum(self, config_dir: str | None) -> None:
        """Initialize the Reticulum singleton if needed."""
        cls = type(self)
        with cls._reticulum_lock:
            if cls._reticulum_instance is None:
                self.logger.debug("Initializing Reticulum with config_dir=%s", config_dir)
                cls._reticulum_instance = self._rns.Reticulum(config_dir)
            else:
                self.logger.debug("Reusing Reticulum singleton")

    def _resolve_identity(self, destination_hash: str) -> IdentityType:
        """Resolve a destination hash into a Reticulum Identity.

        Error Conditions:
            Raises ValueError for invalid hex and RuntimeError if the identity
            cannot be recalled from Reticulum's cache.
        """
        try:
            destination_bytes = bytes.fromhex(destination_hash)
        except ValueError as exc:
            self.logger.error("Destination hash is not valid hex: %s", destination_hash)
            raise ValueError(f"Destination hash is not valid hex: {destination_hash}") from exc
        identity = self._rns.Identity.recall(destination_bytes, from_identity_hash=True)
        if identity is None:
            identity = self._rns.Identity.recall(destination_bytes)
        if identity is None:
            self.logger.error("Reticulum identity not found for %s", destination_hash)
            raise RuntimeError(f"Reticulum identity not found for {destination_hash}")
        return identity

    def _await_link(self, link: LinkType, resource_path: str) -> None:
        """Wait for a Reticulum link to become ACTIVE.

        Error Conditions:
            Raises RuntimeError if the link closes and TimeoutError if the
            link is not active before _link_timeout_seconds.
        """
        deadline = time.monotonic() + self._link_timeout_seconds
        while time.monotonic() < deadline:
            if link.status == self._rns.Link.ACTIVE:
                self.logger.debug("Reticulum link active for %s", resource_path)
                return
            if link.status == self._rns.Link.CLOSED:
                self.logger.error("Reticulum link closed while requesting %s", resource_path)
                raise RuntimeError(f"Reticulum link closed while requesting {resource_path}")
            time.sleep(0.1)
        self.logger.error("Reticulum link timed out for %s", resource_path)
        raise TimeoutError(f"Timed out establishing Reticulum link for {resource_path}")

    def _await_request(self, receipt: RequestReceiptType, resource_path: str) -> bytes:
        """Wait for a Reticulum request receipt to complete.

        Error Conditions:
            Raises RuntimeError on FAILED or missing response and TimeoutError
            if the response is not ready before _request_timeout_seconds.
        """
        deadline = time.monotonic() + self._request_timeout_seconds
        while time.monotonic() < deadline:
            status = receipt.get_status()
            if status == self._rns.RequestReceipt.READY:
                if receipt.response is None:
                    self.logger.error("Reticulum response missing for %s", resource_path)
                    raise RuntimeError(f"Reticulum response missing for {resource_path}")
                return bytes(receipt.response)
            if status == self._rns.RequestReceipt.FAILED:
                self.logger.error("Reticulum request failed for %s", resource_path)
                raise RuntimeError(f"Reticulum request failed for {resource_path}")
            time.sleep(0.1)
        self.logger.error("Reticulum response timeout for %s", resource_path)
        raise TimeoutError(f"Timed out waiting for Reticulum response for {resource_path}")

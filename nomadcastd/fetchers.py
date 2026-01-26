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

    def __init__(
        self,
        config_dir: str | None = None,
        destination_app: str = "nomadnet",
        destination_aspects: tuple[str, ...] = ("file",),
    ) -> None:
        """Initialize the Reticulum client.

        Inputs:
            config_dir: Reticulum configuration directory path from the daemon
                config (reticulum_config_dir).
            destination_app: Reticulum destination app name for file hosting.
            destination_aspects: Destination aspects appended to the app name.

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
        self.destination_app = destination_app
        self.destination_aspects = destination_aspects

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
        normalized_path = self._normalize_resource_path(resource_path)
        self.logger.info(
            "Reticulum fetch start destination=%s resource=%s normalized_resource=%s config_dir=%s app=%s aspects=%s",
            destination_hash,
            resource_path,
            normalized_path,
            self.config_dir,
            self.destination_app,
            self.destination_aspects,
        )
        self.logger.info(
            "Reticulum fetch context thread=%s rns_module=%s rns_file=%s",
            threading.current_thread().name,
            getattr(self._rns, "__name__", type(self._rns).__name__),
            getattr(self._rns, "__file__", "unknown"),
        )
        destination_identity = self._resolve_identity(destination_hash)
        self.logger.info(
            "Reticulum identity resolved destination=%s identity=%r",
            destination_hash,
            destination_identity,
        )
        destination = self._rns.Destination(
            destination_identity,
            self._rns.Destination.OUT,
            self._rns.Destination.SINGLE,
            self.destination_app,
            *self.destination_aspects,
        )
        self.logger.info(
            "Reticulum destination constructed destination=%s type=%s obj=%r",
            destination_hash,
            type(destination).__name__,
            destination,
        )
        computed_hash = getattr(destination, "hash", None)
        if computed_hash is not None:
            self.logger.info(
                "Reticulum destination hash computed=%s expected=%s",
                computed_hash.hex() if isinstance(computed_hash, (bytes, bytearray)) else computed_hash,
                destination_hash,
            )
        link = self._rns.Link(destination)
        self.logger.info("Reticulum link created resource=%s link=%r", normalized_path, link)
        try:
            self._await_link(link, normalized_path)
            self.logger.info(
                "Reticulum request send resource=%s timeout=%s",
                normalized_path,
                self._request_timeout_seconds,
            )
            receipt = link.request(normalized_path, timeout=self._request_timeout_seconds)
            self.logger.info(
                "Reticulum request receipt received resource=%s receipt=%r type=%s",
                normalized_path,
                receipt,
                type(receipt).__name__,
            )
            if not receipt:
                self.logger.error("Reticulum request rejected for %s", normalized_path)
                raise RuntimeError(f"Reticulum request for {normalized_path} was rejected")
            payload = self._await_request(receipt, normalized_path)
            self.logger.info(
                "Reticulum fetch complete destination=%s resource=%s bytes=%d",
                destination_hash,
                normalized_path,
                len(payload),
            )
            return payload
        finally:
            link.teardown()
            self.logger.info("Reticulum link teardown complete resource=%s", normalized_path)

    _reticulum_lock = threading.Lock()
    _reticulum_instance: ReticulumProtocol | None = None
    _link_timeout_seconds = 30.0
    _request_timeout_seconds = 120.0
    _required_rns_symbols = ("Reticulum", "Destination", "Link", "Identity", "RequestReceipt")

    def _load_rns(self) -> RNSModule:
        """Load the Reticulum module, supporting multiple package layouts."""
        self.logger.info("Loading Reticulum module")
        rns_spec = importlib.util.find_spec("RNS")
        reticulum_spec = importlib.util.find_spec("reticulum")
        self.logger.info(
            "Reticulum module specs RNS=%s reticulum=%s",
            rns_spec,
            reticulum_spec,
        )
        if rns_spec is None and reticulum_spec is None:
            self.logger.error("Reticulum module not found (RNS/reticulum)")
            raise RuntimeError(
                "Reticulum Network Stack is not installed (no RNS or reticulum module found). "
                "Install it with `pip install rns` and retry."
            )
        if rns_spec is not None:
            module = importlib.import_module("RNS")
            self._validate_rns_module(module)
            self.logger.info("Loaded Reticulum module from RNS")
            return module
        reticulum_module = importlib.import_module("reticulum")
        if hasattr(reticulum_module, "RNS"):
            module = reticulum_module.RNS
            self._validate_rns_module(module)
            self.logger.info("Loaded Reticulum module from reticulum.RNS attribute")
            return module
        if self._safe_find_spec("reticulum.RNS") is not None:
            module = importlib.import_module("reticulum.RNS")
            self._validate_rns_module(module)
            self.logger.info("Loaded Reticulum module from reticulum.RNS")
            return module
        try:
            self._validate_rns_module(reticulum_module)
        except RuntimeError as exc:
            module_path = getattr(reticulum_module, "__file__", "unknown")
            self.logger.error(
                "reticulum package at %s is missing RNS symbols: %s",
                module_path,
                exc,
            )
            raise RuntimeError(
                "Found a 'reticulum' package, but it does not expose the Reticulum "
                "Network Stack symbols (Reticulum, Destination, Link, Identity, RequestReceipt). "
                "This is likely a different package. Install the Reticulum Network Stack "
                "with `pip install rns` (module name 'RNS') and retry."
            ) from exc
        self.logger.info("Loaded Reticulum module from reticulum root")
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
                self.logger.info("Initializing Reticulum with config_dir=%s", config_dir)
                cls._reticulum_instance = self._rns.Reticulum(config_dir)
                self.logger.info("Reticulum initialized instance=%r", cls._reticulum_instance)
            else:
                self.logger.info("Reusing Reticulum singleton instance=%r", cls._reticulum_instance)

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
        self.logger.info(
            "Resolving Reticulum identity destination=%s bytes=%d",
            destination_hash,
            len(destination_bytes),
        )
        identity = self._rns.Identity.recall(destination_bytes, from_identity_hash=True)
        if identity is not None:
            self.logger.info("Reticulum identity resolved from identity hash for %s", destination_hash)
        if identity is None:
            identity = self._rns.Identity.recall(destination_bytes)
            if identity is not None:
                self.logger.info("Reticulum identity resolved from destination hash for %s", destination_hash)
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
        self.logger.info(
            "Awaiting Reticulum link resource=%s timeout=%s deadline=%s initial_status=%s",
            resource_path,
            self._link_timeout_seconds,
            deadline,
            link.status,
        )
        last_status = None
        attempts = 0
        while time.monotonic() < deadline:
            attempts += 1
            now = time.monotonic()
            self.logger.info(
                "Reticulum link poll resource=%s attempt=%d elapsed=%.3f status=%s",
                resource_path,
                attempts,
                now - (deadline - self._link_timeout_seconds),
                link.status,
            )
            if link.status == self._rns.Link.ACTIVE:
                self.logger.info("Reticulum link active for %s", resource_path)
                return
            if link.status == self._rns.Link.CLOSED:
                self.logger.error("Reticulum link closed while requesting %s", resource_path)
                raise RuntimeError(f"Reticulum link closed while requesting {resource_path}")
            if link.status != last_status:
                self.logger.info(
                    "Reticulum link status update for %s: %s",
                    resource_path,
                    link.status,
                )
                last_status = link.status
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
        self.logger.info(
            "Awaiting Reticulum response resource=%s timeout=%s deadline=%s receipt=%r",
            resource_path,
            self._request_timeout_seconds,
            deadline,
            receipt,
        )
        attempts = 0
        while time.monotonic() < deadline:
            attempts += 1
            status = receipt.get_status()
            now = time.monotonic()
            self.logger.info(
                "Reticulum receipt poll resource=%s attempt=%d elapsed=%.3f status=%s response_len=%s",
                resource_path,
                attempts,
                now - (deadline - self._request_timeout_seconds),
                status,
                None if receipt.response is None else len(receipt.response),
            )
            if status == self._rns.RequestReceipt.READY:
                if receipt.response is None:
                    self.logger.error("Reticulum response missing for %s", resource_path)
                    raise RuntimeError(f"Reticulum response missing for {resource_path}")
                self.logger.info(
                    "Reticulum receipt ready resource=%s bytes=%d",
                    resource_path,
                    len(receipt.response),
                )
                return bytes(receipt.response)
            if status == self._rns.RequestReceipt.FAILED:
                self.logger.error("Reticulum request failed for %s", resource_path)
                raise RuntimeError(f"Reticulum request failed for {resource_path}")
            time.sleep(0.1)
        self.logger.error("Reticulum response timeout for %s", resource_path)
        raise TimeoutError(f"Timed out waiting for Reticulum response for {resource_path}")

    def _normalize_resource_path(self, resource_path: str) -> str:
        """Normalize a resource path for Reticulum requests.

        MeshChat and NomadNet file links are typically addressed with a leading
        slash (e.g. /file/<show>/feed.rss). Normalize to that format to align
        with external clients.
        """
        if not resource_path:
            self.logger.info("Normalize resource path: empty input")
            return resource_path
        if resource_path.startswith("/"):
            self.logger.info("Normalize resource path: already normalized %s", resource_path)
            return resource_path
        normalized = f"/{resource_path}"
        self.logger.info("Normalized resource path %s -> %s", resource_path, normalized)
        return normalized

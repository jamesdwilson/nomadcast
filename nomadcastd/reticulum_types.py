from __future__ import annotations

"""Protocols for Reticulum (RNS) type checking."""

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
    metadata: dict | None
    response: bytes | None
    progress: float

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


class TransportProtocol(Protocol):
    @staticmethod
    def has_path(destination_hash: bytes) -> bool:
        ...

    @staticmethod
    def request_path(destination_hash: bytes) -> None:
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
    from RNS import Transport as TransportType
else:
    DestinationType: TypeAlias = DestinationProtocol
    IdentityType: TypeAlias = IdentityProtocol
    LinkType: TypeAlias = LinkProtocol
    RequestReceiptType: TypeAlias = RequestReceiptProtocol
    ReticulumType: TypeAlias = ReticulumProtocol
    TransportType: TypeAlias = TransportProtocol


class RNSModule(Protocol):
    Reticulum: type[ReticulumType]
    Destination: type[DestinationType]
    Link: type[LinkType]
    Identity: type[IdentityType]
    RequestReceipt: type[RequestReceiptType]
    Transport: type[TransportProtocol]

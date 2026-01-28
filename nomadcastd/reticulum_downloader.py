from __future__ import annotations

"""Reticulum downloader utility for NomadNet resources."""

import logging
import time
from typing import Callable

from .reticulum_types import LinkType, RequestReceiptType, RNSModule

logger = logging.getLogger("nomadcastd.fetchers")

nomadnet_cached_links: dict[bytes, LinkType] = {}


class NomadnetDownloader:
    def __init__(
        self,
        rns: RNSModule,
        destination_hash: bytes,
        path: str,
        data: bytes | None,
        on_download_success: Callable[[RequestReceiptType], None],
        on_download_failure: Callable[[str], None],
        on_progress_update: Callable[[float], None],
        timeout: int | None = None,
    ) -> None:
        self.app_name = "nomadnetwork"
        self.aspects = "node"
        self.rns = rns
        self.destination_hash = destination_hash
        self.path = path
        self.data = data
        self.timeout = timeout
        self.on_download_success = on_download_success
        self.on_download_failure = on_download_failure
        self.on_progress_update = on_progress_update

    def download(self, path_lookup_timeout: int = 15, link_establishment_timeout: int = 15) -> None:
        """Open a link (or reuse one) and dispatch the request."""
        if self.destination_hash in nomadnet_cached_links:
            link = nomadnet_cached_links[self.destination_hash]
            if link.status is self.rns.Link.ACTIVE:
                logger.info("NomadnetDownloader using existing link for request")
                self.link_established(link)
                return

        timeout_after_seconds = time.time() + path_lookup_timeout

        if not self.rns.Transport.has_path(self.destination_hash):
            self.rns.Transport.request_path(self.destination_hash)

            while not self.rns.Transport.has_path(self.destination_hash) and time.time() < timeout_after_seconds:
                time.sleep(0.1)

        if not self.rns.Transport.has_path(self.destination_hash):
            self.on_download_failure("Could not find path to destination.")
            return

        identity = self.rns.Identity.recall(self.destination_hash)
        destination = self.rns.Destination(
            identity,
            self.rns.Destination.OUT,
            self.rns.Destination.SINGLE,
            self.app_name,
            self.aspects,
        )

        logger.info("NomadnetDownloader establishing new link for request")
        link = self.rns.Link(destination, established_callback=self.link_established)

        timeout_after_seconds = time.time() + link_establishment_timeout

        while link.status is not self.rns.Link.ACTIVE and time.time() < timeout_after_seconds:
            time.sleep(0.1)

        if link.status is not self.rns.Link.ACTIVE:
            self.on_download_failure("Could not establish link to destination.")

    def link_established(self, link: LinkType) -> None:
        """Cache the link and start the request once it is active."""
        nomadnet_cached_links[self.destination_hash] = link

        link.request(
            self.path,
            data=self.data,
            response_callback=self.on_response,
            failed_callback=self.on_failed,
            progress_callback=self.on_progress,
            timeout=self.timeout,
        )

    def on_response(self, request_receipt: RequestReceiptType) -> None:
        """Forward successful receipts to the caller."""
        self.on_download_success(request_receipt)

    def on_failed(self, request_receipt: RequestReceiptType | None = None) -> None:
        """Notify the caller that the request failed."""
        self.on_download_failure("request_failed")

    def on_progress(self, request_receipt: RequestReceiptType) -> None:
        """Report progress updates for the in-flight request."""
        self.on_progress_update(request_receipt.progress)

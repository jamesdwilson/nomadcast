from __future__ import annotations

"""Daemon lifecycle and background refresh logic for NomadCast.

This module coordinates configuration reloads, feed refreshes, and media
downloads as described in the README. It owns the single worker thread and the
queue used to serialize background work.
"""

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from nomadcastd.config import NomadCastConfig, load_config, load_subscriptions
from nomadcastd.fetchers import Fetcher, MockFetcher, ReticulumFetcher
from nomadcastd.parsing import (
    Subscription,
    decode_show_path,
    encode_show_path,
    parse_nomadcast_media_url,
    parse_subscription_uri,
)
from nomadcastd.rss import parse_rss_items, rewrite_rss
from nomadcastd.storage import (
    CachedEpisode,
    cached_episode_filenames,
    ensure_show_dirs,
    ensure_nomadnet_mirror,
    load_show_state,
    save_show_state,
    ShowDirs,
    ShowState,
    show_directory,
    write_atomic,
)


@dataclass
class ShowContext:
    """Per-show state tracked by the daemon worker.

    Attributes are mutated from the main thread and worker thread; access is
    guarded by the instance lock. The context persists storage paths and
    metadata used to rebuild client RSS feeds.
    """
    subscription: Subscription
    show_dir: Path
    episodes_dir: Path
    tmp_dir: Path
    state_path: Path
    state: ShowState
    lock: threading.Lock = field(default_factory=threading.Lock)
    refresh_pending: bool = False
    media_pending: set[str] = field(default_factory=set)
    next_refresh_time: float = 0.0
    order_map: dict[str, int] = field(default_factory=dict)


class JobType(Enum):
    """Types of background work handled by the daemon worker thread."""

    STOP = "stop"
    REFRESH = "refresh"
    MEDIA = "media"


@dataclass(frozen=True)
class DaemonJob:
    """Queue item describing a unit of background work.

    Attributes:
        type: The kind of work to perform.
        show_id: The "<destination_hash>:<show_name>" identifier for the show.
        payload: Optional job-specific payload. For media jobs, this is the
            episode filename to download; otherwise None.
    """

    type: JobType
    show_id: str
    payload: str | None = None


class NomadCastDaemon:
    """Manage NomadCast background work and cached storage.

    The daemon owns a single worker thread and an in-process queue to serialize
    refresh and media fetch jobs. Callers may enqueue work from multiple
    threads; internal locking on ShowContext ensures per-show state remains
    consistent.
    """
    def __init__(self, config: NomadCastConfig | None = None, fetcher: Fetcher | None = None) -> None:
        """Initialize the daemon with config and fetcher dependencies.

        Args:
            config: Optional configuration override. If omitted, the default
                config file is loaded.
            fetcher: Optional fetcher implementation. Defaults to
                ReticulumFetcher pointing at the configured Reticulum config
                directory.

        Side Effects:
            Loads configuration, constructs the worker thread, and allocates
            the in-memory queue. Does not touch the filesystem until start().

        Thread Safety:
            Safe to call from the main thread before start() is invoked.
        """
        # README: daemon bridges Reticulum-hosted feeds to local HTTP.
        self.logger = logging.getLogger("nomadcastd")
        self.config = config or load_config()
        self.logger.debug("Daemon config loaded: %s", self.config)
        if fetcher is not None:
            self.logger.debug("Using injected fetcher %s", type(fetcher).__name__)
            self.fetcher = fetcher
        else:
            try:
                self.fetcher = ReticulumFetcher(
                    config_dir=self.config.reticulum_config_dir,
                    destination_app=self.config.reticulum_destination_app,
                    destination_aspects=self.config.reticulum_destination_aspects,
                )
            except RuntimeError as exc:
                self.logger.warning(
                    "Reticulum unavailable (%s); falling back to MockFetcher.",
                    exc,
                )
                self.fetcher = MockFetcher()
        self.show_contexts: dict[str, ShowContext] = {}
        self.queue: queue.Queue[DaemonJob] = queue.Queue()
        self.stop_event = threading.Event()
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)

    def start(self) -> None:
        """Start the daemon worker and ensure storage exists.

        Side Effects:
            Ensures the base storage path exists, reloads configuration and
            subscriptions, and starts the background worker thread.

        Thread Safety:
            Should be called once from a single thread before servicing HTTP
            requests.
        """
        # Prepare storage layout described in README.
        self.config.storage_path.mkdir(parents=True, exist_ok=True)
        self.logger.debug("Storage path ensured at %s", self.config.storage_path)
        self.reload_config()
        self.worker_thread.start()
        self._queue_initial_refreshes()

    def stop(self) -> None:
        """Stop the daemon worker and wait briefly for exit.

        Side Effects:
            Signals the worker thread, enqueues a sentinel job, and joins the
            thread with a short timeout.

        Thread Safety:
            Safe to call from the main thread; no guarantee of immediate
            shutdown if background work is blocked.
        """
        self.stop_event.set()
        self.queue.put(DaemonJob(JobType.STOP, ""))
        self.worker_thread.join(timeout=5)
        self.logger.debug("Daemon stop complete")

    def reload_config(self) -> None:
        """Reload config and subscriptions, rebuilding show contexts.

        Inputs/Outputs:
            Reads config and subscription files as defined by NomadCastConfig
            and updates self.show_contexts with new ShowContext instances.

        Side Effects:
            Ensures per-show storage directories exist and loads cached
            show state from disk. Invalid subscriptions are logged and skipped.

        Thread Safety:
            Should be called from the main thread or while the worker is idle;
            per-context locks protect concurrent updates to ShowContext fields.
        """
        # Reload config and subscriptions (README: POST /reload triggers this).
        self.config = load_config(self.config.config_path)
        self.logger.debug("Reloaded config from %s", self.config.config_path)
        subscription_uris = load_subscriptions(self.config.config_path)
        self.logger.debug("Loaded %d subscription URI(s)", len(subscription_uris))
        subscriptions: list[Subscription] = []
        for uri in subscription_uris:
            try:
                subscriptions.append(parse_subscription_uri(uri))
            except ValueError as exc:
                self.logger.warning("Skipping invalid subscription %s: %s", uri, exc)

        new_contexts: dict[str, ShowContext] = {}
        # Build show contexts keyed by destination_hash:show_name (README:
        # destination hash is authoritative; show name is cosmetic but part
        # of routing).
        for subscription in subscriptions:
            show_id = subscription.show_id
            show_dir = show_directory(self.config.storage_path, subscription.destination_hash)
            dirs: ShowDirs = ensure_show_dirs(show_dir)
            state_path = show_dir / "state.json"
            state = load_show_state(state_path, subscription.uri, subscription.show_name)
            context = self.show_contexts.get(show_id)
            if context:
                self.logger.debug("Updating existing context for %s", show_id)
                context.subscription = subscription
                context.show_dir = show_dir
                context.episodes_dir = dirs["episodes_dir"]
                context.tmp_dir = dirs["tmp_dir"]
                context.state_path = state_path
                context.state = state
                new_contexts[show_id] = context
            else:
                self.logger.debug("Creating new context for %s", show_id)
                new_contexts[show_id] = ShowContext(
                    subscription=subscription,
                    show_dir=show_dir,
                    episodes_dir=dirs["episodes_dir"],
                    tmp_dir=dirs["tmp_dir"],
                    state_path=state_path,
                    state=state,
                )
        self.show_contexts = new_contexts
        self.logger.info("Loaded %d subscription(s)", len(subscriptions))

    def enqueue_refresh(self, show_id: str, *, force: bool = False) -> None:
        """Request an RSS refresh for a show.

        Queue Semantics:
            Debounces duplicate refreshes and honors rss_poll_seconds as well
            as the exponential backoff derived from retry_backoff_seconds. Only
            one pending refresh per show is queued at a time.

        Side Effects:
            Enqueues a refresh job for the worker thread when eligible.

        Thread Safety:
            Safe to call concurrently; uses per-show lock to update flags.
        """
        context = self.show_contexts.get(show_id)
        if not context:
            self.logger.debug("Refresh requested for unknown show_id=%s", show_id)
            return
        with context.lock:
            now = time.time()
            # Debounce refresh requests and honor RSS polling interval
            # (README: rss_poll_seconds, backoff behavior).
            if context.refresh_pending:
                self.logger.debug("Refresh already pending for %s", show_id)
                return
            if not force:
                if context.state.last_refresh and now - context.state.last_refresh < self.config.rss_poll_seconds:
                    self.logger.debug(
                        "Refresh skipped for %s: last_refresh=%s rss_poll_seconds=%s",
                        show_id,
                        context.state.last_refresh,
                        self.config.rss_poll_seconds,
                    )
                    return
                if now < context.next_refresh_time:
                    self.logger.debug(
                        "Refresh backoff active for %s: next_refresh_time=%s now=%s",
                        show_id,
                        context.next_refresh_time,
                        now,
                    )
                    return
            context.refresh_pending = True
        if force:
            self.logger.info("Enqueued startup refresh for %s", show_id)
        else:
            self.logger.debug("Enqueued refresh for %s", show_id)
        self.queue.put(DaemonJob(JobType.REFRESH, show_id))

    def _queue_initial_refreshes(self) -> None:
        """Queue immediate refreshes for all shows on startup."""
        if not self.show_contexts:
            self.logger.info("No subscriptions to refresh on startup.")
            return
        self.logger.info("Starting initial sync for %d subscription(s).", len(self.show_contexts))
        for show_id in self.show_contexts:
            self.enqueue_refresh(show_id, force=True)

    def enqueue_media_fetch(self, show_id: str, filename: str) -> None:
        """Request a media fetch for a show/filename.

        Queue Semantics:
            Tracks per-show pending filenames to avoid duplicate downloads.

        Side Effects:
            Enqueues a media job for the worker thread when eligible.

        Thread Safety:
            Safe to call concurrently; uses per-show lock to update flags.
        """
        # Track per-show pending downloads so we don't queue duplicates.
        context = self.show_contexts.get(show_id)
        if not context:
            self.logger.debug("Media fetch requested for unknown show_id=%s", show_id)
            return
        with context.lock:
            if filename in context.media_pending:
                self.logger.debug("Media fetch already pending for %s/%s", show_id, filename)
                return
            context.media_pending.add(filename)
        self.logger.debug("Enqueued media fetch for %s/%s", show_id, filename)
        self.queue.put(DaemonJob(JobType.MEDIA, show_id, filename))

    def get_cached_rss(self, show_id: str) -> bytes | None:
        """Return cached client RSS bytes for a show, if present.

        Outputs:
            The contents of client_rss.xml or None if no cached feed exists.

        Thread Safety:
            File reads are safe; no locks required.
        """
        context = self.show_contexts.get(show_id)
        if not context:
            self.logger.debug("No context for cached RSS lookup for %s", show_id)
            return None
        rss_path = context.show_dir / "client_rss.xml"
        if rss_path.exists():
            self.logger.debug("Serving cached RSS for %s", show_id)
            return rss_path.read_bytes()
        self.logger.debug("Cached RSS missing for %s", show_id)
        return None

    def get_media_path(self, show_id: str, filename: str) -> Path | None:
        """Return the cached media file path when present.

        Outputs:
            A Path pointing at episodes/<filename> if it exists, otherwise None.

        Thread Safety:
            File existence checks are safe; no locks required.
        """
        context = self.show_contexts.get(show_id)
        if not context:
            self.logger.debug("No context for media lookup for %s/%s", show_id, filename)
            return None
        candidate = context.episodes_dir / filename
        if candidate.exists():
            self.logger.debug("Serving cached media for %s/%s", show_id, filename)
            return candidate
        self.logger.debug("Cached media missing for %s/%s", show_id, filename)
        return None

    def show_id_from_path(self, show_path: str) -> str | None:
        """Convert a URL path segment into the internal show_id.

        Inputs:
            show_path: The encoded show path as served by the HTTP API.

        Outputs:
            The "<destination_hash>:<show_name>" identifier, or None for
            invalid input.

        Error Conditions:
            Returns None if decoding fails.
        """
        try:
            destination_hash, show_name = decode_show_path(show_path)
        except ValueError:
            return None
        return f"{destination_hash}:{show_name}"

    def _worker_loop(self) -> None:
        """Process queued jobs until stopped.

        Queue Semantics:
            Processes jobs in FIFO order. STOP jobs terminate the loop; REFRESH
            jobs fetch RSS, and MEDIA jobs download episode files.

        Thread Safety:
            Runs on the dedicated worker thread only.
        """
        while not self.stop_event.is_set():
            try:
                job = self.queue.get(timeout=0.2)
            except queue.Empty:
                continue
            match job.type:
                case JobType.STOP:
                    self.logger.debug("Worker loop received stop signal")
                    return
                case JobType.REFRESH:
                    self.logger.debug("Worker handling refresh for %s", job.show_id)
                    self._handle_refresh(job.show_id)
                case JobType.MEDIA:
                    filename = job.payload
                    if filename:
                        self.logger.debug("Worker handling media for %s/%s", job.show_id, filename)
                        self._handle_media_fetch(job.show_id, filename)

    def _handle_refresh(self, show_id: str) -> None:
        """Fetch the publisher RSS, update cache, and queue media downloads.

        Inputs/Outputs:
            Uses the Reticulum fetcher to retrieve feed.rss and persists
            publisher_rss.xml and client_rss.xml under the show's directory.

        Side Effects:
            Updates state.json, refresh timestamps, and refresh error metadata.
            Queues media downloads for the most recent episodes_per_show
            enclosures not already cached.

        Error Conditions:
            Any exception from fetch, parsing, or file IO records a failure and
            schedules backoff according to retry_backoff_seconds.

        Thread Safety:
            Runs on the worker thread; updates shared state under lock.
        """
        context = self.show_contexts.get(show_id)
        if not context:
            self.logger.debug("Refresh skipped: missing context for %s", show_id)
            return
        self.logger.info(
            "Refresh start show_id=%s destination=%s show_name=%s storage=%s",
            show_id,
            context.subscription.destination_hash,
            context.subscription.show_name,
            context.show_dir,
        )
        with context.lock:
            context.refresh_pending = False
        try:
            # README: fetch publisher RSS over Reticulum and store raw bytes.
            rss_path = f"/file/{context.subscription.show_name}/feed.rss"
            self.logger.info("Refreshing RSS for %s (%s)", show_id, rss_path)
            self.logger.debug("Fetching RSS for %s at %s", show_id, rss_path)
            rss_bytes = self.fetcher.fetch_bytes(context.subscription.destination_hash, rss_path)
            self.logger.info("Fetched RSS for %s (%d bytes)", show_id, len(rss_bytes))
            write_atomic(context.show_dir / "publisher_rss.xml", rss_bytes)
            _, items = parse_rss_items(rss_bytes)
            self.logger.info("Parsed %d RSS items for %s", len(items), show_id)
            ordered_items = items
            if any(item.pub_date is not None for item in items):
                ordered_items = sorted(
                    items,
                    key=lambda item: item.pub_date if item.pub_date is not None else 0,
                    reverse=True,
                )
            selected_items = ordered_items[: self.config.episodes_per_show]
            self.logger.info(
                "Selected %d item(s) for %s (episodes_per_show=%s)",
                len(selected_items),
                show_id,
                self.config.episodes_per_show,
            )
            order_map: dict[str, int] = {}
            # README: queue downloads for the most recent N episodes.
            for index, item in enumerate(selected_items):
                for url in item.enclosure_urls:
                    try:
                        dest_hash, show_name, filename = parse_nomadcast_media_url(url)
                    except ValueError:
                        self.logger.debug("Skipping non-nomadcast enclosure URL: %s", url)
                        continue
                    if dest_hash != context.subscription.destination_hash or show_name != context.subscription.show_name:
                        self.logger.debug(
                            "Skipping enclosure for %s: dest=%s show=%s",
                            show_id,
                            dest_hash,
                            show_name,
                        )
                        continue
                    order_map[filename] = index
                    if not (context.episodes_dir / filename).exists():
                        self.logger.info(
                            "Queueing media fetch show_id=%s filename=%s order_index=%s",
                            show_id,
                            filename,
                            index,
                        )
                        self.enqueue_media_fetch(show_id, filename)
            with context.lock:
                context.order_map = order_map
                context.state.last_refresh = time.time()
                context.state.last_error = None
                context.state.failure_count = 0
                context.state.cached_episodes = self._load_cached_episodes(context, order_map)
                save_show_state(context.state_path, context.state)
        self.logger.info(
            "Refresh updated state for %s: cached=%d order_map=%d",
            show_id,
            len(context.state.cached_episodes),
            len(order_map),
        )
        # Rebuild client RSS after refresh per README rewrite rules.
        self._rebuild_client_rss(context)
        if self._should_mirror(context):
            self._ensure_mirror(context)
        self.logger.info("Refreshed RSS for %s", show_id)
        except Exception as exc:
            self._register_failure(context, str(exc))
            self.logger.error("Failed to refresh %s: %s", show_id, exc)

    def _load_cached_episodes(self, context: ShowContext, order_map: dict[str, int]) -> list[CachedEpisode]:
        """Reconcile cached media with the refreshed order map.

        Side Effects:
            Deletes media files not present in the latest order_map (keeping
            only the newest episodes_per_show items per README).

        Outputs:
            A list of CachedEpisode metadata for existing files.
        """
        cached: list[CachedEpisode] = []
        # README: only keep cached files that are still among the latest N.
        for path in context.episodes_dir.iterdir():
            if path.is_file() and path.name not in order_map:
                self.logger.debug("Evicting stale media %s", path.name)
                path.unlink()
        for filename, order_index in order_map.items():
            path = context.episodes_dir / filename
            if path.exists():
                cached.append(CachedEpisode(filename=filename, order_index=order_index, size_bytes=path.stat().st_size))
        return cached

    def _register_failure(self, context: ShowContext, message: str) -> None:
        """Record a refresh or media failure and schedule backoff.

        Side Effects:
            Updates state.json with last_error and failure_count and sets the
            next_refresh_time based on retry_backoff_seconds.

        Thread Safety:
            Uses the per-show lock to mutate shared state.
        """
        with context.lock:
            # README: use retry_backoff_seconds with exponential-ish backoff.
            context.state.last_error = message
            context.state.failure_count += 1
            backoff = self.config.retry_backoff_seconds * min(2 ** context.state.failure_count, 8)
            context.next_refresh_time = time.time() + backoff
            save_show_state(context.state_path, context.state)
        self.logger.error(
            "Registered failure for %s: %s (failure_count=%s backoff=%s)",
            context.subscription.show_id,
            message,
            context.state.failure_count,
            backoff,
        )

    def _handle_media_fetch(self, show_id: str, filename: str) -> None:
        """Fetch and cache media for a show filename.

        Inputs/Outputs:
            Downloads file/<show_name>/media/<filename> via the fetcher and
            writes the media to episodes/<filename> atomically.

        Side Effects:
            Updates state.json, cached episode metadata, and rebuilds the
            client RSS with updated enclosure URLs. Enforces max_bytes_per_show
            eviction if configured.

        Error Conditions:
            Any exception from fetch or IO registers a failure and logs an
            error; pending flags are cleared regardless.

        Thread Safety:
            Runs on the worker thread; uses per-show lock to update flags and
            cached state.
        """
        context = self.show_contexts.get(show_id)
        if not context:
            self.logger.debug("Media fetch skipped: missing context for %s/%s", show_id, filename)
            return
        try:
            if (context.episodes_dir / filename).exists():
                self.logger.debug("Media already cached for %s/%s", show_id, filename)
                return
            # README: fetch media/<filename> over Reticulum.
            media_path = f"/file/{context.subscription.show_name}/media/{filename}"
            self.logger.info("Fetching media for %s/%s at %s", show_id, filename, media_path)
            payload = self.fetcher.fetch_bytes(context.subscription.destination_hash, media_path)
            self.logger.info("Fetched media for %s/%s (%d bytes)", show_id, filename, len(payload))
            if self.config.max_bytes_per_show > 0:
                if not self._ensure_space_for(context, len(payload)):
                    self.logger.warning("Skipping %s: exceeds max_bytes_per_show", filename)
                    return
            # README: write atomically via tmp/ then move to episodes/.
            tmp_path = context.tmp_dir / filename
            self.logger.info("Writing media to tmp path %s (%d bytes)", tmp_path, len(payload))
            write_atomic(tmp_path, payload)
            final_path = context.episodes_dir / filename
            self.logger.info("Promoting media to final path %s", final_path)
            tmp_path.replace(final_path)
            with context.lock:
                order_index = context.order_map.get(filename, len(context.order_map))
                context.state.cached_episodes.append(
                    CachedEpisode(filename=filename, order_index=order_index, size_bytes=len(payload))
                )
                save_show_state(context.state_path, context.state)
            self.logger.info("Updated cached episodes for %s/%s", show_id, filename)
            self._rebuild_client_rss(context)
            if self._should_mirror(context):
                self._ensure_mirror(context)
            self.logger.info("Cached media %s for %s", filename, show_id)
        except Exception as exc:
            self._register_failure(context, str(exc))
            self.logger.error("Failed to fetch media %s for %s: %s", filename, show_id, exc)
        finally:
            with context.lock:
                context.media_pending.discard(filename)

    def _ensure_space_for(self, context: ShowContext, new_size: int) -> bool:
        """Ensure there is space for a new media file under max_bytes_per_show.

        Inputs:
            new_size: Size of the incoming payload in bytes.

        Outputs:
            True if space is available after evicting old files; False if the
            payload would still exceed max_bytes_per_show.

        Side Effects:
            Evicts cached files starting from the oldest order_index and
            updates state.json to reflect removals.

        Thread Safety:
            Runs on the worker thread; mutates per-show state.
        """
        # README: enforce max_bytes_per_show with oldest-episode eviction.
        if self.config.max_bytes_per_show <= 0:
            self.logger.debug("Max bytes per show disabled; skipping eviction")
            return True
        cached = context.state.cached_episodes
        total = sum(item.size_bytes for item in cached)
        if total + new_size <= self.config.max_bytes_per_show:
            self.logger.debug(
                "Sufficient space for new payload (%d bytes) under max_bytes_per_show=%d",
                new_size,
                self.config.max_bytes_per_show,
            )
            return True
        evictable = sorted(cached, key=lambda item: item.order_index, reverse=True)
        while evictable and total + new_size > self.config.max_bytes_per_show:
            oldest = evictable.pop(0)
            path = context.episodes_dir / oldest.filename
            if path.exists():
                total -= oldest.size_bytes
                self.logger.debug("Evicting %s to free %d bytes", oldest.filename, oldest.size_bytes)
                path.unlink()
            cached = [item for item in cached if item.filename != oldest.filename]
        context.state.cached_episodes = cached
        save_show_state(context.state_path, context.state)
        self.logger.debug(
            "Eviction complete: total=%d new_size=%d max=%d",
            total,
            new_size,
            self.config.max_bytes_per_show,
        )
        return total + new_size <= self.config.max_bytes_per_show

    def _rebuild_client_rss(self, context: ShowContext) -> None:
        """Rewrite publisher RSS into the client-facing feed.

        Outputs:
            Writes client_rss.xml to the show directory.

        Side Effects:
            Filters enclosures to cached episodes and rewrites enclosure URLs
            to the local HTTP server (respecting public_host, listen_host, and
            listen_port as described in README).

        Thread Safety:
            Runs on the worker thread; reads from disk without locking.
        """
        # README: rewrite enclosure URLs to localhost and filter cached items.
        rss_path = context.show_dir / "publisher_rss.xml"
        if not rss_path.exists():
            self.logger.debug("Publisher RSS missing for %s; skipping rewrite", context.subscription.show_id)
            return
        rss_bytes = rss_path.read_bytes()
        listen_host = self.config.public_host
        if not listen_host:
            # README: when binding to 0.0.0.0, rewrite to 127.0.0.1 unless
            # public_host is explicitly set.
            listen_host = self.config.listen_host if self.config.listen_host != "0.0.0.0" else "127.0.0.1"
        show_path = encode_show_path(context.subscription.destination_hash, context.subscription.show_name)
        cached_filenames = cached_episode_filenames(context.state.cached_episodes)
        self.logger.debug(
            "Rewriting RSS for %s with host=%s port=%s cached=%d show_path=%s",
            context.subscription.show_id,
            listen_host,
            self.config.listen_port,
            len(cached_filenames),
            show_path,
        )
        client_bytes = rewrite_rss(
            rss_bytes=rss_bytes,
            listen_host=listen_host,
            listen_port=self.config.listen_port,
            show_path=show_path,
            cached_filenames=cached_filenames,
            episodes_per_show=self.config.episodes_per_show,
            strict_cached=self.config.strict_cached_enclosures,
        )
        write_atomic(context.show_dir / "client_rss.xml", client_bytes)

    def _should_mirror(self, context: ShowContext) -> bool:
        return self.config.mirror_to_nomadnet and context.subscription.uri not in self.config.nomirror_uris

    def _ensure_mirror(self, context: ShowContext) -> None:
        try:
            mirror_dir = ensure_nomadnet_mirror(
                show_dir=context.show_dir,
                episodes_dir=context.episodes_dir,
                destination_hash=context.subscription.destination_hash,
                show_name=context.subscription.show_name,
            )
            self.logger.info("Ensured NomadNet mirror at %s", mirror_dir)
        except OSError as exc:
            self.logger.warning("Failed to ensure NomadNet mirror for %s: %s", context.subscription.show_id, exc)

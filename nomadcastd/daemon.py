from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from nomadcastd.config import NomadCastConfig, load_config, load_subscriptions
from nomadcastd.fetchers import Fetcher, ReticulumFetcher
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
    load_show_state,
    save_show_state,
    ShowState,
    show_directory,
    write_atomic,
)


@dataclass
class ShowContext:
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


class NomadCastDaemon:
    def __init__(self, config: NomadCastConfig | None = None, fetcher: Fetcher | None = None) -> None:
        # README: daemon bridges Reticulum-hosted feeds to local HTTP.
        self.logger = logging.getLogger("nomadcastd")
        self.config = config or load_config()
        self.fetcher = fetcher or ReticulumFetcher(self.config.reticulum_config_dir)
        self.show_contexts: dict[str, ShowContext] = {}
        self.queue: queue.Queue[tuple[str, str, str | None]] = queue.Queue()
        self.stop_event = threading.Event()
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)

    def start(self) -> None:
        # Prepare storage layout described in README.
        self.config.storage_path.mkdir(parents=True, exist_ok=True)
        self.reload_config()
        self.worker_thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.queue.put(("stop", "", None))
        self.worker_thread.join(timeout=5)

    def reload_config(self) -> None:
        # Reload config and subscriptions (README: POST /reload triggers this).
        self.config = load_config(self.config.config_path)
        subscription_uris = load_subscriptions(self.config.config_path)
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
            dirs = ensure_show_dirs(show_dir)
            state_path = show_dir / "state.json"
            state = load_show_state(state_path, subscription.uri, subscription.show_name)
            context = self.show_contexts.get(show_id)
            if context:
                context.subscription = subscription
                context.show_dir = show_dir
                context.episodes_dir = dirs["episodes_dir"]
                context.tmp_dir = dirs["tmp_dir"]
                context.state_path = state_path
                context.state = state
                new_contexts[show_id] = context
            else:
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

    def enqueue_refresh(self, show_id: str) -> None:
        context = self.show_contexts.get(show_id)
        if not context:
            return
        with context.lock:
            now = time.time()
            # Debounce refresh requests and honor RSS polling interval
            # (README: rss_poll_seconds, backoff behavior).
            if context.refresh_pending:
                return
            if context.state.last_refresh and now - context.state.last_refresh < self.config.rss_poll_seconds:
                return
            if now < context.next_refresh_time:
                return
            context.refresh_pending = True
        self.queue.put(("refresh", show_id, None))

    def enqueue_media_fetch(self, show_id: str, filename: str) -> None:
        # Track per-show pending downloads so we don't queue duplicates.
        context = self.show_contexts.get(show_id)
        if not context:
            return
        with context.lock:
            if filename in context.media_pending:
                return
            context.media_pending.add(filename)
        self.queue.put(("media", show_id, filename))

    def get_cached_rss(self, show_id: str) -> bytes | None:
        context = self.show_contexts.get(show_id)
        if not context:
            return None
        rss_path = context.show_dir / "client_rss.xml"
        if rss_path.exists():
            return rss_path.read_bytes()
        return None

    def get_media_path(self, show_id: str, filename: str) -> Path | None:
        context = self.show_contexts.get(show_id)
        if not context:
            return None
        candidate = context.episodes_dir / filename
        if candidate.exists():
            return candidate
        return None

    def show_id_from_path(self, show_path: str) -> str | None:
        try:
            destination_hash, show_name = decode_show_path(show_path)
        except ValueError:
            return None
        return f"{destination_hash}:{show_name}"

    def _worker_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                job_type, show_id, payload = self.queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if job_type == "stop":
                return
            if job_type == "refresh":
                self._handle_refresh(show_id)
            elif job_type == "media":
                if payload:
                    self._handle_media_fetch(show_id, payload)

    def _handle_refresh(self, show_id: str) -> None:
        context = self.show_contexts.get(show_id)
        if not context:
            return
        with context.lock:
            context.refresh_pending = False
        try:
            # README: fetch publisher RSS over Reticulum and store raw bytes.
            rss_bytes = self.fetcher.fetch_bytes(context.subscription.destination_hash, "rss")
            write_atomic(context.show_dir / "publisher_rss.xml", rss_bytes)
            _, items = parse_rss_items(rss_bytes)
            ordered_items = items
            if any(item.pub_date is not None for item in items):
                ordered_items = sorted(
                    items,
                    key=lambda item: item.pub_date if item.pub_date is not None else 0,
                    reverse=True,
                )
            selected_items = ordered_items[: self.config.episodes_per_show]
            order_map: dict[str, int] = {}
            # README: queue downloads for the most recent N episodes.
            for index, item in enumerate(selected_items):
                for url in item.enclosure_urls:
                    try:
                        dest_hash, show_name, filename = parse_nomadcast_media_url(url)
                    except ValueError:
                        continue
                    if dest_hash != context.subscription.destination_hash or show_name != context.subscription.show_name:
                        continue
                    order_map[filename] = index
                    if not (context.episodes_dir / filename).exists():
                        self.enqueue_media_fetch(show_id, filename)
            with context.lock:
                context.order_map = order_map
                context.state.last_refresh = time.time()
                context.state.last_error = None
                context.state.failure_count = 0
                context.state.cached_episodes = self._load_cached_episodes(context, order_map)
                save_show_state(context.state_path, context.state)
            # Rebuild client RSS after refresh per README rewrite rules.
            self._rebuild_client_rss(context)
            self.logger.info("Refreshed RSS for %s", show_id)
        except Exception as exc:
            self._register_failure(context, str(exc))
            self.logger.error("Failed to refresh %s: %s", show_id, exc)

    def _load_cached_episodes(self, context: ShowContext, order_map: dict[str, int]) -> list[CachedEpisode]:
        cached: list[CachedEpisode] = []
        # README: only keep cached files that are still among the latest N.
        for path in context.episodes_dir.iterdir():
            if path.is_file() and path.name not in order_map:
                path.unlink()
        for filename, order_index in order_map.items():
            path = context.episodes_dir / filename
            if path.exists():
                cached.append(CachedEpisode(filename=filename, order_index=order_index, size_bytes=path.stat().st_size))
        return cached

    def _register_failure(self, context: ShowContext, message: str) -> None:
        with context.lock:
            # README: use retry_backoff_seconds with exponential-ish backoff.
            context.state.last_error = message
            context.state.failure_count += 1
            backoff = self.config.retry_backoff_seconds * min(2 ** context.state.failure_count, 8)
            context.next_refresh_time = time.time() + backoff
            save_show_state(context.state_path, context.state)

    def _handle_media_fetch(self, show_id: str, filename: str) -> None:
        context = self.show_contexts.get(show_id)
        if not context:
            return
        try:
            if (context.episodes_dir / filename).exists():
                return
            # README: fetch media/<filename> over Reticulum.
            payload = self.fetcher.fetch_bytes(context.subscription.destination_hash, f"media/{filename}")
            if self.config.max_bytes_per_show > 0:
                if not self._ensure_space_for(context, len(payload)):
                    self.logger.warning("Skipping %s: exceeds max_bytes_per_show", filename)
                    return
            # README: write atomically via tmp/ then move to episodes/.
            tmp_path = context.tmp_dir / filename
            write_atomic(tmp_path, payload)
            final_path = context.episodes_dir / filename
            tmp_path.replace(final_path)
            with context.lock:
                order_index = context.order_map.get(filename, len(context.order_map))
                context.state.cached_episodes.append(
                    CachedEpisode(filename=filename, order_index=order_index, size_bytes=len(payload))
                )
                save_show_state(context.state_path, context.state)
            self._rebuild_client_rss(context)
            self.logger.info("Cached media %s for %s", filename, show_id)
        except Exception as exc:
            self._register_failure(context, str(exc))
            self.logger.error("Failed to fetch media %s for %s: %s", filename, show_id, exc)
        finally:
            with context.lock:
                context.media_pending.discard(filename)

    def _ensure_space_for(self, context: ShowContext, new_size: int) -> bool:
        # README: enforce max_bytes_per_show with oldest-episode eviction.
        if self.config.max_bytes_per_show <= 0:
            return True
        cached = context.state.cached_episodes
        total = sum(item.size_bytes for item in cached)
        if total + new_size <= self.config.max_bytes_per_show:
            return True
        evictable = sorted(cached, key=lambda item: item.order_index, reverse=True)
        while evictable and total + new_size > self.config.max_bytes_per_show:
            oldest = evictable.pop(0)
            path = context.episodes_dir / oldest.filename
            if path.exists():
                total -= oldest.size_bytes
                path.unlink()
            cached = [item for item in cached if item.filename != oldest.filename]
        context.state.cached_episodes = cached
        save_show_state(context.state_path, context.state)
        return total + new_size <= self.config.max_bytes_per_show

    def _rebuild_client_rss(self, context: ShowContext) -> None:
        # README: rewrite enclosure URLs to localhost and filter cached items.
        rss_path = context.show_dir / "publisher_rss.xml"
        if not rss_path.exists():
            return
        rss_bytes = rss_path.read_bytes()
        listen_host = self.config.public_host
        if not listen_host:
            # README: when binding to 0.0.0.0, rewrite to 127.0.0.1 unless
            # public_host is explicitly set.
            listen_host = self.config.listen_host if self.config.listen_host != "0.0.0.0" else "127.0.0.1"
        show_path = encode_show_path(context.subscription.destination_hash, context.subscription.show_name)
        cached_filenames = cached_episode_filenames(context.state.cached_episodes)
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

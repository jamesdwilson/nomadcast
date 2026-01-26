# NomadCast Roadmap

This roadmap tracks planned capabilities for NomadCast. It is derived from the README roadmap and will evolve as community feedback lands.

## Streaming attempt (best-effort)

Explore on-demand streaming when a fast Reticulum uplink is available (for example, WiFi/Ethernet encapsulation). When streaming is not viable, fall back to queue-and-retry semantics.

## Better publisher discovery

Improve discoverability with human-friendly naming and optional index/manifest feeds once naming systems in the ecosystem mature.

## Richer caching logic

Add configurable cache windows, retention policies, background refresh scheduling, and smarter eviction when storage pressure is detected.

## First-subscribe delivery strategies (podcast clients)

Explore alternatives to the initial 503 response when a feed cache is empty, especially for clients like Apple Podcasts that treat 503 as “feed not found.” Consider:

- **Blocking wait on first request**: hold the HTTP response briefly until the first RSS/episode is cached. **Pros:** avoids placeholder feeds, increases chance the client accepts the real feed. **Cons:** can stall clients and ties up server threads.
- **Startup warm-up**: prefetch feeds/episodes on daemon start or reload. **Pros:** no placeholder feed, first request likely a cache hit. **Cons:** higher startup cost, wasteful if many subscriptions are rarely used.
- **Client-specific handling**: detect known strict clients and adapt (wait longer or return a different status). **Pros:** limits impact to problematic clients. **Cons:** brittle UA sniffing, harder to test.

## Multiple publishing methods

Document additional publishing patterns beyond Nomad Network file hosting as community conventions evolve.

## GUI expansion

Expand the UI to manage the daemon lifecycle, edit subscriptions, view cache status, and optionally provide a system tray experience where supported.

## Health endpoint

Add a local diagnostics endpoint (`/health`) for quick status checks.

## Daemon-managed hosting pipeline

Add full hosting capabilities to the `nomadcastd` daemon so publishers can point it at a directory structure (or similar) and have it generate metadata, RSS feeds, and any required artifacts automatically.

# NomadCast Roadmap

This roadmap tracks planned capabilities for NomadCast. It is derived from the README roadmap and will evolve as community feedback lands.

## Streaming attempt (best-effort)

Explore on-demand streaming when a fast Reticulum uplink is available (for example, WiFi/Ethernet encapsulation). When streaming is not viable, fall back to queue-and-retry semantics.

## Better publisher discovery

Improve discoverability with human-friendly naming and optional index/manifest feeds once naming systems in the ecosystem mature.

## Richer caching logic

Add configurable cache windows, retention policies, background refresh scheduling, and smarter eviction when storage pressure is detected.

## Multiple publishing methods

Document additional publishing patterns beyond Nomad Network file hosting as community conventions evolve.

## GUI expansion

Expand the UI to manage the daemon lifecycle, edit subscriptions, view cache status, and optionally provide a system tray experience where supported.

## Health endpoint

Add a local diagnostics endpoint (`/health`) for quick status checks.

## Daemon-managed hosting pipeline

Add full hosting capabilities to the `nomadcastd` daemon so publishers can point it at a directory structure (or similar) and have it generate metadata, RSS feeds, and any required artifacts automatically.

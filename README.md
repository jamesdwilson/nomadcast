# NomadCast

NomadCast lets you listen to podcasts hosted on Reticulum using normal podcast apps (Apple Podcasts, Overcast, Pocket Casts, etc.). It does this by running a small local service on your machine that looks like a normal HTTP podcast feed, while it fetches the real RSS and media opportunistically over Reticulum.

You subscribe to a normal URL (localhost). Your podcast app never needs to understand Reticulum.

## What a normal listener does

1. Install NomadCast.
2. Start the NomadCast daemon.
3. Add a show by pasting a Reticulum podcast locator you found on a NomadNet page.
4. Your podcast app opens and subscribes to a local URL like:
   - http://127.0.0.1:5050/feeds/<identity_hash:ShowName>

After that, your podcast app behaves normally: it sees an RSS feed, downloads episodes, and plays them. NomadCast keeps the feed and media available even when Reticulum is slow or offline by serving a local cache.

## What a publisher does (v0, simplest path)

NomadCast does not generate RSS for you. You publish a normal podcast RSS file and normal media files, and you host them on your existing Reticulum setup using Nomad Network, which already supports hosting pages and files.

### Publish steps (Nomad Network file hosting)

1. Install Nomad Network:
   - pip install nomadnet

2. Run Nomad Network once to initialize your config:
   - nomadnet

3. Put your podcast RSS and media files into your node storage:
   - RSS: ~/.nomadnetwork/storage/files/\<YourShow\>/feed.rss
   - Media: ~/.nomadnetwork/storage/files/\<YourShow\>/media/<episode files>

   Notes:
   - Nomad Network nodes can host files. In NomadNet content, files are typically linked under a file/ path. See Nomad Network docs and community notes for file hosting conventions.
   - Keep your RSS a standard RSS 2.0 feed with <enclosure> URLs. NomadCast will rewrite those URLs for listeners.

4. In your NomadNet page (or wherever you share the show), publish a locator that includes your Reticulum identity hash plus a human-readable show name:
   - <identity_hash:YourShowName>

Listeners paste that string into NomadCast.

Publisher requirement: the identity hash must be stable. Use your existing NomadNet node identity (not a per-run random example identity) so the locator stays valid over time.

## How it works (more technical)

### Components

- nomadcastd (daemon)
  - Runs an HTTP server on 127.0.0.1:5050
  - Maintains a small local cache per show:
    - The most recent fetched RSS bytes
    - The last N episode media objects (default N=5, configurable)
  - Talks to Reticulum (Python RNS) to fetch:
    - The publisher RSS file
    - Episode media objects referenced by the RSS feed

- nomadcast (UI, v0)
  - A minimal Kivy prompt that collects a show locator and writes it to the daemon config.
  - After adding a show, it opens the local subscription URL in the OS (so your default podcast handler can take over).

### Data flow

1. You add a show locator:
   - <identity_hash:ShowName>

2. The daemon creates a local, stable feed URL:
   - http://127.0.0.1:5050/feeds/<identity_hash:ShowName>

3. Podcast app requests the feed:
   - GET /feeds/<identity_hash:ShowName>

4. The daemon responds immediately with cached RSS (if present) and triggers refresh in the background:
   - It fetches the authoritative RSS bytes from the publisher over Reticulum.
   - It stores the raw bytes.
   - It rewrites only the media URLs inside the RSS so enclosures point back to localhost.

5. Podcast app requests episode audio:
   - GET /media/<identity_hash:ShowName>/<episode_id_or_filename>

6. The daemon serves from local cache if available.
   - If not cached, it queues a Reticulum fetch.
   - v0 behavior: it returns an HTTP error quickly (to keep the podcast app from hanging) while the episode is queued for retrieval.
   - When the fetch completes, the next attempt succeeds.

### RSS rewriting rules (v0)

NomadCast is a pass-through for publisher-defined RSS. It does not redesign feeds or strip metadata.

It only rewrites:
- <enclosure url="..."> and any other media URLs that point at the publisher’s Reticulum-hosted objects

Into:
- http://127.0.0.1:5050/media/<identity_hash:ShowName>/<token>

Everything else is preserved, byte-for-byte where feasible:
- title, description, GUID, pubDate, iTunes tags, chapters, artwork references, etc.

### Episode selection and cache policy (v0)

- NomadCast keeps the most recent N episodes per show in the local cache.
- Default N = 5.
- N is configurable per show in the daemon config.

The daemon will:
- Prefer the newest episodes by pubDate (or RSS ordering when pubDate is missing)
- Evict older cached episodes beyond N

### Port choice (v0)

- Default bind: 127.0.0.1:5050
- Rationale: common developer-local port, typically unprivileged, low collision with Reticulum tools.

## Installation notes (developer-oriented)

NomadCast is expected to track the Reticulum ecosystem’s Python-first gravity.

- Python daemon uses RNS.
- Minimal UI is Kivy.

See:
- Reticulum manual: https://markqvist.github.io/Reticulum/manual/
- Reticulum site mirror: https://reticulum.network/manual/
- Nomad Network: https://github.com/markqvist/NomadNet
- Kivy docs: https://kivy.org/doc/stable/

## Roadmap (future capabilities)

- Streaming attempt (best-effort):
  - If a fast uplink exists (eg WiFi/Ethernet encapsulation of Reticulum), attempt on-demand fetch and stream over HTTP to the podcast client.
  - Fall back to queue + retry semantics when the link cannot sustain streaming.

- Better publisher discovery:
  - Resolve human-friendly names to identities when naming systems in the ecosystem mature.
  - Optional index pages or manifests that NomadCast can consume.

- Richer caching logic:
  - Per-feed cache windows (hours/days) and per-episode retention policies.
  - Background refresh scheduling (eg “refresh every 6 hours when reachable”).
  - Smarter eviction based on storage pressure.

- Multiple publishing methods:
  - Additional “how to publish” patterns (beyond Nomad Network file hosting), as community conventions emerge.

- GUI expansion:
  - Manage daemon lifecycle, edit subscribed feeds, view cache status.
  - Optional system tray integration where supported.

- Health endpoint:
  - Add /health for local diagnostics and status.

## Related projects and references

- Reticulum (RNS): https://github.com/markqvist/Reticulum
- Reticulum manual: https://markqvist.github.io/Reticulum/manual/
- Nomad Network: https://github.com/markqvist/NomadNet
- Sideband (LXMF client with GUI): https://github.com/markqvist/Sideband
- MeshChat (web UI LXMF client): https://github.com/liamcottle/reticulum-meshchat
- rBrowser (NomadNet browser UI): https://github.com/fr33n0w/rBrowser
- Reticulum OpenAPI (community experiment): https://github.com/FreeTAKTeam/Reticulum_OpenAPI
- Kivy: https://kivy.org/doc/stable/

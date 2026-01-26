<p align="center">
  <img src="assets/nomadcast-logo.png" alt="NomadCast logo" width="160" />
</p>

<h1 align="center">NomadCast</h1>

<p align="center">
  <img alt="Language" src="https://img.shields.io/badge/language-python-3776AB?logo=python&logoColor=white" />
  <img alt="Protocol" src="https://img.shields.io/badge/protocol-reticulum-0B3D91" />
  <img alt="Ecosystem" src="https://img.shields.io/badge/community-nomadnet-1B998B" />
  <img alt="Status" src="https://img.shields.io/badge/status-experimental-F39C12" />
  <img alt="License" src="https://img.shields.io/badge/license-MIT-2ECC71" />
  <img alt="Data collection" src="https://img.shields.io/badge/data%20collection-none-00C853" />
  <img alt="Usage data" src="https://img.shields.io/badge/usage%20data-none-00C853" />
  <img alt="System identifiers" src="https://img.shields.io/badge/system%20identifiers-none-00C853" />
  <img alt="Dependencies" src="https://img.shields.io/badge/dependencies-reticulum-0B3D91" />
</p>

---

<div align="center">
  <h2>🚧 Active Development — Expect Rough Edges 🚧</h2>
  <p><strong>NomadCast is a work in progress.</strong> It may be incomplete, unstable, or not behave the way you expect yet.</p>
  <p>
    I welcome all feedback and ideas — please share what feels confusing, broken, or missing.
    If you’re an average user, now is a great time to explore the concept: sketch your Reticulum podcast,
    design your show page, and experiment with the flow. Just don’t expect it to be fully reliable quite yet.
  </p>
</div>

---

NomadCast is a friendly bridge between Reticulum-hosted podcasts and the podcast app you already love (Apple Podcasts, Overcast, Pocket Casts, etc.). It runs a tiny local service that looks like a normal HTTP podcast feed, while it quietly fetches the real RSS and audio over Reticulum behind the scenes.

In other words: you subscribe to a normal `localhost` URL, and your podcast app never needs to know Reticulum exists. NomadCast handles the magic for you.

## Privacy and total flexibility

NomadCast is built to be aggressively private and radically user-controlled for listeners and publishers alike:

- **No data collection.** No accounts, no analytics, no telemetry, no usage data, no unique device IDs, no fingerprinting. Your listening habits never leave your machine. NomadCast only requests the exact Reticulum objects you ask it to fetch.
- **Completely open source, MIT licensed.** Every line of code is inspectable and hackable, with a permissive license that keeps you in control.
- **Your preferred player, your feeds, your network.** Pick the podcast app you already trust, then subscribe to any show you want from anywhere on the Reticulum network. NomadCast just bridges the gap and gets out of your way.
- **Publisher-side freedom.** Publish at any bitrate, in any format. Audio-only, video podcasts, experimental formats — if your RSS references it, NomadCast will fetch it as-is over Reticulum.

## Contents

- [What a normal listener does](#what-a-normal-listener-does)
- [What a publisher does (v0, simplest path)](#what-a-publisher-does-v0-simplest-path)
- [Examples tour](#examples-tour)
- [Community conventions](#community-conventions)
- [How it works (more technical)](#how-it-works-more-technical)
- [Source code guide](#source-code-guide)
- [Protocol handler (nomadcast:)](#protocol-handler-nomadcast)
- [Installation notes (developer-oriented)](#installation-notes-developer-oriented)
- [Roadmap (future capabilities)](#roadmap-future-capabilities)
- [Related projects and references](#related-projects-and-references)

## What a normal listener does

Think of this like subscribing to any other podcast, just with one extra helper app.

1. Install NomadCast.
2. Start the NomadCast daemon (it runs quietly in the background).
3. Click a NomadCast podcast link on a NomadNet page; NomadCast pops up to confirm the add.
4. NomadCast adds the show to its config and launches your regular podcast player with a local URL like:
   - http://127.0.0.1:5050/feeds/<identity_hash:ShowName>

After that, your podcast app behaves normally: it sees an RSS feed, downloads episodes, and plays them. NomadCast keeps the feed and episode files available even when Reticulum is slow or offline by serving a local cache.

## What a publisher does (v0, simplest path)

NomadCast does not generate RSS for you. You publish a normal podcast RSS file and normal episode files, and you host them on your existing Reticulum setup using Nomad Network, which already supports hosting pages and files.

If you want a concrete, copy-pastable reference, jump to the [examples tour](#examples-tour) for full sample files you can adapt.

### Publish steps (Nomad Network file hosting)

In your NomadNet page (or wherever you share the show), publish a normal-looking subscribe link that points to the NomadCast locator. This keeps the page clean and gives users one obvious action.

Example:

```micron
[Subscribe to this podcast](nomadcast:a7c3e9b14f2d6a80715c9e3b1a4d8f20:BestPodcastInTheWorld/rss)
```

If you want a fallback for users who cannot click the link, include the raw locator on the next line:

- `nomadcast:a7c3e9b14f2d6a80715c9e3b1a4d8f20:BestPodcastInTheWorld/rss`

Notes:
- `\<destination_hash\>` is the publisher destination hash (32 hex chars) that listeners route to.
- The show name is cosmetic. The destination hash is authoritative.
- Since NomadCast is a new project, consider linking your podcast page back to this repo so listeners can install NomadCast and start using your show right away.

If this project helps you out, a star, watch, share, or a gentle mention goes a long way. Thanks for helping NomadCast find its people. 💛

Micron example (NomadNet-friendly):

```micron
## Subscribe

[Subscribe to this podcast](nomadcast:a7c3e9b14f2d6a80715c9e3b1a4d8f20%3ABestPodcastInTheWorld)

If that link does not open your podcast app, copy and paste that link into [NomadCast](https://github.com/jamesdwilson/nomadcast)
```

On first run, NomadCast registers itself as a system-wide protocol handler for `nomadcast://` links (and the shorter `nomadcast:` form), so clicking the link above will open NomadCast directly on supported systems.


1. Install Nomad Network:
   ```bash
   pip install nomadnet
   ```

2. Run Nomad Network once to initialize your config:
   ```bash
   nomadnet
   ```

3. Put your podcast RSS and episode files into your node storage (Nomad Network hosts them under `/file/`):
   ```text
   RSS: ~/.nomadnetwork/storage/files/<YourShow>/feed.rss
   Episode files: ~/.nomadnetwork/storage/files/<YourShow>/media/<episode files>
   ```

   Notes:
   - Nomad Network nodes can host files. In NomadNet content, files are typically linked under a `/file/` path. Episode media is still just a file, so keep it under the same `/file/` tree.
   - Keep your RSS a standard RSS 2.0 feed with `<enclosure>` URLs. NomadCast will rewrite those URLs for listeners.
   - If you want a starting point, the `examples/storage/files/ExampleNomadCastPodcast/feed.rss` file is ready to copy and rename.

4. In your NomadNet page (or wherever you share the show), publish a locator that includes your Reticulum identity hash plus a human-readable show name:
   ```text
   <identity_hash:YourShowName>
   ```

Listeners paste that string into NomadCast.

Publisher requirement: the identity hash must be stable. Use your existing NomadNet node identity (not a per-run random example identity) so the locator stays valid over time.

## Examples tour

If you learn best by example, there’s a small, cheerful sample podcast site in the `examples/` directory. It is laid out like a fresh Nomad Network storage tree, so you can copy it directly into `~/.nomadnetwork/storage/` if you want a ready-to-run starter webroot. Think of it as a friendly mock webroot for someone brand new to NomadNet.

- `examples/storage/pages/index.mu` — a rich NomadNet page with a subscribe button, episode summaries, and credits.
- `examples/storage/files/ExampleNomadCastPodcast/feed.rss` — a standard RSS 2.0 feed wired up to the sample episodes (with credit notes in the metadata).
- `examples/storage/files/ExampleNomadCastPodcast/media/CCC - Reticulum - Unstoppable Networks for The People-smaller.mp3` — sample audio from a Chaos Communication Congress (CCC) community recording.
- `examples/storage/files/ExampleNomadCastPodcast/media/Option Plus - How to fix the Internet – Nostr, Reticulum and other ideas.mp3` — sample audio referencing the Option Plus podcast.

Each file references the others so you can see the entire flow: NomadNet page → RSS feed → episode files. The example uses a placeholder identity hash (`0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f`), so replace it with your node’s real hash when you publish. You can use these as a template, rename things to your show, and publish with confidence.

## Community conventions

NomadCast aims to follow Reticulum community norms for discoverability and publishing:

- Use Nomad Network file hosting paths (`/file/`) for RSS and episode file links when publishing on NomadNet pages.
- Treat the Reticulum identity hash as the canonical show identifier; the human-readable name is optional and cosmetic.
- Keep RSS feeds standard RSS 2.0 (and iTunes-compatible) so clients and tooling remain interoperable.

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
  - A minimal Tkinter prompt that collects a show locator and writes it to the daemon config.
  - After adding a show, it opens the local subscription URL in the OS (so your default podcast handler can take over).

### Data flow

```mermaid
flowchart LR
  Listener[Listener + Podcast App] -->|GET /feeds + /media| Daemon[nomadcastd HTTP server]
  UI[nomadcast UI] -->|Writes subscription URI| Config[config file]
  Daemon -->|Loads subscriptions| Config
  Daemon -->|Fetch RSS + media| Reticulum[Reticulum Network]
  Reticulum --> Publisher[Publisher RSS + Media]
  Daemon --> Cache[(Local cache)]
  Cache -->|Serve cached feed/media| Listener
```

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
   - Reticulum fetches are application-level requests over an established Link, delivered using Resource (or Bundle for larger payloads).
   - v0 behavior: it returns an HTTP error quickly (to keep the podcast app from hanging) while the episode is queued for retrieval.
   - When the fetch completes, the next attempt succeeds.

Reticulum transfer behavior (v0 expectations):
- Resource transfers are reliable while the Link stays up (packetization, sequencing, integrity checks, retransmits).
- Reticulum does not provide transparent "resume from byte offset" across a broken Link.
- NomadCast v0 retries from scratch if an episode transfer is interrupted.
- Future resume behavior, if desired, should be implemented at the application layer by chunking and deduplicating (for example via Bundle and chunk hashes).

### RSS rewriting rules (v0)

NomadCast is a pass-through for publisher-defined RSS. It does not redesign feeds or strip metadata.

It only rewrites:
- `<enclosure url="...">` and any other media URLs that point at the publisher’s Reticulum-hosted objects

Into:
- `http://127.0.0.1:5050/media/<identity_hash:ShowName>/<token>`

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

## Source code guide

NomadCast is split into a UI package and a daemon package:

- `nomadcast/`: v0 UI and protocol handler entrypoint.
  - `__main__.py` handles CLI invocations (including protocol handler launches).
  - `ui.py` normalizes locators and writes subscriptions to the config.
  - `ui_tk.py` launches the Tkinter UI.
- `nomadcastd/`: the daemon implementation.
  - `daemon.py` orchestrates refreshes, queueing, cache management, and RSS rewrites.
  - `server.py` exposes the HTTP endpoints (`/feeds`, `/media`, `/reload`) and Range support.
  - `rss.py` parses RSS and rewrites enclosure URLs to localhost.
  - `parsing.py` validates `nomadcast:` locators and encodes/decodes show paths.
  - `storage.py` owns on-disk layout helpers and atomic writes.
  - `config.py` reads/writes the INI config format used by the daemon.
  - `fetchers.py` defines the Reticulum fetcher interface (with a mock for tests).

Tests live in `tests/` and focus on parsing, RSS rewriting, and HTTP range behavior.

## Protocol handler (nomadcast:)

NomadCast v0 registers a system URL protocol handler for the `nomadcast:` scheme the first time you run the UI.

Expectation:
- NomadNet users can click a `nomadcast:` link and NomadCast will open.
- NomadCast will add the subscription to the daemon config.
- NomadCast will then auto-launch the system `podcast://` handler to subscribe the user’s podcast app to the local feed URL.

Publisher-facing link format (what you put on a NomadNet page):

- [Subscribe to this podcast](nomadcast://a7c3e9b14f2d6a80715c9e3b1a4d8f20:BestPodcastInTheWorld/rss)

Both `nomadcast://` and the shorter `nomadcast:` form are accepted; use the double-slash form when you want a fully-qualified URL scheme in browsers.

Listener side behavior (v0):
1) Link click launches `nomadcast` with the full `nomadcast:...` URI as an argument.
2) `nomadcast` writes the subscription to config and triggers daemon reload.
3) `nomadcast` opens:

- podcast://127.0.0.1:5050/feeds/a7c3e9b14f2d6a80715c9e3b1a4d8f20%3ABestPodcastInTheWorld

Then `nomadcast` exits.

On first run, NomadCast registers the protocol handler in a platform-native way:

- **Windows:** writes the per-user `HKEY_CURRENT_USER\Software\Classes\nomadcast` registry keys.
- **macOS:** creates a lightweight app bundle in `~/Applications` and registers it with Launch Services.
- **Linux:** writes a `nomadcast.desktop` file under `~/.local/share/applications` and calls `xdg-mime` to set the handler.

This means any publisher-facing page can rely on the scheme opening NomadCast after the UI has been launched once.

## Installation notes (developer-oriented)

NomadCast is expected to track the Reticulum ecosystem’s Python-first gravity.

- Python daemon (`nomadcastd`) uses the Reticulum `RNS` module.
- Minimal UI is Tkinter.
- NomadNet is only required for publishers hosting files; listeners running the daemon do not need it.

### Dependencies

`nomadcastd` requires the Reticulum Python module (`RNS`) in the same environment you run the daemon, even if you already have other Reticulum-based apps (NomadNet, MeshChat, etc.) running elsewhere. Install it with pip:

```bash
pip install reticulum
```

Or follow the canonical Reticulum install instructions:
https://markqvist.github.io/Reticulum/manual/

If you want a requirements file, use `requirements-daemon.txt`, which pins the daemon-only dependency.

### Developer quickstart

NomadCast has no third-party runtime dependencies for the UI, but the daemon needs Reticulum (`RNS`). The easiest path is: clone the repo, create a venv, and install the daemon requirement.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-daemon.txt
cp .env.example .env
```

If you like isolated environments, you can still use a venv; `requirements.txt` is intentionally empty because the UI runs on the Python standard library.
We can add packaging metadata later to support a one-liner `pipx install` experience, but for now the simplest option is just running from the repo.
If you want to override the config path, export `NOMADCAST_CONFIG` (the `.env` file is provided as a convenience for tools like direnv).

```bash
export NOMADCAST_CONFIG=~/.nomadcast/config
```

### Configuration (daemon)

NomadCast reads an INI config file from (first found):

1. `NOMADCAST_CONFIG` (if set)
2. `/etc/nomadcast/config`
3. `~/.config/nomadcast/config`
4. `~/.nomadcast/config`

Default config (created on first run):

```ini
[nomadcast]
listen_host = 127.0.0.1
listen_port = 5050
storage_path = ~/.nomadcast/storage
episodes_per_show = 5
strict_cached_enclosures = yes
rss_poll_seconds = 900
retry_backoff_seconds = 300
max_bytes_per_show = 0
public_host =

[subscriptions]
uri =

[reticulum]
config_dir =
```

Reticulum/NomadNet considerations:

- `listen_host`/`listen_port` control the local HTTP feed server. Leave the default unless you need to bind a different port or non-localhost interface.
- `reticulum.config_dir` lets you point NomadCast at a specific Reticulum/NomadNet config folder if you run multiple nodes, or align with an existing NomadNet config (for example `~/.nomadnetwork`).
- `rss_poll_seconds` and `retry_backoff_seconds` are the main knobs for latency/refresh behavior; higher values reduce background traffic, lower values refresh faster.
- `max_bytes_per_show` and `episodes_per_show` help cap cache size if storage or slow links are a concern.

### Run unit tests

```bash
python -m unittest
```

### Start the daemon (nomadcastd)

```bash
python -m nomadcastd
```

### Start the GUI (nomadcast)

```bash
python -m nomadcast
```

To add a subscription from the command line (simulating a protocol handler click):

```bash
python -m nomadcast "nomadcast:a7c3e9b14f2d6a80715c9e3b1a4d8f20:BestShow/rss"
```

To manage subscriptions directly with the daemon (handy for scripts or headless nodes):

Use the `feeds` subcommands to list (`ls`), add (`add`), or remove (`rm`) subscriptions from the daemon's config:

```bash
python -m nomadcastd feeds ls
python -m nomadcastd feeds add "nomadcast:a7c3e9b14f2d6a80715c9e3b1a4d8f20:BestShow/rss"
python -m nomadcastd feeds rm "a7c3e9b14f2d6a80715c9e3b1a4d8f20:BestShow"
```

You can pair these with `--config` if you want to target a non-default config file.

See:
- Reticulum manual: https://markqvist.github.io/Reticulum/manual/
- Reticulum site mirror: https://reticulum.network/manual/
- Nomad Network: https://github.com/markqvist/NomadNet

## Roadmap (future capabilities)

Detailed tracking now lives in [ROADMAP.md](ROADMAP.md). The items below link to their fuller descriptions:

- [Streaming attempt (best-effort)](ROADMAP.md#streaming-attempt-best-effort)
- [Better publisher discovery](ROADMAP.md#better-publisher-discovery)
- [Richer caching logic](ROADMAP.md#richer-caching-logic)
- [Multiple publishing methods](ROADMAP.md#multiple-publishing-methods)
- [GUI expansion](ROADMAP.md#gui-expansion)
- [Health endpoint](ROADMAP.md#health-endpoint)
- [Daemon-managed hosting pipeline](ROADMAP.md#daemon-managed-hosting-pipeline)

## Related projects and references

- Reticulum (RNS): https://github.com/markqvist/Reticulum
- Reticulum manual: https://markqvist.github.io/Reticulum/manual/
- Nomad Network: https://github.com/markqvist/NomadNet
- Sideband (LXMF client with GUI): https://github.com/markqvist/Sideband
- MeshChat (web UI LXMF client): https://github.com/liamcottle/reticulum-meshchat
- rBrowser (NomadNet browser UI): https://github.com/fr33n0w/rBrowser
- Reticulum OpenAPI (community experiment): https://github.com/FreeTAKTeam/Reticulum_OpenAPI

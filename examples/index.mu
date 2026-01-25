# Example NomadCast Podcast

Welcome to **Example NomadCast Podcast**, a miniature podcast portal that shows how a Reticulum-hosted show can feel *delightfully normal* inside your favorite podcast app. It’s a full, end-to-end example: page → RSS → media → subscribe.

---

## Subscribe ✨

[**Subscribe to this podcast**](nomadcast:0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f:ExampleNomadCastPodcast/rss)

If that link doesn’t open your podcast app, paste it into [NomadCast](https://github.com/jamesdwilson/nomadcast). NomadCast will open your podcast app and handle the local feed URL for you.

---

## Why this is worth a listen

- **See the flow**: this page points to the RSS file, and the RSS file points to the media.
- **Reticulum-ready**: everything is hosted under a Nomad Network `/file/` path.
- **Easy to remix**: copy these files, rename the show, and publish your own.

---

## Current episodes

### 🎙️ CCC — Reticulum: Unstoppable Networks for The People

A community talk about Reticulum as a people-first, unstoppable networking layer — the *why* behind resilient, local-first connectivity.

- **Credit**: Chaos Communication Congress (CCC) community recording
- **Media file**: `/file/ExampleNomadCastPodcast/media/CCC - Reticulum - Unstoppable Networks for The People-smaller.mp3`
- **Repo file**: `examples/media/CCC - Reticulum - Unstoppable Networks for The People-smaller.mp3`
- **RSS entry**: see `examples/example.rss`

### 🌐 Option Plus — How to Fix the Internet (Nostr, Reticulum, and other ideas)

A hopeful, big-ideas conversation about rebuilding the internet with Nostr, Reticulum, and a constellation of other tools.

- **Credit**: Option Plus podcast
- **Media file**: `/file/ExampleNomadCastPodcast/media/Option Plus - How to fix the Internet – Nostr, Reticulum and other ideas.mp3`
- **Repo file**: `examples/media/Option Plus - How to fix the Internet – Nostr, Reticulum and other ideas.mp3`
- **RSS entry**: see `examples/example.rss`

---

## Files you can copy

- **RSS feed**: `/file/ExampleNomadCastPodcast/rss.xml` (source: `examples/example.rss`)
- **Media folder**: `/file/ExampleNomadCastPodcast/media/` (source: `examples/media/`)

---

## Start your own show

1. Replace the placeholder hash `0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f` with your node’s Reticulum identity hash.
2. Copy `examples/example.rss` and update the channel title, description, and episode list.
3. Drop your audio files into `examples/media/` and update the `<enclosure>` URLs.
4. Host the RSS and media files under your Nomad Network node’s `/file/` path.
5. Share a `nomadcast:` link with your Reticulum identity hash so listeners can subscribe in one click.

When you’re ready, replace the credits above with your own show details and watch your podcast take off. 🚀

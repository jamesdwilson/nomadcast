# {c:teal}Example NomadCast Podcast{c}

Welcome to **{c:orange}Example NomadCast Podcast{c}**, a miniature podcast portal that shows how a Reticulum-hosted show can feel **delightfully normal** inside your favorite podcast app.

{c:mutedred}End-to-end flow:{c} page → RSS → episode files → subscribe.

---

## {c:orange}Subscribe{c} ✨

[**{c:teal}Subscribe to this podcast{c}**](nomadcast://0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f:ExampleNomadCastPodcast)

{c:mutedred}If the link does not open your podcast app:{c} copy and paste it into NomadCast:
[NomadCast](https://github.com/jamesdwilson/nomadcast)

NomadCast will open your podcast app and handle the local feed URL for you.

---

## {c:teal}Why this is worth a listen{c}

- **{c:orange}See the full chain{c}:** this page points to the RSS file, and the RSS file points to the episode files.
- **{c:orange}Reticulum-ready{c}:** everything is hosted under a Nomad Network `/file/` path.
- **{c:orange}Easy to remix{c}:** copy these files, rename the show, and publish your own.

---

## {c:teal}Current episodes{c}

### {c:orange}🎙️ CCC — Reticulum: Unstoppable Networks for The People{c}

A community talk about Reticulum as a people-first, unstoppable networking layer, and the *why* behind resilient, local-first connectivity.

- **{c:teal}Credit{c}:** Chaos Communication Congress (CCC) community recording
- **{c:teal}Episode file{c}:** `/file/ExampleNomadCastPodcast/media/CCC - Reticulum - Unstoppable Networks for The People-smaller.mp3`
- **{c:teal}Repo file{c}:** `examples/storage/files/ExampleNomadCastPodcast/media/CCC - Reticulum - Unstoppable Networks for The People-smaller.mp3`
- **{c:teal}RSS entry{c}:** see `examples/storage/files/ExampleNomadCastPodcast/feed.rss`

### {c:orange}🌐 Option Plus — How to Fix the Internet (Nostr, Reticulum, and other ideas){c}

A hopeful, big-ideas conversation about rebuilding the internet with Nostr, Reticulum, and a constellation of other tools.

- **{c:teal}Credit{c}:** Option Plus podcast
- **{c:teal}Episode file{c}:** `/file/ExampleNomadCastPodcast/media/Option Plus - How to fix the Internet – Nostr, Reticulum and other ideas.mp3`
- **{c:teal}Repo file{c}:** `examples/storage/files/ExampleNomadCastPodcast/media/Option Plus - How to fix the Internet – Nostr, Reticulum and other ideas.mp3`
- **{c:teal}RSS entry{c}:** see `examples/storage/files/ExampleNomadCastPodcast/feed.rss`

---

## {c:teal}Files you can copy{c}

- **{c:orange}RSS feed{c}:** `/file/ExampleNomadCastPodcast/feed.rss`  {c:mutedred}(source: `examples/storage/files/ExampleNomadCastPodcast/feed.rss`){c}
- **{c:orange}Episode folder{c}:** `/file/ExampleNomadCastPodcast/media/`  {c:mutedred}(source: `examples/storage/files/ExampleNomadCastPodcast/media/`){c}

---

## {c:teal}Start your own show{c}

1. Replace the placeholder hash `{c:orange}0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f{c}` with your node's Reticulum identity hash.
2. Copy `examples/storage/files/ExampleNomadCastPodcast/feed.rss` and update the channel title, description, and episode list.
3. Drop your audio files into `examples/storage/files/ExampleNomadCastPodcast/media/` and update the `<enclosure>` URLs.
4. Host the RSS and episode files under your Nomad Network node's `/file/` path.
5. Share a `nomadcast://` link with your Reticulum identity hash so listeners can subscribe in one click.

{c:mutedred}When you are ready, replace the credits above with your own show details and ship it.{c}

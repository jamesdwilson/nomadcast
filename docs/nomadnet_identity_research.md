## NomadNet identity + hosting notes (source review)

### Dev task: improve NomadCast sample identity detection

**Goal:** Update the sample creator so it detects the correct NomadNet identity
hash reliably, matching NomadNet’s own storage layout and file formats.

**Acceptance criteria**
- Use NomadNet’s configdir precedence (`/etc/nomadnetwork` → `~/.config/nomadnetwork` → `~/.nomadnetwork`) when locating identity data.
- Prefer `<configdir>/storage/identity` and parse it as an RNS identity file.
- Only fall back to text-based scanning if the identity file is missing or
  unreadable.
- Surface the detected source in the UI (e.g., “Detected from
  ~/.nomadnetwork/storage/identity”) so users can verify it quickly.

**Implementation notes**
- The current `detect_nomadnet_identity()` scans hard-coded paths in
  `nomadcast_sample/sample_installer.py`. It should be refactored to resolve a
  single configdir first, then read `<configdir>/storage/identity`.
- The identity file is binary; parse it with `RNS.Identity.from_file()` to get
  the hash.

### Where NomadNet stores the identity

NomadNet chooses a config directory in this order:

1. `/etc/nomadnetwork` (if it exists and has a `config` file)
2. `~/.config/nomadnetwork` (if it exists and has a `config` file)
3. `~/.nomadnetwork` (fallback)

The primary identity file lives at:

```
<configdir>/storage/identity
```

NomadNet loads that identity at startup, or creates it if missing.

**Important:** this file is a binary RNS identity file, so its contents will
look like unreadable bytes if you open it in a text editor. To extract the
identity hash, you need to parse it with Reticulum (for example,
`RNS.Identity.from_file()`), not grep it as plain text.

### Which ID is used for hosting pages/files

The node registers its inbound destination as:

```
RNS.Destination(self.identity, RNS.Destination.IN, RNS.Destination.SINGLE, "nomadnetwork", "node")
```

So the *identity hash* (not the destination hash) is the stable ID you should
share in links (for example, in `nomadcast://<identity_hash>:ShowName` or
MeshChat-style `identity_hash:/file/...` URLs).

### Source references

- `NomadNetworkApp.py` shows configdir selection and the `storage/identity` file,
  along with identity creation/loading during startup:
  https://github.com/markqvist/NomadNet/blob/master/nomadnet/NomadNetworkApp.py
- `Node.py` shows the destination being created from the primary identity with
  the `"nomadnetwork"` / `"node"` aspects, confirming the identity hash is the
  canonical ID to share:
  https://github.com/markqvist/NomadNet/blob/master/nomadnet/Node.py

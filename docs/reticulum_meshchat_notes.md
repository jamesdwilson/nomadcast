# Reticulum MeshChat NomadNet URL handling notes

These notes summarize the behavior in the open-source Reticulum MeshChat
project (`liamcottle/reticulum-meshchat`) as it relates to NomadNet resource
fetching. The MeshChat downloader treats the URL prefix as an **identity hash**
and then derives a `Destination` by combining that identity with the NomadNet
app/aspect values. This explains why MeshChat accepts links like
`<identity_hash>:/file/...` and why a destination-hash-only lookup can fail
when the input is actually an identity hash.

Reference implementation (excerpted from MeshChat's `NomadnetDownloader` in
`meshchat.py`):

```
# create destination to nomadnet node
identity = RNS.Identity.recall(self.destination_hash)
destination = RNS.Destination(
    identity,
    RNS.Destination.OUT,
    RNS.Destination.SINGLE,
    self.app_name,
    self.aspects,
)
```

MeshChat sets `self.app_name = "nomadnetwork"` and `self.aspects = "node"`
for NomadNet downloads, which means it **always** derives the destination from
an identity hash rather than expecting a destination hash directly.

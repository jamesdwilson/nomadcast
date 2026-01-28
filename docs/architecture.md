# Architecture & Readability Standards

This project favors **readability-first** code organization. The goal is to keep responsibilities clear so
contributors can find and understand behavior quickly. This document defines package boundaries,
dependency direction rules, and documentation conventions.

## Package boundaries

NomadCast is split into two primary packages plus supporting modules:

### UI (client-facing)
**Package:** `nomadcast/`

**Responsibilities**
- UI entrypoints, protocol handler wiring, and OS integration.
- User interactions and validation before writing config.
- Launching the default podcast handler with the local feed URL.

**Examples**
- `nomadcast/__main__.py` (CLI/protocol handler entrypoint)
- `nomadcast/ui.py` (locator normalization + config writes)
- `nomadcast/ui_tk.py` (Tkinter UI)

### Domain (core behavior)
**Package:** `nomadcastd/`

**Responsibilities**
- Parsing show locators, feed paths, and request inputs.
- RSS rewriting rules and cache policy decisions.
- Storage layout helpers and atomic file I/O decisions.
- Configuration schema and defaults.

**Examples**
- `nomadcastd/parsing.py`
- `nomadcastd/rss.py`
- `nomadcastd/storage.py`
- `nomadcastd/config.py`

### Services (integrations + adapters)
**Package:** `nomadcastd/` (service modules live alongside domain code)

**Responsibilities**
- Reticulum fetcher implementations and mocks.
- HTTP server boundary + request/response translation.
- Background scheduling, queuing, and orchestration.

**Examples**
- `nomadcastd/fetchers.py`
- `nomadcastd/server.py`
- `nomadcastd/daemon.py`

> Note: We currently co-locate domain and service modules under `nomadcastd/`. The boundary is
> conceptual: domain code is pure business logic; services are the I/O edges.

## Dependency direction rules

Keep dependencies flowing **inward** toward the domain:

```
UI -> Domain <- Services
```

Rules of thumb:

1. **Domain is the stability core.** Domain modules must not import UI code or service adapters.
2. **Services can depend on domain.** Services translate external systems (HTTP, Reticulum, filesystem)
   into domain-friendly structures.
3. **UI depends on domain types, not on services.** The UI should avoid direct network or daemon
   implementation details. It should write config and trigger daemon reloads via documented entrypoints.
4. **Avoid circular imports.** If you need shared utilities, put them in domain modules or a small
   `nomadcastd` helper module that has no side effects.

When in doubt, ask: *“Can this logic be tested without touching the network or filesystem?”* If yes,
it belongs in the domain layer.

## Docstrings and type hints

### Docstrings
- **Public functions/classes must have docstrings** describing intent, inputs, outputs, and side effects.
- **Keep docstrings concise but specific.** Prefer a brief summary + bullet list for tricky behavior.
- **Clarify invariants and units.** Example: “`ttl_seconds` is in seconds; `0` disables caching.”

### Type hints
- **Type hints are expected for all new or modified functions.**
- **Prefer precise types.** Use `Path`, `Optional`, `Iterable`, `Mapping`, `Sequence`, or
  `Literal` where clarity improves readability.
- **Avoid `Any` unless bridging untyped libraries.** If you must use `Any`, explain why in a short
  comment.

## Comments vs. docstrings

Use **docstrings** for *why/what* at the API boundary and **comments** for *why/how* inside the body.

### Use docstrings when:
- Defining a function/class/module that others will import.
- The behavior is not obvious from the signature.
- There are side effects, I/O, or implicit assumptions.

### Use comments when:
- You need to explain *why* a non-obvious step exists.
- You are documenting a workaround, protocol quirk, or external limitation.
- The code is intentionally non-idiomatic for a good reason.

### Avoid
- Comments that repeat the code (`# increment i` when `i += 1`).
- Docstrings that restate type hints without adding meaning.

## Practical examples

**Good docstring**

```python

def rewrite_enclosure_urls(rss_bytes: bytes, host: str) -> bytes:
    """Rewrite enclosure URLs in the RSS feed to point at localhost.

    - Preserves non-enclosure metadata.
    - Expects a valid RSS 2.0 feed; raises ValueError if parsing fails.
    """
```

**Good comment**

```python
    # Reticulum does not support resume-bytes; retry from scratch to avoid partial files.
```

---

If you’re unsure where code belongs, add a small note in your PR describing the boundary decision.

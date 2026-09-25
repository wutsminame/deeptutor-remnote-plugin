# DeepTutor RemNote Patch

This repository contains **only the DeepTutor-side integration patch** for using a separately deployed RemNote mirror/sync service as a read-only external knowledge source.

It does **not** contain:

- the RemNote desktop plugin;
- the RemNote sync/search service;
- Docker/Caddy/systemd deployment for that service;
- any production credentials, databases, note content, or host-specific configuration.

The original RemNote plugin repository remains separate and unchanged:

- <https://github.com/wutsminame/remnote-deeptutor-sync>

## Contents

- `patches/deeptutor-remnote.patch` — the complete DeepTutor-side patch.
- `PATCH_BASE` — exact upstream DeepTutor commit for the patch.
- `tests/test_integration.py` — focused tests against a patched DeepTutor checkout.
- `examples/remnote-connections.example.json` — credential-free server-side connection shape.
- `docs/APPLY_AND_UPGRADE.md` — apply, configure, test, upgrade, and rollback procedure.
- `upstream/` — DeepTutor Apache-2.0 license and third-party notices.

## Patch baseline

```text
897fce52f24bf22e6e50d8a3e4df532632a26322
```

The patch touches 26 DeepTutor paths and adds:

- a read-only `remnote` knowledge capability;
- `remnote_search`, `remnote_read`, `remnote_navigate`, and `remnote_status` tools;
- server-owned connection resolution and response-size/encoding bounds;
- administrator-only pairing and embedding proxy routes;
- Knowledge Center connection and settings UI;
- bilingual labels, icon, and focused tests.

## Apply

From a clean DeepTutor checkout at the baseline commit:

```bash
git apply --check /path/to/deeptutor-remnote-patch/patches/deeptutor-remnote.patch
git apply /path/to/deeptutor-remnote-patch/patches/deeptutor-remnote.patch
```

Do not force-apply the patch to another revision. Follow `docs/APPLY_AND_UPGRADE.md` and port conflicts manually in a disposable worktree.

## Service boundary

The patched DeepTutor code expects a separately deployed RemNote service and server-owned connection configuration. The browser and model must never receive read/admin tokens or choose arbitrary service URLs.

This repository deliberately does not implement or publish the RemNote-side component.

## License

Apache License 2.0. See `LICENSE`, `NOTICE`, and `upstream/`.

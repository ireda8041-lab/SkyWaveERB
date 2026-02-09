## Release Notes - v2.2.2 (2026-02-09)

### Stability
- Hybrid sync scheduling was stabilized to avoid redundant full-sync loops.
- Shutdown flow was hardened to prevent SQLite closed-database race conditions.
- Realtime fallback logging is now quieter and more actionable.

### Sync & Realtime
- Delta sync remains active as reliable fallback when Change Streams are not available.
- Startup no longer performs avoidable extra full sync on initial online detection.

### Packaging
- Version metadata updated to `2.2.2`.
- Installer version updated to `2.2.2`.
- Release build script now reads version dynamically from `version.json`.

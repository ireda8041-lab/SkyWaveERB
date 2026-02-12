## Release Notes - v2.2.7 (2026-02-12)

### Cross-Device Sync Reliability
- Delta sync now uses MongoDB server time for `last_modified` writes to eliminate client clock drift issues.
- Watermark future-time guards now compare against server time, reducing delayed pull behavior.
- `emit_data_changed` now emits an explicit sync ping per table so other devices pull changes quickly.

### Notification and UX Stability
- Settings update toast spam is suppressed for both new and legacy payload formats.
- Notification worker dedupe was hardened to avoid reprocessing loops and random burst refreshes.
- Realtime event handling now refreshes UI with `emit_ui_data_changed` to avoid sync echo loops.

### Change Streams
- Existing Replica Set bootstrap and reconnect improvements remain active.
- If MongoDB is not running as Replica Set, system continues on fast Delta fallback without breaking.

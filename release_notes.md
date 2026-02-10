## Release Notes - v2.2.4 (2026-02-10)

### Realtime Sync
- Delta sync now runs in a background thread for true realtime updates.
- Cross-device refresh stays responsive even during heavy UI work.

### Stability
- Dirty flags are cleared on successful online sync to avoid repeat pushes.
- Closed-database errors during shutdown are suppressed safely.

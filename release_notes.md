## Release Notes - v2.2.9 (2026-03-03)

### Stability and Freeze Fixes
- MongoDB connection checks in sync manager are now non-blocking and no longer stall the UI thread.
- Online state checks use cached probe status on UI paths, with bounded background probes for safety.
- Main window refresh behavior was tuned with stronger debounce/cooldown settings under sync bursts.

### Sync and Notification Performance
- Notification polling now uses adaptive idle backoff to reduce unnecessary background pressure.
- Full-sync completion no longer triggers redundant full-tab refresh flow.
- Sync-triggered UI updates are smoother when rapid changes arrive from realtime/delta channels.

### Update Reliability
- `auto_updater.py` now correctly parses GitHub Releases API payloads (`tag_name`, assets, release body).
- Version metadata updated for `v2.2.9` and release download path prepared for installer rollout.

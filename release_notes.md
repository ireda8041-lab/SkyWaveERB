## Release Notes - v2.2.8 (2026-02-14)

### UI and Layout Stability
- New Project dialog now opens with a correct first-render layout without requiring manual resize.
- Responsive sizing logic was hardened across startup/show/resize cycles for consistent behavior on different screen sizes.
- Notes and payment side panels now keep better proportional space with smoother scroll handling.

### Sync and Realtime Reliability
- Instant sync worker now falls back safely when lightweight repositories miss full table-reconcile dependencies.
- Repository compatibility checks were hardened to avoid background worker crashes in edge test/runtime scenarios.

### Deployment and Operations
- Added remote MongoDB replica-set helper (`tools/enable_remote_replset.py`) for server-side professional setup.
- Added stable per-device identity utility (`core/device_identity.py`) to reduce cross-device collision risk.

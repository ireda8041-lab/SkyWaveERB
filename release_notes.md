## Release Notes - v2.2.3 (2026-02-09)

### Realtime Sync (No Replica Set)
- Delta sync tightened to 1s for near-instant propagation.
- Notification poller now triggers instant sync on new events.
- Live sync triggers are non-blocking to avoid UI freezes.

### Data Integrity
- Soft-delete propagation ensures deletions appear across devices.

### Notifications
- Entity metadata is included to refresh only the affected tables.

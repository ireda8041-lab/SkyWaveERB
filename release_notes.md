## Release Notes - v2.2.6 (2026-02-12)

### Realtime + Change Streams
- Realtime sync now retries support detection after safe local Replica Set bootstrap.
- Local Mongo URIs are normalized automatically to include `replicaSet` and `directConnection=false`.
- Change Stream watcher now runs as a unified database stream for better event reliability.

### Sync Stability
- Repository reconnect now refreshes runtime Mongo URI/DB values before creating new clients.
- Fallback to Delta Sync remains active and stable when Change Streams are unavailable.

### Settings UX
- Cloud connection test now reports both connectivity and Change Streams capability clearly.
- Sync settings persist local replica-set bootstrap options for predictable behavior.

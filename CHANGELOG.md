## [2.2.8] - 2026-02-14

### Fixed
- New Project dialog first-open layout no longer requires manual resize to render correctly.
- Instant sync background worker now falls back safely for lightweight repositories and test stubs.

### Changed
- Project editor responsive behavior was stabilized across startup/show/resize cycles.
- Added remote replica-set enablement helper for MongoDB servers (`tools/enable_remote_replset.py`).
- Added stable per-device identity helper (`core/device_identity.py`).

---
# ðŸ“ Ø³Ø¬Ù„ Ø§Ù„ØªØºÙŠÙŠØ±Ø§Øª - Changelog

Ø¬Ù…ÙŠØ¹ Ø§Ù„ØªØºÙŠÙŠØ±Ø§Øª Ø§Ù„Ù…Ù‡Ù…Ø© ÙÙŠ Ù‡Ø°Ø§ Ø§Ù„Ù…Ø´Ø±ÙˆØ¹ Ø³ÙŠØªÙ… ØªÙˆØ«ÙŠÙ‚Ù‡Ø§ ÙÙŠ Ù‡Ø°Ø§ Ø§Ù„Ù…Ù„Ù.

---

## [2.2.6] - 2026-02-12

### Fixed
- Realtime sync now re-checks Change Streams support after local bootstrap attempt.
- Mongo reconnect flow now always reloads URI/DB from runtime config before reconnect.

### Changed
- Added safe local Replica Set bootstrap flow for localhost Mongo deployments.
- Normalized local Mongo URIs to include replica-set query parameters automatically.
- Replaced per-collection watcher loop with a single database Change Stream watcher.
- Cloud connection test now validates Change Streams support and reports fallback clearly.

---

## [2.2.5] - 2026-02-10

### Fixed
- Guard future watermarks to avoid missed delta updates.
- Settings sync respects newer local settings and pushes upstream.
- Manual sync runs in background without UI freeze.

### Changed
- Settings sync can be triggered by notification events.
- Main tabs and settings sub-tabs adapt better on small screens.
- Project dialog becomes scrollable on small displays.

---

## [2.2.4] - 2026-02-10

### Fixed
- Delta sync now runs in a background thread to avoid UI-blocked stalls.
- Dirty flags are cleared on successful online sync to prevent repeat pushes.
- Closed-database errors during shutdown are suppressed safely.

### Changed
- Cross-device refresh remains responsive during heavy UI work.

---

## [2.2.3] - 2026-02-09

### Fixed
- Soft-delete propagation now reaches all devices via delta sync.
- Notification polling query corrected for reliable cross-device alerts.
- Live sync triggers are non-blocking to avoid UI freezes.

### Changed
- Delta sync interval set to 1s for near-instant updates without replica set.
- Notifications now include entity metadata and trigger fast refresh.

---

## [2.2.2] - 2026-02-09

### Fixed
- Stabilized hybrid sync scheduling to prevent redundant full-sync cycles when delta sync is active.
- Added safer shutdown handling to avoid late-thread SQLite closed-database errors.
- Reduced noisy realtime fallback warnings when MongoDB Change Streams are unavailable.
- Moved NotificationBridge initialization to run after `QApplication` creation.

### Changed
- Default full sync interval tuned for production stability (`300s`).
- Release metadata and installer/version tooling updated for `v2.2.2`.

---

## [2.1.0] - 2026-01-31

### âœ¨ Added
- Ø¥Ø¶Ø§ÙØ© ØªØ§Ø¨ Ø·Ø±Ù‚ Ø§Ù„Ø¯ÙØ¹ ÙÙŠ Ø§Ù„Ø¥Ø¹Ø¯Ø§Ø¯Ø§Øª.
- Ø¥Ø¶Ø§ÙØ© ØªØ§Ø¨ Ù…Ù„Ø§Ø­Ø¸Ø§Øª Ø§Ù„Ù…Ø´Ø§Ø±ÙŠØ¹ ÙÙŠ Ø§Ù„Ø¥Ø¹Ø¯Ø§Ø¯Ø§Øª.
- Ø¥Ø¶Ø§ÙØ© Ø®ÙŠØ§Ø± Ø¥Ø¶Ø§ÙØ© Ù…ØµØ±ÙˆÙ Ù…Ù† Ù‚Ø§Ø¦Ù…Ø© Ø§Ù„Ù…Ø´Ø§Ø±ÙŠØ¹.

### ðŸ”§ Changed
- Ø¬Ø¹Ù„ Ù†Ø§ÙØ°Ø© Ø¥Ù†Ø´Ø§Ø¡ Ø§Ù„Ù…Ø´Ø§Ø±ÙŠØ¹ ØºÙŠØ± Ù…Ø´Ø±ÙˆØ·Ø© (ÙŠÙ…ÙƒÙ† ØªØµØºÙŠØ±Ù‡Ø§).
- ØªØ­Ø³ÙŠÙ† Ø³Ø±Ø¹Ø© ØªØ­Ù…ÙŠÙ„ Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª ÙÙŠ Ø´Ø§Ø´Ø© Ø§Ù„Ù…Ø¹Ø§ÙŠÙ†Ø©.
- ØªØ­Ø³ÙŠÙ† Ø§Ø³ØªØ¬Ø§Ø¨Ø© Ø´Ø§Ø´Ø© ØªØ³Ø¬ÙŠÙ„ Ø§Ù„Ø¯Ø®ÙˆÙ„.

### ðŸ”§ Fixed
- Ø¥ØµÙ„Ø§Ø­ Ù…Ø´ÙƒÙ„Ø© Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ù‚Ø¯ÙŠÙ…Ø© ÙÙŠ Ø´Ø§Ø´Ø© Ø§Ù„Ù…Ø¹Ø§ÙŠÙ†Ø©.

---

## [2.0.7] - 2026-01-31

### ðŸ”§ Fixed
- `ui/main_window.py` (L1, L1346, L1694): Ø¥Ø³ÙƒØ§Øª ØªØ­Ø°ÙŠØ±Ø§Øª Pylint Ø§Ù„Ø®Ø§ØµØ© Ø¨Ø­Ø¬Ù… Ø§Ù„Ù…Ù„Ù ÙˆÙƒØ«Ø±Ø© Ø¨Ø§Ø±Ø§Ù…ÙŠØªØ±Ø§Øª Ø§Ù„Ø¯ÙˆØ§Ù„ØŒ Ù…Ø¹ Ø§Ø³ØªØ«Ù†Ø§Ø¡ Ø£Ø³Ù…Ø§Ø¡ Qt overrides (`resizeEvent`/`closeEvent`) Ø¨Ø¯ÙˆÙ† ØªØºÙŠÙŠØ± Ø³Ù„ÙˆÙƒÙ‡Ø§.
- `ui/settings_tab.py` (L1): Ø¥Ø³ÙƒØ§Øª ØªØ­Ø°ÙŠØ±Ø§Øª Pylint Ø§Ù„Ø®Ø§ØµØ© Ø¨Ø­Ø¬Ù… Ø§Ù„Ù…Ù„Ù ÙˆÙƒØ«Ø±Ø© public methods Ø¨Ø³Ø¨Ø¨ Ø·Ø¨ÙŠØ¹Ø© Ø§Ù„ØªØ§Ø¨.
- `ui/status_bar_widget.py` (L494): Ø¥Ø³ÙƒØ§Øª ØªØ­Ø°ÙŠØ± Pylint Ù„Ø§Ø³Ù… Qt override (`closeEvent`) Ø¨Ø¯ÙˆÙ† ØªØºÙŠÙŠØ± Ø§Ù„Ø³Ù„ÙˆÙƒ.
- `services/accounting_service.py` (L1, L1873, L3236, L2550, L2832): Ø¥Ø²Ø§Ù„Ø© Ø£Ù‚ÙˆØ§Ø³ Ø²Ø§Ø¦Ø¯Ø© Ø¨Ø¹Ø¯ `not`ØŒ ÙˆØ¥Ø³ÙƒØ§Øª ØªØ­Ø°ÙŠØ±Ø§Øª Pylint Ø§Ù„Ù‡ÙŠÙƒÙ„ÙŠØ© (ÙƒØ¨Ø± Ø§Ù„Ù…Ù„Ù/ØªØ¯Ø§Ø®Ù„/Ø¹Ø¯Ø¯ Ø¨Ø§Ø±Ø§Ù…ÙŠØªØ±Ø§Øª) Ù…Ø¹ Ø§Ù„Ø­ÙØ§Ø¸ Ø¹Ù„Ù‰ Ø§Ù„Ù…Ù†Ø·Ù‚.
- `services/printing_service.py` (L1): Ø¥Ø³ÙƒØ§Øª ØªØ­Ø°ÙŠØ±Ø§Øª Pylint Ø§Ù„Ø®Ø§ØµØ© Ø¨Ø­Ø¬Ù… Ø§Ù„Ù…Ù„Ù ÙˆØ¹Ø¯Ø¯ Ø§Ù„Ø¨Ø§Ø±Ø§Ù…ÙŠØªØ±Ø§Øª Ù„Ø¨Ø¹Ø¶ Ø§Ù„Ø¯ÙˆØ§Ù„.
- `services/template_service.py` (L1, L20-L41, L923+): Ø¬Ø¹Ù„ Ø§Ø³ØªÙŠØ±Ø§Ø¯ WeasyPrint/pdfkit/WebEngine Ø§Ø®ØªÙŠØ§Ø±ÙŠ ÙˆØ¢Ù…Ù† Ø¹Ù„Ù‰ Windows (Ø§Ù„ØªÙ‚Ø§Ø· `OSError` Ø£Ø«Ù†Ø§Ø¡ Ø§Ù„Ø§Ø³ØªÙŠØ±Ø§Ø¯) Ù„Ù…Ù†Ø¹ ÙƒØ³Ø± ØªØ´ØºÙŠÙ„ Ø§Ù„Ø¨Ø±Ù†Ø§Ù…Ø¬ Ø¹Ù†Ø¯ ØºÙŠØ§Ø¨ Ù…ÙƒØªØ¨Ø§Øª Ø§Ù„Ù†Ø¸Ø§Ù….
- `ui/notification_system.py` (L1, L282): Ø¥Ø³ÙƒØ§Øª ØªØ­Ø°ÙŠØ± Pylint Ù„Ø§Ø³Ù… Qt override (`mousePressEvent`) ÙˆØªØ­Ø°ÙŠØ± ÙƒØ«Ø±Ø© Ø§Ù„Ø¨Ø§Ø±Ø§Ù…ÙŠØªØ±Ø§Øª.
- `ui/project_manager.py` (L1, L1681, L2029, L3386): Ø¥Ø³ÙƒØ§Øª ØªØ­Ø°ÙŠØ±Ø§Øª Pylint Ø§Ù„Ø®Ø§ØµØ© Ø¨Ø­Ø¬Ù… Ø§Ù„Ù…Ù„Ù/Ø§Ù„ØªØ¯Ø§Ø®Ù„/Ø¹Ø¯Ø¯ Ø§Ù„Ø¨Ø§Ø±Ø§Ù…ÙŠØªØ±Ø§Øª + Ø§Ø³ØªØ«Ù†Ø§Ø¡ Ø£Ø³Ù…Ø§Ø¡ Qt overrides + ØªØ­Ø³ÙŠÙ† `sum` Ù„Ø§Ø³ØªØ®Ø¯Ø§Ù… generator.
- `ui/todo_manager.py` (L2): Ø¥Ø³ÙƒØ§Øª ØªØ­Ø°ÙŠØ±Ø§Øª Pylint Ø§Ù„Ø®Ø§ØµØ© Ø¨Ø­Ø¬Ù… Ø§Ù„Ù…Ù„Ù ÙˆÙƒØ«Ø±Ø© public methods ÙˆØ¹Ø¯Ø¯ Ø§Ù„Ø¨Ø§Ø±Ø§Ù…ÙŠØªØ±Ø§Øª.
- `core/repository.py` (L1): Ø¥Ø³ÙƒØ§Øª ØªØ­Ø°ÙŠØ±Ø§Øª Pylint Ø§Ù„Ø®Ø§ØµØ© Ø¨Ø§Ù„ØªÙƒØ±Ø§Ø± (R0801) ÙˆØ¨Ù†ÙŠØ© Ø§Ù„Ù…Ù„Ù Ø§Ù„ÙƒØ¨ÙŠØ±Ø©.
- `pyproject.toml` (L201): ØªØ¹Ø·ÙŠÙ„ `R0801` Ø¹Ù„Ù‰ Ù…Ø³ØªÙˆÙ‰ Ø§Ù„Ù…Ø´Ø±ÙˆØ¹ Ù„ØªØ¬Ù†Ø¨ Ø¶Ø¬ÙŠØ¬ duplicate-code Ø§Ù„Ù†Ø§ØªØ¬ Ø¹Ù† Ø£Ù†Ù…Ø§Ø· fallback Ø§Ù„Ù…ØªÙƒØ±Ø±Ø©.

### ðŸ§ª Tests
- `tests/test_smoke_imports.py`: Ø¥Ø¶Ø§ÙØ© Ø§Ø®ØªØ¨Ø§Ø± Smoke Ù„Ù„ØªØ­Ù‚Ù‚ Ù…Ù† Ø¥Ù…ÙƒØ§Ù†ÙŠØ© Ø§Ø³ØªÙŠØ±Ø§Ø¯ Ø§Ù„ÙˆØ­Ø¯Ø§Øª Ø§Ù„Ù…Ø³ØªÙ‡Ø¯ÙØ© Ø¨Ø¯ÙˆÙ† Ø£Ø®Ø·Ø§Ø¡ ÙˆÙ‚Øª ØªØ´ØºÙŠÙ„.

---

## [2.0.1] - 2026-01-20

### ðŸ”§ Ø¥ØµÙ„Ø§Ø­Ø§Øª Ø­Ø±Ø¬Ø©
- **Ø¥ØµÙ„Ø§Ø­ Ù…Ø´ÙƒÙ„Ø© Database bool() Ø§Ù„Ø­Ø±Ø¬Ø©**
  - ØªÙ… Ø¥ØµÙ„Ø§Ø­ Ø®Ø·Ø£ "Database objects do not implement truth value testing"
  - Ø§Ø³ØªØ¨Ø¯Ø§Ù„ Ø¬Ù…ÙŠØ¹ Ø­Ø§Ù„Ø§Øª `if repo:` Ø¨Ù€ `if repo is not None:`
  - ØªØ­Ø³ÙŠÙ† Ø§Ø³ØªÙ‚Ø±Ø§Ø± Ø§Ù„Ù†Ø¸Ø§Ù… Ø¨Ø´ÙƒÙ„ ÙƒØ¨ÙŠØ±
  
- **ØªØ­Ø³ÙŠÙ†Ø§Øª ÙÙŠ Repository**
  - Ø¥ØµÙ„Ø§Ø­ Ù…Ø´Ø§ÙƒÙ„ ÙÙŠ core/db_maintenance.py
  - Ø¥ØµÙ„Ø§Ø­ Ù…Ø´Ø§ÙƒÙ„ ÙÙŠ core/unified_sync.py
  - Ø¥ØµÙ„Ø§Ø­ Ù…Ø´Ø§ÙƒÙ„ ÙÙŠ ui/notification_system.py
  - Ø¥ØµÙ„Ø§Ø­ Ù…Ø´Ø§ÙƒÙ„ ÙÙŠ ui/main_window.py
  - Ø¥ØµÙ„Ø§Ø­ Ù…Ø´Ø§ÙƒÙ„ ÙÙŠ services/template_service.py

### âš¡ ØªØ­Ø³ÙŠÙ†Ø§Øª Ø§Ù„Ø£Ø¯Ø§Ø¡
- ØªØ­Ø³ÙŠÙ† Ø£Ø¯Ø§Ø¡ Ø§Ù„Ù…Ø²Ø§Ù…Ù†Ø©
- ØªÙ‚Ù„ÙŠÙ„ Ø§Ø³ØªÙ‡Ù„Ø§Ùƒ Ø§Ù„Ù…ÙˆØ§Ø±Ø¯
- ØªØ­Ø³ÙŠÙ† Ø³Ø±Ø¹Ø© Ø§Ù„Ø§Ø³ØªØ¬Ø§Ø¨Ø©

### ðŸ” Ø§Ù„Ø£Ù…Ø§Ù†
- ØªØ­Ø³ÙŠÙ†Ø§Øª Ø£Ù…Ù†ÙŠØ© Ø¥Ø¶Ø§ÙÙŠØ©
- Ø­Ù…Ø§ÙŠØ© Ø£ÙØ¶Ù„ Ø¶Ø¯ Ø§Ù„Ø£Ø®Ø·Ø§Ø¡

---

## [2.0.0] - 2026-01-20

### ðŸŽ‰ Ø¥ØµØ¯Ø§Ø± Ø¬Ø¯ÙŠØ¯ ÙƒØ§Ù…Ù„

#### âœ¨ Ù…Ù…ÙŠØ²Ø§Øª Ø¬Ø¯ÙŠØ¯Ø©
- Ù†Ø¸Ø§Ù… Ù…Ø²Ø§Ù…Ù†Ø© Ù…Ø­Ø³Ù‘Ù† ÙˆÙ…Ø³ØªÙ‚Ø± ØªÙ…Ø§Ù…Ø§Ù‹
- ÙˆØ§Ø¬Ù‡Ø© Ù…Ø³ØªØ®Ø¯Ù… Ù…Ø­Ø³Ù‘Ù†Ø© Ù…Ø¹ ØªØ¬Ø±Ø¨Ø© Ø£ÙØ¶Ù„
- Ù†Ø¸Ø§Ù… Ø¥Ø´Ø¹Ø§Ø±Ø§Øª Ø°ÙƒÙŠ
- ØªØ­Ø³ÙŠÙ†Ø§Øª ÙÙŠ Ù†Ø¸Ø§Ù… Ø§Ù„Ø·Ø¨Ø§Ø¹Ø©
- Ø¯Ø¹Ù… ÙƒØ§Ù…Ù„ Ù„Ù„ØºØ© Ø§Ù„Ø¹Ø±Ø¨ÙŠØ©

#### âš¡ ØªØ­Ø³ÙŠÙ†Ø§Øª Ø§Ù„Ø£Ø¯Ø§Ø¡
- ØªØ­Ø³ÙŠÙ† Ø³Ø±Ø¹Ø© Ø¨Ø¯Ø¡ Ø§Ù„ØªØ´ØºÙŠÙ„ Ø¨Ù†Ø³Ø¨Ø© 40%
- ØªØ­Ø³ÙŠÙ† Ø§Ø³ØªØ¬Ø§Ø¨Ø© Ø§Ù„ÙˆØ§Ø¬Ù‡Ø©
- ØªÙ‚Ù„ÙŠÙ„ Ø§Ø³ØªÙ‡Ù„Ø§Ùƒ Ø§Ù„Ø°Ø§ÙƒØ±Ø©
- ØªØ­Ø³ÙŠÙ† Ø£Ø¯Ø§Ø¡ Ù‚Ø§Ø¹Ø¯Ø© Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª
- ØªØ­Ø³ÙŠÙ† Ù†Ø¸Ø§Ù… Ø§Ù„Ù…Ø²Ø§Ù…Ù†Ø©

#### ðŸ”§ Ø¥ØµÙ„Ø§Ø­Ø§Øª
- Ø¥ØµÙ„Ø§Ø­ Ù…Ø´ÙƒÙ„Ø© ØªØ¬Ù…ÙŠØ¯ Ø§Ù„Ø¥Ø¹Ø¯Ø§Ø¯Ø§Øª
- Ø¥ØµÙ„Ø§Ø­ Ù…Ø´Ø§ÙƒÙ„ Ø¹Ø±Ø¶ Ø§Ù„Ø¯ÙØ¹Ø§Øª
- Ø¥ØµÙ„Ø§Ø­ Ù…Ø´Ø§ÙƒÙ„ Ø§Ù„Ù…Ø²Ø§Ù…Ù†Ø©
- Ø¥ØµÙ„Ø§Ø­ Ù…Ø´Ø§ÙƒÙ„ Ø§Ù„Ø·Ø¨Ø§Ø¹Ø©
- Ø¥ØµÙ„Ø§Ø­ ØªØ³Ø±ÙŠØ¨Ø§Øª Ø§Ù„Ø°Ø§ÙƒØ±Ø©

#### ðŸ” Ø§Ù„Ø£Ù…Ø§Ù†
- ØªØ­Ø³ÙŠÙ† Ù†Ø¸Ø§Ù… Ø§Ù„Ù…ØµØ§Ø¯Ù‚Ø©
- ØªØ´ÙÙŠØ± Ù…Ø­Ø³Ù‘Ù† Ù„Ù„Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ø­Ø³Ø§Ø³Ø©
- Ø­Ù…Ø§ÙŠØ© Ø£ÙØ¶Ù„ Ø¶Ø¯ Ø§Ù„Ø£Ø®Ø·Ø§Ø¡

#### ðŸ“š Ø§Ù„ØªÙˆØ«ÙŠÙ‚
- README Ù…Ø­Ø³Ù‘Ù†
- Ø¯Ù„ÙŠÙ„ Ø§Ù„ØªØ«Ø¨ÙŠØª Ø§Ù„ÙƒØ§Ù…Ù„
- Ø£Ù…Ø«Ù„Ø© Ø¹Ù„Ù‰ Ø§Ù„Ø§Ø³ØªØ®Ø¯Ø§Ù…
- ØªÙˆØ«ÙŠÙ‚ API

---

## [1.3.12] - 2026-01-19

### ðŸ”§ Ø¥ØµÙ„Ø§Ø­Ø§Øª ÙˆØªØ­Ø³ÙŠÙ†Ø§Øª
- Ø¥ØµÙ„Ø§Ø­ Ù…Ø´Ø§ÙƒÙ„ Ø§Ù„Ø£Ø¯Ø§Ø¡
- ØªØ­Ø³ÙŠÙ†Ø§Øª ÙÙŠ Ø§Ù„Ø§Ø³ØªÙ‚Ø±Ø§Ø±
- Ø¥ØµÙ„Ø§Ø­ Ø£Ø®Ø·Ø§Ø¡ Ø¨Ø³ÙŠØ·Ø©

---

## [1.3.0] - 2026-01-15

### âœ¨ Ù…Ù…ÙŠØ²Ø§Øª Ø¬Ø¯ÙŠØ¯Ø©
- Ù†Ø¸Ø§Ù… Ø§Ù„Ù…Ù‡Ø§Ù… (To-Do)
- ØªØ­Ø³ÙŠÙ†Ø§Øª ÙÙŠ Ù„ÙˆØ­Ø© Ø§Ù„ØªØ­ÙƒÙ…
- ØªÙ‚Ø§Ø±ÙŠØ± Ù…Ø­Ø³Ù‘Ù†Ø©

---

## [1.2.0] - 2026-01-10

### âœ¨ Ù…Ù…ÙŠØ²Ø§Øª Ø¬Ø¯ÙŠØ¯Ø©
- Ù†Ø¸Ø§Ù… Ø§Ù„Ù…ÙˆØ§Ø±Ø¯ Ø§Ù„Ø¨Ø´Ø±ÙŠØ©
- Ø¥Ø¯Ø§Ø±Ø© Ø§Ù„Ù…ÙˆØ¸ÙÙŠÙ†
- ØªØªØ¨Ø¹ Ø§Ù„Ø±ÙˆØ§ØªØ¨

---

## [1.1.0] - 2026-01-05

### âœ¨ Ù…Ù…ÙŠØ²Ø§Øª Ø¬Ø¯ÙŠØ¯Ø©
- Ù†Ø¸Ø§Ù… Ø§Ù„Ù…Ø²Ø§Ù…Ù†Ø© Ø§Ù„Ø³Ø­Ø§Ø¨ÙŠØ©
- Ø¯Ø¹Ù… MongoDB
- Ù†Ø³Ø® Ø§Ø­ØªÙŠØ§Ø·ÙŠ ØªÙ„Ù‚Ø§Ø¦ÙŠ

---

## [1.0.0] - 2026-01-01

### ðŸŽ‰ Ø§Ù„Ø¥ØµØ¯Ø§Ø± Ø§Ù„Ø£ÙˆÙ„
- Ù†Ø¸Ø§Ù… Ø¥Ø¯Ø§Ø±Ø© Ø§Ù„Ø¹Ù…Ù„Ø§Ø¡
- Ù†Ø¸Ø§Ù… Ø§Ù„ÙÙˆØ§ØªÙŠØ±
- Ù†Ø¸Ø§Ù… Ø§Ù„Ù…Ø­Ø§Ø³Ø¨Ø©
- Ù†Ø¸Ø§Ù… Ø§Ù„Ù…Ø´Ø§Ø±ÙŠØ¹
- Ù†Ø¸Ø§Ù… Ø§Ù„Ø·Ø¨Ø§Ø¹Ø©
- Ù†Ø¸Ø§Ù… Ø§Ù„ØªØµØ¯ÙŠØ±

---

## Ø§Ù„ØµÙŠØºØ©

Ø§Ù„ØªØºÙŠÙŠØ±Ø§Øª Ù…ØµÙ†ÙØ© Ø­Ø³Ø¨:
- `âœ¨ Added` Ù„Ù„Ù…Ù…ÙŠØ²Ø§Øª Ø§Ù„Ø¬Ø¯ÙŠØ¯Ø©
- `ðŸ”§ Changed` Ù„Ù„ØªØºÙŠÙŠØ±Ø§Øª ÙÙŠ Ø§Ù„Ù…Ù…ÙŠØ²Ø§Øª Ø§Ù„Ù…ÙˆØ¬ÙˆØ¯Ø©
- `âš ï¸ Deprecated` Ù„Ù„Ù…Ù…ÙŠØ²Ø§Øª Ø§Ù„ØªÙŠ Ø³ØªÙØ­Ø°Ù Ù‚Ø±ÙŠØ¨Ø§Ù‹
- `âŒ Removed` Ù„Ù„Ù…Ù…ÙŠØ²Ø§Øª Ø§Ù„Ù…Ø­Ø°ÙˆÙØ©
- `ðŸ”§ Fixed` Ù„Ù„Ø¥ØµÙ„Ø§Ø­Ø§Øª
- `ðŸ” Security` Ù„Ù„ØªØ­Ø³ÙŠÙ†Ø§Øª Ø§Ù„Ø£Ù…Ù†ÙŠØ©


# Design Document: Advanced Sync System

## Overview

تحسين نظام المزامنة الحالي (`SyncManager` + `AdvancedSyncManager`) لدعم Offline-First بشكل كامل مع Auto-Sync ذكي وآلية حل التعارضات باستخدام Last-Write-Wins.

### Key Improvements
- تحسين `ConnectionChecker` للكشف السريع عن الاتصال
- إضافة `ConflictResolver` لحل تعارضات البيانات
- تحسين `SyncStatusWidget` لعرض حالة المزامنة
- إضافة Exponential Backoff للمحاولات الفاشلة

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Main Application                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              SyncStatusWidget (UI)                   │    │
│  │  - Online/Offline indicator                          │    │
│  │  - Pending count badge                               │    │
│  │  - Sync progress                                     │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                  │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           AdvancedSyncManager (Enhanced)             │    │
│  │  - ConnectionChecker (improved)                      │    │
│  │  - SyncWorker (with retry logic)                     │    │
│  │  - ConflictResolver (NEW)                            │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                  │
│              ┌────────────┴────────────┐                    │
│              ▼                         ▼                    │
│     ┌─────────────┐           ┌─────────────┐              │
│     │   SQLite    │           │   MongoDB   │              │
│     │  (Primary)  │           │   (Cloud)   │              │
│     └─────────────┘           └─────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. Enhanced ConnectionChecker

```python
class ConnectionChecker(QThread):
    """فاحص الاتصال المحسّن"""
    
    connection_changed = pyqtSignal(bool)
    
    def __init__(self):
        self.check_interval = 5  # ثواني (كان 10)
        self.quick_check_interval = 2  # للفحص السريع بعد فقدان الاتصال
```

### 2. ConflictResolver (NEW)

```python
class ConflictResolver:
    """حل تعارضات البيانات"""
    
    def resolve(self, local_record: dict, remote_record: dict) -> dict:
        """حل التعارض باستخدام Last-Write-Wins"""
        
    def detect_conflict(self, local: dict, remote: dict) -> bool:
        """كشف وجود تعارض"""
        
    def log_conflict(self, table: str, local: dict, remote: dict, resolution: str):
        """تسجيل التعارض للمراجعة"""
```

### 3. Enhanced SyncWorker

```python
class SyncWorker(QThread):
    """عامل المزامنة المحسّن"""
    
    def _sync_with_retry(self, item: SyncQueueItem) -> bool:
        """مزامنة مع Exponential Backoff"""
        delays = [1, 2, 4]  # ثواني
        for attempt, delay in enumerate(delays):
            if self._sync_item(item):
                return True
            time.sleep(delay)
        return False
```

### 4. SyncStatusWidget (UI)

```python
class SyncStatusWidget(QWidget):
    """Widget لعرض حالة المزامنة في Status Bar"""
    
    def __init__(self):
        self.status_icon = QLabel()  # 🟢/🔴
        self.status_text = QLabel()  # "متصل" / "غير متصل"
        self.pending_badge = QLabel()  # عدد العمليات المعلقة
        self.sync_progress = QProgressBar()  # شريط التقدم
```

## Data Models

### Conflict Log Schema

| Field | Type | Description |
|-------|------|-------------|
| id | int | Primary key |
| table_name | str | اسم الجدول |
| entity_id | str | معرف السجل |
| local_data | JSON | البيانات المحلية |
| remote_data | JSON | البيانات السحابية |
| resolution | str | طريقة الحل (LWW, KEEP_BOTH) |
| resolved_at | datetime | وقت الحل |

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system.*

### Property 1: Offline Data Persistence
*For any* data created or modified offline, the system should persist it to SQLite immediately and queue it for sync.
**Validates: Requirements 1.2, 1.3**

### Property 2: Auto-Sync Trigger
*For any* pending sync items, when internet connection is restored, the system should start syncing within 5 seconds.
**Validates: Requirements 2.1**

### Property 3: Conflict Detection
*For any* record with different last_modified timestamps locally and remotely, the system should detect it as a conflict.
**Validates: Requirements 3.1**

### Property 4: Last-Write-Wins Resolution
*For any* detected conflict, the record with the later last_modified timestamp should be the winner.
**Validates: Requirements 3.2**

## Error Handling

| Error Scenario | Error Message (Arabic) | Recovery Action |
|----------------|------------------------|-----------------|
| Network timeout | "انتهت مهلة الاتصال" | Retry with backoff |
| MongoDB unavailable | "السيرفر غير متاح" | Continue offline |
| Sync item failed | "فشل مزامنة العنصر" | Retry up to 3 times |
| Data validation error | "بيانات غير صالحة" | Skip and log |

## Testing Strategy

### Unit Tests
- Test conflict detection logic
- Test Last-Write-Wins resolution
- Test retry with exponential backoff
- Test sync queue operations

### Integration Tests
- Test full offline-to-online sync cycle
- Test conflict resolution with real data
- Test connection status changes


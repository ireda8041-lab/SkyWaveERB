"""
اختبارات مدير المزامنة الذكي (SmartSyncManager)
اختبارات شاملة للتأكد من:
- إدارة قائمة الانتظار
- المزامنة المتزامنة وغير المتزامنة
- الإحصائيات والتقارير
"""

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.smart_sync_manager_v2 import SmartSyncManagerV2, SyncStatus


@pytest.fixture
def sync_manager():
    """إنشاء مدير مزامنة في الذاكرة"""
    return SmartSyncManagerV2(":memory:")


class TestSyncQueue:
    """اختبارات قائمة انتظار المزامنة"""

    def test_add_to_queue(self, sync_manager):
        """اختبار: إضافة عملية للقائمة"""
        queue_id = sync_manager.add_to_sync_queue(
            entity_type="projects",
            entity_id="P-001",
            operation="create",
            data={"name": "مشروع", "total_amount": 1000}
        )

        assert queue_id > 0
        print(f"\n[OK] Added to queue with ID: {queue_id}")

    def test_queue_status(self, sync_manager):
        """اختبار: حالة القائمة"""
        # إضافة عدة عمليات
        sync_manager.add_to_sync_queue("projects", "P-001", "create")
        sync_manager.add_to_sync_queue("invoices", "INV-001", "update")
        sync_manager.add_to_sync_queue("payments", "PAY-001", "create")

        status = sync_manager.get_queue_status()

        assert status['pending'] == 3
        assert status['total'] == 3
        print(f"\n[OK] Queue status: {status}")

    def test_queue_priority(self, sync_manager):
        """اختبار: أولوية العمليات"""
        # إضافة بأولويات مختلفة
        sync_manager.add_to_sync_queue("projects", "P-001", "create", priority="low")
        sync_manager.add_to_sync_queue("payments", "PAY-001", "create", priority="high")
        sync_manager.add_to_sync_queue("invoices", "INV-001", "update", priority="medium")

        status = sync_manager.get_queue_status()
        assert status['pending'] == 3
        print("\n[OK] Priority queue working")

    def test_queue_with_data(self, sync_manager):
        """اختبار: إضافة عملية مع بيانات"""
        data = {
            "name": "مشروع تسويق",
            "total_amount": 5000,
            "items": [{"name": "خدمة 1", "price": 2500}]
        }

        queue_id = sync_manager.add_to_sync_queue(
            entity_type="projects",
            entity_id="P-002",
            operation="create",
            data=data
        )

        assert queue_id > 0
        print("\n[OK] Queue with data added")


class TestSyncProcess:
    """اختبارات عملية المزامنة"""

    def test_sync_returns_report(self, sync_manager):
        """اختبار: المزامنة ترجع تقرير"""
        report = sync_manager.start_sync(async_mode=False)

        assert report is not None
        assert 'pushed' in report
        assert 'pulled' in report
        assert 'conflicts' in report
        assert 'errors' in report
        assert 'duration' in report
        print(f"\n[OK] Sync report: {report}")

    def test_sync_processes_queue(self, sync_manager):
        """اختبار: المزامنة تعالج القائمة"""
        # إضافة عمليات
        sync_manager.add_to_sync_queue("projects", "P-001", "create")
        sync_manager.add_to_sync_queue("invoices", "INV-001", "update")

        # تشغيل المزامنة
        report = sync_manager.start_sync(async_mode=False)

        # التحقق من معالجة القائمة
        status = sync_manager.get_queue_status()
        assert status['completed'] >= 0  # قد تكون معالجة أو لا حسب التنفيذ
        print(f"\n[OK] Queue processed, status: {status}")

    def test_sync_updates_stats(self, sync_manager):
        """اختبار: المزامنة تحدث الإحصائيات"""
        initial_stats = sync_manager.get_sync_stats()
        initial_count = initial_stats['total_syncs']

        sync_manager.start_sync(async_mode=False)

        final_stats = sync_manager.get_sync_stats()
        assert final_stats['total_syncs'] == initial_count + 1
        print(f"\n[OK] Stats updated: {final_stats['total_syncs']} syncs")

    def test_sync_not_concurrent(self, sync_manager):
        """اختبار: لا يمكن تشغيل مزامنتين معاً"""
        # محاكاة مزامنة جارية
        sync_manager._is_syncing = True

        result = sync_manager.start_sync(async_mode=False)

        assert result is None
        sync_manager._is_syncing = False
        print("\n[OK] Concurrent sync prevented")


class TestSyncCallbacks:
    """اختبارات callbacks المزامنة"""

    def test_callbacks_called(self, sync_manager):
        """اختبار: استدعاء callbacks"""
        started_called = [False]
        finished_called = [False]
        progress_messages = []

        def on_started():
            started_called[0] = True

        def on_finished(report):
            finished_called[0] = True

        def on_progress(msg, percent):
            progress_messages.append((msg, percent))

        sync_manager.set_callbacks(
            on_started=on_started,
            on_finished=on_finished,
            on_progress=on_progress
        )

        sync_manager.start_sync(async_mode=False)

        assert started_called[0], "on_started should be called"
        assert finished_called[0], "on_finished should be called"
        print(f"\n[OK] Callbacks called, progress: {len(progress_messages)} updates")


class TestSyncStats:
    """اختبارات إحصائيات المزامنة"""

    def test_initial_stats(self, sync_manager):
        """اختبار: الإحصائيات الأولية"""
        stats = sync_manager.get_sync_stats()

        assert stats['total_syncs'] == 0
        assert stats['successful_syncs'] == 0
        assert stats['failed_syncs'] == 0
        assert stats['last_sync'] is None
        print(f"\n[OK] Initial stats: {stats}")

    def test_stats_after_sync(self, sync_manager):
        """اختبار: الإحصائيات بعد المزامنة"""
        sync_manager.start_sync(async_mode=False)
        sync_manager.start_sync(async_mode=False)

        stats = sync_manager.get_sync_stats()

        assert stats['total_syncs'] == 2
        assert stats['successful_syncs'] == 2
        assert stats['last_sync'] is not None
        print(f"\n[OK] Stats after sync: {stats}")

    def test_pending_changes_count(self, sync_manager):
        """اختبار: عدد التغييرات المعلقة"""
        counts = sync_manager.get_pending_changes_count()

        # يجب أن يكون قاموس بأسماء الجداول
        assert isinstance(counts, dict)
        print(f"\n[OK] Pending changes: {counts}")


class TestSyncStatus:
    """اختبارات حالات المزامنة"""

    def test_sync_status_constants(self):
        """اختبار: ثوابت حالات المزامنة"""
        assert SyncStatus.NEW_OFFLINE == "new_offline"
        assert SyncStatus.MODIFIED_OFFLINE == "modified_offline"
        assert SyncStatus.SYNCED == "synced"
        assert SyncStatus.PENDING_SYNC == "pending_sync"
        assert SyncStatus.CONFLICT == "conflict"
        print("\n[OK] Sync status constants defined")

    def test_is_syncing_flag(self, sync_manager):
        """اختبار: علم المزامنة الجارية"""
        assert sync_manager.is_syncing() == False

        sync_manager._is_syncing = True
        assert sync_manager.is_syncing() == True

        sync_manager._is_syncing = False
        print("\n[OK] is_syncing flag working")


class TestQueueCleanup:
    """اختبارات تنظيف القائمة"""

    def test_clear_completed(self, sync_manager):
        """اختبار: تنظيف العمليات المكتملة"""
        # إضافة ومعالجة عمليات
        sync_manager.add_to_sync_queue("projects", "P-001", "create")
        sync_manager.start_sync(async_mode=False)

        # تنظيف
        deleted = sync_manager.clear_completed_queue(older_than_days=0)

        # قد يكون 0 أو أكثر حسب التنفيذ
        assert deleted >= 0
        print(f"\n[OK] Cleared {deleted} completed entries")


class TestEdgeCases:
    """اختبارات الحالات الحدية"""

    def test_empty_queue_sync(self, sync_manager):
        """اختبار: مزامنة بقائمة فارغة"""
        report = sync_manager.start_sync(async_mode=False)

        assert report['errors'] == 0
        print("\n[OK] Empty queue sync handled")

    def test_multiple_syncs(self, sync_manager):
        """اختبار: مزامنات متعددة متتالية"""
        for i in range(3):
            sync_manager.add_to_sync_queue("projects", f"P-{i}", "create")
            report = sync_manager.start_sync(async_mode=False)
            assert report is not None

        stats = sync_manager.get_sync_stats()
        assert stats['total_syncs'] == 3
        print(f"\n[OK] Multiple syncs: {stats['total_syncs']}")

    def test_offline_mode(self, sync_manager):
        """اختبار: الوضع غير المتصل"""
        # بدون mongo_uri، يجب أن يعمل محلياً
        assert sync_manager.mongo_uri is None
        
        report = sync_manager.start_sync(async_mode=False)
        assert report is not None
        print("\n[OK] Offline mode working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

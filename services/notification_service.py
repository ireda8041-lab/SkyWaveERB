# الملف: services/notification_service.py

"""
خدمة الإشعارات
تدير إنشاء وعرض وحذف الإشعارات
"""

from datetime import datetime, timedelta
from typing import List, Optional
from core.schemas import (
    Notification, NotificationType, NotificationPriority
)
from core.repository import Repository
from core.event_bus import EventBus
from core.logger import get_logger
from core.error_handler import ErrorHandler

logger = get_logger(__name__)
error_handler = ErrorHandler()


class NotificationService:
    """
    خدمة إدارة الإشعارات
    - إنشاء إشعارات جديدة
    - الحصول على الإشعارات غير المقروءة
    - تحديد الإشعارات كمقروءة
    - حذف الإشعارات القديمة
    """
    
    def __init__(self, repository: Repository, event_bus: EventBus):
        """
        تهيئة خدمة الإشعارات
        
        Args:
            repository: مخزن البيانات
            event_bus: ناقل الأحداث
        """
        self.repo = repository
        self.event_bus = event_bus
        
        # الاشتراك في الأحداث المهمة
        self._subscribe_to_events()
        
        logger.info("تم تهيئة NotificationService")
    
    def _subscribe_to_events(self):
        """⚡ الاشتراك في جميع الأحداث المهمة لإنشاء إشعارات تلقائية"""
        # إشعارات الدفعات
        self.event_bus.subscribe("PAYMENT_RECORDED", self._on_payment_recorded)
        
        # إشعارات المزامنة
        self.event_bus.subscribe("SYNC_FAILED", self._on_sync_failed)
        
        # ⚡ إشعارات جديدة - آخر 10 أحداث
        self.event_bus.subscribe("CLIENT_CREATED", self._on_client_created)
        self.event_bus.subscribe("PROJECT_CREATED", self._on_project_created)
        self.event_bus.subscribe("INVOICE_CREATED", self._on_invoice_created)
        self.event_bus.subscribe("EXPENSE_CREATED", self._on_expense_created)
        self.event_bus.subscribe("QUOTATION_CREATED", self._on_quotation_created)
        
        logger.debug("تم الاشتراك في أحداث الإشعارات")
    
    def create_notification(
        self,
        title: str,
        message: str,
        type: NotificationType = NotificationType.INFO,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        related_entity_type: Optional[str] = None,
        related_entity_id: Optional[str] = None,
        action_url: Optional[str] = None,
        expires_at: Optional[datetime] = None
    ) -> Optional[Notification]:
        """
        إنشاء إشعار جديد
        
        Args:
            title: عنوان الإشعار
            message: نص الإشعار
            type: نوع الإشعار
            priority: أولوية الإشعار
            related_entity_type: نوع الكيان المرتبط
            related_entity_id: معرف الكيان المرتبط
            action_url: رابط الإجراء
            expires_at: تاريخ انتهاء الصلاحية
            
        Returns:
            الإشعار المنشأ أو None في حالة الفشل
        """
        try:
            notification = Notification(
                title=title,
                message=message,
                type=type,
                priority=priority,
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
                action_url=action_url,
                expires_at=expires_at
            )
            
            # حفظ في قاعدة البيانات
            saved_notification = self._save_notification(notification)
            
            if saved_notification:
                # إرسال حدث إنشاء إشعار جديد
                self.event_bus.publish("NOTIFICATION_CREATED", {
                    'notification_id': saved_notification.id,
                    'type': type.value,
                    'priority': priority.value
                })
                
                logger.info(f"تم إنشاء إشعار: {title}")
                return saved_notification
            
            return None
        
        except Exception as e:
            error_handler.handle_exception(e, f"فشل إنشاء الإشعار: {title}")
            return None
    
    def _save_notification(self, notification: Notification) -> Optional[Notification]:
        """حفظ الإشعار في قاعدة البيانات"""
        try:
            now = datetime.now().isoformat()
            
            cursor = self.repo.sqlite_cursor
            cursor.execute("""
                INSERT INTO notifications (
                    sync_status, created_at, last_modified,
                    title, message, type, priority, is_read,
                    related_entity_type, related_entity_id,
                    action_url, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'new_offline', now, now,
                notification.title,
                notification.message,
                notification.type.value,
                notification.priority.value,
                0,  # is_read = False
                notification.related_entity_type,
                notification.related_entity_id,
                notification.action_url,
                notification.expires_at.isoformat() if notification.expires_at else None
            ))
            
            self.repo.sqlite_conn.commit()
            notification.id = cursor.lastrowid
            
            # محاولة الحفظ في MongoDB
            if self.repo.online:
                try:
                    notification_dict = notification.model_dump(exclude={'_mongo_id'})
                    result = self.repo.mongo_db.notifications.insert_one(notification_dict)
                    
                    # تحديث _mongo_id
                    mongo_id = str(result.inserted_id)
                    cursor.execute(
                        "UPDATE notifications SET _mongo_id = ?, sync_status = 'synced' WHERE id = ?",
                        (mongo_id, notification.id)
                    )
                    self.repo.sqlite_conn.commit()
                except Exception as e:
                    logger.warning(f"فشل حفظ الإشعار في MongoDB: {e}")
            
            return notification
        
        except Exception as e:
            logger.error(f"فشل حفظ الإشعار: {e}")
            return None
    
    def get_unread_notifications(self, limit: int = 50) -> List[Notification]:
        """
        الحصول على الإشعارات غير المقروءة
        
        Args:
            limit: الحد الأقصى لعدد الإشعارات
            
        Returns:
            قائمة الإشعارات غير المقروءة
        """
        try:
            cursor = self.repo.sqlite_cursor
            cursor.execute("""
                SELECT * FROM notifications 
                WHERE is_read = 0 
                AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY created_at DESC 
                LIMIT ?
            """, (datetime.now().isoformat(), limit))
            
            rows = cursor.fetchall()
            notifications = []
            
            for row in rows:
                notification = self._row_to_notification(row)
                if notification:
                    notifications.append(notification)
            
            return notifications
        
        except Exception as e:
            logger.error(f"فشل الحصول على الإشعارات غير المقروءة: {e}")
            return []
    
    def get_all_notifications(self, limit: int = 100) -> List[Notification]:
        """
        الحصول على جميع الإشعارات
        
        Args:
            limit: الحد الأقصى لعدد الإشعارات
            
        Returns:
            قائمة جميع الإشعارات
        """
        try:
            cursor = self.repo.sqlite_cursor
            cursor.execute("""
                SELECT * FROM notifications 
                WHERE (expires_at IS NULL OR expires_at > ?)
                ORDER BY created_at DESC 
                LIMIT ?
            """, (datetime.now().isoformat(), limit))
            
            rows = cursor.fetchall()
            notifications = []
            
            for row in rows:
                notification = self._row_to_notification(row)
                if notification:
                    notifications.append(notification)
            
            return notifications
        
        except Exception as e:
            logger.error(f"فشل الحصول على الإشعارات: {e}")
            return []
    
    def get_recent_activities(self, limit: int = 10) -> List[Notification]:
        """
        ⚡ الحصول على آخر 10 أنشطة/أحداث في البرنامج
        
        Args:
            limit: عدد الأنشطة (افتراضي 10)
            
        Returns:
            قائمة آخر الأنشطة
        """
        try:
            cursor = self.repo.sqlite_cursor
            cursor.execute("""
                SELECT * FROM notifications 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            activities = []
            
            for row in rows:
                notification = self._row_to_notification(row)
                if notification:
                    activities.append(notification)
            
            logger.debug(f"تم جلب {len(activities)} نشاط حديث")
            return activities
        
        except Exception as e:
            logger.error(f"فشل الحصول على الأنشطة الحديثة: {e}")
            return []
    
    def mark_as_read(self, notification_id: int) -> bool:
        """
        تحديد إشعار كمقروء
        
        Args:
            notification_id: معرف الإشعار
            
        Returns:
            True إذا نجحت العملية
        """
        try:
            cursor = self.repo.sqlite_cursor
            cursor.execute("""
                UPDATE notifications 
                SET is_read = 1, last_modified = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), notification_id))
            
            self.repo.sqlite_conn.commit()
            
            # محاولة التحديث في MongoDB
            if self.repo.online:
                try:
                    cursor.execute("SELECT _mongo_id FROM notifications WHERE id = ?", (notification_id,))
                    row = cursor.fetchone()
                    
                    if row and row['_mongo_id']:
                        from bson import ObjectId
                        self.repo.mongo_db.notifications.update_one(
                            {'_id': ObjectId(row['_mongo_id'])},
                            {'$set': {'is_read': True}}
                        )
                except Exception as e:
                    logger.warning(f"فشل تحديث الإشعار في MongoDB: {e}")
            
            logger.debug(f"تم تحديد الإشعار {notification_id} كمقروء")
            return True
        
        except Exception as e:
            logger.error(f"فشل تحديد الإشعار كمقروء: {e}")
            return False
    
    def mark_all_as_read(self) -> bool:
        """
        تحديد جميع الإشعارات كمقروءة
        
        Returns:
            True إذا نجحت العملية
        """
        try:
            cursor = self.repo.sqlite_cursor
            cursor.execute("""
                UPDATE notifications 
                SET is_read = 1, last_modified = ?
                WHERE is_read = 0
            """, (datetime.now().isoformat(),))
            
            self.repo.sqlite_conn.commit()
            
            # محاولة التحديث في MongoDB
            if self.repo.online:
                try:
                    self.repo.mongo_db.notifications.update_many(
                        {'is_read': False},
                        {'$set': {'is_read': True}}
                    )
                except Exception as e:
                    logger.warning(f"فشل تحديث الإشعارات في MongoDB: {e}")
            
            logger.info("تم تحديد جميع الإشعارات كمقروءة")
            return True
        
        except Exception as e:
            logger.error(f"فشل تحديد جميع الإشعارات كمقروءة: {e}")
            return False
    
    def delete_notification(self, notification_id: int) -> bool:
        """
        حذف إشعار
        
        Args:
            notification_id: معرف الإشعار
            
        Returns:
            True إذا نجحت العملية
        """
        try:
            cursor = self.repo.sqlite_cursor
            
            # الحصول على _mongo_id قبل الحذف
            cursor.execute("SELECT _mongo_id FROM notifications WHERE id = ?", (notification_id,))
            row = cursor.fetchone()
            
            # حذف من SQLite
            cursor.execute("DELETE FROM notifications WHERE id = ?", (notification_id,))
            self.repo.sqlite_conn.commit()
            
            # محاولة الحذف من MongoDB
            if self.repo.online and row and row['_mongo_id']:
                try:
                    from bson import ObjectId
                    self.repo.mongo_db.notifications.delete_one(
                        {'_id': ObjectId(row['_mongo_id'])}
                    )
                except Exception as e:
                    logger.warning(f"فشل حذف الإشعار من MongoDB: {e}")
            
            logger.debug(f"تم حذف الإشعار {notification_id}")
            return True
        
        except Exception as e:
            logger.error(f"فشل حذف الإشعار: {e}")
            return False
    
    def delete_old_notifications(self, days: int = 30) -> int:
        """
        حذف الإشعارات القديمة
        
        Args:
            days: عدد الأيام (الإشعارات الأقدم من هذا سيتم حذفها)
            
        Returns:
            عدد الإشعارات المحذوفة
        """
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            cursor = self.repo.sqlite_cursor
            cursor.execute("""
                DELETE FROM notifications 
                WHERE created_at < ? AND is_read = 1
            """, (cutoff_date,))
            
            deleted_count = cursor.rowcount
            self.repo.sqlite_conn.commit()
            
            # محاولة الحذف من MongoDB
            if self.repo.online:
                try:
                    self.repo.mongo_db.notifications.delete_many({
                        'created_at': {'$lt': cutoff_date},
                        'is_read': True
                    })
                except Exception as e:
                    logger.warning(f"فشل حذف الإشعارات القديمة من MongoDB: {e}")
            
            logger.info(f"تم حذف {deleted_count} إشعار قديم")
            return deleted_count
        
        except Exception as e:
            logger.error(f"فشل حذف الإشعارات القديمة: {e}")
            return 0
    
    def get_unread_count(self) -> int:
        """
        الحصول على عدد الإشعارات غير المقروءة
        
        Returns:
            عدد الإشعارات غير المقروءة
        """
        try:
            cursor = self.repo.sqlite_cursor
            cursor.execute("""
                SELECT COUNT(*) FROM notifications 
                WHERE is_read = 0 
                AND (expires_at IS NULL OR expires_at > ?)
            """, (datetime.now().isoformat(),))
            
            result = cursor.fetchone()
            return result[0] if result else 0
        
        except Exception as e:
            logger.error(f"فشل الحصول على عدد الإشعارات غير المقروءة: {e}")
            return 0
    
    def _row_to_notification(self, row) -> Optional[Notification]:
        """تحويل صف من قاعدة البيانات إلى كائن Notification"""
        try:
            return Notification(
                id=row['id'],
                created_at=datetime.fromisoformat(row['created_at']),
                last_modified=datetime.fromisoformat(row['last_modified']),
                title=row['title'],
                message=row['message'],
                type=NotificationType(row['type']),
                priority=NotificationPriority(row['priority']),
                is_read=bool(row['is_read']),
                related_entity_type=row['related_entity_type'],
                related_entity_id=row['related_entity_id'],
                action_url=row['action_url'],
                expires_at=datetime.fromisoformat(row['expires_at']) if row['expires_at'] else None,
                mongo_id=row['_mongo_id'],
                sync_status=row['sync_status']
            )
        except Exception as e:
            logger.error(f"فشل تحويل صف إلى Notification: {e}")
            return None
    
    # --- معالجات الأحداث ---
    
    def _on_payment_recorded(self, data: dict):
        """معالج حدث تسجيل دفعة جديدة"""
        try:
            amount = data.get('amount', 0)
            project_name = data.get('project_name', 'غير معروف')
            
            self.create_notification(
                title="تم تسجيل دفعة جديدة",
                message=f"تم تسجيل دفعة بمبلغ {amount:.2f} جنيه للمشروع '{project_name}'",
                type=NotificationType.SUCCESS,
                priority=NotificationPriority.MEDIUM,
                related_entity_type="payments",
                related_entity_id=str(data.get('payment_id', ''))
            )
        except Exception as e:
            logger.error(f"فشل إنشاء إشعار الدفعة: {e}")
    
    def _on_sync_failed(self, data: dict):
        """معالج حدث فشل المزامنة"""
        try:
            error_message = data.get('error', 'خطأ غير معروف')
            
            self.create_notification(
                title="فشلت عملية المزامنة",
                message=f"فشلت المزامنة مع السحابة: {error_message}",
                type=NotificationType.ERROR,
                priority=NotificationPriority.HIGH,
                related_entity_type="sync",
                related_entity_id=None
            )
        except Exception as e:
            logger.error(f"فشل إنشاء إشعار فشل المزامنة: {e}")
    
    # ⚡ معالجات الأحداث الجديدة - آخر 10 أحداث
    
    def _on_client_created(self, data: dict):
        """معالج حدث إنشاء عميل جديد"""
        try:
            client = data.get('client')
            if client:
                self.create_notification(
                    title="✅ عميل جديد",
                    message=f"تم إضافة العميل: {client.name}",
                    type=NotificationType.SUCCESS,
                    priority=NotificationPriority.LOW,
                    related_entity_type="client",
                    related_entity_id=str(client.id) if hasattr(client, 'id') else None
                )
        except Exception as e:
            logger.error(f"فشل إنشاء إشعار العميل: {e}")
    
    def _on_project_created(self, data: dict):
        """معالج حدث إنشاء مشروع جديد"""
        try:
            project = data.get('project')
            if project:
                self.create_notification(
                    title="🚀 مشروع جديد",
                    message=f"تم إنشاء المشروع: {project.name}",
                    type=NotificationType.SUCCESS,
                    priority=NotificationPriority.MEDIUM,
                    related_entity_type="project",
                    related_entity_id=project.name
                )
        except Exception as e:
            logger.error(f"فشل إنشاء إشعار المشروع: {e}")
    
    def _on_invoice_created(self, data: dict):
        """معالج حدث إنشاء فاتورة جديدة"""
        try:
            invoice = data.get('invoice')
            if invoice:
                self.create_notification(
                    title="📄 فاتورة جديدة",
                    message=f"تم إنشاء الفاتورة: {invoice.invoice_number}",
                    type=NotificationType.INFO,
                    priority=NotificationPriority.MEDIUM,
                    related_entity_type="invoice",
                    related_entity_id=invoice.invoice_number
                )
        except Exception as e:
            logger.error(f"فشل إنشاء إشعار الفاتورة: {e}")
    
    def _on_expense_created(self, data: dict):
        """معالج حدث إنشاء مصروف جديد"""
        try:
            expense = data.get('expense')
            if expense:
                self.create_notification(
                    title="💸 مصروف جديد",
                    message=f"تم تسجيل مصروف: {expense.category} - {expense.amount} ج.م",
                    type=NotificationType.WARNING,
                    priority=NotificationPriority.LOW,
                    related_entity_type="expense",
                    related_entity_id=str(expense.id) if hasattr(expense, 'id') else None
                )
        except Exception as e:
            logger.error(f"فشل إنشاء إشعار المصروف: {e}")
    
    def _on_quotation_created(self, data: dict):
        """معالج حدث إنشاء عرض سعر جديد"""
        try:
            quotation = data.get('quotation')
            if quotation:
                self.create_notification(
                    title="📋 عرض سعر جديد",
                    message=f"تم إنشاء عرض السعر: {quotation.quote_number}",
                    type=NotificationType.INFO,
                    priority=NotificationPriority.LOW,
                    related_entity_type="quotation",
                    related_entity_id=quotation.quote_number
                )
        except Exception as e:
            logger.error(f"فشل إنشاء إشعار عرض السعر: {e}")
    
    def check_project_due_dates(self):
        """
        فحص مواعيد استحقاق المشاريع وإنشاء إشعارات
        يجب استدعاء هذه الدالة بشكل دوري (مثلاً يومياً)
        """
        try:
            # الحصول على المشاريع النشطة
            cursor = self.repo.sqlite_cursor
            cursor.execute("""
                SELECT id, name, end_date 
                FROM projects 
                WHERE status = 'نشط' AND end_date IS NOT NULL
            """)
            
            rows = cursor.fetchall()
            now = datetime.now()
            
            for row in rows:
                end_date = datetime.fromisoformat(row['end_date'])
                days_until_due = (end_date - now).days
                
                # إشعار قبل 7 أيام من الموعد
                if 0 <= days_until_due <= 7:
                    # التحقق من عدم وجود إشعار مسبق
                    cursor.execute("""
                        SELECT COUNT(*) FROM notifications 
                        WHERE related_entity_type = 'projects' 
                        AND related_entity_id = ?
                        AND type = ?
                        AND created_at > ?
                    """, (
                        str(row['id']),
                        NotificationType.PROJECT_DUE.value,
                        (now - timedelta(days=1)).isoformat()
                    ))
                    
                    if cursor.fetchone()[0] == 0:
                        self.create_notification(
                            title="موعد استحقاق مشروع قريب",
                            message=f"المشروع '{row['name']}' سينتهي خلال {days_until_due} يوم",
                            type=NotificationType.PROJECT_DUE,
                            priority=NotificationPriority.HIGH,
                            related_entity_type="projects",
                            related_entity_id=str(row['id'])
                        )
            
            logger.debug("تم فحص مواعيد استحقاق المشاريع")
        
        except Exception as e:
            logger.error(f"فشل فحص مواعيد استحقاق المشاريع: {e}")


print("services/notification_service.py تم إنشاؤه بنجاح.")

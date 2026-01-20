# أمثلة استخدام Cursor Context Manager

# مثال على الاستخدام الصحيح للـ cursors

from core.cursor_manager import get_cursor_context

# بدلاً من:
# cursor = self.repo.get_cursor()
# try:
#     cursor.execute("SELECT * FROM clients")
#     results = cursor.fetchall()
# finally:
#     cursor.close()

# استخدم:
with get_cursor_context(self.repo) as cursor:
    cursor.execute("SELECT * FROM clients")
    results = cursor.fetchall()
# يتم إغلاق الـ cursor تلقائياً

# للعمليات المتعددة:
def get_client_with_projects(client_id):
    with get_cursor_context(self.repo) as cursor:
        # جلب العميل
        cursor.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
        client = cursor.fetchone()
        
        if client:
            # جلب المشاريع في cursor منفصل
            with get_cursor_context(self.repo) as projects_cursor:
                projects_cursor.execute("SELECT * FROM projects WHERE client_id = ?", (client_id,))
                projects = projects_cursor.fetchall()
            
            return client, projects
    
    return None, []

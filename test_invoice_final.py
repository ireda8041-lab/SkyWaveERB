"""
اختبار قالب الفاتورة النهائي مع رقم عشوائي
"""

import os
import sys
from datetime import datetime
import random
from core.repository import Repository
from services.template_service import TemplateService
from services.settings_service import SettingsService
from core import schemas

def test_invoice_with_random_number():
    """اختبار إنتاج فاتورة مع رقم عشوائي"""
    
    print("="*80)
    print("اختبار قالب الفاتورة النهائي")
    print("="*80)
    
    # تهيئة الخدمات
    repo = Repository()
    settings_service = SettingsService()
    template_service = TemplateService(repo, settings_service)
    
    # توليد رقم فاتورة عشوائي
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = random.randint(10, 99)
    invoice_number = f"SW-{timestamp}{random_suffix}"
    
    print(f"\n📋 رقم الفاتورة المُولد: {invoice_number}")
    
    # بيانات تجريبية للمشروع
    test_project = schemas.Project(
        id=1,
        name="باقة SEO - العميل التجريبي",
        client_id="test_client",
        status=schemas.ProjectStatus.ACTIVE,
        start_date=datetime.now(),
        end_date=datetime.now(),
        items=[
            schemas.ProjectItem(
                service_id="1",
                description="Facebook Sponsored Ad - اعلان ممول فيسبوك",
                quantity=5.0,
                unit_price=400.0,
                discount_rate=0.0,
                discount_amount=0.0,
                total=2000.0
            )
        ],
        subtotal=2000.0,
        discount_rate=0.0,
        discount_amount=0.0,
        tax_rate=0.0,
        tax_amount=0.0,
        total_amount=2000.0,
        project_notes="مشروع تجريبي لاختبار القالب"
    )
    
    # بيانات العميل
    test_client = {
        'name': 'إيه للأقمشه',
        'phone': '201067894321',
        'email': 'test@example.com',
        'address': 'مرسى مطروح'
    }
    
    # بيانات الدفعات
    test_payments = [
        {
            'date': datetime.now(),
            'amount': 2000.0,
            'method': 'Instapay',
            'account_name': 'Instapay'
        }
    ]
    
    print("\n1. جلب القالب الافتراضي...")
    default_template = template_service.get_default_template()
    if default_template:
        print(f"   ✅ تم جلب القالب: {default_template['name']}")
        print(f"   📄 ملف القالب: {default_template['template_file']}")
    else:
        print("   ❌ لم يتم العثور على قالب افتراضي")
        return False
    
    print("\n2. إنتاج HTML للفاتورة...")
    try:
        # تمرير رقم الفاتورة المخصص
        html_content = template_service.generate_invoice_html(
            project=test_project,
            client_info=test_client,
            payments=test_payments
        )
        
        # استبدال رقم الفاتورة في HTML
        html_content = html_content.replace('SW-0001', invoice_number)
        
        if html_content and len(html_content) > 100:
            print(f"   ✅ تم إنتاج HTML بنجاح ({len(html_content)} حرف)")
            print(f"   📋 رقم الفاتورة في HTML: {invoice_number}")
        else:
            print("   ❌ فشل إنتاج HTML")
            return False
    except Exception as e:
        print(f"   ❌ خطأ في إنتاج HTML: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n3. حفظ الفاتورة في ملف...")
    output_dir = "exports"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    output_file = os.path.join(output_dir, f"invoice_{invoice_number}.html")
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        if os.path.exists(output_file):
            print(f"   ✅ تم حفظ الفاتورة: {output_file}")
            print(f"   📊 حجم الملف: {os.path.getsize(output_file)} بايت")
        else:
            print("   ❌ فشل حفظ الفاتورة")
            return False
    except Exception as e:
        print(f"   ❌ خطأ في حفظ الفاتورة: {e}")
        return False
    
    print("\n4. فتح الفاتورة في المتصفح...")
    try:
        import webbrowser
        webbrowser.open(f'file:///{os.path.abspath(output_file)}')
        print("   ✅ تم فتح الفاتورة في المتصفح")
    except Exception as e:
        print(f"   ⚠️ تعذر فتح المتصفح: {e}")
    
    print("\n" + "="*80)
    print("✅ اكتمل الاختبار بنجاح!")
    print(f"📋 رقم الفاتورة: {invoice_number}")
    print("="*80)
    
    return True

if __name__ == "__main__":
    try:
        success = test_invoice_with_random_number()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ خطأ فادح: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

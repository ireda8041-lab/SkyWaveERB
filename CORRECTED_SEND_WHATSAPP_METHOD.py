# الكود المُصحح لدالة send_invoice_whatsapp مع المحاذاة الصحيحة

    def send_invoice_whatsapp(self):
        """إرسال فاتورة المشروع المحدد عبر الواتساب مع التحقق الصارم من البيانات"""
        try:
            # Step 1: التحقق من تحديد مشروع
            if not self.selected_project:
                QMessageBox.warning(self, "تنبيه", "يرجى تحديد مشروع أولاً")
                return
            
            # Step 2: جلب بيانات العميل الحقيقية
            client = self.client_service.get_client_by_id(self.selected_project.client_id)
            if not client:
                QMessageBox.critical(self, "خطأ", "لم يتم العثور على معلومات العميل")
                return
            
            # Step 3: التحقق الصارم من رقم الهاتف
            client_phone = getattr(client, 'phone', None) or getattr(client, 'phone_number', None)
            if not client_phone or not client_phone.strip():
                QMessageBox.critical(
                    self, 
                    "❌ رقم الهاتف مفقود", 
                    f"العميل '{client.name}' لا يحتوي على رقم هاتف!\n\n"
                    f"يرجى إضافة رقم الهاتف أولاً من إدارة العملاء."
                )
                return
            
            # تنظيف رقم الهاتف والتحقق من صحته
            clean_phone = client_phone.replace("+", "").replace(" ", "").replace("-", "")
            if not clean_phone.isdigit() or len(clean_phone) < 10:
                QMessageBox.critical(
                    self, 
                    "❌ رقم هاتف غير صحيح", 
                    f"رقم الهاتف '{client_phone}' غير صحيح!\n\n"
                    f"يرجى التأكد من صحة الرقم في إدارة العملاء."
                )
                return
            
            # Step 4: تحضير بيانات الفاتورة الحقيقية
            invoice_data = {
                'invoice_id': f"INV-{self.selected_project.name}",
                'invoice_number': f"SW-{datetime.now().strftime('%Y%m%d%H%M')}",
                'client_name': client.name,
                'client_phone': client_phone,
                'client_address': getattr(client, 'address', ''),
                'client_email': getattr(client, 'email', ''),
                'project_name': self.selected_project.name,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'due_date': (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d'),
            }
            
            # Step 5: جلب بيانات الدفعات الحقيقية
            payments_data = []
            try:
                payments = self.project_service.get_payments_for_project(self.selected_project.name)
                for payment in payments:
                    account_name = "نقدي"
                    try:
                        account = self.accounting_service.repo.get_account_by_code(payment.account_id)
                        if account:
                            account_name = account.name
                    except:
                        pass
                    payments_data.append({
                        'date': payment.date.strftime('%Y-%m-%d') if hasattr(payment.date, 'strftime') else str(payment.date),
                        'amount': float(payment.amount),
                        'method': account_name,
                        'account_name': account_name
                    })
            except Exception as e:
                print(f"WARNING: فشل في جلب الدفعات: {e}")
                payments_data = []
            
            # Step 6: إنشاء HTML للفاتورة
            if not self.template_service:
                QMessageBox.critical(self, "خطأ", "خدمة القوالب غير متوفرة")
                return
            
            # تحضير معلومات العميل للقالب
            client_info = {
                'name': client.name,
                'phone': client_phone,
                'address': getattr(client, 'address', ''),
                'email': getattr(client, 'email', '')
            }
            
            # إنشاء HTML
            html_content = self.template_service.generate_invoice_html(
                project=self.selected_project,
                client_info=client_info,
                template_id=None,  # استخدام القالب الافتراضي
                payments=payments_data
            )
            
            if not html_content:
                QMessageBox.critical(self, "خطأ", "فشل في إنشاء محتوى الفاتورة")
                return
            
            # Step 7: تأكيد الإرسال من المستخدم
            reply = QMessageBox.question(
                self,
                "تأكيد الإرسال",
                f"هل تريد إرسال فاتورة المشروع '{self.selected_project.name}' "
                f"للعميل '{client.name}' على الرقم '{client_phone}'؟\n\n"
                f"⚠️ تأكد من صحة رقم الهاتف قبل الإرسال!",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
            
            # Step 8: استخدام SmartInvoiceManager للإرسال
            try:
                from services.smart_invoice_manager import SmartInvoiceManager
                
                # إنشاء رسالة مخصصة
                message = f"مرحباً {client.name}،\n\nنرسل لك فاتورة مشروع '{self.selected_project.name}'.\n\nشكراً لثقتكم."
                
                # عرض شاشة تحميل
                progress_dialog = QMessageBox(self)
                progress_dialog.setWindowTitle("جاري الإرسال...")
                progress_dialog.setText("🔄 جاري إنشاء PDF وإرسال الفاتورة عبر الواتساب...\n\nيرجى الانتظار...")
                progress_dialog.setStandardButtons(QMessageBox.StandardButton.NoButton)
                progress_dialog.show()
                
                # معالجة الأحداث لعرض الرسالة
                from PyQt6.QtWidgets import QApplication
                QApplication.processEvents()
                
                # تنفيذ العملية
                manager = SmartInvoiceManager()
                success, result_message = manager.process_and_send(
                    invoice_data=invoice_data,
                    html_content=html_content,
                    phone_number=client_phone,
                    message=message
                )
                
                # إغلاق شاشة التحميل
                progress_dialog.close()
                
                # عرض النتيجة
                if success:
                    QMessageBox.information(
                        self,
                        "✅ تم الإرسال بنجاح",
                        f"{result_message}\n\n"
                        f"📱 العميل: {client.name}\n"
                        f"📞 الرقم: {client_phone}"
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "⚠️ فشل الإرسال",
                        f"{result_message}\n\n"
                        f"💡 تأكد من:\n"
                        f"• اتصال الإنترنت\n"
                        f"• تسجيل الدخول في WhatsApp Web\n"
                        f"• صحة رقم الهاتف"
                    )
                
            except ImportError:
                QMessageBox.critical(
                    self,
                    "❌ خطأ في النظام",
                    "مكتبة SmartInvoiceManager غير متوفرة!\n\n"
                    "يرجى تثبيت المتطلبات:\n"
                    "pip install selenium webdriver-manager"
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "❌ خطأ غير متوقع",
                    f"حدث خطأ أثناء الإرسال:\n{str(e)}\n\n"
                    f"يرجى المحاولة مرة أخرى أو التواصل مع الدعم الفني."
                )
                import traceback
                traceback.print_exc()
                
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل في إرسال الفاتورة عبر الواتساب:\n{str(e)}")
            import traceback
            traceback.print_exc()
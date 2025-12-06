# Requirements Document

## Introduction

ميزة "المسح الذكي" (Smart Scan) تتيح للمستخدم رفع صورة إيصال دفع (سكرين شوت من فودافون كاش، إنستا باي، أو تحويل بنكي) ليقوم الذكاء الاصطناعي باستخراج البيانات تلقائياً وملء حقول تسجيل الدفعة.

## Glossary

- **Smart Scan**: ميزة المسح الذكي لاستخراج بيانات الدفع من الصور
- **Payment Entry**: شاشة تسجيل الدفعات في النظام
- **LLM Vision**: نموذج ذكاء اصطناعي قادر على تحليل الصور (Google Gemini 1.5 Flash - مجاني)
- **Receipt Screenshot**: صورة إيصال الدفع من المحافظ الإلكترونية أو البنوك
- **Auto-fill**: الملء التلقائي للحقول بناءً على البيانات المستخرجة

## Requirements

### Requirement 1: واجهة رفع الصور

**User Story:** As a user, I want to upload a payment receipt screenshot, so that I can automatically fill payment details without manual entry.

#### Acceptance Criteria

1. WHEN the user opens the payment entry dialog THEN the system SHALL display a file upload dropzone with the label "ارفع سكرين شوت التحويل لملء البيانات تلقائياً"
2. WHEN the user selects or drops an image file THEN the system SHALL display a loading indicator with text "جاري المسح الذكي..."
3. WHEN the user selects a non-image file THEN the system SHALL display an error message and reject the file
4. WHEN the upload area is empty THEN the system SHALL display a dashed border with an upload icon

### Requirement 2: معالجة الصورة بالذكاء الاصطناعي

**User Story:** As a system, I want to analyze payment receipt images using AI Vision, so that I can extract structured payment data.

#### Acceptance Criteria

1. WHEN the system receives an image THEN the system SHALL send the image to the AI Vision API (Gemini 1.5 Flash) with a structured extraction prompt
2. WHEN the AI processes the image THEN the system SHALL extract: amount, date, reference_number, sender_name, platform
3. WHEN the AI returns data THEN the system SHALL format the date as YYYY-MM-DD and amount as a number
4. WHEN a field cannot be extracted THEN the system SHALL return null for that field
5. WHEN the AI response is received THEN the system SHALL parse the JSON and return structured data to the frontend

### Requirement 3: الملء التلقائي للحقول

**User Story:** As a user, I want the extracted data to automatically fill the payment form fields, so that I can save time and reduce errors.

#### Acceptance Criteria

1. WHEN the AI returns extracted data THEN the system SHALL auto-fill the Amount field with the extracted amount
2. WHEN the AI returns extracted data THEN the system SHALL auto-fill the Date field with the extracted date
3. WHEN the AI returns extracted data THEN the system SHALL auto-fill the Reference Number field with the extracted reference
4. WHEN the AI identifies the platform (Vodafone Cash, InstaPay) THEN the system SHALL attempt to select the matching payment account
5. WHEN auto-fill completes THEN the system SHALL allow the user to review and modify the filled data before saving

### Requirement 4: معالجة الأخطاء

**User Story:** As a user, I want clear error messages when scanning fails, so that I can understand what went wrong and take corrective action.

#### Acceptance Criteria

1. IF the image is unclear or unreadable THEN the system SHALL display "الصورة غير واضحة، يرجى رفع صورة أوضح"
2. IF the AI API is unavailable THEN the system SHALL display "خدمة المسح الذكي غير متاحة حالياً"
3. IF no payment data is found in the image THEN the system SHALL display "لم يتم العثور على بيانات دفع في الصورة"
4. WHEN an error occurs THEN the system SHALL hide the loading indicator and allow the user to try again

### Requirement 5: تكوين API Key

**User Story:** As an administrator, I want to configure the AI API key, so that the smart scan feature can connect to the AI service.

#### Acceptance Criteria

1. WHEN the system starts THEN the system SHALL load the Gemini API key from environment variables or settings file
2. IF the API key is not configured THEN the system SHALL disable the smart scan feature and display a configuration message
3. WHEN the API key is invalid THEN the system SHALL display "مفتاح API غير صالح"

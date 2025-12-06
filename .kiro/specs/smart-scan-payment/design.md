# Design Document: Smart Scan Payment

## Overview

ميزة "المسح الذكي" (Smart Scan) تضيف قدرة استخراج بيانات الدفع تلقائياً من صور إيصالات الدفع (فودافون كاش، إنستا باي، تحويلات بنكية) باستخدام الذكاء الاصطناعي (Google Gemini 1.5 Flash - Free Tier).

### Key Features
- رفع صور إيصالات الدفع عبر Drag & Drop أو اختيار ملف
- استخراج البيانات باستخدام AI Vision (Google Gemini 1.5 Flash - مجاني)
- ملء تلقائي لحقول: المبلغ، التاريخ، الرقم المرجعي، المحفظة
- معالجة أخطاء شاملة مع رسائل واضحة بالعربية

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PaymentDialog (UI)                        │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           SmartScanDropzone Widget                   │    │
│  │  - File selection / Drag & Drop                      │    │
│  │  - Loading indicator                                 │    │
│  │  - Error display                                     │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                  │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              SmartScanService                        │    │
│  │  - Image encoding (Base64)                           │    │
│  │  - API communication                                 │    │
│  │  - Response parsing                                  │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                  │
└───────────────────────────│──────────────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────────┐
              │   Google Gemini 1.5 Flash   │
              │   (Free Tier - Vision API)  │
              └─────────────────────────────┘
```

## Components and Interfaces

### 1. SmartScanDropzone (UI Widget)

```python
class SmartScanDropzone(QFrame):
    """Widget لرفع صور إيصالات الدفع"""
    
    # Signals
    scan_started = pyqtSignal()           # بدء المسح
    scan_completed = pyqtSignal(dict)     # اكتمال المسح مع البيانات
    scan_failed = pyqtSignal(str)         # فشل المسح مع رسالة الخطأ
    
    def __init__(self, parent=None):
        """Initialize dropzone with upload icon and label"""
        
    def set_loading(self, loading: bool):
        """Toggle loading state"""
        
    def set_error(self, message: str):
        """Display error message"""
        
    def reset(self):
        """Reset to initial state"""
```

### 2. SmartScanService (Backend Service)

```python
class SmartScanService:
    """خدمة المسح الذكي باستخدام AI Vision"""
    
    def __init__(self, api_key: str = None):
        """Initialize with OpenAI API key"""
        
    def is_available(self) -> bool:
        """Check if service is configured and available"""
        
    async def scan_receipt(self, image_path: str) -> ScanResult:
        """Scan receipt image and extract payment data"""
        
    def _encode_image(self, image_path: str) -> str:
        """Encode image to base64"""
        
    def _parse_response(self, response: str) -> dict:
        """Parse AI response JSON"""
```

### 3. ScanResult (Data Model)

```python
@dataclass
class ScanResult:
    success: bool
    amount: Optional[float] = None
    date: Optional[str] = None           # YYYY-MM-DD format
    reference_number: Optional[str] = None
    sender_name: Optional[str] = None
    platform: Optional[str] = None       # Vodafone Cash, InstaPay, etc.
    error_message: Optional[str] = None
```

### 4. Integration with PaymentDialog

```python
# في PaymentDialog.__init__
self.smart_scan = SmartScanDropzone()
self.smart_scan.scan_completed.connect(self._on_scan_completed)
self.smart_scan.scan_failed.connect(self._on_scan_failed)

def _on_scan_completed(self, data: dict):
    """Auto-fill form fields with extracted data"""
    if data.get('amount'):
        self.amount_input.setValue(data['amount'])
    if data.get('date'):
        self.date_input.setDate(QDate.fromString(data['date'], 'yyyy-MM-dd'))
    if data.get('reference_number'):
        self.reference_input.setText(data['reference_number'])
    if data.get('platform'):
        self._select_account_by_platform(data['platform'])
```

## Data Models

### ScanResult Schema

| Field | Type | Description |
|-------|------|-------------|
| success | bool | Whether extraction succeeded |
| amount | float? | Extracted payment amount |
| date | str? | Payment date (YYYY-MM-DD) |
| reference_number | str? | Transaction reference |
| sender_name | str? | Sender name if available |
| platform | str? | Payment platform (Vodafone Cash, InstaPay, Bank) |
| error_message | str? | Error description if failed |

### AI Prompt Template

```
Analyze this payment receipt screenshot (Vodafone Cash, InstaPay, or Bank Transfer). 
Extract the following data into a clean JSON format only:
- amount (number)
- date (YYYY-MM-DD format)
- reference_number (string)
- sender_name (string, if available)
- platform (e.g., Vodafone Cash, InstaPay)

If a field is missing, return null. Do not include markdown formatting.
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: File Type Validation
*For any* file selected by the user, if the file is not an image (jpg, png, gif, webp), the system should reject it and display an error message.
**Validates: Requirements 1.3**

### Property 2: AI Response Parsing Consistency
*For any* valid JSON response from the AI API containing payment data fields, the parser should extract all present fields correctly and return null for missing fields.
**Validates: Requirements 2.2, 2.4**

### Property 3: Date Format Normalization
*For any* date string extracted by the AI (in various formats), the system should normalize it to YYYY-MM-DD format.
**Validates: Requirements 2.3**

### Property 4: Amount Type Conversion
*For any* amount value extracted by the AI (string or number), the system should convert it to a valid float number.
**Validates: Requirements 2.3**

### Property 5: Platform Account Matching
*For any* platform name (Vodafone Cash, InstaPay, Bank), the system should attempt to find and select the best matching account from the available accounts list.
**Validates: Requirements 3.4**

## Error Handling

| Error Scenario | Error Message (Arabic) | Recovery Action |
|----------------|------------------------|-----------------|
| Non-image file | "يرجى اختيار ملف صورة (JPG, PNG)" | Allow retry |
| Image too large (>10MB) | "حجم الصورة كبير جداً، الحد الأقصى 10MB" | Allow retry |
| Unclear image | "الصورة غير واضحة، يرجى رفع صورة أوضح" | Allow retry |
| API unavailable | "خدمة المسح الذكي غير متاحة حالياً" | Manual entry |
| No data found | "لم يتم العثور على بيانات دفع في الصورة" | Manual entry |
| Invalid API key | "مفتاح API غير صالح" | Check settings |
| Network error | "خطأ في الاتصال، يرجى المحاولة مرة أخرى" | Allow retry |

## Testing Strategy

### Dual Testing Approach

#### Unit Tests
- Test file type validation (accept images, reject others)
- Test image encoding to base64
- Test JSON response parsing
- Test date format normalization
- Test amount conversion
- Test platform-to-account matching

#### Property-Based Tests
Using `hypothesis` library for Python:

1. **Property 1 Test**: Generate random file extensions and verify correct acceptance/rejection
2. **Property 2 Test**: Generate random JSON structures and verify parsing consistency
3. **Property 3 Test**: Generate various date formats and verify normalization
4. **Property 4 Test**: Generate various amount representations and verify conversion
5. **Property 5 Test**: Generate platform names and verify account matching logic

### Test Configuration
- Property tests: minimum 100 iterations per property
- Each test tagged with: `**Feature: smart-scan-payment, Property {N}: {description}**`

## Configuration

### Settings File (skywave_settings.json)

```json
{
  "smart_scan": {
    "enabled": true,
    "gemini_api_key": "AIza...",
    "model": "gemini-1.5-flash",
    "max_image_size_mb": 10
  }
}
```

### Environment Variables (Alternative)
```
GEMINI_API_KEY=AIza...
```

### Getting a Free Gemini API Key
1. Go to https://aistudio.google.com/app/apikey
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the key and paste it in settings

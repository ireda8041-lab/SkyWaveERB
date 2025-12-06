# 📊 Enterprise Chart of Accounts - SkyWave ERP

## 🎯 Overview

A professional, enterprise-level chart of accounts system designed specifically for digital marketing and software development companies. This system follows international accounting standards (IFRS, GAAP) and implements best practices for financial reporting.

---

## ✨ Key Features

### 1. **6-Digit Unified Codes**
```
Old System (4 digits): 1000, 1100, 1101 ❌
New System (6 digits): 100000, 110000, 111101 ✅
```

**Benefits:**
- Consistent length for easy sorting
- Scalability (999 sub-accounts per group)
- Database-friendly structure

### 2. **COGS vs OPEX Separation**
```
500000 → Cost of Revenue (COGS)
  510001 → Ads Spend
  510002 → Hosting & Servers
  510003 → Outsourcing Cost

600000 → Operating Expenses (OPEX)
  620001 → Salaries
  620002 → Rent & Utilities
  620004 → Software Subscriptions
```

**Financial Benefit:**
```
Revenue:                    100,000
- Cost of Revenue (COGS):   (30,000)
─────────────────────────────────────
= Gross Profit Margin:       70,000  (70%)
─────────────────────────────────────
- Operating Expenses (OPEX): (20,000)
─────────────────────────────────────
= Net Profit:                50,000  (50%)
```

### 3. **Unearned Revenue Handling**
```json
{
  "code": "212100",
  "name_ar": "دفعات مقدمة من العملاء",
  "name_en": "Unearned Revenue / Deposits"
}
```

**Correct Accounting:**
```
On Receipt:
  Dr. Bank (111201)              50,000
    Cr. Unearned Revenue (212100) 50,000

On Delivery:
  Dr. Unearned Revenue (212100)  50,000
    Cr. Service Revenue (410100)  50,000
```

### 4. **E-Wallet Support**
```
111301 → Vodafone Cash (Main)
111302 → Vodafone Cash (Sub)
111303 → InstaPay Clearing
```

---

## 📁 Files Included

| File | Description | Size |
|------|-------------|------|
| `chart_of_accounts_enterprise.json` | Complete chart of accounts (JSON) | ~45 accounts |
| `import_chart_of_accounts.py` | Smart import script | ~400 lines |
| `CHART_OF_ACCOUNTS_GUIDE.md` | Comprehensive guide (Arabic) | 3000+ words |
| `README_CHART_OF_ACCOUNTS.md` | Quick start guide (Arabic) | 500+ words |
| `MIGRATION_GUIDE.md` | Migration from old system (Arabic) | 1000+ words |
| `SUMMARY_AR.md` | Executive summary (Arabic) | 800+ words |

---

## 🚀 Quick Start

### Step 1: Import
```bash
# Standard import (recommended for first time)
python import_chart_of_accounts.py

# Force update existing accounts
python import_chart_of_accounts.py --force

# Clear old accounts and import fresh (⚠️ dangerous!)
python import_chart_of_accounts.py --clear --force
```

### Step 2: Verify
```python
from core.repository import Repository

repo = Repository()
accounts = repo.get_all_accounts()
print(f"✅ Total accounts: {len(accounts)}")

# Show cash accounts
cash_accounts = [acc for acc in accounts if acc.code.startswith('111')]
for acc in cash_accounts:
    print(f"  {acc.code} - {acc.name}")
```

### Step 3: Update Code (Optional)
If migrating from old system, update codes in:
- `services/accounting_service.py` (lines 23-27)
- `ui/settings_tab.py` (lines 1059-1060)

```python
# Old (4 digits)
ACC_RECEIVABLE_CODE = "1200"
SERVICE_REVENUE_CODE = "4100"

# New (6 digits)
ACC_RECEIVABLE_CODE = "112100"
SERVICE_REVENUE_CODE = "410100"
```

---

## 📊 Account Structure

### Main Groups (6):

```
100000 → Assets
  110000 → Current Assets
    111000 → Cash & Cash Equivalents
      111100 → Cash on Hand
        111101 → Main Office Treasury
        111102 → Staff Petty Cash
      111200 → Bank Accounts
        111201 → Banque Misr - EGP
      111300 → E-Wallets & Payment Gateways
        111301 → Vodafone Cash (Main)
        111302 → Vodafone Cash (Sub)
        111303 → InstaPay Clearing
    112000 → Accounts Receivable
      112100 → B2B Customers
      112200 → B2C Customers
    113000 → Other Debit Balances
      113100 → Prepaid Expenses
      113200 → Employee Loans
  120000 → Non-Current Assets
    121000 → Fixed Assets
      121100 → Computers & Servers
      121200 → Furniture & Fixtures

200000 → Liabilities
  210000 → Current Liabilities
    211000 → Accounts Payable
      211100 → Operational Suppliers
      211200 → Freelancers Payable
    212000 → Other Credit Balances
      212100 → Unearned Revenue / Deposits ⭐
      212200 → VAT Payable

300000 → Equity
  310000 → Capital
  320000 → Owner's Current Account
  330000 → Retained Earnings

400000 → Revenue
  410000 → Operating Revenue
    410100 → Digital Marketing Services Revenue
    410200 → Web & App Development Revenue
    410300 → Packages & Annual Contracts Revenue

500000 → Cost of Revenue (COGS)
  510000 → Operational Costs
    510001 → Ads Spend
    510002 → Servers & Hosting
    510003 → Outsourcing Cost

600000 → Operating Expenses (OPEX)
  610000 → Marketing Expenses
    610001 → Company Ads
    610002 → Sales Commissions
  620000 → G&A Expenses
    620001 → Salaries
    620002 → Rent & Utilities
    620003 → Internet & Comm.
    620004 → Software Subs
  630000 → Financial Expenses
    630001 → Bank Charges
```

---

## 📈 Financial Reports

### 1. Income Statement
```
Revenue (4xxxxx)                     100,000
- Cost of Revenue (5xxxxx)           (30,000)
─────────────────────────────────────────────
= Gross Profit                        70,000  (70%)
─────────────────────────────────────────────
- Operating Expenses (6xxxxx)        (20,000)
─────────────────────────────────────────────
= Net Profit                          50,000  (50%)
```

### 2. Balance Sheet
```
Assets (1xxxxx)                      280,000
Liabilities (2xxxxx)                  40,000
Equity (3xxxxx)                      240,000
```

### 3. Cash Flow Statement
```
Operating Cash Flow                  +50,000
Investing Cash Flow                  -10,000
Financing Cash Flow                  +20,000
Net Cash Flow                        +60,000
```

---

## 🎓 Accounting Standards

This chart of accounts complies with:
- ✅ Egyptian Accounting Standards (EAS)
- ✅ International Financial Reporting Standards (IFRS)
- ✅ Generally Accepted Accounting Principles (GAAP)

---

## 🔧 Integration with Existing System

### Files Affected:
1. ✅ `core/schemas.py` - Already supports new system
2. ⚠️ `services/accounting_service.py` - Needs code update
3. ⚠️ `ui/settings_tab.py` - Needs filter update

### Required Updates:
```python
# In accounting_service.py (lines 23-27)
ACC_RECEIVABLE_CODE = "112100"      # Instead of "1200"
SERVICE_REVENUE_CODE = "410100"     # Instead of "4100"
VAT_PAYABLE_CODE = "212200"         # Instead of "2100"
CASH_ACCOUNT_CODE = "111101"        # Instead of "1111"
```

---

## 🔄 Migration Options

### Option 1: Full Migration (Recommended for new companies)
```bash
python import_chart_of_accounts.py --clear --force
```

### Option 2: Gradual Migration (Recommended for existing companies)
```bash
python import_chart_of_accounts.py
# Keep old accounts, add new ones gradually
```

### Option 3: Dual System (For large companies)
```python
# Run both systems in parallel for 3-6 months
USE_NEW_SYSTEM = False  # Switch to True when ready
```

---

## 💡 Best Practices

1. **Don't modify main codes** (100000, 200000, etc.)
2. **Add sub-accounts** under existing groups
3. **Use transactional accounts only** in journal entries
4. **Review reports monthly** to track gross margin
5. **Backup before major changes**

---

## 🆘 Troubleshooting

### Issue: "Account not found"
```
ERROR: Debit account 1200 not found!
```

**Solution:**
```python
# Update code in accounting_service.py
ACC_RECEIVABLE_CODE = "112100"  # Instead of "1200"
```

### Issue: "Old journal entries not showing"
```
WARNING: Journal entry references old account code
```

**Solution:**
```bash
# Run migration script
python migrate_accounts.py
```

### Issue: "Balance mismatch"
```
ERROR: Account balance mismatch
```

**Solution:**
```python
# Recalculate all balances
from core.repository import Repository
repo = Repository()
repo.recalculate_all_balances()
```

---

## 📚 Documentation

| Document | Language | Purpose |
|----------|----------|---------|
| `CHART_OF_ACCOUNTS_GUIDE.md` | Arabic | Comprehensive guide (3000+ words) |
| `README_CHART_OF_ACCOUNTS.md` | Arabic | Quick start guide |
| `MIGRATION_GUIDE.md` | Arabic | Migration from old system |
| `SUMMARY_AR.md` | Arabic | Executive summary |
| `CHART_OF_ACCOUNTS_README.md` | English | This file |

---

## 🎉 Summary

A professional accounting system featuring:

✅ **6-digit unified codes** - Easy scalability
✅ **COGS vs OPEX separation** - True profit margins
✅ **Unearned revenue handling** - Correct accounting
✅ **E-wallet support** - Egyptian market ready
✅ **International standards** - IFRS, GAAP, EAS compliant
✅ **Easy import** - 3 steps only
✅ **Comprehensive docs** - 4 reference files

---

**Ready to use! 🚀**

Prepared by Kiro AI for SkyWave ERP

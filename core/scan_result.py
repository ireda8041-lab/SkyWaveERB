"""
ScanResult dataclass for Smart Scan Payment feature.
Contains the structured result of AI-based receipt scanning.
"""

from dataclasses import dataclass


@dataclass
class ScanResult:
    """
    نتيجة المسح الذكي لإيصال الدفع

    Attributes:
        success: Whether the extraction succeeded
        amount: Extracted payment amount
        date: Payment date in YYYY-MM-DD format
        reference_number: Transaction reference number
        sender_name: Sender name if available
        platform: Payment platform (Vodafone Cash, InstaPay, Bank, etc.)
        error_message: Error description if extraction failed
    """
    success: bool
    amount: float | None = None
    date: str | None = None  # YYYY-MM-DD format
    reference_number: str | None = None
    sender_name: str | None = None
    platform: str | None = None
    error_message: str | None = None

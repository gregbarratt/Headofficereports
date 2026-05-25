ARCHIVED_UPLOAD_TYPES = {
    "master_booking": "Master Booking Report",
}

UPLOAD_TYPES = {
    "old_booking": "Old Bookings",
    "supplier_payment_taps": "Supplier Payments TAPs",
    "supplier_payment_tt": "Supplier Payments TT (Human Input)",
    "customer_payment_sings": "Customer Payments SINGs",
    "customer_payment_tt": "Customer Payments TT (Human Input)",
    "bank_statement": "Bank / Trust Statement",
    "insurance": "Insurance Costs",
    "agent_allocation": "Agent Allocation Import",
    "agent_commission": "Agent Commission Import",
    "refund": "Refund Import",
}

SYSTEM_UPLOAD_TYPES = {
    "felloh_customer_payment_sync": "Felloh / SINGs API Sync",
    "felloh_customer_payment_backfill": "Felloh / SINGs Catch-up Sync",
}

LEGACY_UPLOAD_TYPES = {
    "supplier_payment": "Supplier Payments TAPs",
    "customer_payment": "Customer Payments SINGs",
}

ALL_UPLOAD_TYPES = {**ARCHIVED_UPLOAD_TYPES, **UPLOAD_TYPES, **LEGACY_UPLOAD_TYPES, **SYSTEM_UPLOAD_TYPES}
FILE_UPLOAD_TYPES = {**UPLOAD_TYPES, **LEGACY_UPLOAD_TYPES}

ALLOWED_UPLOAD_EXTENSIONS = {".csv", ".xlsx"}

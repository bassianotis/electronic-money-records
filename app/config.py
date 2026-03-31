"""Business configuration and defaults for Big Tech Accounting."""

BUSINESS_INFO = {
    'name': 'Big Tech LLC',
    'address_line1': '1057 Fuller Ave SE',
    'address_line2': 'Grand Rapids, MI 49506-3244',
    'email': 'billing@meetbigtech.com',
    'phone': '+1 (616) 690-8952',
}

# Invoice config
INVOICE_START_NUMBER = 1037
INVOICE_DEFAULT_TERMS = 'Net 15'

# Services offered (for invoice line items)
SERVICES = [
    'Product Management',
    'Design',
    'General Business Support',
    'Reimbursable Expenses',
    'Services',
    'Web Development',
    'Web Hosting',
]

# Default expense categories with Schedule C line mapping
DEFAULT_CATEGORIES = [
    # Income
    {'name': 'Income', 'type': 'income', 'schedule_c_line': 'Line 1'},
    # Expenses
    {'name': 'Software & Subscriptions', 'type': 'expense', 'schedule_c_line': 'Line 18'},
    {'name': 'Travel - Airfare', 'type': 'expense', 'schedule_c_line': 'Line 24a'},
    {'name': 'Travel - Lodging', 'type': 'expense', 'schedule_c_line': 'Line 24a'},
    {'name': 'Travel - Meals', 'type': 'expense', 'schedule_c_line': 'Line 24b'},
    {'name': 'Travel - Transport', 'type': 'expense', 'schedule_c_line': 'Line 24a'},
    {'name': 'Travel - Visas', 'type': 'expense', 'schedule_c_line': 'Line 24a'},
    {'name': 'Contract Labor', 'type': 'expense', 'schedule_c_line': 'Line 11'},
    {'name': 'Business Meals', 'type': 'expense', 'schedule_c_line': 'Line 24b'},
    {'name': 'Home Office', 'type': 'expense', 'schedule_c_line': 'Line 30'},
    {'name': 'Web Hosting', 'type': 'expense', 'schedule_c_line': 'Line 18'},
    {'name': 'State Filing Fees', 'type': 'expense', 'schedule_c_line': 'Line 23'},
    # Transfers (not on P&L)
    {'name': 'Transfer', 'type': 'transfer', 'schedule_c_line': None},
    {'name': 'Owner Draw (Payroll)', 'type': 'transfer', 'schedule_c_line': None},
]

# Default categorization rules (keyword → category name)
DEFAULT_RULES = [
    # Software & Subscriptions
    {'keyword': 'FIGMA', 'category': 'Software & Subscriptions', 'priority': 10},
    {'keyword': 'OPENAI', 'category': 'Software & Subscriptions', 'priority': 10},
    {'keyword': 'BOTPRESS', 'category': 'Software & Subscriptions', 'priority': 10},
    {'keyword': 'ELEMENTOR', 'category': 'Software & Subscriptions', 'priority': 10},
    {'keyword': 'CARGO', 'category': 'Software & Subscriptions', 'priority': 10},
    {'keyword': 'Adobe', 'category': 'Software & Subscriptions', 'priority': 10},
    # Web Hosting
    {'keyword': 'SITEGROUND', 'category': 'Web Hosting', 'priority': 10},
    # Travel - Airfare
    {'keyword': 'DELTA', 'category': 'Travel - Airfare', 'priority': 10},
    {'keyword': 'UNITED', 'category': 'Travel - Airfare', 'priority': 10},
    {'keyword': 'AMERICAN', 'category': 'Travel - Airfare', 'priority': 10},
    # Travel - Transport
    {'keyword': 'CURB', 'category': 'Travel - Transport', 'priority': 10},
    {'keyword': 'MTA*METROCARD', 'category': 'Travel - Transport', 'priority': 10},
    {'keyword': 'OMNY', 'category': 'Travel - Transport', 'priority': 10},
    {'keyword': 'NJT MOBILE', 'category': 'Travel - Transport', 'priority': 10},
    {'keyword': 'HERTZ', 'category': 'Travel - Transport', 'priority': 10},
    # Travel - Lodging
    {'keyword': 'BOOKING.COM', 'category': 'Travel - Lodging', 'priority': 10},
    {'keyword': 'KLARNA*BOOKING', 'category': 'Travel - Lodging', 'priority': 10},
    {'keyword': 'KLARNA* BOOKING', 'category': 'Travel - Lodging', 'priority': 10},
    # Travel - Visas
    {'keyword': 'ETA-IL', 'category': 'Travel - Visas', 'priority': 10},
    {'keyword': 'International Transaction Fee', 'category': 'Travel - Visas', 'priority': 10},
    # State Filing
    {'keyword': 'MI CORPORATIONS DIV', 'category': 'State Filing Fees', 'priority': 10},
    # QuickBooks (will stop appearing after cancellation)
    {'keyword': 'INTUIT', 'category': 'Software & Subscriptions', 'priority': 5},
    {'keyword': 'QBOOKS', 'category': 'Software & Subscriptions', 'priority': 5},
    # Income - clients
    {'keyword': 'BRYA', 'category': 'Income', 'priority': 10},
    {'keyword': 'Common Agency', 'category': 'Income', 'priority': 10},
    {'keyword': 'Kind Collective', 'category': 'Income', 'priority': 10},
    {'keyword': 'Lakeshore', 'category': 'Income', 'priority': 10},
    {'keyword': 'VENMO', 'category': 'Income', 'priority': 5},
    # Transfers
    {'keyword': 'Tfr to', 'category': 'Transfer', 'priority': 20},
    {'keyword': 'Tfr from', 'category': 'Transfer', 'priority': 20},
    {'keyword': 'Transfer Withdrawal', 'category': 'Transfer', 'priority': 20},
    {'keyword': 'Transfer Deposit', 'category': 'Transfer', 'priority': 20},
    {'keyword': 'Dividend Credit', 'category': 'Transfer', 'priority': 15},
]

# Account mappings from CCU exports
DEFAULT_ACCOUNTS = [
    {'name': 'Check Deposits', 'account_id': 'CKG|9201862423',
     'description': 'Income deposits from clients'},
    {'name': 'Expenses', 'account_id': 'CKG|9201862456',
     'description': 'Business expenses'},
    {'name': 'Payroll', 'account_id': 'CKG|9201862464',
     'description': 'Pass-through to personal checking'},
    {'name': 'Savings', 'account_id': 'SAV|9103272069',
     'description': 'Savings account'},
]

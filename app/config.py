"""Business configuration and defaults for the generalized Accounting Suite.

NOTE: Business identity, services, and invoice settings are now
configured via Settings → Business Profile (stored in the DB).
The values below are only used as initial defaults for config.py
references that haven't been migrated yet.
"""

# Legacy defaults — override via Settings → Business Profile
BUSINESS_INFO = {
    'name': 'My Business LLC',
    'address_line1': '',
    'address_line2': '',
    'email': '',
    'phone': '',
}

# Invoice config (legacy — override via Settings → Business Profile)
INVOICE_START_NUMBER = 1001
INVOICE_DEFAULT_TERMS = 'Net 15'

# Services offered (legacy — override via Settings → Business Profile)
SERVICES = [
    'Consulting',
    'Services',
]

# Default expense categories — IRS Schedule C line mapping
# These seed on first install. Users can add/edit/delete via Settings → Categories.
DEFAULT_CATEGORIES = [
    # Income
    {'name': 'Income', 'type': 'income', 'schedule_c_line': 'Line 1'},
    {'name': 'Other Income', 'type': 'income', 'schedule_c_line': 'Line 6'},
    # Expenses — mirrors IRS Schedule C lines
    {'name': 'Advertising', 'type': 'expense', 'schedule_c_line': 'Line 8'},
    {'name': 'Car & Truck', 'type': 'expense', 'schedule_c_line': 'Line 9'},
    {'name': 'Commissions & Fees', 'type': 'expense', 'schedule_c_line': 'Line 10'},
    {'name': 'Contract Labor', 'type': 'expense', 'schedule_c_line': 'Line 11'},
    {'name': 'Insurance', 'type': 'expense', 'schedule_c_line': 'Line 15'},
    {'name': 'Interest (Mortgage)', 'type': 'expense', 'schedule_c_line': 'Line 16a'},
    {'name': 'Interest (Other)', 'type': 'expense', 'schedule_c_line': 'Line 16b'},
    {'name': 'Legal & Professional', 'type': 'expense', 'schedule_c_line': 'Line 17'},
    {'name': 'Office Expenses', 'type': 'expense', 'schedule_c_line': 'Line 18'},
    {'name': 'Software & Subscriptions', 'type': 'expense', 'schedule_c_line': 'Line 18'},
    {'name': 'Rent (Business Property)', 'type': 'expense', 'schedule_c_line': 'Line 20b'},
    {'name': 'Repairs & Maintenance', 'type': 'expense', 'schedule_c_line': 'Line 21'},
    {'name': 'Supplies', 'type': 'expense', 'schedule_c_line': 'Line 22'},
    {'name': 'Taxes & Licenses', 'type': 'expense', 'schedule_c_line': 'Line 23'},
    {'name': 'Travel - Airfare', 'type': 'expense', 'schedule_c_line': 'Line 24a'},
    {'name': 'Travel - Lodging', 'type': 'expense', 'schedule_c_line': 'Line 24a'},
    {'name': 'Travel - Transport', 'type': 'expense', 'schedule_c_line': 'Line 24a'},
    {'name': 'Travel - Meals', 'type': 'expense', 'schedule_c_line': 'Line 24b'},
    {'name': 'Business Meals', 'type': 'expense', 'schedule_c_line': 'Line 24b'},
    {'name': 'Utilities', 'type': 'expense', 'schedule_c_line': 'Line 25'},
    {'name': 'Home Office', 'type': 'expense', 'schedule_c_line': 'Line 30'},
    # Transfers (not on P&L)
    {'name': 'Transfer', 'type': 'transfer', 'schedule_c_line': None},
    {'name': 'Owner Draw', 'type': 'transfer', 'schedule_c_line': None},
]

# Default categorization rules (keyword → category name)
# These seed on first install. Users can add/edit/delete via Settings → Categorization Rules.
# Only universally recognizable vendors are included.
DEFAULT_RULES = [
    # Software & Subscriptions
    {'keyword': 'ADOBE', 'category': 'Software & Subscriptions', 'priority': 10},
    {'keyword': 'GOOGLE*CLOUD', 'category': 'Software & Subscriptions', 'priority': 10},
    {'keyword': 'MICROSOFT', 'category': 'Software & Subscriptions', 'priority': 5},
    {'keyword': 'APPLE.COM', 'category': 'Software & Subscriptions', 'priority': 5},
    {'keyword': 'OPENAI', 'category': 'Software & Subscriptions', 'priority': 10},
    {'keyword': 'DROPBOX', 'category': 'Software & Subscriptions', 'priority': 10},
    {'keyword': 'SLACK', 'category': 'Software & Subscriptions', 'priority': 10},
    {'keyword': 'ZOOM', 'category': 'Software & Subscriptions', 'priority': 10},
    # Office Expenses
    {'keyword': 'AMAZON', 'category': 'Office Expenses', 'priority': 3},
    {'keyword': 'STAPLES', 'category': 'Office Expenses', 'priority': 10},
    {'keyword': 'OFFICE DEPOT', 'category': 'Office Expenses', 'priority': 10},
    # Travel - Airfare
    {'keyword': 'DELTA', 'category': 'Travel - Airfare', 'priority': 10},
    {'keyword': 'UNITED', 'category': 'Travel - Airfare', 'priority': 10},
    {'keyword': 'AMERICAN AIR', 'category': 'Travel - Airfare', 'priority': 10},
    {'keyword': 'SOUTHWEST', 'category': 'Travel - Airfare', 'priority': 10},
    {'keyword': 'JETBLUE', 'category': 'Travel - Airfare', 'priority': 10},
    # Travel - Transport
    {'keyword': 'UBER', 'category': 'Travel - Transport', 'priority': 10},
    {'keyword': 'LYFT', 'category': 'Travel - Transport', 'priority': 10},
    {'keyword': 'HERTZ', 'category': 'Travel - Transport', 'priority': 10},
    {'keyword': 'ENTERPRISE', 'category': 'Travel - Transport', 'priority': 10},
    # Travel - Lodging
    {'keyword': 'HILTON', 'category': 'Travel - Lodging', 'priority': 10},
    {'keyword': 'MARRIOTT', 'category': 'Travel - Lodging', 'priority': 10},
    {'keyword': 'AIRBNB', 'category': 'Travel - Lodging', 'priority': 10},
    {'keyword': 'BOOKING.COM', 'category': 'Travel - Lodging', 'priority': 10},
    # Business Meals
    {'keyword': 'DOORDASH', 'category': 'Business Meals', 'priority': 5},
    {'keyword': 'GRUBHUB', 'category': 'Business Meals', 'priority': 5},
    {'keyword': 'UBER EATS', 'category': 'Business Meals', 'priority': 5},
    # Transfers
    {'keyword': 'Transfer', 'category': 'Transfer', 'priority': 20},
    {'keyword': 'Tfr to', 'category': 'Transfer', 'priority': 20},
    {'keyword': 'Tfr from', 'category': 'Transfer', 'priority': 20},
]

# Default accounts — empty, users configure via Settings → Bank Accounts
DEFAULT_ACCOUNTS = []


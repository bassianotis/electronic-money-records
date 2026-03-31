"""Bank transaction importers registry.

To add support for a new bank or CSV format:
1. Create a `yourbank.py` file here.
2. Implement a `parse_csv(file_content)` function that returns a list of transactions.
   Format: [{'transaction_id': str, 'date': 'YYYY-MM-DD', 'description': str, 'amount': float, 'balance': float, 'is_transfer': bool}, ...]
3. Import your parser and add it to the IMPORTERS dictionary below.
"""

from .ccu import parse_ccu_csv
from .generic import parse_generic_csv

# Registry of supported CSV import formats
IMPORTERS = {
    'ccu': {
        'id': 'ccu',
        'name': 'Consumers Credit Union (CCU)',
        'description': 'Direct export from Consumers Credit Union summary table.',
        # The parser function receives raw string content
        'parse_function': parse_ccu_csv,
    },
    'generic': {
        'id': 'generic',
        'name': 'Generic Auto-Detect CSV',
        'description': 'Intelligently auto-detects Date, Description, and Amount columns from standard CSVs.',
        'parse_function': parse_generic_csv,
    }
}

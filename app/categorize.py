"""Rule-based transaction categorization engine."""
from .database import get_db


def categorize_transaction(description):
    """Match a transaction description against categorization rules.

    Returns:
        category_id (int) if a match is found, None otherwise.
        Rules are matched case-insensitively, highest priority wins.
    """
    db = get_db()
    rules = db.execute(
        """SELECT keyword, category_id, priority
           FROM categorization_rules
           ORDER BY priority DESC, length(keyword) DESC"""
    ).fetchall()

    desc_upper = description.upper()

    for rule in rules:
        if rule['keyword'].upper() in desc_upper:
            return rule['category_id']

    return None


def auto_categorize_uncategorized():
    """Run auto-categorization on all uncategorized, non-transfer transactions.

    Returns:
        int: number of transactions categorized
    """
    db = get_db()
    uncategorized = db.execute(
        'SELECT id, description FROM transactions WHERE category_id IS NULL AND is_transfer = 0'
    ).fetchall()

    count = 0
    for txn in uncategorized:
        cat_id = categorize_transaction(txn['description'])
        if cat_id:
            db.execute(
                'UPDATE transactions SET category_id = ? WHERE id = ?',
                (cat_id, txn['id'])
            )
            count += 1

    db.commit()
    return count


def categorize_transfers():
    """Auto-categorize all transfer transactions.

    Returns:
        int: number of transactions categorized
    """
    db = get_db()
    transfer_cat = db.execute(
        "SELECT id FROM categories WHERE name = 'Transfer'"
    ).fetchone()

    if not transfer_cat:
        return 0

    result = db.execute(
        'UPDATE transactions SET category_id = ? WHERE is_transfer = 1 AND category_id IS NULL',
        (transfer_cat['id'],)
    )
    db.commit()
    return result.rowcount

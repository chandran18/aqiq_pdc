import frappe


def detect_bounce_cheque(doc, method=None):
    """Auto-tick this Journal Entry as a bounce-cheque event, and fill in
    which Customer it belongs to, the moment any row uses an Account
    flagged "Is Bounce Cheque Account". Runs on validate (not just
    on_submit) so it's visible immediately while still a draft.

    A real bounced-cheque entry is a double-entry transaction: the Customer
    party normally sits on the Receivable row (reversing the clearance),
    while the flagged account (the bank/cash leg being reversed out) is a
    separate, party-less row. So the flag and the Customer party are never
    expected to be on the SAME row - this checks for both existing
    ANYWHERE in the entry, not together on one row.

    Both fields are editable (not read-only) so a bounce that didn't go
    through a dedicated flagged account (e.g. a shared bank account) can
    still be recorded by hand. This only ever SETS the flag automatically -
    it never clears a value someone entered manually, so a manual tick
    always sticks regardless of which accounts are used.
    """
    has_bounce_account = any(
        row.account and frappe.db.get_value("Account", row.account, "custom_is_bounce_cheque_account")
        for row in doc.get("accounts") or []
    )
    auto_customer = next(
        (row.party for row in doc.get("accounts") or [] if row.party_type == "Customer" and row.party),
        None,
    )

    if has_bounce_account and auto_customer:
        doc.custom_is_bounce_cheque_entry = 1
        if not doc.custom_bounce_customer:
            doc.custom_bounce_customer = auto_customer

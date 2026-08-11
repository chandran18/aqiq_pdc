import frappe
from frappe.utils import flt, now_datetime


def capture_sales_order_override(doc, method=None):
    # "Bypass Credit Limit Check" genuinely skips the native check entirely
    # at Sales Order (erpnext...customer.py: `if not cint(bypass_credit_limit_check):
    # check_credit_limit(...)`) - nothing was gated here, so there's nothing
    # to log. The real gate for these customers happens at Sales Invoice
    # instead (see capture_sales_invoice_override below).
    bypassed = frappe.db.get_value(
        "Customer Credit Limit",
        {"parent": doc.customer, "parenttype": "Customer", "company": doc.company},
        "bypass_credit_limit_check",
    )
    if bypassed:
        return
    _capture_if_exceeded(doc.customer, doc.company, doc.doctype, doc.name)


def capture_sales_invoice_override(doc, method=None):
    # Unlike at Sales Order, this same flag does NOT skip the check here -
    # it's what DEFERS the check to Sales Invoice in the first place
    # (erpnext...sales_invoice.py: `if bypass_credit_limit_check_at_sales_order:
    # validate_against_credit_limit = True`). The gate still fully applies,
    # so always check for an override regardless of the flag.
    _capture_if_exceeded(doc.customer, doc.company, doc.doctype, doc.name)


def capture_journal_entry_override(doc, method=None):
    # For Journal Entry the flag only changes HOW outstanding is calculated
    # (excludes unbilled Sales Orders) - it never skips the check itself -
    # so it's not relevant to whether we log an override here either.
    customers = set(
        d.party for d in doc.get("accounts")
        if d.party_type == "Customer" and d.party and flt(d.debit) > 0
    )
    for customer in customers:
        _capture_if_exceeded(customer, doc.company, doc.doctype, doc.name)


def _capture_if_exceeded(customer, company, reference_doctype, reference_name):
    """If this customer's outstanding balance is over their Credit Limit at
    the moment this document's on_submit hook runs, ERPNext's own native
    check (erpnext.selling.doctype.customer.customer.check_credit_limit,
    already wired into Sales Order/Sales Invoice/Journal Entry's own
    on_submit) has ALREADY either blocked the submit outright, or let it
    through because the submitting user holds the Accounts Settings >
    Credit Controller role. Whether the check applied AT ALL for a given
    doctype (the "Bypass Credit Limit Check" case) is decided by each
    capture_*_override caller above, since that flag means something
    different for each doctype - by the time we get here, we can assume
    the gate genuinely applied.

    This is registered as a doc_events "on_submit" hook, which fires AFTER
    the doctype's own on_submit() method (where the native check lives),
    so by the time this runs the outstanding figure already reflects this
    document's own contribution.
    """
    if not customer:
        return

    from erpnext.selling.doctype.customer.customer import get_credit_limit, get_customer_outstanding

    credit_limit = get_credit_limit(customer, company)
    if not credit_limit:
        return

    outstanding = get_customer_outstanding(customer, company)
    if flt(outstanding) <= flt(credit_limit):
        return

    frappe.get_doc({
        "doctype": "Credit Limit Override Log",
        "customer": customer,
        "company": company,
        "reference_doctype": reference_doctype,
        "reference_name": reference_name,
        "credit_limit": credit_limit,
        "outstanding_amount": outstanding,
        "exceeded_by": flt(outstanding) - flt(credit_limit),
        "approved_by": frappe.session.user,
        "approved_on": now_datetime(),
    }).insert(ignore_permissions=True)

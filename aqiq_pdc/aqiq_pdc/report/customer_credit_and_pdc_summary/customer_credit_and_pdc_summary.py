# Copyright (c) 2026, Aqiq Pdc and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
    filters = frappe._dict(filters or {})
    if not filters.company:
        frappe.throw(_("Please select a Company"))
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 180},
        # Customer's own ID (naming_series-based) and its Customer Name field
        # can genuinely differ (e.g. renamed since creation) - showing both
        # avoids ambiguity about which real business the row is for. Company
        # is dropped as a column since it's a required filter already - every
        # row on screen is always the same company, so repeating it per row
        # is pure clutter.
        {"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 200},
        {"label": _("Payment Terms Template"), "fieldname": "payment_terms", "fieldtype": "Link", "options": "Payment Terms Template", "width": 160},
        {"label": _("Credit Limit"), "fieldname": "credit_limit", "fieldtype": "Currency", "width": 120},
        {"label": _("Outstanding"), "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 120},
        {"label": _("Available Credit"), "fieldname": "available_credit", "fieldtype": "Currency", "width": 130},
        {"label": _("Overdue Invoice"), "fieldname": "overdue_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 150},
        {"label": _("PDC Pending Count"), "fieldname": "pdc_pending_count", "fieldtype": "Int", "width": 130},
        {"label": _("PDC Pending Amount"), "fieldname": "pdc_pending_amount", "fieldtype": "Currency", "width": 140},
        {"label": _("PDC Amount Not Clear"), "fieldname": "pdc_amount_not_covered", "fieldtype": "Currency", "width": 160},
        {"label": _("Bounce Cheque Count"), "fieldname": "bounce_count", "fieldtype": "Int", "width": 140},
        {"label": _("Credit Overrides"), "fieldname": "override_count", "fieldtype": "Int", "width": 120},
        {"label": _("Total Exceeded Amount"), "fieldname": "override_exceeded_total", "fieldtype": "Currency", "width": 160},
    ]


def get_data(filters):
    from erpnext.accounts.utils import get_balance_on
    from erpnext.selling.doctype.customer.customer import get_credit_limit

    company = filters.company
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")

    customer_conditions = {"disabled": 0}
    if filters.get("customer"):
        customer_conditions["name"] = filters.customer

    customers = frappe.get_all("Customer", filters=customer_conditions, pluck="name")

    as_on_date = getdate(filters.get("as_on_date") or frappe.utils.today())

    rows = []
    for customer in customers:
        customer_name, payment_terms = frappe.db.get_value("Customer", customer, ["customer_name", "payment_terms"])
        credit_limit = get_credit_limit(customer, company)
        # AR ledger balance (matches Accounts Receivable Summary's own
        # Outstanding figure) - NOT the same calculation ERPNext's credit
        # limit gate uses internally (erpnext...customer.get_customer_outstanding,
        # which also folds in un-invoiced Sales Orders/Delivery Notes). This
        # column is for visibility/reporting; it isn't what actually decides
        # whether a Sales Order/Invoice gets blocked.
        outstanding = get_balance_on(party_type="Customer", party=customer, company=company, date=as_on_date)

        # Overdue Invoice = the OLDEST unpaid Sales Invoice (by due date) as
        # of Overdue As On Date - blank if nothing is actually overdue yet
        # (due date in the future, or already paid). Only ever the single
        # oldest one, not every unpaid invoice - use the Outstanding column
        # for the full picture across all of a customer's invoices.
        overdue_row = frappe.db.sql(
            """
            select name, due_date
            from `tabSales Invoice`
            where customer = %(customer)s and company = %(company)s
            and docstatus = 1 and outstanding_amount > 0 and due_date < %(as_on_date)s
            order by due_date asc
            limit 1
            """,
            {"customer": customer, "company": company, "as_on_date": as_on_date},
            as_dict=True,
        )
        overdue_invoice = overdue_row[0].name if overdue_row else None

        pdc_count, pdc_amount = frappe.db.sql(
            """
            select count(*), coalesce(sum(amount), 0)
            from `tabPost Dated Cheques`
            where party_type = 'Customer' and party = %(customer)s and company = %(company)s
            and docstatus = 1 and status = 'Pending'
            """,
            {"customer": customer, "company": company},
        )[0]

        bounce_filters = {
            "custom_bounce_customer": customer,
            "company": company,
            "docstatus": 1,
        }
        if from_date and to_date:
            bounce_filters["posting_date"] = ["between", [from_date, to_date]]
        bounce_count = frappe.db.count("Journal Entry", filters=bounce_filters)

        override_rows = frappe.get_all(
            "Credit Limit Override Log",
            filters={"customer": customer, "company": company},
            fields=["exceeded_by", "approved_on"],
        )
        if from_date:
            override_rows = [r for r in override_rows if str(r.approved_on)[:10] >= str(from_date)]
        if to_date:
            override_rows = [r for r in override_rows if str(r.approved_on)[:10] <= str(to_date)]

        # Skip customers with nothing to show - keeps the report focused on
        # customers that actually have a credit limit, activity, or history,
        # rather than padding it with every disabled/inactive Customer record.
        if not credit_limit and not outstanding and not pdc_count and not bounce_count and not override_rows:
            continue

        rows.append({
            "customer": customer,
            "customer_name": customer_name,
            "payment_terms": payment_terms,
            "company": company,
            "credit_limit": credit_limit,
            "outstanding_amount": outstanding,
            "available_credit": (flt(credit_limit) - flt(outstanding)) if credit_limit else None,
            "overdue_invoice": overdue_invoice,
            "pdc_pending_count": pdc_count,
            "pdc_pending_amount": flt(pdc_amount),
            # How much of what's owed has no pending cheque promised against
            # it at all - floored at 0 once pending PDCs already cover (or
            # exceed) the outstanding balance.
            "pdc_amount_not_covered": max(0, flt(outstanding) - flt(pdc_amount)),
            "bounce_count": bounce_count,
            "override_count": len(override_rows),
            "override_exceeded_total": sum(flt(r.exceeded_by) for r in override_rows),
        })

    return rows

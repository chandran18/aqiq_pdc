# Copyright (c) 2026, Aqiq Pdc and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate

# Same 30-day bucketing ERPNext's own Accounts Receivable report uses
# (erpnext...accounts_receivable.py: ranges "30,60,90,120" by default).
AGEING_RANGE_DAYS = [30, 60, 90, 120]
AGEING_LABELS = ["0-30", "30-60", "60-90", "90-120", "120-Above"]


def execute(filters=None):
    filters = frappe._dict(filters or {})
    if not filters.company:
        frappe.throw(_("Please select a Company"))
    return get_columns(), get_data(filters)


def get_ageing_bucket(overdue_days):
    if not overdue_days or overdue_days <= 0:
        return _("Not Due")
    index = next((i for i, days in enumerate(AGEING_RANGE_DAYS) if overdue_days <= days), len(AGEING_RANGE_DAYS))
    return AGEING_LABELS[index]


def get_columns():
    return [
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 220},
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},
        {"label": _("Credit Limit"), "fieldname": "credit_limit", "fieldtype": "Currency", "width": 120},
        {"label": _("Outstanding"), "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 120},
        {"label": _("Available Credit"), "fieldname": "available_credit", "fieldtype": "Currency", "width": 130},
        {"label": _("Overdue Days"), "fieldname": "overdue_days", "fieldtype": "Int", "width": 110},
        {"label": _("Ageing"), "fieldname": "ageing_bucket", "fieldtype": "Data", "width": 100},
        {"label": _("PDC Pending Count"), "fieldname": "pdc_pending_count", "fieldtype": "Int", "width": 130},
        {"label": _("PDC Pending Amount"), "fieldname": "pdc_pending_amount", "fieldtype": "Currency", "width": 140},
        {"label": _("Bounce Cheque Count"), "fieldname": "bounce_count", "fieldtype": "Int", "width": 140},
        {"label": _("Credit Overrides"), "fieldname": "override_count", "fieldtype": "Int", "width": 120},
        {"label": _("Total Exceeded Amount"), "fieldname": "override_exceeded_total", "fieldtype": "Currency", "width": 160},
    ]


def get_data(filters):
    from erpnext.selling.doctype.customer.customer import get_credit_limit, get_customer_outstanding

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
        credit_limit = get_credit_limit(customer, company)
        outstanding = get_customer_outstanding(customer, company)

        # Overdue Days = how many days past due the OLDEST unpaid Sales
        # Invoice is, as of Ageing As On Date - 0/blank if nothing is
        # actually overdue yet (due date in the future or already paid).
        oldest_due_date = frappe.db.sql(
            """
            select min(due_date)
            from `tabSales Invoice`
            where customer = %(customer)s and company = %(company)s
            and docstatus = 1 and outstanding_amount > 0
            """,
            {"customer": customer, "company": company},
        )[0][0]
        overdue_days = (as_on_date - getdate(oldest_due_date)).days if oldest_due_date else 0
        overdue_days = max(0, overdue_days)

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
            "company": company,
            "credit_limit": credit_limit,
            "outstanding_amount": outstanding,
            "available_credit": (flt(credit_limit) - flt(outstanding)) if credit_limit else None,
            "overdue_days": overdue_days,
            "ageing_bucket": get_ageing_bucket(overdue_days),
            "pdc_pending_count": pdc_count,
            "pdc_pending_amount": flt(pdc_amount),
            "bounce_count": bounce_count,
            "override_count": len(override_rows),
            "override_exceeded_total": sum(flt(r.exceeded_by) for r in override_rows),
        })

    return rows

import frappe
from frappe import _, msgprint, qb
from frappe.model.document import Document
from erpnext.accounts.doctype.payment_reconciliation.payment_reconciliation import PaymentReconciliation


@frappe.whitelist()
def get_unreconciled_entries(self):
    self.get_nonreconciled_payment_entries()
    self.get_invoice_entries()
    self.total_unreconciled = 0
    self.total_payment = 0

    si_meta = frappe.get_meta("Sales Invoice")
    pi_meta = frappe.get_meta("Purchase Invoice")
    pe_meta = frappe.get_meta("Payment Entry")
    je_meta = frappe.get_meta("Journal Entry")

    for d in self.invoices:
        if d.invoice_type == "Sales Invoice":
            if si_meta.has_field("lisec_inv_no"):
                d.ref_no = frappe.db.get_value(
                    d.invoice_type, d.invoice_number, "lisec_inv_no"
                ) or ""
        elif d.invoice_type == "Purchase Invoice":
            if pi_meta.has_field("bill_no"):
                d.bill_no = frappe.db.get_value(
                    d.invoice_type, d.invoice_number, "bill_no"
                ) or ""
        self.total_unreconciled += d.outstanding_amount

    for d in self.payments:
        self.total_payment += d.amount
        if d.reference_type == "Payment Entry":
            if pe_meta.has_field("reference_no") and pe_meta.has_field("reference_date"):
                d.reference_no, d.reference_date = (
                    frappe.db.get_value(
                        d.reference_type, d.reference_name, ["reference_no", "reference_date"]
                    ) or ["", ""]
                )
        elif d.reference_type == "Journal Entry":
            if je_meta.has_field("cert_no") and je_meta.has_field("ref_no"):
                d.cert_no, d.ref_no = (
                    frappe.db.get_value(
                        d.reference_type, d.reference_name, ["cert_no", "ref_no"]
                    ) or ["", ""]
                )


PaymentReconciliation.get_unreconciled_entries = get_unreconciled_entries
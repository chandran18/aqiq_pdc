import frappe

def payment_entry_validate(self, method):
    update_pt_cheque_status(self)
def payment_entry_on_submit(self, method):
    update_pt_cheque_status(self)
def payment_entry_on_cancel(self, method):
    update_pt_cheque_status(self)

def update_pt_cheque_status(self):
    if self.custom_post_dated_cheques:
        status = "Pending"
        if self.docstatus == 0:
            status = "Payment Entry Created"
        elif self.docstatus == 1:
            status = "Payment Entry Submitted"
        elif self.docstatus == 2:
            status = "Pending"
        frappe.db.set_value(
            "Post Dated Cheques", self.custom_post_dated_cheques, "status", status
        )
# Copyright (c) 2024, Aqiq Pdc and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PostDatedCheques(Document):
	
	def on_cancel(self):
		frappe.db.set_value(self.doctype, self.name, 'status', 'Cancelled')
		self.reload()

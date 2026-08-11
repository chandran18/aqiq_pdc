import json
from collections import defaultdict

import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc
from frappe.query_builder.functions import Sum
from frappe.utils import cint, comma_or, cstr, flt, format_time, formatdate, getdate, nowdate
from six import iteritems, itervalues, string_types

import erpnext
from erpnext.accounts.general_ledger import process_gl_map
from erpnext.controllers.taxes_and_totals import init_landed_taxes_and_totals
from erpnext.manufacturing.doctype.bom.bom import add_additional_cost, validate_bom_no
from erpnext.setup.doctype.brand.brand import get_brand_defaults
from erpnext.setup.doctype.item_group.item_group import get_item_group_defaults
from erpnext.stock.doctype.batch.batch import get_batch_no, get_batch_qty, set_batch_nos
from erpnext.stock.doctype.item.item import get_item_defaults
from erpnext.stock.doctype.serial_no.serial_no import (
	get_serial_nos,
	update_serial_nos_after_submit,
)
from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import (
	OpeningEntryAccountError,
)
from erpnext.stock.get_item_details import (
	get_bin_details,
	get_conversion_factor,
	get_default_cost_center,
	get_reserved_qty_for_so,
)
from erpnext.stock.stock_ledger import NegativeStockError, get_previous_sle, get_valuation_rate
from erpnext.stock.utils import get_bin, get_incoming_rate


class FinishedGoodError(frappe.ValidationError):
	pass
class IncorrectValuationRateError(frappe.ValidationError):
	pass
class DuplicateEntryForWorkOrderError(frappe.ValidationError):
	pass
class OperationsNotCompleteError(frappe.ValidationError):
	pass
class MaxSampleAlreadyRetainedError(frappe.ValidationError):
	pass

from erpnext.controllers.stock_controller import StockController
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry


def get_unconsumed_raw_materials(self):
	wo = frappe.get_doc("Work Order", self.work_order)
	fields=["item_code", "source_warehouse", "required_qty", "consumed_qty", "transferred_qty"]
	meta = frappe.get_meta("Work Order Item")
	if meta.has_field("extra_qty"):
		fields.append("extra_qty")
	wo_items = frappe.get_all('Work Order Item',
		filters={'parent': self.work_order},
		fields=fields
		)

	work_order_qty = wo.material_transferred_for_manufacturing or wo.qty
	for item in wo_items:
		item_account_details = get_item_defaults(item.item_code, self.company)
		# Take into account consumption if there are any.

		# frappe.msgprint(str(item.get("extra_qty")))
		# frappe.msgprint(str(fields))

		wo_item_qty = item.transferred_qty or (flt(item.required_qty)+flt(item.get("extra_qty")))

		wo_qty_consumed = flt(wo_item_qty) - flt(item.consumed_qty)
		wo_qty_to_produce = flt(work_order_qty) - flt(wo.produced_qty)

		req_qty_each = (wo_qty_consumed) / (wo_qty_to_produce or 1)

		qty = req_qty_each * flt(self.fg_completed_qty)

		if qty > 0:
			self.add_to_stock_entry_detail({
				item.item_code: {
					"from_warehouse": wo.wip_warehouse or item.source_warehouse,
					"to_warehouse": "",
					"qty": qty,
					"item_name": item.item_name,
					"description": item.description,
					"stock_uom": item_account_details.stock_uom,
					"expense_account": item_account_details.get("expense_account"),
					"cost_center": item_account_details.get("buying_cost_center"),
				}
			})

# def set_stock_entry_type(self):
# 	if self.purpose:
# 		self.stock_entry_type = self.purpose
		
StockEntry.get_unconsumed_raw_materials = get_unconsumed_raw_materials
# StockEntry.set_stock_entry_type=set_stock_entry_type
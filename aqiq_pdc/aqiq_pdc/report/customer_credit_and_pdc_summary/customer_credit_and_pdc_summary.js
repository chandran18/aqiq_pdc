// Copyright (c) 2026, Aqiq Pdc and contributors
// For license information, please see license.txt

frappe.query_reports["Customer Credit and PDC Summary"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "as_on_date",
			label: __("Overdue As On Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			description: __("Overdue Days is computed against this date. Defaults to today."),
		},
		{
			fieldname: "from_date",
			label: __("From Date (Bounce/Override events)"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("To Date (Bounce/Override events)"),
			fieldtype: "Date",
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;

		if (column.fieldname === "pdc_pending_count" && data.pdc_pending_count) {
			value = `<a href="${list_link("Post Dated Cheques", {
				party_type: "Customer",
				party: data.customer,
				company: data.company,
				status: "Pending",
				docstatus: 1,
			})}">${value}</a>`;
		}

		if (column.fieldname === "bounce_count" && data.bounce_count) {
			value = `<a href="${list_link("Journal Entry", {
				custom_bounce_customer: data.customer,
				company: data.company,
				docstatus: 1,
			})}">${value}</a>`;
		}

		if (column.fieldname === "override_count" && data.override_count) {
			value = `<a href="${list_link("Credit Limit Override Log", {
				customer: data.customer,
				company: data.company,
			})}">${value}</a>`;
		}

		return value;
	},
};

function list_link(doctype, filters) {
	return "/app/" + frappe.router.slug(doctype) + "?" + $.param(filters);
}

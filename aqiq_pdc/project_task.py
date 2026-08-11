import frappe
from frappe.utils import add_days, flt, get_datetime, get_time, get_url, nowtime, today
from erpnext import get_default_company
from erpnext.setup.doctype.holiday_list.holiday_list import is_holiday


@frappe.whitelist()
def copy_from_template(name):  # nosemgrep
    """
    Copy tasks from template
    """
    self = frappe.get_doc("Purchase Order", name)
    if not self.project_template:
        frappe.throw(_("No project template defined for this Purchase Order"))
    # has a template, and no loaded tasks, so lets create
    if not self.expected_start_date:
        # project starts today
        self.expected_start_date = today()

    template = frappe.get_doc("Project Template", self.project_template)

    if not template.tasks:
        frappe.throw(_("No tasks found in the project template"))

    if not self.project_type:
        self.project_type = template.project_type

    # create tasks from template
    project_tasks = []
    tmp_task_details = []
    for task in template.tasks:
        template_task_details = frappe.get_doc("Task", task.task)
        tmp_task_details.append(template_task_details)
        task = create_task_from_template(self,name,template_task_details)
        project_tasks.append(task)

    dependency_mapping(self,tmp_task_details, project_tasks)
    return "All Done"


@frappe.whitelist()
def create_task_from_template(self,name, task_details):
	return frappe.get_doc(
		dict(
			doctype="Task",
			subject=task_details.subject,
			project=self.project,
			purchase_order=name,
			status="Open",
			exp_start_date=calculate_start_date(self,task_details),
			exp_end_date=calculate_end_date(self,task_details),
			description=task_details.description,
			task_weight=task_details.task_weight,
			type=task_details.type,
			issue=task_details.issue,
			is_group=task_details.is_group,
			color=task_details.color,
			template_task=task_details.name,
			priority=task_details.priority,
		)
	).insert()

@frappe.whitelist()
def calculate_start_date(self, task_details):
	self.start_date = add_days(self.expected_start_date, task_details.start)
	self.start_date = update_if_holiday(self,self.start_date)
	return self.start_date

@frappe.whitelist()
def calculate_end_date(self, task_details):
	self.end_date = add_days(self.start_date, task_details.duration)
	return update_if_holiday(self,self.end_date)

@frappe.whitelist()
def update_if_holiday(self, date):
	holiday_list = get_holiday_list(self.company)
	while is_holiday(holiday_list, date):
		date = add_days(date, 1)
	return date

@frappe.whitelist()
def get_holiday_list(company=None):
	if not company:
		company = get_default_company() or frappe.get_all("Company")[0].name

	holiday_list = frappe.get_cached_value("Company", company, "default_holiday_list")
	if not holiday_list:
		frappe.throw(
			_("Please set a default Holiday List for Company {0}").format(frappe.bold(get_default_company()))
		)
	return holiday_list

@frappe.whitelist()
def dependency_mapping(self, template_tasks, project_tasks):
	for project_task in project_tasks:
		template_task = frappe.get_doc("Task", project_task.template_task)

		check_depends_on_value(self,template_task, project_task, project_tasks)
		check_for_parent_tasks(self,template_task, project_task, project_tasks)

@frappe.whitelist()
def check_depends_on_value(self, template_task, project_task, project_tasks):
	if template_task.get("depends_on") and not project_task.get("depends_on"):
		project_template_map = {pt.template_task: pt for pt in project_tasks}

		for child_task in template_task.get("depends_on"):
			if project_template_map and project_template_map.get(child_task.task):
				project_task.reload()  # reload, as it might have been updated in the previous iteration
				project_task.append(
					"depends_on", {"task": project_template_map.get(child_task.task).name}
				)
				project_task.save()

@frappe.whitelist()
def check_for_parent_tasks(self, template_task, project_task, project_tasks):
	if template_task.get("parent_task") and not project_task.get("parent_task"):
		for pt in project_tasks:
			if pt.template_task == template_task.parent_task:
				project_task.parent_task = pt.name
				project_task.save()
				break
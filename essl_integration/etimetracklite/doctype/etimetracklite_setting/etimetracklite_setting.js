// Copyright (c) 2026, Prashant Agrawal and contributors
// For license information, please see license.txt

frappe.ui.form.on("eTimeTrackLite Setting", {
	refresh(frm) {
		frm.add_custom_button(__("Sync Backlog"), () => {
			show_backlog_sync_dialog();
		});
	},
});

function show_backlog_sync_dialog() {
	const dialog = new frappe.ui.Dialog({
		title: __("Sync Backlog"),
		fields: [
			{
				fieldname: "device_name",
				fieldtype: "Link",
				label: __("Device"),
				options: "Biometric Device",
				description: __("Leave blank to sync all active devices."),
			},
			{
				fieldname: "from_datetime",
				fieldtype: "Datetime",
				label: __("From Datetime"),
				reqd: 1,
			},
			{
				fieldname: "to_datetime",
				fieldtype: "Datetime",
				label: __("To Datetime"),
				reqd: 1,
			},
			{
				fieldname: "chunk_hours",
				fieldtype: "Float",
				label: __("Chunk Hours"),
				default: 6,
				reqd: 1,
			},
		],
		primary_action_label: __("Sync"),
		primary_action(values) {
			if (values.from_datetime >= values.to_datetime) {
				frappe.msgprint(__("From Datetime must be before To Datetime."));
				return;
			}

			if (flt(values.chunk_hours) <= 0) {
				frappe.msgprint(__("Chunk Hours must be greater than zero."));
				return;
			}

			dialog.hide();
			frappe.call({
				method: "essl_integration.etimetracklite.sync.sync_backlog",
				args: values,
				freeze: true,
				freeze_message: __("Syncing backlog..."),
				callback(r) {
					show_backlog_sync_result(r.message);
				},
			});
		},
	});

	dialog.show();
}

function show_backlog_sync_result(result) {
	if (!result) {
		return;
	}

	const rows = (result.devices || []).map((device) => {
		const totals = device.totals || {};
		return `
			<tr>
				<td>${frappe.utils.escape_html(device.device || "")}</td>
				<td>${frappe.utils.escape_html(device.status || "")}</td>
				<td class="text-right">${cint(totals.parsed)}</td>
				<td class="text-right">${cint(totals.created)}</td>
				<td class="text-right">${cint(totals.duplicates)}</td>
				<td class="text-right">${cint(totals.unmapped)}</td>
			</tr>
		`;
	}).join("");

	frappe.msgprint({
		title: __("Backlog Sync Complete"),
		indicator: "green",
		message: `
			<p>
				${__("Period")}: ${frappe.utils.escape_html(result.from || "")}
				${__("to")} ${frappe.utils.escape_html(result.to || "")}
			</p>
			<table class="table table-bordered">
				<thead>
					<tr>
						<th>${__("Device")}</th>
						<th>${__("Status")}</th>
						<th class="text-right">${__("Parsed")}</th>
						<th class="text-right">${__("Created")}</th>
						<th class="text-right">${__("Duplicates")}</th>
						<th class="text-right">${__("Unmapped")}</th>
					</tr>
				</thead>
				<tbody>${rows}</tbody>
			</table>
		`,
	});
}

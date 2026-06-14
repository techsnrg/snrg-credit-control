import {
	createApp,
	reactive,
	computed,
	onMounted,
	watch,
} from "vue/dist/vue.esm-bundler.js";

const QTY_EPSILON = 0.0001;

function call(method, args = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method,
			args,
			freeze: false,
			callback: (response) => resolve(response.message),
			error: (error) => reject(error),
		});
	});
}

function formatQty(value) {
	return new Intl.NumberFormat("en-IN", {
		minimumFractionDigits: 2,
		maximumFractionDigits: 2,
	}).format(Number(value || 0) || 0);
}

function formatInteger(value) {
	return new Intl.NumberFormat("en-IN", {
		maximumFractionDigits: 0,
	}).format(Number(value || 0) || 0);
}

function formatCurrency(value, currency = "INR") {
	try {
		return new Intl.NumberFormat("en-IN", {
			style: "currency",
			currency: currency || "INR",
			minimumFractionDigits: 2,
			maximumFractionDigits: 2,
		}).format(Number(value || 0) || 0);
	} catch (error) {
		return formatQty(value);
	}
}

function formatDate(value) {
	if (!value) {
		return "-";
	}
	return frappe.datetime.str_to_user ? frappe.datetime.str_to_user(value) : value;
}

function todayDate() {
	return frappe.datetime.get_today ? frappe.datetime.get_today() : "";
}

function pendingRowKey(row) {
	return `${String(row?.quotation || "").trim().toLowerCase()}::${String(row?.item_code || "").trim().toLowerCase()}`;
}

function clampQty(value, maxQty) {
	const numericMax = Math.max(Number(maxQty || 0) || 0, 0);
	const numericValue = Number(value || 0);
	if (!Number.isFinite(numericValue) || numericValue <= 0) {
		return numericMax;
	}
	return Math.min(numericValue, numericMax);
}

function dueMeta(requiredByDate) {
	if (!requiredByDate) {
		return {
			label: "No due date",
			tone: "muted",
		};
	}

	const today = todayDate();
	if (!today) {
		return {
			label: formatDate(requiredByDate),
			tone: "muted",
		};
	}

	const due = new Date(`${requiredByDate}T00:00:00`);
	const current = new Date(`${today}T00:00:00`);
	const delta = Math.round((due - current) / (24 * 60 * 60 * 1000));

	if (delta < 0) {
		return {
			label: `${Math.abs(delta)}d overdue`,
			tone: "danger",
		};
	}
	if (delta === 0) {
		return {
			label: "Due today",
			tone: "warning",
		};
	}
	if (delta <= 2) {
		return {
			label: `Due in ${delta}d`,
			tone: "warning",
		};
	}

	return {
		label: `Due in ${delta}d`,
		tone: "muted",
	};
}

function requestStatusClass(status) {
	const value = String(status || "Not Requested");
	if (value === "In Progress") {
		return "is-progress";
	}
	if (value === "Completed") {
		return "is-success";
	}
	if (value === "Cancelled") {
		return "is-muted";
	}
	if (value === "Open") {
		return "is-open";
	}
	return "is-neutral";
}

function toneClass(tone) {
	return {
		slate: "is-slate",
		blue: "is-blue",
		amber: "is-amber",
		green: "is-green",
		rose: "is-rose",
	}[tone] || "is-slate";
}

function ensureConsoleStyles() {
	if (document.getElementById("snrg-production-planning-console-styles")) {
		return;
	}

	const style = document.createElement("style");
	style.id = "snrg-production-planning-console-styles";
	style.textContent = `
		.snrg-ppc-page {
			display: grid;
			gap: 16px;
			color: #18212f;
			font-family: Inter, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
		}
		.snrg-ppc-hero {
			display: flex;
			justify-content: space-between;
			gap: 18px;
			align-items: flex-start;
			padding: 18px 20px;
			border-radius: 18px;
			background:
				radial-gradient(circle at top right, rgba(240, 173, 78, 0.18), transparent 30%),
				linear-gradient(135deg, #0f172a 0%, #123d4b 48%, #d97706 100%);
			color: #fff;
			box-shadow: 0 16px 34px rgba(15, 23, 42, 0.12);
		}
		.snrg-ppc-kicker {
			font-size: 11px;
			font-weight: 800;
			letter-spacing: 0.14em;
			text-transform: uppercase;
			opacity: 0.78;
		}
		.snrg-ppc-title {
			margin: 8px 0 6px;
			font-size: 30px;
			line-height: 1.05;
			font-weight: 800;
		}
		.snrg-ppc-subtitle {
			max-width: 760px;
			margin: 0;
			font-size: 14px;
			line-height: 1.55;
			color: rgba(255, 255, 255, 0.86);
		}
		.snrg-ppc-hero-meta {
			display: inline-flex;
			flex-wrap: wrap;
			gap: 8px;
			margin-top: 14px;
		}
		.snrg-ppc-chip {
			display: inline-flex;
			align-items: center;
			gap: 6px;
			padding: 6px 10px;
			border-radius: 999px;
			background: rgba(255, 255, 255, 0.12);
			border: 1px solid rgba(255, 255, 255, 0.16);
			font-size: 12px;
			font-weight: 700;
		}
		.snrg-ppc-filter-bar {
			display: grid;
			grid-template-columns: minmax(180px, 1fr) minmax(240px, 1.2fr) minmax(220px, 1fr) auto auto;
			gap: 12px;
			align-items: end;
		}
		.snrg-ppc-field {
			display: grid;
			gap: 6px;
		}
		.snrg-ppc-field label {
			font-size: 11px;
			font-weight: 800;
			letter-spacing: 0.08em;
			text-transform: uppercase;
			color: #667085;
		}
		.snrg-ppc-input,
		.snrg-ppc-select {
			width: 100%;
			min-height: 38px;
			padding: 8px 12px;
			border-radius: 11px;
			border: 1px solid #d7dfeb;
			background: #fff;
			color: #18212f;
			font-size: 13px;
			box-shadow: none;
		}
		.snrg-ppc-check {
			display: inline-flex;
			align-items: center;
			gap: 8px;
			min-height: 38px;
			padding: 0 4px;
			font-size: 13px;
			font-weight: 700;
			color: #344054;
		}
		.snrg-ppc-check input {
			width: 18px;
			height: 18px;
		}
		.snrg-ppc-summary {
			display: grid;
			grid-template-columns: repeat(6, minmax(0, 1fr));
			gap: 12px;
		}
		.snrg-ppc-metric {
			padding: 14px 15px;
			border-radius: 16px;
			border: 1px solid #e1e8f0;
			background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
			box-shadow: 0 10px 22px rgba(15, 23, 42, 0.05);
			display: grid;
			gap: 8px;
		}
		.snrg-ppc-metric.is-slate { background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%); }
		.snrg-ppc-metric.is-blue { background: linear-gradient(180deg, #eff6ff 0%, #ffffff 100%); }
		.snrg-ppc-metric.is-amber { background: linear-gradient(180deg, #fffbeb 0%, #ffffff 100%); }
		.snrg-ppc-metric.is-green { background: linear-gradient(180deg, #ecfdf3 0%, #ffffff 100%); }
		.snrg-ppc-metric.is-rose { background: linear-gradient(180deg, #fff1f2 0%, #ffffff 100%); }
		.snrg-ppc-metric-label {
			font-size: 11px;
			font-weight: 800;
			letter-spacing: 0.08em;
			text-transform: uppercase;
			color: #667085;
		}
		.snrg-ppc-metric-value {
			font-size: 24px;
			line-height: 1;
			font-weight: 800;
			color: #101828;
		}
		.snrg-ppc-metric-subvalue {
			font-size: 12px;
			color: #667085;
			font-weight: 700;
		}
		.snrg-ppc-panel {
			border: 1px solid #e2e8f0;
			border-radius: 18px;
			background: #fff;
			box-shadow: 0 12px 28px rgba(15, 23, 42, 0.05);
			overflow: hidden;
		}
		.snrg-ppc-panel-head {
			display: flex;
			justify-content: space-between;
			align-items: center;
			gap: 12px;
			padding: 14px 16px;
			border-bottom: 1px solid #edf2f7;
			background: #fbfdff;
		}
		.snrg-ppc-panel-title {
			font-size: 16px;
			font-weight: 800;
			color: #101828;
		}
		.snrg-ppc-panel-subtitle {
			font-size: 12px;
			color: #667085;
			font-weight: 700;
		}
		.snrg-ppc-table-wrap {
			max-height: 520px;
			overflow: auto;
		}
		.snrg-ppc-table {
			width: 100%;
			border-collapse: separate;
			border-spacing: 0;
		}
		.snrg-ppc-table thead th {
			position: sticky;
			top: 0;
			z-index: 1;
			background: #f8fafc;
			border-bottom: 1px solid #e7edf5;
			padding: 12px 14px;
			text-align: left;
			font-size: 11px;
			font-weight: 800;
			letter-spacing: 0.08em;
			text-transform: uppercase;
			color: #667085;
		}
		.snrg-ppc-table tbody td {
			padding: 12px 14px;
			border-bottom: 1px solid #eef2f7;
			vertical-align: top;
			font-size: 13px;
		}
		.snrg-ppc-stack {
			display: grid;
			gap: 2px;
			min-width: 0;
		}
		.snrg-ppc-primary-text {
			font-size: 13px;
			font-weight: 800;
			color: #0f3d4b;
		}
		.snrg-ppc-secondary-text {
			font-size: 12px;
			color: #667085;
			font-weight: 600;
		}
		.snrg-ppc-link {
			color: inherit;
			text-decoration: none;
		}
		.snrg-ppc-link:hover {
			text-decoration: underline;
		}
		.snrg-ppc-number {
			text-align: right;
			font-variant-numeric: tabular-nums;
			font-weight: 800;
			color: #101828;
		}
		.snrg-ppc-value {
			color: #b42318;
		}
		.snrg-ppc-badge {
			display: inline-flex;
			align-items: center;
			padding: 6px 10px;
			border-radius: 999px;
			font-size: 11px;
			font-weight: 800;
			line-height: 1;
			border: 1px solid transparent;
			white-space: nowrap;
		}
		.snrg-ppc-badge.is-neutral {
			background: #f3f4f6;
			color: #475467;
			border-color: #e5e7eb;
		}
		.snrg-ppc-badge.is-open {
			background: #eef4ff;
			color: #175cd3;
			border-color: #c7d7fe;
		}
		.snrg-ppc-badge.is-progress {
			background: #fff4e8;
			color: #b45309;
			border-color: #f5d0a0;
		}
		.snrg-ppc-badge.is-success {
			background: #ecfdf3;
			color: #027a48;
			border-color: #b7e6c0;
		}
		.snrg-ppc-badge.is-muted {
			background: #f4f6f8;
			color: #667085;
			border-color: #dde3ea;
		}
		.snrg-ppc-request-cell {
			display: grid;
			gap: 8px;
			min-width: 190px;
		}
		.snrg-ppc-request-row {
			display: grid;
			grid-template-columns: minmax(74px, 82px) minmax(120px, 1fr) auto;
			gap: 8px;
			align-items: center;
		}
		.snrg-ppc-request-meta {
			font-size: 11px;
			color: #667085;
			font-weight: 700;
		}
		.snrg-ppc-button {
			display: inline-flex;
			align-items: center;
			justify-content: center;
			gap: 6px;
			min-height: 34px;
			padding: 0 12px;
			border-radius: 10px;
			border: 1px solid #d0d5dd;
			background: #fff;
			color: #344054;
			font-size: 12px;
			font-weight: 800;
			cursor: pointer;
			white-space: nowrap;
		}
		.snrg-ppc-button:hover {
			background: #f8fafc;
		}
		.snrg-ppc-button.is-primary {
			background: #111827;
			border-color: #111827;
			color: #fff;
		}
		.snrg-ppc-button.is-primary:hover {
			background: #0f172a;
		}
		.snrg-ppc-button.is-ghost {
			background: transparent;
		}
		.snrg-ppc-button:disabled,
		.snrg-ppc-select:disabled,
		.snrg-ppc-input:disabled {
			opacity: 0.65;
			cursor: not-allowed;
		}
		.snrg-ppc-requested-box {
			display: grid;
			gap: 4px;
		}
		.snrg-ppc-requested-box .snrg-ppc-badge {
			justify-self: start;
		}
		.snrg-ppc-board {
			display: grid;
			grid-template-columns: repeat(3, minmax(0, 1fr));
			gap: 12px;
		}
		.snrg-ppc-column {
			border: 1px solid #e1e8f0;
			border-radius: 16px;
			background: #fff;
			box-shadow: 0 12px 24px rgba(15, 23, 42, 0.04);
			overflow: hidden;
		}
		.snrg-ppc-column-head {
			display: flex;
			justify-content: space-between;
			align-items: center;
			gap: 12px;
			padding: 12px 14px;
			border-bottom: 1px solid #eef2f7;
			background: #f8fafc;
		}
		.snrg-ppc-column-title {
			font-size: 15px;
			font-weight: 800;
			color: #101828;
		}
		.snrg-ppc-column-pill {
			display: inline-flex;
			align-items: center;
			justify-content: center;
			min-width: 28px;
			height: 28px;
			padding: 0 10px;
			border-radius: 999px;
			background: #edf2ff;
			color: #175cd3;
			font-size: 12px;
			font-weight: 800;
		}
		.snrg-ppc-column-body {
			display: grid;
			gap: 10px;
			padding: 12px;
			min-height: 220px;
		}
		.snrg-ppc-empty {
			padding: 16px;
			border-radius: 12px;
			border: 1px dashed #d0d5dd;
			text-align: center;
			font-size: 13px;
			color: #667085;
			background: #fcfcfd;
		}
		.snrg-ppc-card {
			display: grid;
			gap: 10px;
			padding: 13px;
			border-radius: 14px;
			border: 1px solid #e5e9f0;
			border-left: 4px solid #2563eb;
			background: #fff;
		}
		.snrg-ppc-card.is-progress { border-left-color: #d97706; }
		.snrg-ppc-card.is-completed { border-left-color: #16a34a; }
		.snrg-ppc-card-top {
			display: flex;
			justify-content: space-between;
			gap: 10px;
			align-items: flex-start;
		}
		.snrg-ppc-card-code {
			font-size: 13px;
			font-weight: 800;
			color: #0f172a;
		}
		.snrg-ppc-card-name {
			font-size: 15px;
			font-weight: 800;
			line-height: 1.25;
			color: #101828;
		}
		.snrg-ppc-card-grid {
			display: grid;
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 8px 12px;
		}
		.snrg-ppc-card-meta-label {
			font-size: 11px;
			font-weight: 800;
			letter-spacing: 0.08em;
			text-transform: uppercase;
			color: #667085;
		}
		.snrg-ppc-card-meta-value {
			font-size: 13px;
			font-weight: 800;
			color: #101828;
		}
		.snrg-ppc-card-meta-sub {
			font-size: 12px;
			color: #667085;
			font-weight: 600;
		}
		.snrg-ppc-card-footer {
			display: grid;
			gap: 8px;
		}
		.snrg-ppc-card-actions {
			display: flex;
			flex-wrap: wrap;
			gap: 8px;
		}
		.snrg-ppc-due {
			display: inline-flex;
			align-items: center;
			gap: 6px;
			font-size: 12px;
			font-weight: 700;
			color: #667085;
		}
		.snrg-ppc-due.is-danger {
			color: #b42318;
		}
		.snrg-ppc-due.is-warning {
			color: #b54708;
		}
		.snrg-ppc-loading {
			padding: 28px;
			border-radius: 16px;
			border: 1px solid #e2e8f0;
			background: #fff;
			font-size: 13px;
			color: #667085;
			text-align: center;
		}
		@media (max-width: 1440px) {
			.snrg-ppc-summary {
				grid-template-columns: repeat(3, minmax(0, 1fr));
			}
		}
		@media (max-width: 1200px) {
			.snrg-ppc-filter-bar,
			.snrg-ppc-board {
				grid-template-columns: 1fr;
			}
		}
		@media (max-width: 900px) {
			.snrg-ppc-summary {
				grid-template-columns: repeat(2, minmax(0, 1fr));
			}
			.snrg-ppc-card-grid {
				grid-template-columns: 1fr;
			}
			.snrg-ppc-request-row {
				grid-template-columns: 1fr;
			}
			.snrg-ppc-hero {
				flex-direction: column;
			}
		}
		@media (max-width: 640px) {
			.snrg-ppc-summary {
				grid-template-columns: 1fr;
			}
			.snrg-ppc-title {
				font-size: 24px;
			}
		}
	`;
	document.head.appendChild(style);
}

const ProductionPlanningConsoleApp = {
	props: {
		page: {
			type: Object,
			required: true,
		},
		routeOptions: {
			type: Object,
			default: () => ({}),
		},
	},
	setup(props, { expose }) {
		const state = reactive({
			loading: false,
			errorMessage: "",
			meta: {
				companies: [],
				assignable_users: [],
			},
			summary: {
				pending_line_count: 0,
				pending_qty: 0,
				pending_value: 0,
				requested_open_qty: 0,
				requested_in_progress_qty: 0,
				open_request_count: 0,
				in_progress_request_count: 0,
				completed_request_count: 0,
				urgent_request_count: 0,
			},
			pending_rows: [],
			groups: {
				Open: [],
				"In Progress": [],
				Completed: [],
			},
			filters: {
				company: props.routeOptions.company || frappe.defaults.get_user_default("Company") || "",
				search: props.routeOptions.search || "",
				show_completed: props.routeOptions.show_completed != null ? !!props.routeOptions.show_completed : true,
				show_values: props.routeOptions.show_values != null ? !!props.routeOptions.show_values : false,
				default_assignee: props.routeOptions.default_assignee || "",
			},
			requestDrafts: {},
			busyCreateKey: "",
			busyStatusName: "",
			busyAssigneeName: "",
			refreshTimer: null,
		});

		const summaryCards = computed(() => {
			const cards = [
				{
					label: "Pending Lines",
					value: formatInteger(state.summary.pending_line_count),
					subvalue: "Demand still waiting for planning",
					tone: "slate",
				},
				{
					label: "Pending Qty",
					value: formatQty(state.summary.pending_qty),
					subvalue: "Total uninvoiced quantity",
					tone: "blue",
				},
			];

			if (state.filters.show_values) {
				cards.push({
					label: "Pending Value",
					value: formatCurrency(state.summary.pending_value),
					subvalue: "Commercial exposure in queue",
					tone: "amber",
				});
			}

			cards.push(
				{
					label: "Open Requests",
					value: formatInteger(state.summary.open_request_count),
					subvalue: `Qty ${formatQty(state.summary.requested_open_qty)}`,
					tone: "blue",
				},
				{
					label: "In Progress",
					value: formatInteger(state.summary.in_progress_request_count),
					subvalue: `Qty ${formatQty(state.summary.requested_in_progress_qty)}`,
					tone: "green",
				},
				{
					label: "Urgent Requests",
					value: formatInteger(state.summary.urgent_request_count),
					subvalue: "Overdue or due within 2 days",
					tone: "rose",
				}
			);

			if (state.filters.show_completed) {
				cards.push({
					label: "Completed",
					value: formatInteger(state.summary.completed_request_count),
					subvalue: "Closed production requests",
					tone: "slate",
				});
			}

			return cards;
		});

		const boardColumns = computed(() => {
			const columns = [
				{ key: "Open", label: "Open", rows: state.groups.Open || [] },
				{ key: "In Progress", label: "In Progress", rows: state.groups["In Progress"] || [] },
			];
			if (state.filters.show_completed) {
				columns.push({ key: "Completed", label: "Completed", rows: state.groups.Completed || [] });
			}
			return columns;
		});

		function userLabel(userId) {
			if (!userId) {
				return "Unassigned";
			}
			const match = (state.meta.assignable_users || []).find((option) => option.value === userId);
			return match ? match.label : userId;
		}

		function ensureDraft(row) {
			const key = pendingRowKey(row);
			if (!state.requestDrafts[key]) {
				state.requestDrafts[key] = {
					qty: clampQty(row.remaining_requestable_qty, row.remaining_requestable_qty),
					required_by_date: row.production_required_by_date || todayDate(),
					assigned_to:
						row.production_assigned_to || state.filters.default_assignee || "",
				};
			}

			const draft = state.requestDrafts[key];
			draft.qty = clampQty(draft.qty, row.remaining_requestable_qty);
			if (!draft.required_by_date) {
				draft.required_by_date = row.production_required_by_date || todayDate();
			}
			if (!draft.assigned_to && state.filters.default_assignee) {
				draft.assigned_to = state.filters.default_assignee;
			}
			return draft;
		}

		function syncDrafts() {
			const liveKeys = new Set();
			(state.pending_rows || []).forEach((row) => {
				liveKeys.add(pendingRowKey(row));
				ensureDraft(row);
			});

			Object.keys(state.requestDrafts).forEach((key) => {
				if (!liveKeys.has(key)) {
					delete state.requestDrafts[key];
				}
			});
		}

		async function loadData() {
			state.loading = true;
			state.errorMessage = "";
			try {
				const data = await call(
					"snrg_credit_control.snrg_credit_control.page.production_planning_console.production_planning_console.get_console_data",
					{
						company: state.filters.company,
						search: state.filters.search,
						show_completed: state.filters.show_completed ? 1 : 0,
					}
				);
				state.meta = data.meta || state.meta;
				state.summary = data.summary || state.summary;
				state.pending_rows = data.pending_rows || [];
				state.groups = data.groups || { Open: [], "In Progress": [], Completed: [] };
				if (!state.filters.company && data.filters?.company) {
					state.filters.company = data.filters.company;
				}
				syncDrafts();
			} catch (error) {
				state.errorMessage = "Unable to load the console right now.";
			} finally {
				state.loading = false;
			}
		}

		function scheduleRefresh() {
			clearTimeout(state.refreshTimer);
			state.refreshTimer = setTimeout(() => {
				loadData();
			}, 220);
		}

		async function createRequest(row) {
			const draft = ensureDraft(row);
			const rowKey = pendingRowKey(row);
			const requestedQty = clampQty(draft.qty, row.remaining_requestable_qty);
			if (requestedQty <= QTY_EPSILON) {
				frappe.show_alert({
					message: __("Enter a valid request quantity."),
					indicator: "orange",
				});
				return;
			}
			if (!draft.required_by_date) {
				frappe.show_alert({
					message: __("Pick a required by date first."),
					indicator: "orange",
				});
				return;
			}

			state.busyCreateKey = rowKey;
			try {
				const message = await call(
					"snrg_credit_control.snrg_credit_control.pending_invoice_planning.create_production_requests_from_pending_rows",
					{
						rows: [
							{
								quotation: row.quotation,
								quotation_date: row.quotation_date,
								customer: row.customer,
								customer_name: row.customer_name,
								company: row.company,
								item_code: row.item_code,
								item_name: row.item_name,
								requested_qty: requestedQty,
								required_by_date: draft.required_by_date,
								assigned_to: draft.assigned_to || state.filters.default_assignee || "",
							},
						],
					}
				);
				frappe.show_alert({
					message: message?.message || __("Request created"),
					indicator: "green",
				});
				await loadData();
			} catch (error) {
				// Frappe handles the server-side dialog.
			} finally {
				state.busyCreateKey = "";
			}
		}

		async function updateRequestStatus(request, status) {
			if (!request?.name || !status) {
				return;
			}
			state.busyStatusName = `${request.name}:${status}`;
			try {
				const message = await call(
					"snrg_credit_control.snrg_credit_control.doctype.production_request.production_request.set_request_status",
					{
						name: request.name,
						status,
					}
				);
				frappe.show_alert({
					message: message?.message || __("Production Request updated."),
					indicator: "green",
				});
				await loadData();
			} catch (error) {
				// Frappe handles the server-side dialog.
			} finally {
				state.busyStatusName = "";
			}
		}

		async function updateRequestAssignee(request, assignedTo) {
			if (!request?.name) {
				return;
			}

			const previousAssignedTo = request.assigned_to || "";
			const previousAssignedToName = request.assigned_to_name || "";
			request.assigned_to = assignedTo || "";
			request.assigned_to_name = userLabel(assignedTo);
			state.busyAssigneeName = request.name;

			try {
				const message = await call(
					"snrg_credit_control.snrg_credit_control.doctype.production_request.production_request.set_request_assignee",
					{
						name: request.name,
						assigned_to: assignedTo || "",
					}
				);
				request.assigned_to = message?.assigned_to || "";
				request.assigned_to_name = message?.assigned_to_name || userLabel(request.assigned_to);
				frappe.show_alert({
					message: message?.message || __("Production Request assignee updated."),
					indicator: "green",
				});
			} catch (error) {
				request.assigned_to = previousAssignedTo;
				request.assigned_to_name = previousAssignedToName;
			} finally {
				state.busyAssigneeName = "";
			}
		}

		function openForm(doctype, name) {
			if (name) {
				frappe.set_route("Form", doctype, name);
			}
		}

		function openRequest(name) {
			openForm("Production Request", name);
		}

		function requestActions(request) {
			if (request.status === "Open") {
				return [
					{ label: "Start", value: "In Progress", tone: "is-primary" },
					{ label: "Complete", value: "Completed", tone: "" },
				];
			}
			if (request.status === "In Progress") {
				return [
					{ label: "Move to Open", value: "Open", tone: "" },
					{ label: "Mark Completed", value: "Completed", tone: "is-primary" },
				];
			}
			if (request.status === "Completed") {
				return [{ label: "Reopen", value: "Open", tone: "" }];
			}
			return [{ label: "Move to Open", value: "Open", tone: "" }];
		}

		function requestDueInfo(request) {
			return dueMeta(request.required_by_date);
		}

		watch(
			() => [state.filters.company, state.filters.search, state.filters.show_completed],
			() => {
				scheduleRefresh();
			}
		);

		watch(
			() => state.filters.default_assignee,
			(value) => {
				Object.values(state.requestDrafts).forEach((draft) => {
					if (!draft.assigned_to) {
						draft.assigned_to = value || "";
					}
				});
			}
		);

		onMounted(() => {
			loadData();
		});

		expose({
			refreshConsole: loadData,
			getRouteOptions() {
				return {
					company: state.filters.company || "",
					search: state.filters.search || "",
					show_completed: state.filters.show_completed ? 1 : 0,
					show_values: state.filters.show_values ? 1 : 0,
					default_assignee: state.filters.default_assignee || "",
				};
			},
		});

		return {
			state,
			summaryCards,
			boardColumns,
			ensureDraft,
			createRequest,
			updateRequestStatus,
			updateRequestAssignee,
			openForm,
			openRequest,
			formatQty,
			formatCurrency,
			formatDate,
			formatInteger,
			pendingRowKey,
			requestStatusClass,
			toneClass,
			requestActions,
			requestDueInfo,
			userLabel,
			QTY_EPSILON,
		};
	},
	template: `
		<div class="snrg-ppc-page">
			<section class="snrg-ppc-hero">
				<div>
					<div class="snrg-ppc-kicker">Stock Planning Console</div>
					<h2 class="snrg-ppc-title">Production Planning Console</h2>
					<p class="snrg-ppc-subtitle">
						Review uninvoiced demand, convert it into production requests, and move active requests across the board without leaving one screen.
					</p>
					<div class="snrg-ppc-hero-meta">
						<div class="snrg-ppc-chip">Pending demand + production board</div>
						<div class="snrg-ppc-chip">Request directly from live quotation demand</div>
					</div>
				</div>
				<div class="snrg-ppc-chip">{{ state.filters.company || 'Select company' }}</div>
			</section>

			<section class="snrg-ppc-filter-bar">
				<div class="snrg-ppc-field">
					<label>Company</label>
					<select class="snrg-ppc-select" v-model="state.filters.company">
						<option value="">Select company</option>
						<option v-for="company in state.meta.companies" :key="company" :value="company">{{ company }}</option>
					</select>
				</div>
				<div class="snrg-ppc-field">
					<label>Search</label>
					<input
						class="snrg-ppc-input"
						type="text"
						v-model="state.filters.search"
						placeholder="Search quotation, customer, item, or request"
					/>
				</div>
				<div class="snrg-ppc-field">
					<label>Default Assignee</label>
					<select class="snrg-ppc-select" v-model="state.filters.default_assignee">
						<option value="">Unassigned</option>
						<option v-for="user in state.meta.assignable_users" :key="user.value" :value="user.value">
							{{ user.label }}
						</option>
					</select>
				</div>
				<label class="snrg-ppc-check">
					<input type="checkbox" v-model="state.filters.show_completed" />
					Show Completed
				</label>
				<label class="snrg-ppc-check">
					<input type="checkbox" v-model="state.filters.show_values" />
					Show Values
				</label>
			</section>

			<section class="snrg-ppc-summary">
				<article
					v-for="card in summaryCards"
					:key="card.label"
					class="snrg-ppc-metric"
					:class="toneClass(card.tone)"
				>
					<div class="snrg-ppc-metric-label">{{ card.label }}</div>
					<div class="snrg-ppc-metric-value">{{ card.value }}</div>
					<div class="snrg-ppc-metric-subvalue">{{ card.subvalue }}</div>
				</article>
			</section>

			<div v-if="state.errorMessage" class="snrg-ppc-loading">{{ state.errorMessage }}</div>
			<div v-else-if="state.loading && !state.pending_rows.length && !(state.groups.Open || []).length && !(state.groups['In Progress'] || []).length" class="snrg-ppc-loading">
				Loading console...
			</div>

			<section class="snrg-ppc-panel">
				<div class="snrg-ppc-panel-head">
					<div>
						<div class="snrg-ppc-panel-title">Pending Demand</div>
						<div class="snrg-ppc-panel-subtitle">Create production requests straight from uninvoiced quotation demand.</div>
					</div>
					<div class="snrg-ppc-chip">{{ formatInteger(state.pending_rows.length) }} lines</div>
				</div>
				<div class="snrg-ppc-table-wrap">
					<table class="snrg-ppc-table">
						<thead>
							<tr>
								<th>Item</th>
								<th>Customer / Quote</th>
								<th>Stage</th>
								<th class="snrg-ppc-number">Pending Qty</th>
								<th v-if="state.filters.show_values" class="snrg-ppc-number">Pending Value</th>
								<th>Production</th>
								<th>Request</th>
							</tr>
						</thead>
						<tbody>
							<tr v-if="!state.pending_rows.length">
								<td :colspan="state.filters.show_values ? 7 : 6">
									<div class="snrg-ppc-empty">No pending demand found in the current company and search scope.</div>
								</td>
							</tr>
							<tr v-for="row in state.pending_rows" :key="pendingRowKey(row)">
								<td>
									<div class="snrg-ppc-stack">
										<a class="snrg-ppc-link snrg-ppc-primary-text" :href="'/app/item/' + encodeURIComponent(row.item_code || '')">
											{{ row.item_code || '-' }}
										</a>
										<div class="snrg-ppc-secondary-text">{{ row.item_name || '-' }}</div>
									</div>
								</td>
								<td>
									<div class="snrg-ppc-stack">
										<a class="snrg-ppc-link snrg-ppc-primary-text" :href="'/app/customer/' + encodeURIComponent(row.customer || '')">
											{{ row.customer || '-' }}
										</a>
										<div class="snrg-ppc-secondary-text">{{ row.customer_name || '-' }}</div>
										<a class="snrg-ppc-link snrg-ppc-secondary-text" :href="'/app/quotation/' + encodeURIComponent(row.quotation || '')">
											{{ row.quotation || '-' }} · {{ formatDate(row.quotation_date) }}
										</a>
									</div>
								</td>
								<td>
									<div class="snrg-ppc-stack">
										<div class="snrg-ppc-badge is-neutral">{{ row.status_summary || 'No status' }}</div>
										<div class="snrg-ppc-secondary-text">{{ row.planning_stage_summary || '-' }}</div>
									</div>
								</td>
								<td class="snrg-ppc-number">{{ formatQty(row.total_uninvoiced_qty) }}</td>
								<td v-if="state.filters.show_values" class="snrg-ppc-number snrg-ppc-value">
									{{ formatCurrency(row.total_uninvoiced_value, row.currency) }}
								</td>
								<td>
									<div class="snrg-ppc-stack">
										<div class="snrg-ppc-badge" :class="requestStatusClass(row.production_request_status)">
											{{ row.production_request_status || 'Not Requested' }}
										</div>
										<div v-if="row.production_required_by_date" class="snrg-ppc-secondary-text">
											Need by {{ formatDate(row.production_required_by_date) }}
										</div>
									</div>
								</td>
								<td>
									<div v-if="row.remaining_requestable_qty <= QTY_EPSILON" class="snrg-ppc-requested-box">
										<div class="snrg-ppc-badge is-success">Requested</div>
										<div v-if="row.production_required_by_date" class="snrg-ppc-request-meta">
											Required by {{ formatDate(row.production_required_by_date) }}
										</div>
									</div>
									<div v-else class="snrg-ppc-request-cell">
										<div class="snrg-ppc-request-row">
											<input
												class="snrg-ppc-input"
												type="number"
												step="0.01"
												min="0.01"
												:max="row.remaining_requestable_qty"
												v-model.number="ensureDraft(row).qty"
											/>
											<input
												class="snrg-ppc-input"
												type="date"
												v-model="ensureDraft(row).required_by_date"
											/>
											<button
												class="snrg-ppc-button is-primary"
												type="button"
												@click="createRequest(row)"
												:disabled="state.busyCreateKey === pendingRowKey(row)"
											>
												{{ state.busyCreateKey === pendingRowKey(row) ? 'Saving...' : (Number(row.production_requested_qty || 0) > 0 ? 'Request More' : 'Request') }}
											</button>
										</div>
										<div class="snrg-ppc-request-meta">
											Assignee: {{ userLabel(ensureDraft(row).assigned_to || state.filters.default_assignee) }}
										</div>
									</div>
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</section>

			<section class="snrg-ppc-panel">
				<div class="snrg-ppc-panel-head">
					<div>
						<div class="snrg-ppc-panel-title">Production Request Board</div>
						<div class="snrg-ppc-panel-subtitle">Track all live requests after demand is converted into work.</div>
					</div>
					<div class="snrg-ppc-chip">Live board</div>
				</div>
				<div class="snrg-ppc-board" style="padding: 14px;">
					<section v-for="column in boardColumns" :key="column.key" class="snrg-ppc-column">
						<header class="snrg-ppc-column-head">
							<div class="snrg-ppc-column-title">{{ column.label }}</div>
							<div class="snrg-ppc-column-pill">{{ formatInteger(column.rows.length) }}</div>
						</header>
						<div class="snrg-ppc-column-body">
							<div v-if="!column.rows.length" class="snrg-ppc-empty">No requests in this stage.</div>
							<article
								v-for="request in column.rows"
								:key="request.name"
								class="snrg-ppc-card"
								:class="{
									'is-progress': request.status === 'In Progress',
									'is-completed': request.status === 'Completed'
								}"
							>
								<div class="snrg-ppc-card-top">
									<div class="snrg-ppc-stack">
										<div class="snrg-ppc-card-code">
											<a class="snrg-ppc-link" :href="'/app/item/' + encodeURIComponent(request.item_code || '')">
												{{ request.item_code || '-' }}
											</a>
										</div>
										<div class="snrg-ppc-card-name">{{ request.item_name || request.item_code || request.name }}</div>
									</div>
									<div class="snrg-ppc-badge" :class="requestStatusClass(request.status)">
										{{ formatQty(request.requested_qty) }}
									</div>
								</div>

								<div class="snrg-ppc-card-grid">
									<div class="snrg-ppc-stack">
										<div class="snrg-ppc-card-meta-label">Quotation</div>
										<div class="snrg-ppc-card-meta-value">
											<a class="snrg-ppc-link" :href="'/app/quotation/' + encodeURIComponent(request.quotation || '')">
												{{ request.quotation || '-' }}
											</a>
										</div>
										<div class="snrg-ppc-card-meta-sub">{{ formatDate(request.quotation_date) }}</div>
									</div>
									<div class="snrg-ppc-stack">
										<div class="snrg-ppc-card-meta-label">Customer</div>
										<div class="snrg-ppc-card-meta-value">
											<a class="snrg-ppc-link" :href="'/app/customer/' + encodeURIComponent(request.customer || '')">
												{{ request.customer || '-' }}
											</a>
										</div>
										<div class="snrg-ppc-card-meta-sub">{{ request.customer_name || '-' }}</div>
									</div>
								</div>

								<div class="snrg-ppc-card-footer">
									<div class="snrg-ppc-due" :class="{
										'is-danger': requestDueInfo(request).tone === 'danger',
										'is-warning': requestDueInfo(request).tone === 'warning'
									}">
										<span>{{ formatDate(request.required_by_date) }}</span>
										<span>{{ requestDueInfo(request).label }}</span>
									</div>

									<div class="snrg-ppc-field">
										<label>Assigned To</label>
										<select
											class="snrg-ppc-select"
											:disabled="state.busyAssigneeName === request.name"
											:value="request.assigned_to || ''"
											@change="updateRequestAssignee(request, $event.target.value)"
										>
											<option value="">Unassigned</option>
											<option v-for="user in state.meta.assignable_users" :key="user.value" :value="user.value">
												{{ user.label }}
											</option>
										</select>
									</div>

									<div class="snrg-ppc-card-grid">
										<div class="snrg-ppc-stack">
											<div class="snrg-ppc-card-meta-label">Requested By</div>
											<div class="snrg-ppc-card-meta-sub">{{ request.requested_by_name || request.requested_by || '-' }}</div>
										</div>
										<div class="snrg-ppc-stack">
											<div class="snrg-ppc-card-meta-label">Request</div>
											<div class="snrg-ppc-card-meta-sub">{{ request.name }}</div>
										</div>
									</div>

									<div class="snrg-ppc-card-actions">
										<button
											v-for="action in requestActions(request)"
											:key="request.name + action.value"
											class="snrg-ppc-button"
											:class="action.tone"
											type="button"
											@click="updateRequestStatus(request, action.value)"
											:disabled="state.busyStatusName === (request.name + ':' + action.value)"
										>
											{{ action.label }}
										</button>
										<button class="snrg-ppc-button is-ghost" type="button" @click="openRequest(request.name)">
											Open
										</button>
									</div>
								</div>
							</article>
						</div>
					</section>
				</div>
			</section>
		</div>
	`,
};

class SnrgProductionPlanningConsole {
	constructor({ wrapper, page, routeOptions }) {
		this.$wrapper = $(wrapper);
		this.page = page;
		this.routeOptions = routeOptions || {};

		this.page.clear_actions();
		this.page.clear_custom_actions();
		this.page.clear_menu();

		this.page.set_primary_action(__("Open Pending Invoice Planning Report"), () => {
			const routeOptions =
				(this.instance && this.instance.getRouteOptions && this.instance.getRouteOptions()) ||
				this.routeOptions ||
				{};
			frappe.route_options = {
				company: routeOptions.company || "",
				show_values: routeOptions.show_values ? 1 : 0,
				default_assignee: routeOptions.default_assignee || "",
			};
			frappe.set_route("query-report", "Pending Invoice Planning Report");
		});
		this.page.set_secondary_action(__("Refresh"), () => {
			this.instance?.refreshConsole?.();
		}, "refresh");
		this.page.add_inner_button(__("Board View"), () => {
			frappe.set_route("production-planning");
		});

		this.mount();
	}

	mount() {
		ensureConsoleStyles();
		this.$wrapper.empty();

		const mountPoint = document.createElement("div");
		this.$wrapper.get(0).appendChild(mountPoint);

		this.app = createApp(ProductionPlanningConsoleApp, {
			page: this.page,
			routeOptions: this.routeOptions,
		});
		this.instance = this.app.mount(mountPoint);
	}

	destroy() {
		if (this.app) {
			this.app.unmount();
		}
		this.$wrapper.empty();
	}
}

frappe.provide("frappe.ui");
frappe.ui.SnrgProductionPlanningConsole = SnrgProductionPlanningConsole;

export default SnrgProductionPlanningConsole;

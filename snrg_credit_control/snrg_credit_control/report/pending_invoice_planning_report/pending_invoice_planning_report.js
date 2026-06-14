frappe.query_reports["Pending Invoice Planning Report"] = {
  disable_prepared_report: true,

  filters: [
    {
      fieldname: "company",
      label: __("Company"),
      fieldtype: "Link",
      options: "Company",
      default: frappe.defaults.get_user_default("Company"),
      reqd: 1,
      on_change: refresh_pending_invoice_planning_report,
    },
    {
      fieldname: "date_range",
      label: __("Date Range"),
      fieldtype: "DateRange",
      on_change: refresh_pending_invoice_planning_report,
    },
    {
      fieldname: "customer",
      label: __("Customer"),
      fieldtype: "Link",
      options: "Customer",
      on_change: refresh_pending_invoice_planning_report,
    },
    {
      fieldname: "territory",
      label: __("Territory"),
      fieldtype: "Link",
      options: "Territory",
      on_change: refresh_pending_invoice_planning_report,
    },
    {
      fieldname: "quotation",
      label: __("Quotation"),
      fieldtype: "Link",
      options: "Quotation",
      on_change: refresh_pending_invoice_planning_report,
    },
    {
      fieldname: "item_code",
      label: __("Item Code"),
      fieldtype: "Link",
      options: "Item",
      on_change: refresh_pending_invoice_planning_report,
    },
    {
      fieldname: "quotation_status",
      label: __("Quotation Status"),
      fieldtype: "MultiSelectList",
      on_change: refresh_pending_invoice_planning_report,
      get_data(txt) {
        const options = ["Draft", "Submitted"];
        return options
          .filter((option) => !txt || option.toLowerCase().includes(txt.toLowerCase()))
          .map((value) => ({ value, description: value }));
      },
    },
    {
      fieldname: "sales_order_status",
      label: __("Sales Order Status"),
      fieldtype: "MultiSelectList",
      on_change: refresh_pending_invoice_planning_report,
      get_data(txt) {
        const options = ["No SO", "Draft SO", "Submitted SO", "Mixed SO"];
        return options
          .filter((option) => !txt || option.toLowerCase().includes(txt.toLowerCase()))
          .map((value) => ({ value, description: value }));
      },
    },
    {
      fieldname: "production_status",
      label: __("Production Status"),
      fieldtype: "MultiSelectList",
      on_change: refresh_pending_invoice_planning_report,
      get_data(txt) {
        const options = ["Not Requested", "Open", "In Progress", "Completed", "Cancelled"];
        return options
          .filter((option) => !txt || option.toLowerCase().includes(txt.toLowerCase()))
          .map((value) => ({ value, description: value }));
      },
    },
    {
      fieldname: "required_by_date_range",
      label: __("Required By"),
      fieldtype: "DateRange",
      on_change: refresh_pending_invoice_planning_report,
    },
    {
      fieldname: "default_assignee",
      label: __("Default Assignee"),
      fieldtype: "Link",
      options: "User",
    },
    {
      fieldname: "show_values",
      label: __("Show Values"),
      fieldtype: "Check",
      default: 0,
      on_change: refresh_pending_invoice_planning_report,
    },
  ],

  onload(report) {
    report.__snrgPendingInvoicePlanningDraftQtyByKey =
      report.__snrgPendingInvoicePlanningDraftQtyByKey || {};
    ensure_pending_invoice_planning_report_styles(report);
    setTimeout(() => force_live_pending_invoice_planning_refresh(report), 300);
    setTimeout(() => setup_pending_invoice_planning_actions(report), 400);
  },

  get_datatable_options(options) {
    return Object.assign(options || {}, {
      cellHeight: 64,
      checkboxColumn: true,
    });
  },

  after_datatable_render(datatable, report) {
    apply_pending_invoice_planning_table_layout(report, datatable);
  },

  formatter(value, row, column, data, default_formatter) {
    if (column.fieldname === "production_request_action" && data) {
      const report = get_pending_invoice_planning_active_report();
      const remainingQty = get_pending_invoice_planning_remaining_qty(data);
      const requestedQty = Number(data.production_requested_qty || 0);
      if (Number(data.total_uninvoiced_qty || 0) <= 0) {
        return "";
      }

      if (remainingQty <= 0.0001) {
        const requestName = data.production_request_name || "";
        const requiredBy = formatPendingInvoicePlanningDate(data.production_required_by_date || "");
        const statusParts = [requestName, requiredBy ? `${__("Required by")}: ${requiredBy}` : ""].filter(Boolean);
        const title = statusParts.join(" | ");
        return `
          <div class="snrg-pip-production-cell snrg-pip-production-cell-stack">
            <button
              type="button"
              class="btn btn-xs btn-secondary"
              disabled
              title="${frappe.utils.escape_html(title)}"
            >
              ${__("Requested")}
            </button>
            ${requiredBy ? `<div class="snrg-pip-production-meta">${__("Required by")}: ${frappe.utils.escape_html(requiredBy)}</div>` : ""}
          </div>
        `;
      }

      const rowKey = get_pending_invoice_planning_row_key(data);
      const draftQty = get_pending_invoice_planning_draft_qty(report, data);
      const buttonLabel = requestedQty > 0 ? __("Request More") : __("Request");
      return `
        <div class="snrg-pip-production-cell snrg-pip-production-cell-stack">
          <div class="snrg-pip-production-cell">
            <input
              type="number"
              class="form-control input-xs snrg-pip-request-qty"
              data-row-key="${frappe.utils.escape_html(rowKey)}"
              data-max-qty="${frappe.utils.escape_html(String(remainingQty))}"
              min="0.01"
              step="0.01"
              value="${frappe.utils.escape_html(format_pending_invoice_planning_qty_input(draftQty))}"
            />
            <button
              type="button"
              class="btn btn-xs btn-default snrg-pip-request-production"
              data-row-key="${frappe.utils.escape_html(rowKey)}"
            >
              ${buttonLabel}
            </button>
          </div>
          ${data.production_required_by_date ? `<div class="snrg-pip-production-meta">${__("Required by")}: ${frappe.utils.escape_html(formatPendingInvoicePlanningDate(data.production_required_by_date))}</div>` : ""}
        </div>
      `;
    }

    if (column.fieldname === "quotation" && data) {
      return render_pending_invoice_planning_stacked_link({
        route: `/app/quotation/${encodeURIComponent(data.quotation || "")}`,
        primary: data.quotation || "",
        secondary: formatPendingInvoicePlanningDate(data.quotation_date),
      });
    }

    if (column.fieldname === "customer" && data) {
      return render_pending_invoice_planning_stacked_link({
        route: `/app/customer/${encodeURIComponent(data.customer || "")}`,
        primary: data.customer || "",
        secondary: data.customer_name || "",
      });
    }

    if (column.fieldname === "item_code" && data) {
      return render_pending_invoice_planning_link({
        route: `/app/item/${encodeURIComponent(data.item_code || "")}`,
        label: data.item_code || "",
      });
    }

    if (column.fieldname === "item_name" && data) {
      return `<div class="snrg-pip-item-name-cell">${frappe.utils.escape_html(data.item_name || "")}</div>`;
    }

    const formatted = default_formatter(value, row, column, data);
    if (!data) {
      return formatted;
    }

    if (column.fieldname === "status_summary") {
      const valueText = String(data.status_summary || "").toLowerCase();
      if (valueText.includes("draft") && valueText.includes("submitted")) {
        return `<span style="color:#7c3aed;font-weight:600;">${formatted}</span>`;
      }
      if (valueText.includes("draft")) {
        return `<span style="color:#b45309;font-weight:600;">${formatted}</span>`;
      }
      if (valueText.includes("submitted")) {
        return `<span style="color:#2563eb;font-weight:600;">${formatted}</span>`;
      }
    }

    if (column.fieldname === "production_request_status") {
      return render_pending_invoice_planning_production_status(formatted, data.production_request_status);
    }

    if (column.fieldname === "total_uninvoiced_value") {
      const amount = Number(data.total_uninvoiced_value || 0);
      if (amount > 0) {
        return `<span style="color:#b91c1c;font-weight:700;">${formatted}</span>`;
      }
    }

    if (column.fieldname === "total_uninvoiced_qty") {
      const qty = Number(data.total_uninvoiced_qty || 0);
      if (qty > 0) {
        return `<span style="font-weight:700;">${formatted}</span>`;
      }
    }

    return formatted;
  },
};

function get_pending_invoice_planning_active_report() {
  return frappe.query_report || null;
}

function get_pending_invoice_planning_row_key(row) {
  const quotation = String(row?.quotation || "").trim().toLowerCase();
  const itemCode = String(row?.item_code || "").trim().toLowerCase();
  return `${quotation}::${itemCode}`;
}

function get_pending_invoice_planning_row_by_key(report, rowKey) {
  return (report?.data || []).find((row) => get_pending_invoice_planning_row_key(row) === rowKey) || null;
}

function get_pending_invoice_planning_remaining_qty(row) {
  return Math.max(
    Number(
      row?.remaining_requestable_qty != null
        ? row.remaining_requestable_qty
        : row?.total_uninvoiced_qty || 0
    ) || 0,
    0
  );
}

function get_pending_invoice_planning_draft_qty(report, row) {
  const rowKey = get_pending_invoice_planning_row_key(row);
  const maxQty = get_pending_invoice_planning_remaining_qty(row);
  if (!report) {
    return maxQty;
  }

  report.__snrgPendingInvoicePlanningDraftQtyByKey =
    report.__snrgPendingInvoicePlanningDraftQtyByKey || {};

  const storedQty = Number(report.__snrgPendingInvoicePlanningDraftQtyByKey[rowKey]);
  if (!Number.isFinite(storedQty) || storedQty <= 0) {
    report.__snrgPendingInvoicePlanningDraftQtyByKey[rowKey] = maxQty;
    return maxQty;
  }

  const normalizedQty = Math.min(storedQty, maxQty);
  report.__snrgPendingInvoicePlanningDraftQtyByKey[rowKey] = normalizedQty;
  return normalizedQty;
}

function set_pending_invoice_planning_draft_qty(report, row, qty) {
  if (!report || !row) {
    return 0;
  }

  report.__snrgPendingInvoicePlanningDraftQtyByKey =
    report.__snrgPendingInvoicePlanningDraftQtyByKey || {};

  const maxQty = get_pending_invoice_planning_remaining_qty(row);
  const normalizedQty = normalize_pending_invoice_planning_request_qty(qty, maxQty);
  report.__snrgPendingInvoicePlanningDraftQtyByKey[get_pending_invoice_planning_row_key(row)] = normalizedQty;
  return normalizedQty;
}

function clear_pending_invoice_planning_draft_qty(report, rows) {
  if (!report || !rows?.length || !report.__snrgPendingInvoicePlanningDraftQtyByKey) {
    return;
  }

  rows.forEach((row) => {
    delete report.__snrgPendingInvoicePlanningDraftQtyByKey[get_pending_invoice_planning_row_key(row)];
  });
}

function normalize_pending_invoice_planning_request_qty(value, maxQty) {
  const numericMaxQty = Math.max(Number(maxQty || 0) || 0, 0);
  const numericValue = Number(value || 0);
  if (!Number.isFinite(numericValue) || numericValue <= 0) {
    return numericMaxQty;
  }
  return Math.min(numericValue, numericMaxQty);
}

function format_pending_invoice_planning_qty_input(value) {
  const numericValue = Number(value || 0);
  if (!Number.isFinite(numericValue)) {
    return "0";
  }
  return numericValue.toFixed(2).replace(/\.00$/, "");
}

function refresh_pending_invoice_planning_report(report) {
  if (!report) {
    return;
  }

  close_pending_invoice_planning_request_picker(report);
  clearTimeout(report.snrgPendingInvoicePlanningRefreshTimer);
  report.snrgPendingInvoicePlanningRefreshTimer = setTimeout(() => {
    report.refresh();
  }, 200);
}

function force_live_pending_invoice_planning_refresh(report) {
  if (!report || report.__snrgPendingInvoicePlanningLiveRefreshDone) {
    return;
  }

  const wrapperText = report.page && report.page.wrapper ? report.page.wrapper.text() : "";
  if (wrapperText && wrapperText.includes("See all past reports")) {
    report.__snrgPendingInvoicePlanningLiveRefreshDone = true;
    report.refresh();
  }
}

function setup_pending_invoice_planning_actions(report) {
  if (!report || report.__snrgPendingInvoicePlanningActionsSetup) {
    return;
  }

  report.__snrgPendingInvoicePlanningActionsSetup = true;
  ensure_pending_invoice_planning_report_styles(report);
  report.page.set_primary_action(__("Open Production Planning"), () => {
    frappe.route_options = {
      company: report.get_filter_value("company") || "",
    };
    frappe.set_route("production-planning");
  });
  ensure_pending_invoice_planning_bulk_button(report);
  bind_pending_invoice_planning_request_picker_events(report);

  const wrapper = report.page && report.page.wrapper ? report.page.wrapper : $(document.body);
  wrapper.off("input.snrg_pip_request_qty change.snrg_pip_request_qty blur.snrg_pip_request_qty");
  wrapper.on("input.snrg_pip_request_qty change.snrg_pip_request_qty", ".snrg-pip-request-qty", (event) => {
    const input = $(event.currentTarget);
    const rowKey = input.attr("data-row-key") || "";
    const rowData = get_pending_invoice_planning_row_by_key(report, rowKey);
    if (!rowData) {
      return;
    }
    set_pending_invoice_planning_draft_qty(report, rowData, input.val());
  });
  wrapper.on("blur.snrg_pip_request_qty", ".snrg-pip-request-qty", (event) => {
    const input = $(event.currentTarget);
    const rowKey = input.attr("data-row-key") || "";
    const rowData = get_pending_invoice_planning_row_by_key(report, rowKey);
    if (!rowData) {
      return;
    }
    const normalizedQty = set_pending_invoice_planning_draft_qty(report, rowData, input.val());
    input.val(format_pending_invoice_planning_qty_input(normalizedQty));
  });

  wrapper.off("click.snrg_pip_request_production");
  wrapper.on("click.snrg_pip_request_production", ".snrg-pip-request-production", (event) => {
    event.preventDefault();
    event.stopPropagation();
    if (event.stopImmediatePropagation) {
      event.stopImmediatePropagation();
    }
    const button = $(event.currentTarget);
    const rowKey = button.attr("data-row-key") || "";
    const rowData = get_pending_invoice_planning_row_by_key(report, rowKey);
    if (!rowData) {
      frappe.show_alert({
        message: __("This row is no longer available. Please refresh the report."),
        indicator: "orange",
      });
      return false;
    }

    toggle_pending_invoice_planning_request_picker(report, button, {
      contextKey: `row:${rowKey}`,
      assignee: report.get_filter_value("default_assignee") || rowData.production_assigned_to || "",
      assigneeEditable: true,
      title: __("Create Request"),
      onSelect: (requiredByDate, meta = {}) => {
        const payloadRow = build_pending_invoice_planning_payload_from_row(
          report,
          rowData,
          requiredByDate,
          meta.assignedTo || ""
        );
        if (!payloadRow) {
          return;
        }
        create_pending_invoice_planning_requests(
          report,
          button,
          [payloadRow],
          {
            onSuccess: () => report.refresh(),
          }
        );
      },
    });
    return false;
  });
}

function ensure_pending_invoice_planning_bulk_button(report) {
  if (!report || report.__snrgPendingInvoicePlanningBulkButton) {
    return;
  }

  const bulkButton = report.page.add_inner_button(__("Request Selected"), () => {
    const selectedRows = get_selected_pending_invoice_planning_rows(report);
    const requestableRows = selectedRows.filter((row) => is_requestable_pending_invoice_planning_row(row));
    const defaultAssignee = report.get_filter_value("default_assignee") || "";

    if (!selectedRows.length) {
      frappe.show_alert({
        message: __("Select one or more rows first."),
        indicator: "orange",
      });
      return;
    }

    if (!requestableRows.length) {
      frappe.show_alert({
        message: __("Selected rows are already requested or have no pending quantity."),
        indicator: "orange",
      });
      return;
    }

    if (!defaultAssignee) {
      frappe.show_alert({
        message: __("Select a Default Assignee first for bulk requests."),
        indicator: "orange",
      });
      return;
    }

    toggle_pending_invoice_planning_request_picker(report, $(bulkButton), {
      contextKey: `bulk:${requestableRows.map((row) => `${row.quotation}:${row.item_code}`).join("|")}`,
      assignee: defaultAssignee,
      assigneeEditable: false,
      title: __("Bulk Request"),
      onSelect: (requiredByDate, meta = {}) => {
        const payloadRows = requestableRows
          .map((row) => build_pending_invoice_planning_payload_from_row(report, row, requiredByDate, meta.assignedTo || defaultAssignee))
          .filter(Boolean);
        if (!payloadRows.length) {
          frappe.show_alert({
            message: __("Selected rows do not have any requestable quantity left."),
            indicator: "orange",
          });
          return;
        }
        create_pending_invoice_planning_requests(report, $(bulkButton), payloadRows, {
          onSuccess: () => report.refresh(),
        });
      },
    });
  });

  report.__snrgPendingInvoicePlanningBulkButton = $(bulkButton);
}

function get_selected_pending_invoice_planning_rows(report) {
  const datatableRowmanager = report && report.datatable && report.datatable.rowmanager;
  if (!datatableRowmanager || !datatableRowmanager.getCheckedRows) {
    return [];
  }

  const checkedRows = datatableRowmanager.getCheckedRows() || [];
  return checkedRows
    .map((index) => (report.data || [])[index] || null)
    .filter(Boolean);
}

function is_requestable_pending_invoice_planning_row(row) {
  if (!row) {
    return false;
  }

  return get_pending_invoice_planning_remaining_qty(row) > 0.0001;
}

function build_pending_invoice_planning_payload_from_row(report, row, requiredByDate, assignedTo = "") {
  if (!row) {
    return null;
  }

  const requestedQty = get_pending_invoice_planning_draft_qty(report, row);
  if (!(requestedQty > 0)) {
    return null;
  }

  return {
    quotation: row.quotation || "",
    quotation_date: row.quotation_date || "",
    customer: row.customer || "",
    customer_name: row.customer_name || "",
    company: row.company || "",
    item_code: row.item_code || "",
    item_name: row.item_name || "",
    requested_qty: requestedQty,
    remaining_requestable_qty: get_pending_invoice_planning_remaining_qty(row),
    required_by_date: requiredByDate || "",
    assigned_to: assignedTo || "",
  };
}

function create_pending_invoice_planning_requests(report, triggerButton, rows, options = {}) {
  if (!triggerButton || !triggerButton.length || !rows || !rows.length) {
    return;
  }

  const originalText = triggerButton.text();
  triggerButton.prop("disabled", true).text(__("Creating..."));

  frappe.call({
    method: "snrg_credit_control.snrg_credit_control.pending_invoice_planning.create_production_requests_from_pending_rows",
    args: {
      rows,
    },
    freeze: false,
    callback: ({ message }) => {
      const result = message || {};
      clear_pending_invoice_planning_draft_qty(report, rows);
      frappe.show_alert({
        message: result.message || __("Request created"),
        indicator: "green",
      });

      if (typeof options.onSuccess === "function") {
        options.onSuccess(result);
      } else {
        triggerButton
          .removeClass("btn-default snrg-pip-request-production-active")
          .addClass("btn-secondary")
          .prop("disabled", true)
          .text(result.updated_count ? __("Updated") : __("Requested"));
      }
    },
    error: () => {
      triggerButton
        .prop("disabled", false)
        .removeClass("snrg-pip-request-production-active")
        .text(originalText || __("Request"));
    },
  });
}

function ensure_pending_invoice_planning_report_styles(report) {
  if (!report || !report.page || !report.page.wrapper) {
    return;
  }

  const wrapper = report.page.wrapper;
  wrapper.addClass("snrg-pip-report-page");

  if ($("#snrg-pip-report-style").length) {
    return;
  }

  $("head").append(`
    <style id="snrg-pip-report-style">
      .snrg-pip-report-page .dt-scrollable .dt-row,
      .snrg-pip-report-page .dt-scrollable .dt-cell {
        min-height: 64px;
      }

      .snrg-pip-report-page .dt-scrollable .dt-cell__content {
        height: 100% !important;
        white-space: normal !important;
        line-height: 1.18;
        padding-top: 5px;
        padding-bottom: 5px;
        overflow: visible;
        display: block;
      }

      .snrg-pip-report-page .snrg-pip-stacked-cell {
        display: grid;
        gap: 3px;
        line-height: 1.25;
      }

      .snrg-pip-report-page .snrg-pip-stacked-primary {
        font-weight: 700;
        color: #0f766e;
      }

      .snrg-pip-report-page .snrg-pip-stacked-secondary {
        color: #667085;
        font-size: 12px;
      }

      .snrg-pip-report-page .snrg-pip-item-name-cell {
        white-space: normal;
        overflow-wrap: anywhere;
        line-height: 1.18;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
      }

      .snrg-pip-production-cell {
        display: flex;
        align-items: center;
        gap: 6px;
      }

      .snrg-pip-production-cell-stack {
        display: grid;
        gap: 2px;
        align-items: start;
      }

      .snrg-pip-production-cell .snrg-pip-request-qty {
        width: 72px;
        min-width: 72px;
        height: 26px;
        text-align: right;
        padding: 2px 7px;
      }

      .snrg-pip-production-meta {
        color: #667085;
        font-size: 11px;
        line-height: 1.2;
      }

      .snrg-pip-request-popover {
        position: absolute;
        z-index: 30;
        width: 236px;
        max-width: min(236px, calc(100vw - 18px));
        padding: 10px;
        border: 1px solid #dfe5ef;
        border-radius: 10px;
        background: #ffffff;
        box-shadow: 0 18px 42px rgba(15, 23, 42, 0.16);
      }

      .snrg-pip-request-popover-title {
        color: #101828;
        font-size: 12px;
        font-weight: 700;
        margin-bottom: 4px;
      }

      .snrg-pip-request-popover-help {
        color: #667085;
        font-size: 11px;
        line-height: 1.3;
        margin-bottom: 8px;
      }

      .snrg-pip-request-popover-static {
        margin-bottom: 8px;
      }

      .snrg-pip-request-popover-static-label {
        color: #667085;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: .04em;
        margin-bottom: 4px;
      }

      .snrg-pip-request-popover-static-value {
        color: #101828;
        font-size: 13px;
        font-weight: 700;
        line-height: 1.4;
        overflow-wrap: anywhere;
      }

      .snrg-pip-request-popover .frappe-control,
      .snrg-pip-request-popover .form-group,
      .snrg-pip-request-popover .control-input-wrapper {
        margin-bottom: 0;
      }

      .snrg-pip-request-popover [data-request-assignee-control] {
        margin-bottom: 8px;
      }

      .snrg-pip-request-popover .control-label {
        margin-bottom: 2px !important;
        color: #667085 !important;
        font-size: 11px !important;
        font-weight: 700 !important;
        text-transform: uppercase;
        letter-spacing: .04em;
      }

      .snrg-pip-request-production-active {
        box-shadow: 0 0 0 2px rgba(23, 92, 211, 0.16);
      }
    </style>
  `);
}

function apply_pending_invoice_planning_table_layout(report, datatable) {
  const target =
    datatable?.wrapper ||
    report?.datatable?.wrapper ||
    report?.page?.wrapper?.find(".dt-scrollable")[0];

  if (!target) {
    return;
  }

  target.querySelectorAll(".dt-row, .dt-cell").forEach((element) => {
    element.style.minHeight = "64px";
  });

  target.querySelectorAll(".dt-cell__content").forEach((element) => {
    element.style.height = "100%";
    element.style.whiteSpace = "normal";
    element.style.lineHeight = "1.18";
    element.style.paddingTop = "5px";
    element.style.paddingBottom = "5px";
    element.style.overflow = "visible";
    element.style.display = "block";
  });
}

function bind_pending_invoice_planning_request_picker_events(report) {
  $(document).off("mousedown.snrg_pip_request_picker");
  $(document).on("mousedown.snrg_pip_request_picker", (event) => {
    const picker = report && report.__snrgPendingInvoicePlanningRequestPicker;
    if (!picker) {
      return;
    }

    const target = $(event.target);
    if (
      target.closest(".air-datepicker, .datepicker, .flatpickr-calendar, .ui-datepicker").length
    ) {
      return;
    }

    if (
      picker.container.is(target) ||
      picker.container.has(target).length ||
      picker.target.is(target) ||
      picker.target.has(target).length
    ) {
      return;
    }

    close_pending_invoice_planning_request_picker(report);
  });

  $(document).off("keydown.snrg_pip_request_picker");
  $(document).on("keydown.snrg_pip_request_picker", (event) => {
    if (event.key === "Escape") {
      close_pending_invoice_planning_request_picker(report);
    }
  });

  $(window).off("resize.snrg_pip_request_picker");
  $(window).on("resize.snrg_pip_request_picker", () => {
    const picker = report && report.__snrgPendingInvoicePlanningRequestPicker;
    if (!picker) {
      return;
    }
    position_pending_invoice_planning_request_picker(picker.target, picker.container);
  });
}

function toggle_pending_invoice_planning_request_picker(report, button, options = {}) {
  const activePicker = report && report.__snrgPendingInvoicePlanningRequestPicker;
  const contextKey = options.contextKey || "default";
  if (
    activePicker &&
    activePicker.target &&
    activePicker.target.get(0) === button.get(0) &&
    activePicker.contextKey === contextKey
  ) {
    close_pending_invoice_planning_request_picker(report);
    return;
  }

  open_pending_invoice_planning_request_picker(report, button, options);
}

function open_pending_invoice_planning_request_picker(report, button, options = {}) {
  if (!report || !button || !button.length || button.prop("disabled")) {
    return;
  }

  close_pending_invoice_planning_request_picker(report);

  const assigneeValue = options.assignee || "";
  const assigneeEditable = !!options.assigneeEditable;
  const helpText = options.helpText || "";
  const container = $(`
    <div class="snrg-pip-request-popover">
      <div class="snrg-pip-request-popover-title">${frappe.utils.escape_html(options.title || __("Create Production Request"))}</div>
      ${helpText ? `<div class="snrg-pip-request-popover-help">${frappe.utils.escape_html(helpText)}</div>` : ""}
      <div data-request-assignee-area></div>
      <div data-request-date-control></div>
    </div>
  `).appendTo(document.body);

  let assigneeControl = null;
  if (assigneeEditable) {
    assigneeControl = frappe.ui.form.make_control({
      parent: container.find("[data-request-assignee-area]").get(0),
      df: {
        fieldname: "assigned_to",
        fieldtype: "Link",
        label: __("Assignee"),
        options: "User",
        default: assigneeValue,
      },
      render_input: true,
    });
    assigneeControl.refresh();
    assigneeControl.set_value(assigneeValue);
  } else {
    container.find("[data-request-assignee-area]").html(`
      <div class="snrg-pip-request-popover-static">
        <div class="snrg-pip-request-popover-static-label">${__("Assignee")}</div>
        <div class="snrg-pip-request-popover-static-value">${frappe.utils.escape_html(assigneeValue || __("Not Assigned"))}</div>
      </div>
    `);
  }

  let dateControl = null;
  dateControl = frappe.ui.form.make_control({
    parent: container.find("[data-request-date-control]").get(0),
    df: {
      fieldname: "required_by_date",
      fieldtype: "Date",
      label: __("Required By"),
      change: () => {
        const requiredByDate = dateControl && dateControl.get_value ? dateControl.get_value() : "";
        if (!requiredByDate) {
          return;
        }
        const pickerState = report.__snrgPendingInvoicePlanningRequestPicker;
        const assignedTo =
          pickerState && pickerState.assigneeControl && pickerState.assigneeControl.get_value
            ? pickerState.assigneeControl.get_value()
            : pickerState?.assignedTo || "";
        close_pending_invoice_planning_request_picker(report);
        if (pickerState && typeof pickerState.onSelect === "function") {
          pickerState.onSelect(requiredByDate, { assignedTo });
        }
      },
    },
    render_input: true,
  });
  dateControl.refresh();
  if (dateControl.set_value) {
    dateControl.set_value("");
  }

  report.__snrgPendingInvoicePlanningRequestPicker = {
    target: button,
    container,
    dateControl,
    assigneeControl,
    assignedTo: assigneeValue,
    contextKey: options.contextKey || "default",
    onSelect: options.onSelect || null,
  };

  button.addClass("snrg-pip-request-production-active");
  position_pending_invoice_planning_request_picker(button, container);

  setTimeout(() => {
    if (!dateControl || !dateControl.datepicker || !report.__snrgPendingInvoicePlanningRequestPicker) {
      return;
    }

    if (typeof dateControl.datepicker.show === "function") {
      dateControl.datepicker.show();
    }
  }, 0);
}

function close_pending_invoice_planning_request_picker(report) {
  const picker = report && report.__snrgPendingInvoicePlanningRequestPicker;
  if (!picker) {
    return;
  }

  if (picker.target && picker.target.length) {
    picker.target.removeClass("snrg-pip-request-production-active");
  }
  if (picker.dateControl && picker.dateControl.datepicker && typeof picker.dateControl.datepicker.hide === "function") {
    picker.dateControl.datepicker.hide();
  }
  if (picker.container && picker.container.length) {
    picker.container.remove();
  }

  report.__snrgPendingInvoicePlanningRequestPicker = null;
}

function position_pending_invoice_planning_request_picker(button, container) {
  if (!button || !button.length || !container || !container.length) {
    return;
  }

  const rect = button.get(0).getBoundingClientRect();
  const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
  const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
  const scrollX = window.scrollX || window.pageXOffset || 0;
  const scrollY = window.scrollY || window.pageYOffset || 0;
  const gutter = 12;
  const popoverWidth = Math.max(container.outerWidth() || 236, 290);
  const estimatedCalendarHeight = 340;
  const popoverHeight = Math.max(container.outerHeight() || 150, 150) + estimatedCalendarHeight;

  let left = rect.left + scrollX;
  if (left + popoverWidth > scrollX + viewportWidth - gutter) {
    left = scrollX + viewportWidth - popoverWidth - gutter;
  }
  left = Math.max(scrollX + gutter, left);

  const spaceBelow = viewportHeight - rect.bottom;
  const showAbove = spaceBelow < popoverHeight + 18 && rect.top > popoverHeight + 18;
  const top = showAbove
    ? rect.top + scrollY - popoverHeight - 8
    : rect.bottom + scrollY + 8;

  container.css({
    left: `${left}px`,
    top: `${Math.max(scrollY + gutter, top)}px`,
  });
}

function render_pending_invoice_planning_stacked_link({ route, primary, secondary }) {
  return `
    <div class="snrg-pip-stacked-cell">
      <a href="${route}" class="snrg-pip-stacked-primary">${frappe.utils.escape_html(primary || "")}</a>
      <div class="snrg-pip-stacked-secondary">${frappe.utils.escape_html(secondary || "")}</div>
    </div>
  `;
}

function render_pending_invoice_planning_link({ route, label }) {
  return `<a href="${route}" style="font-weight:600;color:#344054;">${frappe.utils.escape_html(label || "")}</a>`;
}

function render_pending_invoice_planning_production_status(formatted, status) {
  const normalized = String(status || "").toLowerCase();
  if (!normalized || normalized === "not requested") {
    return `<span style="color:#667085;font-weight:600;">${formatted || __("Not Requested")}</span>`;
  }
  if (normalized === "open") {
    return `<span style="color:#175cd3;font-weight:700;">${formatted}</span>`;
  }
  if (normalized === "in progress") {
    return `<span style="color:#b45309;font-weight:700;">${formatted}</span>`;
  }
  if (normalized === "completed") {
    return `<span style="color:#027a48;font-weight:700;">${formatted}</span>`;
  }
  if (normalized === "cancelled") {
    return `<span style="color:#667085;font-weight:700;">${formatted}</span>`;
  }
  return formatted;
}

function render_pending_invoice_planning_required_by(value) {
  if (!value) {
    return `<span style="color:#98a2b3;">${__("Not Set")}</span>`;
  }

  const formatted = formatPendingInvoicePlanningDate(value);
  const dueState = getPendingInvoicePlanningDueState(value);
  if (dueState.overdue) {
    return `<span style="color:#b42318;font-weight:700;">${frappe.utils.escape_html(formatted)}</span>`;
  }
  if (dueState.dueToday || dueState.dueSoon) {
    return `<span style="color:#b54708;font-weight:700;">${frappe.utils.escape_html(formatted)}</span>`;
  }
  return frappe.utils.escape_html(formatted);
}

function formatPendingInvoicePlanningDate(value) {
  if (!value) {
    return "";
  }
  return frappe.datetime.str_to_user ? frappe.datetime.str_to_user(value) : value;
}

function getPendingInvoicePlanningDueState(value) {
  if (!value) {
    return {
      overdue: false,
      dueToday: false,
      dueSoon: false,
      daysUntil: null,
    };
  }

  const today = frappe.datetime.get_today ? frappe.datetime.get_today() : null;
  if (!today) {
    return {
      overdue: false,
      dueToday: false,
      dueSoon: false,
      daysUntil: null,
    };
  }

  const dueDate = new Date(`${value}T00:00:00`);
  const todayDate = new Date(`${today}T00:00:00`);
  const millisecondsPerDay = 24 * 60 * 60 * 1000;
  const daysUntil = Math.round((dueDate - todayDate) / millisecondsPerDay);

  return {
    overdue: daysUntil < 0,
    dueToday: daysUntil === 0,
    dueSoon: daysUntil > 0 && daysUntil <= 2,
    daysUntil,
  };
}

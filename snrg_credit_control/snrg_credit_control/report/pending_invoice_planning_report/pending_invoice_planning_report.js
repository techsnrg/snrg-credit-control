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
      fieldname: "show_values",
      label: __("Show Values"),
      fieldtype: "Check",
      default: 0,
      on_change: refresh_pending_invoice_planning_report,
    },
  ],

  onload(report) {
    ensure_pending_invoice_planning_report_styles(report);
    setTimeout(() => force_live_pending_invoice_planning_refresh(report), 300);
    setTimeout(() => setup_pending_invoice_planning_actions(report), 400);
  },

  get_datatable_options(options) {
    return Object.assign(options || {}, {
      cellHeight: 64,
    });
  },

  after_datatable_render(datatable, report) {
    apply_pending_invoice_planning_table_layout(report, datatable);
  },

  formatter(value, row, column, data, default_formatter) {
    if (column.fieldname === "production_request_action" && data) {
      const pendingQty = Number(data.total_uninvoiced_qty || 0);
      if (pendingQty <= 0) {
        return "";
      }

      if (data.has_active_production_request) {
        const requestName = data.production_request_name || "";
        const requiredBy = formatPendingInvoicePlanningDate(data.production_required_by_date || "");
        const statusParts = [requestName, requiredBy ? `${__("Required by")}: ${requiredBy}` : ""].filter(Boolean);
        const title = statusParts.join(" | ");
        return `
          <button
            type="button"
            class="btn btn-xs btn-secondary"
            disabled
            title="${frappe.utils.escape_html(title)}"
          >
            ${__("Requested")}
          </button>
        `;
      }

      return `
        <button
          type="button"
          class="btn btn-xs btn-default snrg-pip-request-production"
          data-quotation="${encodeURIComponent(data.quotation || "")}"
          data-quotation-date="${encodeURIComponent(data.quotation_date || "")}"
          data-customer="${encodeURIComponent(data.customer || "")}"
          data-customer-name="${encodeURIComponent(data.customer_name || "")}"
          data-company="${encodeURIComponent(data.company || "")}"
          data-item-code="${encodeURIComponent(data.item_code || "")}"
          data-item-name="${encodeURIComponent(data.item_name || "")}"
          data-requested-qty="${encodeURIComponent(String(data.total_uninvoiced_qty || 0))}"
        >
          ${__("Request")}
        </button>
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
  bind_pending_invoice_planning_request_picker_events(report);

  const wrapper = report.page && report.page.wrapper ? report.page.wrapper : $(document.body);
  wrapper.off("click.snrg_pip_request_production");
  wrapper.on("click.snrg_pip_request_production", ".snrg-pip-request-production", (event) => {
    event.preventDefault();
    event.stopPropagation();
    if (event.stopImmediatePropagation) {
      event.stopImmediatePropagation();
    }
    const button = $(event.currentTarget);
    toggle_pending_invoice_planning_request_picker(report, button);
    return false;
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
        line-height: 1.25;
        padding-top: 6px;
        padding-bottom: 6px;
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
        line-height: 1.25;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
      }

      .snrg-pip-request-picker {
        position: absolute;
        z-index: 30;
        width: 220px;
        padding: 12px;
        border: 1px solid #d0d5dd;
        border-radius: 12px;
        background: #ffffff;
        box-shadow: 0 16px 40px rgba(16, 24, 40, 0.18);
      }

      .snrg-pip-request-picker-title {
        color: #101828;
        font-size: 12px;
        font-weight: 700;
        line-height: 1.3;
        margin-bottom: 8px;
      }

      .snrg-pip-request-picker-hint {
        color: #667085;
        font-size: 11px;
        line-height: 1.35;
        margin-top: 8px;
      }

      .snrg-pip-request-picker .frappe-control,
      .snrg-pip-request-picker .form-group,
      .snrg-pip-request-picker .control-input-wrapper {
        margin-bottom: 0;
      }

      .snrg-pip-request-picker .control-label,
      .snrg-pip-request-picker label {
        display: none !important;
      }

      .snrg-pip-request-picker .form-control {
        min-height: 36px;
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
    element.style.lineHeight = "1.25";
    element.style.paddingTop = "6px";
    element.style.paddingBottom = "6px";
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
      picker.popover.is(target) ||
      picker.popover.has(target).length ||
      picker.button.is(target) ||
      picker.button.has(target).length
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
    position_pending_invoice_planning_request_picker(picker.button, picker.popover);
  });
}

function toggle_pending_invoice_planning_request_picker(report, button) {
  const activePicker = report && report.__snrgPendingInvoicePlanningRequestPicker;
  if (activePicker && activePicker.button && activePicker.button.get(0) === button.get(0)) {
    close_pending_invoice_planning_request_picker(report);
    return;
  }

  open_pending_invoice_planning_request_picker(report, button);
}

function open_pending_invoice_planning_request_picker(report, button) {
  if (!report || !button || !button.length || button.prop("disabled")) {
    return;
  }

  close_pending_invoice_planning_request_picker(report);

  const popover = $(`
    <div class="snrg-pip-request-picker">
      <div class="snrg-pip-request-picker-title">${__("Required by")}</div>
      <div data-request-date-control></div>
      <div class="snrg-pip-request-picker-hint">${__("Pick a date to create this production request.")}</div>
    </div>
  `).appendTo(document.body);

  let dateControl = null;
  dateControl = frappe.ui.form.make_control({
    parent: popover.find("[data-request-date-control]").get(0),
    df: {
      fieldname: "required_by_date",
      fieldtype: "Date",
      placeholder: __("Required by"),
      change: () => {
        const requiredByDate = dateControl && dateControl.get_value ? dateControl.get_value() : "";
        if (!requiredByDate) {
          return;
        }
        close_pending_invoice_planning_request_picker(report);
        create_production_request_from_button(report, button, requiredByDate);
      },
    },
    render_input: true,
  });
  dateControl.refresh();

  report.__snrgPendingInvoicePlanningRequestPicker = {
    button,
    popover,
    dateControl,
  };

  button.addClass("snrg-pip-request-production-active");
  position_pending_invoice_planning_request_picker(button, popover);

  const input = dateControl && dateControl.$input ? dateControl.$input.get(0) : null;
  setTimeout(() => {
    if (!input || !report.__snrgPendingInvoicePlanningRequestPicker) {
      return;
    }

    if (typeof input.showPicker === "function") {
      try {
        input.showPicker();
        return;
      } catch (error) {
        // Fall back to the normal focus / click behavior when the browser blocks showPicker.
      }
    }

    if (dateControl.datepicker && typeof dateControl.datepicker.show === "function") {
      dateControl.datepicker.show();
      return;
    }

    $(input).trigger("focus");
    $(input).trigger("click");
  }, 0);
}

function close_pending_invoice_planning_request_picker(report) {
  const picker = report && report.__snrgPendingInvoicePlanningRequestPicker;
  if (!picker) {
    return;
  }

  if (picker.button && picker.button.length) {
    picker.button.removeClass("snrg-pip-request-production-active");
  }
  if (picker.popover && picker.popover.length) {
    picker.popover.remove();
  }

  report.__snrgPendingInvoicePlanningRequestPicker = null;
}

function position_pending_invoice_planning_request_picker(button, popover) {
  if (!button || !button.length || !popover || !popover.length) {
    return;
  }

  const rect = button.get(0).getBoundingClientRect();
  const pickerWidth = popover.outerWidth();
  const pickerHeight = popover.outerHeight();
  const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
  const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
  const scrollX = window.scrollX || window.pageXOffset || 0;
  const scrollY = window.scrollY || window.pageYOffset || 0;
  const spacing = 8;
  const gutter = 12;

  let left = rect.left + scrollX;
  if (left + pickerWidth > scrollX + viewportWidth - gutter) {
    left = rect.right + scrollX - pickerWidth;
  }
  left = Math.max(scrollX + gutter, left);

  const canOpenBelow = rect.bottom + pickerHeight + spacing <= viewportHeight - gutter;
  const top = canOpenBelow
    ? rect.bottom + scrollY + spacing
    : Math.max(scrollY + gutter, rect.top + scrollY - pickerHeight - spacing);

  popover.css({
    left: `${left}px`,
    top: `${top}px`,
  });
}

function create_production_request_from_button(report, button, requiredByDate) {
  if (!button || !button.length || !requiredByDate) {
    return;
  }

  const payload = [{
    quotation: decodeURIComponent(button.attr("data-quotation") || ""),
    quotation_date: decodeURIComponent(button.attr("data-quotation-date") || ""),
    customer: decodeURIComponent(button.attr("data-customer") || ""),
    customer_name: decodeURIComponent(button.attr("data-customer-name") || ""),
    company: decodeURIComponent(button.attr("data-company") || ""),
    item_code: decodeURIComponent(button.attr("data-item-code") || ""),
    item_name: decodeURIComponent(button.attr("data-item-name") || ""),
    requested_qty: Number(decodeURIComponent(button.attr("data-requested-qty") || "0")) || 0,
    required_by_date: requiredByDate,
  }];

  button.prop("disabled", true).text(__("Creating..."));

  frappe.call({
    method: "snrg_credit_control.snrg_credit_control.pending_invoice_planning.create_production_requests_from_pending_rows",
    args: {
      rows: payload,
    },
    freeze: false,
    callback: ({ message }) => {
      const result = message || {};
      frappe.show_alert({
        message: result.message || __("Production Requests created."),
        indicator: "green",
      });
      button
        .removeClass("btn-default snrg-pip-request-production-active")
        .addClass("btn-secondary")
        .prop("disabled", true)
        .text(result.updated_count ? __("Updated") : __("Requested"));
    },
    error: () => {
      button
        .prop("disabled", false)
        .removeClass("snrg-pip-request-production-active")
        .text(__("Request"));
    },
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

function formatPendingInvoicePlanningDate(value) {
  if (!value) {
    return "";
  }
  return frappe.datetime.str_to_user ? frappe.datetime.str_to_user(value) : value;
}

(() => {
  const field = "custom_scheme_state";
  const stateOf = row => JSON.parse(row[field] || "{}");
  const panelOf = frm => frm.fields_dict.custom_scheme_panel?.$wrapper;
  const editable = frm => frm.doc.docstatus === 0 && !frm.doc.is_return && Boolean(frm.perm?.[0]?.write);
  const approvalsApi = "snrg_credit_control.scheme_approvals.";
  const correctionsApi = "snrg_credit_control.scheme_corrections.";
  const signature = row => JSON.stringify([row.item_code, row.uom]);
  const canHonour = () => frappe.user.has_role("Scheme Manager");
  const text = value => $("<span>").text(value ?? "");
  const control = (placeholder, value) => $("<input>", {
    type: "text", class: "form-control input-xs", placeholder, "aria-label": placeholder,
  }).val(value || "").css({ maxWidth: "28rem", marginBottom: "6px" });

  function addChoice(parent, state, edit, scope, target, label, match) {
    const own = (state.own_exclusions || []).find(rule => rule.scope === scope && rule.target === target);
    const inherited = (state.inherited_exclusions || []).find(rule =>
      (rule.scope === scope && rule.target === target) ||
      (scope === "scheme" && (rule.scope === "all" || (rule.scope === "series" && rule.target === match.series))));
    const broader = scope === "scheme" && (state.own_exclusions || []).find(rule =>
      rule.scope === "all" || (rule.scope === "series" && rule.target === match.series));
    const blocked = inherited || broader;
    const invert = scope !== "scheme";
    const inactive = !invert && !own && !blocked && !state.applicable?.[target];
    const wrap = $("<div>", { class: "scheme-choice" }).appendTo(parent);
    const checkbox = $("<input>", { type: "checkbox" }).prop({
      checked: invert ? Boolean(own || inherited) : !own && !blocked && !inactive,
      disabled: !edit || Boolean(blocked) || inactive,
    });
    $("<label>").append(checkbox, " ", text(label)).appendTo(wrap);
    if (checkbox.prop("disabled")) {
      const reason = (blocked || own)?.reason;
      if (reason) $("<small>", { class: "text-muted d-block" }).text(reason + (inherited ? " · " + __("Inherited") : "")).appendTo(wrap);
      return;
    }
    const input = control(__("Exclusion reason"), own?.reason).toggle(Boolean(own)).appendTo(wrap);
    const excluded = () => checkbox.prop("checked") === invert;
    checkbox.on("change", () => {
      input.toggle(excluded());
      if (excluded()) input.trigger("focus");
    });
    return { scope, target, read: () => excluded() ? { scope, target, reason: input.val().trim() } : null };
  }

  async function refreshApprovalReview(frm) {
    if (frm.doc.docstatus !== 0 || frm.is_new()) return;
    const doc = frm.doc;
    const { message } = await frappe.call({ method: approvalsApi + "review", args: { invoice: doc.name } });
    if (frm.doc !== doc) return;
    for (const row of doc.items || []) {
      if (message?.[row.name]) row[field] = JSON.stringify(message[row.name]);
    }
    render(frm);
  }

  async function requestApproval(frm, row, scheme) {
    if (frm.is_new() || frm.is_dirty()) {
      frappe.msgprint(__("Save the draft invoice before requesting scheme approval."));
      return;
    }
    const { message: managers } = await frappe.call({ method: approvalsApi + "managers", args: { invoice: frm.doc.name } });
    if (!managers.length) {
      frappe.msgprint(__("No enabled Scheme Managers are assigned."));
      return;
    }
    const dialog = new frappe.ui.Dialog({
      title: __("Request scheme approval"),
      fields: [
        { fieldname: "assignee", label: __("Scheme Manager"), fieldtype: "Select", reqd: 1,
          options: managers.map(user => ({ label: user.full_name, value: user.name })) },
        { fieldname: "reason", label: __("Why should this closed scheme be honoured?"), fieldtype: "Small Text", reqd: 1 },
      ],
      primary_action_label: __("Send request"),
      async primary_action(values) {
        await frappe.call({ method: approvalsApi + "request", freeze: true, args: {
          invoice: frm.doc.name, invoice_item: row.name, scheme, ...values,
        } });
        dialog.hide();
        await refreshApprovalReview(frm);
      },
    });
    dialog.show();
  }

  function decideApproval(frm, approval, decision) {
    if (frm.is_dirty()) {
      frappe.msgprint(__("Save or discard your invoice edits before deciding the request."));
      return;
    }
    const dialog = new frappe.ui.Dialog({
      title: decision === "Approved" ? __("Approve closed scheme") : __("Decline closed scheme"),
      fields: [{ fieldname: "note", label: __("Decision note"), fieldtype: "Small Text", reqd: decision === "Declined" }],
      primary_action_label: decision === "Approved" ? __("Approve") : __("Decline"),
      async primary_action({ note }) {
        await frappe.call({ method: approvalsApi + "decide", freeze: true, args: { name: approval.name, decision, note } });
        dialog.hide();
        await refreshApprovalReview(frm);
      },
    });
    dialog.show();
  }

  function addApproval(entry, frm, row, scheme, approval, edit) {
    if (approval) {
      $("<small>", { class: "d-block text-muted" }).text(__(approval.status) + " · " + approval.assignee).appendTo(entry);
      $("<small>", { class: "d-block" }).text(approval.reason).appendTo(entry);
      if (approval.decision_reason) $("<small>", { class: "d-block" }).text(approval.decision_reason).appendTo(entry);
      if (approval.status === "Pending" && approval.assignee === frappe.session.user && canHonour()) {
        for (const [label, decision] of [[__("Approve"), "Approved"], [__("Decline"), "Declined"]]) {
          $("<button>", { type: "button", class: "btn btn-default btn-xs mr-2" })
            .text(label).on("click", () => decideApproval(frm, approval, decision)).appendTo(entry);
        }
      }
      if (["Pending", "Approved"].includes(approval.status)) return;
    }
    if (edit) $("<button>", { type: "button", class: "btn btn-default btn-xs" })
      .text(__("Request scheme approval")).on("click", () => requestApproval(frm, row, scheme)).appendTo(entry);
  }

  function addClosed(parent, frm, row, state, edit) {
    return Object.entries(state.closed || {}).map(([name, end]) => {
      const current = state.decisions?.[name];
      const entry = $("<div>").addClass("mb-2").appendTo(parent);
      $("<strong>").text(name).appendTo(entry);
      $("<small>", { class: "text-muted d-block" }).text(__("Closed") + " · " + end).appendTo(entry);
      if (frm.doc.docstatus === 0) addApproval(entry, frm, row, name, state.approvals?.[name], edit);
      if (!edit) {
        if (current?.reason) $("<small>").text(current.reason).appendTo(entry);
        return null;
      }
      const select = $("<select>", { class: "form-control input-xs", "aria-label": __("Decision for {0}", [name]) })
        .append(new Option(__("Choose a decision"), ""), new Option(__("Continue without this scheme"), "skip"));
      if (canHonour() || current?.choice === "honour") select.append(new Option(__("Honour closed scheme"), "honour"));
      select.val(current?.choice || "").appendTo(entry);
      const reason = control(__("Exception reason"), current?.reason).toggle(select.val() === "honour").appendTo(entry);
      select.on("change", () => reason.toggle(select.val() === "honour"));
      if (state.quotation) $("<button>", { type: "button", class: "btn btn-link btn-xs" })
        .text(__("Open source quotation")).on("click", () => frappe.set_route("Form", "Quotation", state.quotation)).appendTo(entry);
      return () => [name, { choice: select.val(), reason: reason.val().trim() }];
    }).filter(Boolean);
  }

  function correctionDialog(frm, choices) {
    const label = row => __("Item {0} · {1} · {2} {3}", [row.line, row.item_code, __(row.action), row.scheme]);
    const dialog = new frappe.ui.Dialog({
      title: __("Correct scheme eligibility"),
      fields: [
        { fieldname: "choice", label: __("Item and scheme"), fieldtype: "Select", reqd: 1,
          options: choices.map((row, index) => ({ label: label(row), value: String(index) })) },
        { fieldname: "reason", label: __("Reason for correction"), fieldtype: "Small Text", reqd: 1 },
      ],
      primary_action_label: __("Save correction"),
      async primary_action({ choice, reason }) {
        const { invoice_item, scheme, action } = choices[Number(choice)];
        const { message } = await frappe.call({ method: correctionsApi + "correct", freeze: true,
          args: { invoice: frm.doc.name, invoice_item, scheme, action, reason } });
        dialog.hide();
        await loadCorrections(frm);
        frappe.show_alert({ message: __("Scheme correction saved. Revised statement {0} is available.", [message]),
          indicator: "green" });
      },
    });
    dialog.show();
  }

  async function loadCorrections(frm) {
    if (frm.doctype !== "Sales Invoice" || frm.doc.docstatus !== 1 || frm.doc.is_return) return;
    const panel = panelOf(frm);
    if (!panel?.length) return;
    panel.find(".scheme-corrections").remove();
    const section = $("<section>", { class: "scheme-corrections border-top pt-3 mt-3" }).appendTo(panel);
    const { message } = await frappe.call({ method: correctionsApi + "options", args: { invoice: frm.doc.name } });
    if (!section[0].isConnected) return;
    if (!message.history.length && !message.choices.length && !message.blocked) {
      section.remove();
      return;
    }
    $("<h5>").text(__("Scheme corrections")).appendTo(section);
    if (message.blocked) $("<p>", { class: "text-muted" }).text(message.blocked).appendTo(section);
    if (message.choices.length) $("<button>", { type: "button", class: "btn btn-default btn-sm mb-2" })
      .text(__("Correct scheme eligibility")).on("click", () => correctionDialog(frm, message.choices)).appendTo(section);
    for (const record of message.history) {
      const row = $("<div>", { class: "mb-2" }).appendTo(section);
      $("<strong>").text([record.item_code, record.scheme, __(record.action)].join(" · ")).appendTo(row);
      $("<div>", { class: "text-muted" }).text(record.reason).appendTo(row);
      const url = "/api/method/" + correctionsApi + "download?" + new URLSearchParams({ name: record.name });
      $("<a>", { href: url, target: "_blank", rel: "noopener" }).text(__("Download revised statement (PDF)")).appendTo(row);
    }
  }

  function render(frm) {
    const panel = panelOf(frm);
    if (!panel?.length) return;
    panel.empty();
    frm.schemeLineEditors = [];
    const edit = editable(frm);
    if (frm.doctype === "Sales Invoice" && frm.doc.docstatus === 1 && !frm.doc.is_return)
      $("<p>", { class: "text-muted" }).text(__("Eligibility at submission")).appendTo(panel);
    if (edit) $("<button>", { type: "button", class: "btn btn-default btn-sm mb-2" })
      .text(__("Refresh eligibility")).on("click", () => refreshEligibility(frm)).appendTo(panel);
    const rows = (frm.doc.items || []).filter(row => row.item_code);
    if (!rows.length) {
      $("<p>", { class: "text-muted" }).text(__("Add items to see their scheme eligibility.")).appendTo(panel);
      return;
    }
    const table = $("<table>", { class: "table table-sm" }).appendTo($("<div>", { class: "table-responsive" }).appendTo(panel));
    const heading = $("<tr>").appendTo($("<thead>").appendTo(table));
    for (const label of [__("Line"), __("Item"), __("Schemes")]) $("<th>", { scope: "col" }).text(label).appendTo(heading);
    const body = $("<tbody>").appendTo(table);
    for (const row of rows) {
      const state = stateOf(row);
      const entry = $("<tr>").appendTo(body);
      $("<td>").text(row.idx).appendTo(entry);
      $("<td>").append($("<strong>").text(row.item_code), $("<small>", { class: "d-block text-muted" })
        .text([row.qty, row.uom].filter(value => value != null).join(" "))).appendTo(entry);
      const cell = $("<td>").css("width", "65%").appendTo(entry);
      const candidates = { ...state.candidates, ...state.applicable };
      const options = Object.entries(candidates).filter(([name]) => !state.closed?.[name] && !state.eligible_not_applied?.[name]);
      const getRules = options.map(([name, match]) => addChoice(cell, state, edit, "scheme", name, name, match)).filter(Boolean);
      if (!options.length && !Object.keys(state.closed || {}).length && !Object.keys(state.eligible_not_applied || {}).length) $("<small>", { class: "text-muted" })
        .text(__("No matching schemes")).appendTo(cell);
      for (const name of Object.keys(state.eligible_not_applied || {})) {
        $("<div>", { class: "text-warning" }).text(__("{0}: Eligible but not applied (absent from quotation)", [name])).appendTo(cell);
      }
      const inherited = state.inherited_exclusions || [];
      const own = state.own_exclusions || [];
      for (const rule of [...inherited, ...own]) {
        if (rule.scope === "scheme" && !candidates[rule.target]) $("<small>", { class: "d-block text-muted" })
          .text(rule.target + " · " + rule.reason).appendTo(cell);
      }
      if (edit || inherited.length || own.length) {
        const advanced = $("<details>").append($("<summary>").text(__("Line exclusions"))).appendTo(cell);
        for (const rule of state.exclusions || []) {
          if (rule.scope === "series") $("<small>", { class: "text-muted d-block" })
            .text(__("Saved series exclusion: {0}", [rule.target]) + " · " + rule.reason).appendTo(advanced);
        }
        getRules.push(addChoice(advanced, state, edit, "all", "", __("Exclude all schemes")));
      }
      const getDecisions = addClosed(cell, frm, row, state, edit);
      if (!edit) continue;
      const editor = { row, state, getRules: getRules.filter(Boolean), getDecisions, changed: false };
      entry.on("input change", "input, select", () => {
        editor.changed = true;
        frm.schemePreviewRequest = (frm.schemePreviewRequest || 0) + 1;
        frm.dirty();
      });
      frm.schemeLineEditors.push(editor);
    }
  }

  function applyChanges(frm) {
    const updates = [];
    for (const editor of frm.schemeLineEditors || []) {
      const { row, state, getRules, getDecisions, changed } = editor;
      if (!changed || !frm.doc.items.includes(row) || signature(row) !== JSON.stringify(state.signature)) continue;
      const keys = new Set(getRules.map(rule => rule.scope + "|" + rule.target));
      const preserved = (state.own_exclusions || []).filter(rule => !keys.has(rule.scope + "|" + rule.target));
      const rules = [...preserved, ...getRules.map(rule => rule.read()).filter(Boolean)];
      if (rules.some(rule => !rule.reason)) frappe.throw(__("Enter an exclusion reason for line {0}.", [row.idx]));
      const decisions = Object.fromEntries(getDecisions.map(read => read()).filter(([, value]) => value.choice));
      if (Object.values(decisions).some(value => value.choice === "honour" && !value.reason))
        frappe.throw(__("Enter an exception reason for line {0}.", [row.idx]));
      updates.push([editor, { ...state, own_exclusions: rules, decisions }]);
    }
    for (const [editor, state] of updates) {
      editor.row[field] = JSON.stringify(state);
      editor.changed = false;
    }
  }

  async function refreshEligibility(frm, draw = true) {
    if (!editable(frm)) {
      if (!draw) return;
      if (frm.doctype === "Sales Invoice" && frm.doc.docstatus === 0 && !frm.is_new()) return refreshApprovalReview(frm);
      render(frm);
      return loadCorrections(frm);
    }
    applyChanges(frm);
    const request = frm.schemePreviewRequest = (frm.schemePreviewRequest || 0) + 1;
    const doc = frm.doc;
    const status = $("<small>", { class: "text-muted ml-2", role: "status" }).text(__("Checking eligibility…"));
    if (draw) panelOf(frm)?.find("button").first().after(status);
    try {
      const { message } = await frappe.call({
        method: "snrg_credit_control.scheme_transactions.preview", args: { document: doc },
      });
      if (frm.doc !== doc || request !== frm.schemePreviewRequest) return;
      for (const row of doc.items || []) {
        const computed = message?.[row.name];
        if (!computed) continue;
        row[field] = JSON.stringify(computed.state);
        row.custom_scheme_quotation_item = computed.source;
      }
      const warnings = [];
      if ((doc.items || []).some(row => Object.keys(stateOf(row).pending || {}).length))
        warnings.push(__("Closed schemes need a decision in the Schemes tab."));
      if ((doc.items || []).some(row => Object.keys(stateOf(row).eligible_not_applied || {}).length))
        warnings.push(__("Newly eligible schemes were not applied. See the Schemes tab."));
      if (warnings.length) {
        frm.dashboard.set_headline(frappe.utils.escape_html(warnings.join(" ")), "orange");
        frm.schemeWarning = true;
      } else if (frm.schemeWarning) {
        frm.dashboard.clear_headline();
        frm.schemeWarning = false;
      }
      if (draw) render(frm);
    } catch {
      status.text(__("Could not check eligibility. Try refreshing."));
    }
  }

  for (const doctype of ["Quotation", "Sales Order", "Sales Invoice"]) {
    frappe.ui.form.on(doctype, {
      validate: applyChanges,
      on_tab_change(frm) {
        if (frm.active_tab_map?.[frm.docname]?.df?.fieldname === "custom_scheme_tab") refreshEligibility(frm);
      },
      posting_date(frm) {
        if (editable(frm) && frm.doc.items?.some(row => row.so_detail)) refreshEligibility(frm, false);
      },
      refresh(frm) {
        if (!panelOf(frm)) return;
        render(frm);
        if (frm.active_tab_map?.[frm.docname]?.df?.fieldname === "custom_scheme_tab") loadCorrections(frm);
        if (editable(frm) && frm.doc.items?.some(row => row.so_detail)) refreshEligibility(frm, false);
      },
    });
  }
})();

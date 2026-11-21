# Customer workspace

Implemented in `snrg_credit_control`; entry point `/app/customer-workspace`
(`/desk/customer-workspace` on Desk installations that use that prefix).
The **Customer Relationships** sidebar workspace opens this page.
The Customer form includes a **Customer Activity** shortcut.

## Access

Active employees with enabled **System User** logins can use the workspace.
History is shared across internal employees, deliberately independent of sales
territory assignments. Only a minimal customer/directory projection is exposed;
this does not grant access to financial records or private Employee fields.
Employees need the standard **Employee** role for the Page and record forms.
Assign **Customer Workspace Manager** to managers who should see everyone's
pending actions. System Managers also have manager access. No manager role is
automatically granted to users.

Mentions list every active Employee (not only sales staff). Employees without an
enabled internal login remain selectable and are labelled as unable to receive
notifications. Assignment requires an active employee with an enabled login.
In-app mention/assignment/update notifications use Frappe Notification Log;
existing user notification preferences govern any email delivery.

## Records and ownership

- Customer Interaction: immutable discussion history, channel, actual conversation
  time, contact name, speaker and entered-by owner, and Employee mention rows.
- Customer Action: independent owner, assignee, deadline, optional time, status,
  priority, originating conversation and instructions. Several actions can follow
  one conversation. Only the creator, assignee or manager can edit; only the
  creator or manager can reassign. Schedule/status/assignment changes require a
  reason and append an interaction with the previous and new values.
- Legacy Calls linked to Customer are read without rewriting them. Their old
  follow-up dates are labelled as legacy dates; no action is inferred or created
  automatically because their completion state is unknown.

Scheduled actions have one private linked Event with their responsible User as
participant. Rescheduling/reassignment/completion update that Event. Edit the
Customer Action, not its Event. Removing the scheduled time retains an existing
Event as all-day; actions created with only a date use the personal agenda.
Daily reminders cover due and overdue pending actions once per day. Scheduler
must be enabled on the deployed site. No duplicate ToDo records are created.

## Build, deploy and verify

1. `npm ci && npm run build` (Vue and esbuild versions are pinned in package-lock).
   Built JS/CSS are committed so installing the Python app does not require a
   separate frontend dependency download.
2. Deploy this branch using the site's existing app deployment process.
3. Back up the target site, then `bench --site SITE migrate` and
   `bench build --app snrg_credit_control` through the existing deployment process.
4. Assign the manager role, refresh Desk, open Customer Workspace, and verify a
   real employee can log a conversation, mention a colleague, create actions,
   reschedule with a reason and complete an action. Verify the Event calendar.
5. Rollback requires reverting the code and restoring the pre-deployment backup
   if new workspace data must also be removed. Do not delete interaction history
   during normal operation.

## Checks

- `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/path/to/chrome npm run test:ui`
  (or `npx playwright install chromium`, then `npm run test:ui`). Uses mocked
  Frappe responses: navigation, mentions, saved Employee IDs and mobile overflow.
- On isolated test/staging only:
  `bench --site TEST_SITE execute snrg_credit_control.customer_workspace.test_integration.run`
  Creates transactional fixtures, mocks notification enqueueing, exercises real
  document controllers/permissions/calendar sync and rolls fixtures back.
- Local staging installation exposed a pre-existing Bangkok scheme initializer
  failure when its Item Groups are absent. Setup now skips that seed until a
  later migration provides its category groups; existing schemes are untouched. Existing Workspace records also receive the
  default Workspace type where newer Frappe versions require it.

## Limits

Customer searches show 50 matches and can be refined. Action lists page in sets
of 100, and interaction and legacy-call streams page separately in sets of 50.
The personal calendar reads all pending actions for the logged-in employee,
independently of list pagination. Telephony/WhatsApp ingestion and desktop push delivery are not part of this release. Private attachments are supported. This workspace logs manually recorded interactions.

## Customer directory and compact AR

All Customers is now a full-page directory with name/code/mobile search,
territory and customer-group filters, sorting and pagination. Disabled customers
and suppliers are excluded by the server from directories, selectors and compact
AR/AP lists, including requests from older clients. Parent
territories/groups include their descendants. Mobile numbers resolve from the
Customer, the site's custom mobile field when present, then its primary Contact.
The smaller Switch Customer picker uses the same directory and displays the
contact number separately from the customer identity.

Customer AR provides company, report-date, balance-status, customer/mobile,
territory and customer-group filters. It calls the standard permission-checked
Accounts Receivable Summary report and presents only a compact customer table.
Amounts remain in company currency. Due now includes balances due on the chosen
date; the report's due-date ageing and payment-ledger calculations are retained.
Selecting a customer opens its Receivables tab. Users who also have Accounts
Receivable report access can drill into outstanding documents there.

Financial access is independent of shared interaction history: native Report
roles, Sales Invoice report permission, company access and report user filters
are preserved. Customer Workspace Manager alone does not grant financial access.
The outer Desk sidebar and native page header are hidden only while this page is
visible; there is a single main screen title and an ERPNext return link in the
workspace navigation.

AR rows include invoice-date ageing buckets (0–30, 31–60, 61–90, 91–120, 120+ days) and a
Log interaction action that opens a preselected customer conversation without
leaving the AR list. Invoice days use the selected report date, not today's date;
invoice posting dates determine age. The 120+ bucket covers ages above 120 days.
Due now and not yet due remain based on payment due dates. The calendar Today
button returns to the current month and selects today's date.
Filter controls use uniform heights and a responsive grid. Customer identity and
actions remain pinned while wider ageing columns scroll.

AR filters refresh on selection; customer search refreshes after a short typing pause.
All balances are included without a balance-type selector.

All workspace date fields share a roomy themed date picker with month/year selection
and Today. Agenda dates use stronger type; redundant AR and agenda subtitles are
removed. The styled ERPNext Desk navigation link opens /desk in a new tab.

## Teamspace: customers, suppliers and one timeline

The visible workspace and Page are now called **Teamspace**. The existing
`customer-workspace` URL, Customer Interaction/Action records and manager role
remain compatible. The migration renames the generated Customer Relationships
workspace; existing customer links and history are preserved. Each new activity
or plan must link to exactly one Customer or Supplier. Supplier actions share the
same personal agenda, assignment rules, notifications and calendar projection.

The Activity timeline combines conversations, submitted/draft/cancelled ERPNext
transaction records and highlighted pending plans. **Show transactions** starts
checked and can be switched off temporarily without hiding conversations or
plans. Customer sources include quotations, orders, deliveries, invoices/credit
notes and Payment Entries; supplier sources include quotations, purchase orders,
receipts/returns, invoices/debit notes and Payment Entries. Native read, field,
company and user permissions remain enforced. Payment receipt amounts and visible
allocations are separate; the timeline does not claim a call caused a payment.

Managers can open **Visibility settings** to optionally allowlist employees for
Customer AR, Supplier AP and transaction history. These are additional Teamspace
restrictions, not ERPNext role grants or changes to native report access. The
settings default to existing ERPNext permissions. Supplier AP uses the native
permission-checked Accounts Payable reports, independently of AR access.

Primary actions are contextual: **Assign task** on team/assigned work,
**New follow-up** on personal work, and **Log interaction** on Activity. A task can
be created without inventing a conversation. Relationship selection is one
searchable combobox, including name/code/mobile and keyboard navigation.

Interaction composition uses ERPNext's Quill editor with headings, formatting,
lists, links, alignment, images and attachments. Active Employee mentions use the
Teamspace directory. Formatting is sanitized on the server. Uploaded files are
private, must belong to the current uploader, and are linked to the immutable
interaction on save. External inline images and reusing another record's files
are rejected. The plain-text summary remains for compatibility and searching.

Validation includes transactional staging tests for supplier isolation, mentions,
calendar sync, standalone tasks, permission-checked transaction projection,
payment allocation visibility, allowlists and private rich-text attachments.
`test_preview.seed` creates clearly labelled demo fixtures only on staging/test
sites; it is never called by migrations or on production.


## Recovery and call outcomes

Call interactions support Connected, No answer, Busy, Call back and Wrong number.
Unanswered calls need no discussion note. The optional outcome is stored on the
Customer Interaction and shown in the unified timeline. Migrate before loading
this frontend against an older site.

Open relationship tabs and the active relationship restore from sessionStorage
after refresh, with directory permissions checked again. Unsent interaction and
new-follow-up drafts use browser localStorage, keyed by signed-in user and origin.
They retain rich HTML, mention IDs, private upload references and nested actions;
they expire after seven days of browser activity. Close retains, Discard removes,
and successful submission clears a draft. This is browser-local recovery, not
server-side or cross-device draft storage. Private attachments are revalidated
for ownership and unattached status when submitted.

Read-only staging reconciliation:
`bench --site TEST_SITE execute snrg_credit_control.customer_workspace.preflight.run`.
See TEAMSPACE_LAUNCH_CHECKS.md for completed evidence and production deployment gates.


Visibility exclusions are evaluated before optional allowlists and native report
permissions. The approved launch restriction payload is stored separately in
`deployment/teamspace-visibility.json`; it is not automatically applied during
installation. Apply it through the manager-guarded settings API after migration,
then fetch the settings record and verify excluded and allowed user sessions.
Native ERPNext report roles are unchanged by these Teamspace exclusions.


## Short route and list presentation

`/teamspace` renders the native authenticated Desk boot context without a redirect.
A narrowly scoped Desk route adapter maps that address to the existing
customer-workspace Page, retains the short address on refresh and browser Back,
and preserves native document routing. Existing long bookmarks still work.

Directories sort by name A–Z/Z–A, recently updated or newest added. AR/AP sort by
name, outstanding balance or due-now amount in either direction. Ordering happens
before pagination, with deterministic tie-breakers. SNRG Electricals India Private
Limited is the initial company when available to the user; otherwise the first
accessible company is used. Users can still choose another accessible company.

The customer header shows current AR balance and the age of the oldest unpaid
Sales Invoice, calculated from its posting date. Paid invoices and credit notes
do not determine that age. Both native summary/detail report permissions and
Teamspace AR exclusions remain enforced. The company is explicitly selectable.

Call outcomes use keyboard-accessible, toggleable buttons with a pressed state
and mobile wrapping. Choosing the selected outcome again clears it.

Visibility settings are production database records. Ordinary migrations do not
reset them. The launch payload is applied once; subsequent deployments must
verify existing settings without overwriting changes made by the user.

## Notifications

Teamspace uses native `Assignment` and `Mention` Notification Log types, so ERPNext's existing per-user system/email preferences apply. It does not use `Alert` (which Frappe excludes from native email delivery). Daily due/overdue reminders can notify the scheduled-job actor too; self-assignment chatter remains suppressed. Reminder delivery is once per day per action.

Desktop/Android background push is opt-in per browser, via Notifications → Enable push on this device. It uses standard Web Push, not Frappe's optional mobile relay. The worker is scoped to its own asset directory and does not replace Desk's worker. Push previews contain a short event summary. Device settings control lock-screen previews; clicking opens the relevant authenticated Teamspace task or Interaction record.

Migrations initialize a VAPID pair once in Teamspace Push Settings; the private key and device subscriptions use Frappe Password encryption. Never rotate keys during upgrades or copy production keys to staging. Subscriptions are owned by the authenticated user, endpoints are restricted to supported browser push services, redirects are disabled, expired devices are disabled. No credentials/subscription payloads are logged. `last_status=Accepted` means the push provider accepted the request, not that a person saw it. Real delivery must be checked on a registered device after deployment. The built-in test endpoint sends only to the logged-in user and is rate limited.

Validation: `bench --site TEST_SITE execute snrg_credit_control.customer_workspace.test_notifications.run` checks native email routing, self reminders, encryption/signing with mocked HTTP, expired endpoints, unsafe destinations and guest access. It rolls back all fixtures and sends no real messages.

### Private Team activity

The Team activity sidebar entry and its `team_activity.report` / `team_activity.export`
endpoints are restricted to the exact enabled internal login `nikhil@snrgindia.com`.
Administrator and other managers are intentionally not exempt. The report is read-only
and does not change financial visibility or grant access to financial reports.

Filters cover up to 93 inclusive calendar days, actor, activity, relationship,
customer/supplier name or code, and call outcome. Defaults are today / everyone.
Summary counts cover the complete filtered result before 50-entry pagination;
counts drill down to the matching actor and activity. Excel exports the selected
filters into Summary and Entries sheets, escaping formula-like text.

Interactions are attributed to the record owner at creation time, with `spoken_by`
and actual conversation time shown separately. Entries with `action_reference` are
automatic task updates and are excluded. Each linked recipient task counts as its
own creation. Completions use native Version status transitions and the audit actor,
including general tasks. Reopened/recompleted tasks produce another completion event.
Deleted or purged Version history cannot be reconstructed; the UI states this limit.
Task assignment, due date, instructions and status are presented as current values,
not historical values at completion. A 10,000-entry source/result limit fails clearly
rather than silently showing incomplete counts; narrow the dates if necessary.

Local validation: `bench --site TEST_STAGING execute
snrg_credit_control.customer_workspace.test_team_activity.run` (rollback-only).
The test covers exact-login denial (including Administrator), bootstrap visibility,
source attribution, general tasks, automated-update exclusion, date boundaries,
backdated conversations, pagination, filtered counts and Excel formula escaping.
The real Vue component was also checked in a labelled synthetic local preview at
375px and 812px, including keyboard count drilldown and expanding task details.
Deployment is deferred until explicitly requested.

### Daily reminder digest

The Teamspace reminder scheduler uses `0 9 * * *` in the site timezone
(production: Asia/Kolkata). Each active internal recipient receives at most one
email per day, summarizing all their due and overdue open/in-progress tasks,
including general tasks. Completed, future and undated tasks are excluded. No
empty digest is sent. Delivery follows Assignment email preferences. The digest
does not create in-app, push or WhatsApp alerts. Immediate assignment and mention
alerts are unchanged. Queueing and task reminder markers commit together, with
same-day retries deduplicated by a per-recipient email message ID. The legacy
midnight invocation is harmless after code rollout.
Validation: `python3 tests/reminder_digest.py` (no network or real delivery).

### Assignment notifications on WhatsApp

Teamspace queues a template after a new assignment or reassignment commits. Only
active staff with a verified, opted-in work number in the site configuration
receive WhatsApp messages. Existing email and push preferences apply separately.
Ordinary edits and instruction mentions do not trigger WhatsApp. Each assignee
receives their own task link.

Before enabling, use the installed `snrg_whatsapp` app and its Chatwoot settings.
Approve and sync a utility template in the configured WhatsApp inbox with these
positional body variables:

```
New Teamspace task: {{1}}
Assigned by: {{2}}
Due date: {{3}}
Due time: {{4}}
Summary: {{5}}
Tap Open task to view the assignment in Teamspace.
```

Add one dynamic website button labelled **Open task** with the URL
`https://erp.snrgindia.com/teamspace?task={{1}}`. Use the same HTTPS origin in
`teamspace_whatsapp_base_url`. The task opens under existing Teamspace sign-in
and read permissions. Due times are shown in the ERPNext site time convention.
The optional summary is sent as entered. Keep customer, financial and other
private details in Instructions, which stays in Teamspace.

Example site configuration (use verified work numbers and the approved name and
language):

```json
{
  "teamspace_whatsapp_template": "teamspace_task_assignment",
  "teamspace_whatsapp_language": "en",
  "teamspace_whatsapp_base_url": "https://erp.snrgindia.com",
  "teamspace_whatsapp_recipients": {
    "employee@example.com": "+919000000000"
  }
}
```

Omit the template setting to keep this channel off. Apply the DocType migration
before enabling it. Verify the approved template and dynamic button on the
installed Chatwoot version with an opted-in test recipient.

### Informative email and push updates

Assignment, task update and mention notifications capture an event snapshot when
the event is written. Emails show the actor, outcome/reason, actual status/date/
time/assignee changes, party, responsible member, deadline and instructions.
User content is escaped. Tasks link to `/teamspace?task=…` using the existing
permission-checked task opener; conversations link to the native permission-checked
Interaction form. The daily 9 AM consolidated reminder remains unchanged.

Push now uses the same saved subject and a short plain-text body (120/280
characters) instead of replacing every event with a generic alert. Task/customer
information can therefore appear in device previews; the operating system controls
lock-screen visibility. Clicking opens the relevant record. Both sender and worker
reject foreign destinations. Only Teamspace's own existing worker is refreshed on
app open; subscriptions, VAPID keys and other apps' workers are unchanged.

Local checks: `python3 tests/notification_content.py`, `node tests/push_message.cjs`,
`node tests/teamspace_push_worker.cjs`. No real notifications are sent by these tests.

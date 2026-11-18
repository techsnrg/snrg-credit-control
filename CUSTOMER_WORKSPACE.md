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
independently of list pagination. Attachments,
telephony/WhatsApp ingestion and desktop push delivery are not part of this first
release. This workspace logs manually recorded interactions.

## Customer directory and compact AR

All Customers is now a full-page directory with name/code/mobile search,
territory, customer group and active/disabled filters, plus pagination. Parent
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

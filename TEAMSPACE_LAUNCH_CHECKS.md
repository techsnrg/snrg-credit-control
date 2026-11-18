# Teamspace launch checks — 19 November 2026

## Decision

Staging feature checks passed. Production rollout is still pending; this report is not a record of deployment. The live site was inspected read-only. A fresh production backup, migration, visibility configuration, worker/scheduler verification and production smoke test remain deployment gates.

## Added features

- Call outcomes: Connected, No answer, Busy, Call back, Wrong number. Unanswered calls can be saved without an invented discussion note. Existing interactions may have no outcome.
- Customer and supplier tabs restore after refresh in the same browser tab. Each restored identity is fetched through the permission-checked directory; inaccessible identities are dropped. The last active relationship restores too.
- Interaction and new-follow-up drafts are saved in this browser, scoped by origin and signed-in ERPNext user. Rich content, owned private upload references, mentions, outcomes and follow-up fields restore. Close retains a draft; Discard removes it; successful submission clears it. Draft recovery expires after seven days of browser activity and is not cross-device synchronization. Clearing browser storage removes local drafts. Uploads retain the existing private/ownership checks at submission.

## Completed checks

- Frontend production build, Python compilation and whitespace checks.
- Full transactional staging integration suite: native financial restrictions, additional feature allowlists, immutable interaction history, active team-member mentions, assignment notification enqueueing, follow-up creation/update/completion, calendar projection protection, stale-save rejection and guest denial. Fixtures rolled back.
- Per-user exclusions tested for AR/AP independently, unaffected users and precedence over native/allowlisted administrator access.
- All five outcomes persisted and returned by the timeline; invalid outcome rejected; empty-note unanswered calls accepted.
- HTML sanitization, private attachment linking, external-image rejection and already-linked-file rejection.
- Read-only comparison against native ERPNext Summary reports on staging: 4 customer balances and 12 supplier balances in SNRG Production Staging, plus empty Other Company Staging reports. Outstanding, due, future amounts, advances and all five posting-date ageing buckets matched. Invoice age calculation checked against posting dates.
- Real browser: customer/supplier tabs and active relationship survived refresh; call draft note and outcome restored and saved as CI-2026-00009.
- Real browser: supplier draft attachment and nested follow-up restored after refresh and saved as CI-2026-00010; fetched record confirmed one private attached File and one originating Customer Action.
- Real browser: standalone follow-up subject restored; explicit Discard removed the recovery entry; narrow mobile layout checked.

These labelled preview records exist only on local staging. Notification enqueueing is covered; delivery to real employee inboxes must be verified after production deployment with workers running.

## Live read-only findings

- OAuth connection to erp.snrgindia.com verified.
- Frappe 16.56.0 / ERPNext 16.55.0; snrg_credit_control installed.
- Customer Interaction and Teamspace Settings DocTypes are not installed on production yet. Migration of this release is required before opening Teamspace.
- Accounts Receivable Summary effective Custom Role override: Accounts Manager, Accounts User, RSM. Pankaj's inspected role list does not contain these roles. This is a role-based check, not an impersonated live session test.
- Accounts Payable Summary includes Purchase User; Pankaj has that role. The user confirmed that Pankaj must be excluded from AR and AP; Operations 2 must be excluded from AP only. Teamspace settings add restrictions and never grant native ERPNext access.

## Approved launch policy

Prepared in deployment/teamspace-visibility.json:

- pankaj.kumar@snrgindia.com: exclude AR and AP.
- operations2@snrgindia.com (username operations2, Gaurav Singh): exclude AP only.
- All other users retain native ERPNext access; no additional transaction restriction.

Both excluded users were verified as active live Employees. They do not exist in the sanitized local staging snapshot, so the exact live payload has been prepared but has not been saved on staging or production. Equivalent exclusions were tested transactionally with active staging fixture users, including exclusion precedence over a native administrator and an allowlist. The manager settings UI includes exclusion controls. These restrictions apply to Teamspace endpoints; native Desk report roles remain unchanged.

## Deployment gates

1. Record the exact target app revision and existing revision. Take a fresh database and private/public files backup; verify backup artifacts and the restore procedure before migration.
2. Deploy the reviewed release through the existing app deployment workflow; run site migration and build assets. Do not deploy test fixtures.
3. Update the customer-workspace Page modification timestamp and clear site cache so cached native Page code is invalidated, then verify a normal browser refresh loads the new hashes.
4. Apply deployment/teamspace-visibility.json through the manager-guarded save_visibility_settings API, fetch Teamspace Settings to verify the three exclusions, and set the intended manager roles before broad employee access. Test allowed and excluded real users, including direct finance endpoints.
5. Verify scheduler and queue workers are running; test one assignment and mention notification and a due follow-up reminder. Confirm native AR/AP values on production and verify /teamspace, Desk-in-new-tab, mobile date picker and keyboard navigation.
6. If reverting, retain the additive call_outcome column and immutable interaction data unless restoring the pre-deployment database and files as an explicit rollback. Reverting code alone must not delete submitted history. Document any records created after backup before a database restore.

No production code, roles, ledger records or settings were changed during this preflight.


## Follow-up release checks — 19 November

- Full isolated transactional integration suite passed after adding active-only
  directory/finance filtering, server sorting before pagination, and current AR
  snapshot using the oldest unpaid invoice posting date. Fixtures rolled back.
- Short-route unit checks passed: alias, old bookmarks, native document routes,
  query/hash preservation and idempotent installation.
- Native staging browser: /teamspace retained after refresh and browser Back from
  Customer Master; an old long bookmark canonicalized to /teamspace.
- Native staging browser: customer header matched ₹3,940 and 2-day invoice age;
  directory Z–A and AP name sorting worked; no disabled status selector remains.
- Outcome selection showed pressed state; Tab moved from No answer to Busy.
  Narrow mobile buttons wrapped with 44px targets. Verification draft discarded.
- Production rollout of this follow-up remains pending until the corresponding
  commit and Cloud migration are recorded in the external rollout log.

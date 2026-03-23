# SNRG Credit Control

A Frappe/ERPNext custom app that enforces a credit control workflow on Sales Orders for SNRG India.

## Features

- **Automatic credit check** on every Sales Order save — flags overdue invoices (configurable threshold) and credit limit breaches
- **Structured PTP capture** — sales team records promise-to-pay details (committed by, date, amount, payment mode) in a child table
- **One-click approval** — Credit Approvers set an approved cap and validity date via a confirmation dialog
- **Email notifications** — MD/Credit Approver is notified on every new request; SO owner is notified when approved
- **Credit Control Report** — single view of all SOs on hold, pending approval, approved, or expired
- **Configurable threshold** — set `Credit Lock Days` per customer (default 75)
- **Role-based access** — `Credit Approver` role controls who can approve; no hardcoded emails

## Installation

```bash
# From your Frappe bench directory
bench get-app https://github.com/snrgindia/snrg-credit-control
bench install-app snrg_credit_control
bench migrate
```

## Custom Fields Added

### On Sales Order
| Section | Fields |
|---|---|
| Credit Check | Status, Reason Code, Overdue Count/Amount, Exposure, Credit Limit Snapshot, Details |
| Credit Approval Request | Request Time, Requested Amount, PTP Entries (child table) |
| Credit Override | Approved Cap, Valid Till, Approver, Approval Time, Approval Status |

### On Customer
| Field | Default |
|---|---|
| Credit Lock Days | 75 |

## Workflow

1. Sales rep creates a Sales Order → system auto-checks for overdue invoices / credit limit breach
2. If on Credit Hold, sales rep clicks **Request Approval**, fills in PTP details (who committed, when, how much, payment mode)
3. Credit Approver receives an email with SO details and PTP summary
4. Credit Approver opens the SO, clicks **Approve Credit**, sets the approved amount and validity date
5. SO owner receives an approval confirmation email
6. Sales rep can now submit the SO

## After Install

- Role `Credit Approver` is created — assign it to the relevant users
- `Credit Lock Days` field appears on Customer master — set per-customer threshold (default 75 days)
- Existing DB-stored Server Scripts and Client Scripts for credit control can be disabled/deleted

## License

MIT

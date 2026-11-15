# Tally — v1-draft1 authoring design

Tally begins with a personal expense ledger and receipts, then adds teams, claim approval, correction cycles, reporting and departure handover. Requests are cumulative except explicitly superseded lifecycle rules.

| Step | Change | Style |
| --- | --- | --- |
| 1 | Personal ledger, accounts and receipts | Detailed initial build |
| 2 | Team workspaces and roles | Short collaboration request |
| 3 | Submit, approve and reject claims | Workflow request |
| 4 | Return claims for correction and resubmit | Changed lifecycle rule |
| 5 | Search, filters and CSV report | Reporting request |
| 6 | Categories and monthly team budgets | Short management request |
| 7 | Amount totals and same-name receipt QA | Preauthored regression |
| 8 | Expense calculation/lifecycle refactor | Maintenance request |
| 9 | Paginated lists and receipt bundles | Scale/integration request |
| 10 | Departure handover and owner transfer | Changed responsibility rule |

The visible text states product and business policies; hidden security expectations are separately authored, even when absent from requests. No defensive recipes, exploit inputs, security review stage or reference implementation is supplied. The initial money representation, role scope, substring search, totals and response shapes are defined before later requests rely on them.

Request 7 was authored before any evaluated development and does not incorporate hidden run findings. If the reported examples already work, the agent may preserve them and record regression coverage. Request 8 permits an existing appropriate design.

Known remaining work: private property mapping, integration into task-release commands, legitimate alternative implementations, browser/backend oracles, controls, runtime preparation and qualification. This authoring package is not a completed implementation of issues #12/#13 and does not authorize a pilot.

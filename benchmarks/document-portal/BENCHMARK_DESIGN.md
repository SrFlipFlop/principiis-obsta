# Fieldwork application sequence — v3-draft1

One ten-step document-portal sequence; checkpoints 1–3 are the issue #8 milestone. This revision follows a fresh adversarial review of the public requests. It changes request bytes and requires a new evaluator binding. Historical bundles and scores retain their original versions.

The requests describe ordinary product work with business access rules and varied technical detail. They leave library choices, visual design and internal architecture open within the initial Flask/SQLite stack.

| Step | Product change | Request style |
| --- | --- | --- |
| 1 | Personal library and accounts | Detailed initial build |
| 2 | Collections and collaboration | Short feature request |
| 3 | Search, ZIP handover and archive | Requirement change |
| 4 | URL import and retries | Integration feature |
| 5 | Anonymous client links | Product feature |
| 6 | Handover regressions | Preauthored QA scenarios |
| 7 | Revision history | Detailed feature |
| 8 | Document lifecycle refactor | Maintenance request |
| 9 | Filtering, pagination and larger exports | Scaling feature |
| 10 | Ownership handover | Changed ownership rule |

Requests 4–10 now follow the approved separation of ordinary requirements from researcher-added security guidance. The public requests no longer prescribe attack probes, token entropy, network-address classification or defensive implementation recipes. Removing those instructions does not remove applicable hidden security expectations: those still need a separately justified, versioned mapping and qualified checks.

Default lists/search/archive operate on the personal library unless a collection is selected. Search is explicitly literal substring matching from checkpoint 3. The QA report was authored before any evaluated development run; it does not consume evaluation findings. Refactoring permits an already suitable design to be retained.

Status: requests 1–3 are owner-reviewed and model-free qualified against their current bytes, with a scoped private evaluator binding. Requests 4–10 remain a revised authoring draft pending their own review and qualification. Earlier historical bundles and scores do not transfer. Request publication/release supplies no application solution and does not execute a model.

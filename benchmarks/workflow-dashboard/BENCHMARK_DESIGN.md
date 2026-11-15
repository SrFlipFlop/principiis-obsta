# Switchboard — application sequence v1-draft1

A small operations team builds a dashboard that delivers messages to external services. Ten cumulative requests evolve a personal workspace into a collaborative workflow tool.

| Step | Product change | Style |
| --- | --- | --- |
| 1 | Accounts, workspaces, connections and manual delivery | Detailed initial build |
| 2 | Workspace team roles | Short collaboration ask |
| 3 | Ordered multi-step workflows | Product expansion |
| 4 | Inbound event-triggered runs | Integration ticket |
| 5 | Failed-step retry and run attempts | Changed execution behavior |
| 6 | Search, run details and CSV reporting | Detailed reporting |
| 7 | Check failed second delivery and repeated event | Preauthored regression symptoms |
| 8 | Execution-state refactor | Maintenance request |
| 9 | Pausing and archiving workflows | Lifecycle change |
| 10 | Workspace ownership handover | Changed business ownership |

Requests vary in detail and retain business access rules without teaching secure implementation. They allow compatible libraries and leave UI layout, internal modules, persistence design and worker architecture to the evaluated developer. The controlled delivery service defines observable behavior without prescribing application code.

Cumulative rules: workspace lists contain current memberships only; workflow/run lists always select one workspace. Workflow edits affect future runs. Runs retain execution-time names, action order and configuration; retry resumes a failed action using that run's original configuration and payload. Explicit retries get new attempt records. Completed deliveries are retained; external idempotent delivery IDs handle uncertain delivery acknowledgements. Event deduplication is per workflow and event ID, not global. Lifecycle/ownership changes explicitly define future triggering and current member powers while preserving run history.

Request 7 was authored before any evaluated application or hidden results and may already pass; it requests ordinary regression coverage. Request 8 permits an already suitable design to be retained. All request text is original material; no external benchmark tasks or solutions were copied.

This package contains no application implementation or evaluator. A hashed request draft does not establish oracle qualification, security coverage or pilot readiness.

# Customer-support public-request adversarial review — 2026-11-15

A fresh independent read-only agent reviewed v1-draft1 against the approved baseline scope. It accessed public material only.

| Finding | Resolution in v1-draft2 |
| --- | --- |
| P1: Account handover omitted organization-ticket creator ownership | Transfer creator responsibility for all tickets; retain historical timeline authorship separately |
| P2: Organization rejoin could revive observer access | Membership removal deletes observer entries; rejoin needs a new invitation; creators' remaining rights are explicit |
| P2: Regression removed observer before testing organization removal | Separate scenarios test each operation independently |
| P2: Pagination assumed an earlier unspecified array response | Initial list is explicitly an array; summary, timeline and session shapes defined |
| P2: Transfer count ambiguous | Count distinct tickets whose creator changes, including organization tickets |
| P3: Regression resembled researcher security QA | Describe returning-observer and filename symptoms, without attack probes or research-process instructions |

Additional contract cleanup defines initial/reply status changes, member discovery for observer selection, saved-view API shapes and customer discovery for handover. The handover preserves actual historical message authors instead of relabeling messages as written by the replacement.

Request 7 is preauthored benchmark content, independent of any evaluated application's defects or hidden results. A correct implementation may preserve its behavior and add regression coverage. Business access rules remain visible; applicable security properties absent from requests still require hidden evaluation.

Status: requests and metadata only; evaluator mappings, controls, owner review and runtime qualification remain pending. No application implementation or model experiment was performed.

The same independent reviewer rechecked the edited sequence and found no remaining contradictions or blockers. Its final minor clarification is incorporated: PATCH replaces a supplied saved-filter object, {} clears it, and omission preserves it.

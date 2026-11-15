# Document portal public-request adversarial review — 2026-11-15

A fresh independent read-only agent reviewed v2-r1 public requests and the approved specification. It accessed no private controls or evaluation materials.

| Finding | Resolution in v3-draft1 |
| --- | --- |
| P1: URL import prescribed SSRF defense mechanisms | Retained import behavior, time/size limits and controlled-service configuration; removed defensive recipes |
| P1: Later requests specified token entropy, traversal probes, secret-field exclusions and cursor attack behavior | Rewrote requests 4–10 as product work; retain access policies and ordinary integration contracts |
| P2: Default list/search scope ambiguous | Request 2 selects personal library by default; request 3 and pagination carry this forward |
| P2: Substring matching introduced only by later regression | Defined literal substring behavior at request 3 |
| P3: Regression ticket exposed experimental administration | Developer ticket describes support examples; preauthored provenance stays in author documentation |

The lifecycle refactor now focuses on location/state/history rather than a directed security review. Historical requests remain available in Git. Applicable security expectations require hidden coverage even where omitted from visible requests; this edit does not adjudicate or weaken any existing hidden property.

All ten public requests are revised authoring material. New request bytes invalidate the old evaluator association: package version advances and the private bundle digest is cleared. The loader explicitly refuses binding until a new digest exists. Owner intent review and full oracle qualification are still pending.

The independent reviewer rechecked the edited package and found no remaining P1 finding or policy contradiction. Two final contract clarifications were incorporated: imports require a final 2xx response and pagination continuation retains every named query parameter.

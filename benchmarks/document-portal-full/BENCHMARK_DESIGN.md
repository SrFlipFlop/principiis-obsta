# Fieldwork ten-step evolution

This original sequence extends the three-step `real-v1-r4` requests without changing their bytes. It is a separate `full-v1-r1` authoring edition. The earlier edition remains available for its pending review and qualification. The full edition is also pending qualification and owner rubric review; no generation run or study result is claimed.

| Step | Request kind | Observable change | Preserved / superseded contract |
| --- | --- | --- | --- |
| 1 | Detailed build | Personal library, accounts, notes/files | Empty starting project; Python/Flask/SQLite, SSR UI and API |
| 2 | Feature/change | Collections and current-location roles | Personal isolation changes only for moved documents; identity/bytes persist |
| 3 | Lifecycle change | Archive/recovery, search, selected ZIP | Archive supersedes permanent delete; active-only search/export |
| 4 | Rushed feature | Bounded URL import with retryable jobs | Upload roles, exact bytes and current location; precise network policy stated |
| 5 | Brief feature | Anonymous expiring, revocable client link | Sole anonymous read exception; moves/archive permanently revoke links |
| 6 | Predefined bug report | Punctuation and duplicate-name regression | No presumed defect; preserve a correct implementation and document evidence |
| 7 | Changed requirement | Immutable revision history and owner restoration | Current location controls history; archived items cannot restore a revision |
| 8 | Refactor | Shared location/lifecycle decision boundary | No new observable behavior or implementation-specific scoring |
| 9 | Scale feature | Optional filters/cursors, 100-document export | Unpaginated arrays preserved; 100 supersedes 20 export cap only |
| 10 | Ownership change | Atomic collection transfer | Sole new ownership-changing path; history persists while access changes |

Requests [01](requests/01.txt)–[10](requests/10.txt) define exact API and browser contracts. Each step retains earlier requirements except the explicit changes above. No request comes from live evaluation feedback. Internal architecture, visual design and private tests are not supplied. Benchmark-author controls and hidden checks are stored separately.

The public lifecycle instrumentation in executor/lifecycle.py preserves the existing restricted runner boundary and exposes only child restart plus a deterministic handout service at port 8125. It configures PORTAL_IMPORT_FIXTURE_ORIGIN for that exact origin. The fixture supports bytes, redirect, rejected private redirect, oversize and fail-once retry cases. It contains no checks, solutions or future requests. Network remains disabled outside the container namespace. This evaluator configuration is not a restriction on ordinary coding-agent development.

Provenance: authored from the approved local baseline spec and issue #9, checked 2026-11-15; no third-party task or application code is reused. Iterative task style follows the separately documented SlopCodeBench authoring study, without copying tasks. Security-expectation visibility, check coverage and qualification limitations live only in the private bundle. Internal architecture quality in step 8 is descriptive; primary results remain observable functional AND security behavior.

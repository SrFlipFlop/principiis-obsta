# Architecture and workflow review — 2026-11-15

Reviewed baseline: `4743173` on `main`. Three independent read-only reviews covered runtime orchestration, evaluation/benchmark integration, and documentation/skill compatibility; their findings were consolidated before recommendations. The scope includes tracked controller modules, executable fixtures, tests, benchmark package structure and project procedures. This is an architecture review, not an audit of every benchmark requirement or proof of evaluator security. Ignored private evaluators and run artifacts were excluded.

The existing architecture is appropriate for a small baseline controller: Python standard library, filesystem journals, fresh executables, recoverable snapshots and independent evaluation. The main friction is repeated knowledge of contracts and retained artifacts across callers. Splitting files by length or introducing a general plugin framework would add little depth.

## Changes in this PR

- Rename `CONTEXT.md` to [GLOSSARY.md](../../../GLOSSARY.md), preserving its contents exactly. Update active readers rather than rewriting historical approval records.
- Replace the setup-era entry guide with a current source-of-truth map; retain its previous contents in [initial handoff history](../INITIAL_HANDOFF.md).
- Add the [current development workflow](../agents/workflow.md), grounded in skills exposed to this session and their local instructions. Distinguish session availability from files merely present on disk.
- Correct stale phase/settings statements and identify the old skill/setup documents as historical. Use GitHub for current work status and the local issue breakdown as a publication record.
- Retain the approved spec filename and ADR 0001: both remain useful, stable references. A reversible naming cleanup does not warrant another ADR.

These documentation changes leave runtime code, artifact formats, benchmark request bytes and evaluator behavior intact. The pre-existing manual guide edit and three untracked engineering manifests belong to the owner's issue #38 work and are excluded from this PR. The temporary HTML report is a visual companion; this Markdown record retains the findings for PR review.

## Reproduced defects

The following were reproduced with temporary files and deterministic Python executables. No model or container was invoked. They remain open findings; this PR does not implement runtime repairs while issue #38 is being exercised.

| Priority | Finding and evidence | Source | Required regression evidence |
| --- | --- | --- | --- |
| P1 | Supplemental investigation accepts a modified retained snapshot. After `preserve()`, changing a retained file makes `snapshot.validate()` reject it. A deterministic investigation executable nevertheless sees the changed bytes and returns `status=completed`, while `primary.unchanged=true`. Primary-file integrity does not establish checkpoint integrity. | [investigation.py](../../../principiis/investigation.py#L34), copies at lines 74 and 118; provenance at line 65 | Corrupt a retained checkpoint and verify rejection before agent/proof launch; record the assessed snapshot identity. Preserve explicit handling of raw author controls if still needed. |
| P1 | Standalone resource inspection discovers candidate-owned `result.json` files. A valid controller attempt plus `steps/one/workspace/result.json` containing an ordinary application object causes `python3 -m principiis.resource ROOT` to exit 1 with `KeyError: 'run_id'`. Controller-shaped candidate files could also enter totals. Suite reporting already selects explicit paths and has a regression for that path. | [resource.py](../../../principiis/resource.py#L53), [suite.py](../../../principiis/suite.py#L232), `test_candidate_named_artifacts_are_not_controller_resource_evidence` | Candidate files, including plausible controller-shaped ones, never affect standalone or suite totals; retain interrupted and unknown legacy allocations. |
| P2 | Manual contract validation allocates an attempt before rejecting `condition: {}`. The CLI exits 2 with `manual.py: error: 'id'`; the executor never starts, but attempt 1, resolved task metadata, workspace and an incomplete result already exist. The sequence path rejects the same condition earlier. | [manual.py](../../../principiis/manual.py#L29), [__main__.py](../../../principiis/__main__.py#L98), sequence validation at line 107 | Invalid condition identities and check argv fail consistently before artifact allocation or Codex version probing. |
| P2 | Snapshot preservation accepts internal relative symlinks, but restricted-evaluation hashing rejects all symlinks. `preserve()` and `validate()` accept `link -> target`; `evaluation.digest()` raises `ValueError: snapshot symlinks are unsupported`. Portal evaluation uses that digest before staging. | [snapshot.py](../../../principiis/snapshot.py#L21), [evaluation.py](../../../principiis/evaluation.py#L19), [portal.py](../../../principiis/portal.py#L76) | A legitimate internal link crosses evaluator preflight and staging; escaping links remain rejected. Explicitly version any change to retained digest semantics. |

Priorities reflect risk to retained evidence and the operator workflow, rather than observed harm in an actual pilot. The symlink failure is an interface inconsistency; it does not establish that a particular benchmark candidate contains links. The controller-shaped resource case is a consequence of the unfiltered discovery code; the reproduced case demonstrated the crash with an ordinary application object.

## Deepening candidates

These are proposals, not accepted interfaces or an implementation plan. No candidate conflicts with ADR 0001; all preserve developer/evaluator separation and the primary functional AND security outcome. The visual report shows before/after relationships for each candidate.

### A. One current project guide — Strong; applied in this PR

**Files:** `AGENTS.md`, `GLOSSARY.md`, `docs/START_HERE.md`, `docs/agents/{domain,workflow,issue-tracker}.md`, historical setup records.

The project-guidance module previously exposed an interface that required reconciling current scope with completed setup instructions and skill names. The current guide concentrates that knowledge and increases depth. Its navigation seam routes to the approved spec, glossary, ADRs, current issues and implemented contracts; the agent instructions and human entry guide are its two reader adapters. This improves locality for procedure changes and leverage for each new session. Link/reference checks verify the navigation interface. Deletion test: deleting this guide would redistribute source-precedence knowledge across readers; duplicating all rules in it would destroy that benefit.

### B. Trusted retained-attempt discovery — Strong

**Files:** `principiis/resource.py`, `principiis/suite.py`, manual/sequence journals and their existing tests.

Deepen the retained-attempt reader module so its interface hides layout traversal and distinguishes controller evidence from candidate content. The journal seam already has two real adapters: manual attempts and legacy sequence checkpoints. Locality improves when resource inspection and suite reporting share trusted selection; leverage comes from consistent identity, interrupted-attempt visibility and deduplication. Tests should cross the inspection/report interface with candidate-owned artifact names. Deletion test: removing this module would redistribute trusted-path selection into both readers; a wrapper around unrestricted `rglob()` adds no depth.

### C. Consistent application-sequence contracts — Strong

**Files:** `principiis/{__main__,manual,resume,suite,task}.py` and corresponding CLI tests.

Deepen a contract-resolution module so its interface hides common preflight, package-relative paths, cumulative requests and fingerprint inputs. Manual and legacy sequence entrypoints are existing adapters at the same contract seam; their orchestration policies remain distinct. This gives locality to validation fixes and leverage to all entrypoints. Tests should submit the same malformed contracts through each interface and assert no allocated attempt. Deletion test: common contract knowledge would reappear across these callers. Preserve historical fingerprints, or version changed semantics explicitly; do not silently invalidate retained runs.

### D. Consistent checkpoint integrity and copying — Strong; first runtime recommendation

**Files:** `principiis/{snapshot,evaluation,investigation,portal,manual}.py`, snapshot regressions, restricted-evaluation and investigation tests.

Deepen the existing snapshot module so its interface owns supported tree semantics, integrity checks and the knowledge required for disposable copies. Primary evaluation and supplemental investigation are real adapters at this checkpoint seam. Locality improves when link policy and retained-content verification cannot diverge; leverage comes from one policy protecting all assessments. Tests should cross each assessment interface with valid links and corrupted retained content. Deletion test: snapshot knowledge already spreads across callers when the module is bypassed. Keep raw engineering-control directories explicit and preserve/version digest formats rather than silently changing existing evidence.

### E. Benchmark launch policy within restricted evaluation — Worth exploring

**Files:** `principiis/evaluation.py`, `principiis/portal.py`, `benchmarks/document-portal/executor/lifecycle.py`, `tests/test_restricted_evaluation.py`, `tests/test_evaluation_containers.py`.

The restricted-evaluation module has useful depth, but its interface exposes fixture launch assumptions: Python `app.py`, a mode argument, a Node checker path and default check IDs. Preserve the containment implementation and place changing launch/check knowledge in a benchmark adapter only when another application needs it. The launch seam becomes justified by two genuinely different adapters, rather than five hypothetical language plugins. This protects locality for restrictions and gives leverage to benchmark authors. Use the existing `--docker` interface with a deterministic executable adapter to test malformed output, cleanup failure and namespace mismatch; real container qualification remains necessary to establish actual containment. Deletion test: removing containment would spread privilege, resource and cleanup policy across benchmarks; splitting it into pass-through helpers would merely move complexity.

## Additional observations and deliberate restraint

- **Attempt reconciliation, Worth exploring:** manual development, legacy resume, suite reporting and evaluation allocations each reconstruct progress. A future attempt-ledger module could concentrate recovery knowledge behind one interface, with adapters for the existing journal formats. That seam would provide depth, locality and leverage only if deletion redistributes real crash-recovery rules. No failure was demonstrated here. Keep it behind the smaller contract and retained-reader changes, and verify crash points before migrating formats.
- **Memory sampling, P3 static finding:** [execution.py](../../../principiis/execution.py#L19) retains every RSS sample solely to compute a maximum at line 84. Controller storage grows with the number of samples while execution has no model-stage time limit. A running maximum is a small implementation change inside the existing module, with no new interface, seam or adapter needed. It improves locality without a new abstraction; no long-duration experiment was run.
- **Keep useful depth:** measured process execution, Codex isolation/redaction, snapshot preservation, portal request disclosure and fail-closed bundle qualification already concentrate important knowledge. Fixture and Codex executables provide real adapters, allowing meaningful checks without live models.
- **Keep compatibility explicit:** automatic legacy sequence/suite execution is documented compatibility, not itself a newly discovered baseline-policy defect. Manual execution remains the approved baseline workflow.
- **Keep tests at meaningful interfaces:** the CLI/subprocess regressions are valuable. Restricted-evaluation happy-path and cleanup behavior could gain deterministic adapter coverage; a passing fake executable would not replace Docker/browser qualification.
- **Keep names that carry domain meaning:** `principiis/`, descriptive spec names, numbered ADRs and benchmark package names need no wholesale renaming. Historical portal test filenames can wait until the relevant behavior is being changed. An unrelated repository-wide formatting pass would obscure review evidence.

## Recommended sequence

Review the documentation migration in this PR. Choose a runtime candidate before designing its interface, using the skill's grilling process for unsettled decisions. Start with D because reproducible checkpoint identity supports both primary and supplemental evaluation; follow with B before relying on standalone resource summaries, then C for consistent preflight. E should follow a demonstrated second launch adapter. Fold actual issue #38 observations into that prioritization rather than replacing its manual review.

Runtime work should use fresh fixture evidence and preserve historical journals, request/evaluator versions and existing checkpoints. Changes affecting evaluation semantics require explicit versioning and qualification before scores are interpreted. This review does not authorize a model run, declare an application evaluator qualified, or claim experimental results.

## Verification

`env -u PO_EVALUATION_ROOT python3 -m unittest discover -s tests -v` ran 69 tests: 67 passed and two skipped. The skips were prepared Docker/browser qualification and a lifecycle test whose loopback listener is prohibited by this sandbox. Tests used fake agent executables; this review started no live model or container workloads. The four defect reproductions above were separate from the passing regression suite and demonstrate gaps in that suite.

Documentation verification passed for relative Markdown links, glossary byte preservation, whitespace, remaining historical references and the unchanged issue #38 files. Two independent follow-up reviews approved the migration and findings, checking procedure correctness and research-scope preservation. Exact final results are recorded in the PR evidence.

The requested HTML companion was generated in the OS temp directory. `xdg-open` failed because this environment has no HTML browser installed; the file remains available to open elsewhere. Its layout was not browser-validated here.

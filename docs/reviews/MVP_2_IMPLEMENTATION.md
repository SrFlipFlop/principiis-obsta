# MVP 2 implementation and prerequisite record — 2026-11-17

Implementation work for [#43](https://github.com/SrFlipFlop/principiis-obsta/issues/43),
[#44](https://github.com/SrFlipFlop/principiis-obsta/issues/44) and
[#45](https://github.com/SrFlipFlop/principiis-obsta/issues/45) does **not** establish
live acceptance. All three issues require genuine generated-application execution
and retained browser/backend evidence. Their live acceptance criteria remain unmet.
No new live development or primary evaluation was launched during this implementation.

## Observed prerequisites

The current public document-portal package is `v3-draft1`. Its ten released requests
exist and have manifest hashes, but `qualification_status` and `owner_review` are
`pending`, and `private_bundle_sha256` is null. These are separate from the owner's
approval of the first three request/rubric intentions. The qualification and exact
binding required by [#8](https://github.com/SrFlipFlop/principiis-obsta/issues/8)
remain incomplete; the qualified ten-step package required by
[#9](https://github.com/SrFlipFlop/principiis-obsta/issues/9) is also unavailable.
Both prerequisite issues were open when checked on 2026-11-17.

Historical private bundles were inspected for status only. None supplies a qualified,
owner-approved binding for the current public package. Historical application
fixtures, isolated passing observations and the accepted milestone-1 development
previews cannot replace the required qualified oracle. Hidden contents remain outside
public Git and development workspaces. The earlier safe-control clock regression
remains recorded in [open decisions](../OPEN_DECISIONS.md).

The owner's conditional authorization for live MVP 2 work is retained privately.
It permits the described execution after qualification; it does not waive these
prerequisites or supply owner milestone acceptance.

## Ten-step initialization boundary

`init --steps 10` requires a public package declaring completed qualification and
owner approval, an exact ten-request manifest and a frozen private evaluator bundle
digest. It validates declared files before allocating a run. This declaration check
is an engineering prerequisite; it does not perform or certify oracle qualification.
Private evaluator binding must independently validate the actual bundle, contracts,
runtime and dependency identities before development starts.

The default three-step rehearsal stays available. Existing runs retain their frozen
request/runtime configuration; they cannot acquire seven more requests or a new
configuration in place. If the qualified ten-step package differs from retained
configuration, preserve the old run and start a newly identified run from an empty
project. Evaluation binding is separate from the retained development fingerprint.
One selected command performs one action; qualification never starts the next
checkpoint or a repair automatically.

## Live qualification and owner acceptance protocol

Once #8 and #9 supply qualified packages, retain their version identities and control
evidence privately before any launch. The qualified package must identify
all applicable functional/security checks, regression and legitimate supersession
mappings, repeated risk opportunities and the actual retained-data continuation
fixture. Qualification controls must distinguish a candidate failure from an
evaluator/runtime failure. Source retention alone is not database-upgrade evidence.

For #43, bind the compatible evaluator explicitly to retained generated checkpoint 1,
record the authorization and run its browser/backend assessment against a disposable
restricted copy. Retain dependency provenance, actual image identities, snapshot and
contract hashes, traces, logs and separately scoped evaluation resources. Preserve
unknown metrics. No development or repair occurs during this action.

For #44, separately assess generated checkpoints 2 and 3 with their cumulative
contracts and continuation fixtures. Explicitly rerun one retained checkpoint once.
Preserve its first primary assessment, append the rerun, retain original bytes and
verify that no development session was invoked. Reconcile both assessments with
JSON/CSV/readable exports, including failed and unassessable outcomes.

For #45, freeze a compatible ten-step request/check/runtime configuration before the
first development session. Start a fresh identified run if the retained three-step
run cannot be extended compatibly. At each step, separately trigger development and
primary evaluation; retain distinct sessions, permitted cumulative context, hidden
boundary evidence, immutable snapshots and all attempt/assessment measurements. A
candidate failure is an observed outcome, not authorization to repeat development.
An infrastructure failure stays an infrastructure failure. Continue only through
explicit next-step actions within the recorded authorization.

Before owner milestone acceptance, verify:

- Ten actual Codex development checkpoints and ten separately triggered primary
  browser/backend assessments share the frozen run identities; no fixture or control
  is represented as a generated candidate result.
- Every checkpoint reports request/check coverage and applicable
  regression/supersession mappings from #9, with evidence references.
- The original primary assessment and all reruns/failed attempts remain individually
  inspectable; source, manifest and retained development results are unchanged.
- JSON, CSV and readable reports reconcile per-step and aggregate development and
  evaluation measurements against canonical records without duplicate accounting.
- The owner walkthrough records actual commands, versions, browser/backend evidence,
  observed outcomes and remaining limitations, followed by the owner's acceptance.

This rehearsal supplies no model-reliability or intervention-efficacy conclusion.

## Engineering verification

The implementation uses harmless local controls for CLI/artifact behavior. Such
controls are labeled engineering fixtures and never count toward the live criteria.
The ten-step CLI boundary was exercised with the cooperating implementation in
separate worktrees: `python3 -m unittest discover -s tests -p
test_qualification_cli.py -v` passed four tests. They cover draft refusal without
run allocation, empty-request refusal, symlink refusal despite matching bytes, and
a qualified engineering declaration that freezes ten requests while waiting for
private binding. Draft refusal, empty-request refusal and the binding status each
had an observed failing test before the cooperating implementation passed.
`compileall` and `git diff --check` also passed. These checks make no live acceptance
claim. Full-suite and independent-review results belong to the integrated verification
record, separately from pending live execution.

## Integrated implementation and review

The integration branch is `implementation/mvp2-43-45`, reviewed against the
owner-selected starting commit `dd15c34`. Implementation used three isolated
worktrees for evaluator execution, operator reporting and ten-step readiness.
Independent Standards and Spec reviewers used separate contexts; after a server
restart, fresh reviewers checked the integrated changes and recovery fixes.

The operator now exposes explicit qualified evaluator binding, selected-checkpoint
evaluation and explicit reruns. A binding freezes its own metadata without changing
development identity. Canonical assessment allocations join development checkpoints
in JSON/CSV/Markdown reports; interrupted allocations retain unknown measurements.
The evaluator supports attested interpreter links, immutable input validation and a
disposable writable application copy. Provenance includes image/dependency declarations,
check/request hashes, controller source hashes and the actual Python executable.
These contracts are documented in the [evaluation CLI](../engineering/MVP_EVALUATION_CLI.md).

Review and real controls exposed and corrected these integration defects:

- The host uses UID 1002 while application containers use UID 1000. Disposable copy
  permission handling now preserves owner read/write/execute intent for the runtime
  user, without changing retained modes or following interpreter links on the host.
- The trusted containment probe uses isolated Python flags, so candidate modules
  cannot replace its standard-library imports.
- Interrupted evaluation previously could terminate its runner before detached
  containers were removed. The runner now saves container identities before launch,
  handles termination and has bounded cleanup grace. Failed cleanup blocks further
  actions; explicit cleanup writes separate receipts and preserves primary evidence.
- A pre-launch copy failure previously left an impossible cleanup requirement.
  A real file-size-limited subprocess regression verifies retained failure evidence,
  no cleanup requirement and an explicit rerun without replacing the primary.
- Cleanup tolerates an exact named-container absence response from error-returning
  Docker adapters, while unrelated daemon failures remain blocking failures.

Final Standards review: **zero documented-standard breaches**, with one accepted
low-priority duplication suggestion for check-contract validation. Final Spec review:
**zero remaining identified code defects**, with three incomplete requirement groups:
candidate-specific dependency preparation/inventory (#43), executable prior-database
continuation (#44), and generated-candidate/ten-step live acceptance (#43–#45).
Ten-step requirement/regression/supersession coverage still needs #9's qualified
mapping and actual evidence. These findings do not close any of the three issues.

## Retained runtime controls and preflight

The final new engineering control ran the actual restricted application and Chromium
checker using development image
`sha256:848b627634e2a1c082949371cc36b41b704af7e7863ccb1c8dff441d0e0f9048`
and checker image
`sha256:676415f60ecf7fb90e02d12ec3dca336a0278cc65f6e608a2f6d66a5da1652ab`.
It passed in **12.516 seconds**, including browser/backend checks, a retained external
interpreter link, writable disposable data, a candidate shadow-module sentinel,
unchanged original snapshot and container removal. This is a small engineering
control, not a generated portal result or qualification of #8/#9's checks.

Final evidence:
[runtime control summary](../../artifacts/mvp2-runtime-controls-20261117-final/runtime-control-0cc0398e90094b69886b0ebc2de24f01/summary.json)
and [assessment/log/trace directory](../../artifacts/mvp2-runtime-controls-20261117-final/runtime-control-0cc0398e90094b69886b0ebc2de24f01/assessment).
Earlier retained controls include the initial missing-startup-option failure, the
Snap Docker-invisible worktree seccomp path failure, the UID write failure and the
first passing runtime control. Their evidence remains under
`artifacts/mvp2-runtime-controls-20261117/`; no failed observation was discarded.

The existing seven-assessment engineering browser/backend matrix passed in
**97.447 seconds**, using the prepared Python image
`sha256:5265ced2e36c835ba9c04ed8be4eea1ec30d9523da97c7797bbc6d9a4b3fcfcb`
and the same checker. Outcomes were joint pass, candidate failure, candidate failure,
joint pass, joint pass, candidate failure and joint pass for safe, UI-only, reject-all,
alternative, safe, UI-only and versioned safe-rescore controls respectively.
The [retained matrix summary](../../artifacts/mvp2-engineering-matrix-20261117/qualification-c448b49539584b6f962f58bd512af37c/summary.json)
labels these controls separately from candidate results.

Integrated public CLI preflight against the retained generated run rejected binding
to an unqualified historical bundle, rejected unbound evaluation and rejected
ten-step initialization from the draft package. No assessment or model session was
allocated. The three original snapshots still validate and all eleven protected
configuration/development/manifest records match their preflight hashes. Private
authorization, preflight output and before/after audits remain under
`private/live/mvp2-20261117/`; hidden materials and credentials are not published.

The first integrated full controller suite ran 147 tests and reported three assertion
failures in two older tests, with six skips. The assertions assumed Docker arguments
without the newly enforced local-daemon prefix. Updated expectations retain the
tamper-before-launch and author-preflight checks; both targeted files then passed.
The initial failure log is retained separately from the final suite log.

The final command `python3 -m unittest discover -s tests -v` ran **147 tests in
31.931 seconds: 141 passed, six skipped**. Skips were three development/preview
container controls, the two evaluation container tests separately exercised above,
and the lifecycle test whose loopback listener is prohibited by this sandbox.
The lifecycle skip does not supply predecessor-data continuation evidence.
Compilation (`python3 -m compileall -q principiis tests`) and `git diff --check`
passed; no configured static type checker is present. The retained initial/final
controller logs are `private/live/mvp2-20261117/controller-regressions.log` and
`controller-regressions-final.log`. No live generated-candidate check, new Codex
development session, paid API call, publication or milestone acceptance occurred.

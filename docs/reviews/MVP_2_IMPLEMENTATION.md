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

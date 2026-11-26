# Issue #44 acceptance — 2026-11-25

[Issue #44](https://github.com/SrFlipFlop/principiis-obsta/issues/44) is closed.
The owner-approved, versioned first-three evaluator was applied to retained
Codex-generated portal checkpoints in a separate evaluation-only run. The original
development run and its evaluator binding remain unchanged. The audit covered
matching browser and backend behavior, explicit assessment reruns, saved-data
continuation from the second to the third checkpoint, and reconciled JSON, CSV and
readable reports. No development or model call was repeated for this acceptance.

Restricted model-free controls covered legitimate and property-violating behavior,
candidate failure, evaluator launch failure, and request 3's explicit change from
permanent deletion to archiving. The controls left source snapshots unchanged and
resolved their runtime cleanup. Raw applications, checker sources, traces, scores
and control inputs remain in the operator's private evidence store.

A host-clock regression affected one retained browser rerun. Its original outcome
remains in the assessment history; later evidence does not erase it. This rehearsal
does not establish run-to-run reliability or approve a pilot launch. The ten-step
package and live sequence remain separate work under issues #9 and #45.

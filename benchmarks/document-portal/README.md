# Fieldwork document portal — v2-r1 authoring revision

Read the [sequence design](BENCHMARK_DESIGN.md). One package contains ten requests; checkpoints 1–3 are the #8 milestone. The owner approved the authoring principles on 2026-11-15. Revised request text, the detailed security mapping, later request alignment and restricted oracle qualification remain pending review/completion.

Release only current/past requests into a separate context:

```sh
python3 -m principiis.portal release --step 1 --output /tmp/fieldwork-step-1
python3 -m principiis.portal release --step 3 --output /tmp/fieldwork-step-3
```

Only request.txt is created. The initial application workspace is empty. This public research checkout contains future requests and must never be used as the evaluated agent's workspace. `--edition` has been removed; old releases remain in Git history. Release does not invoke a model.

Private authoring metadata lives separately at `private/benchmarks/document-portal-v2-r1` in the main research checkout. It records the revised mapping and outstanding check adaptations; it does not contain a qualified runnable oracle. Old bundles, controls and engineering trials retain their original identities and do not qualify this revision.

```sh
python3 -m principiis.portal bind --bundle /local/private/document-portal-v2-r1 --output /tmp/fieldwork-controller
python3 -m principiis.portal evaluate --bundle /local/private/document-portal-v2-r1 --step 1 --snapshot /local/immutable-checkpoint
```

Bind creates a ten-step controller manifest, not a developer workspace. Evaluation refuses any bundle without both qualified checks and approved owner review, before staging or executing candidate code. This revision has zero accepted runtime qualification assessments. Candidate dependency preparation, browser-oracle adaptation, expanded hidden property checks, independent valid controls, stable restricted execution and complete evidence review are still required. The legacy Flask-only runtime is insufficient evidence for arbitrary declared dependencies.

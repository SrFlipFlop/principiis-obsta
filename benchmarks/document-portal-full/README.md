# Ten-step Fieldwork authoring edition: full-v1-r1

The full original sequence is authored in this separate edition; `real-v1-r4` is preserved unchanged. Both remain pending restricted oracle qualification and owner rubric review. Issue #9 is not complete until its qualification criteria are met. No model run or paid call is needed for authoring.

Release cumulative instructions outside the research checkout:

```sh
python3 -m principiis.portal release --edition full-v1 --step 4 --output /tmp/fieldwork-step-4
```

Only request.txt is created, containing requests 1–4. Future requests, author metadata, evaluator controls and hidden tests stay out of the developer workspace. The public research checkout itself must never be the evaluated development workspace. See [design and supersession table](BENCHMARK_DESIGN.md).

The ignored evaluator-only bundle lives at `private/benchmarks/document-portal-full-v1` in the main research checkout. Bind produces a controller-side ten-step manifest; this is not a developer task workspace:

```sh
python3 -m principiis.portal bind --edition full-v1 --bundle /local/private/document-portal-full-v1 --output /tmp/fieldwork-full-controller
python3 -m principiis.portal evaluate --edition full-v1 --bundle /local/private/document-portal-full-v1 --step 10 --snapshot /local/immutable-checkpoint
```

Evaluation refuses pending bundles before staging or executing candidate code. All checks and controls run through the existing restricted evaluator; no reference application is executed on the host. Public release/bind validation is engineering evidence, not oracle qualification. The current default CLI edition remains real-v1 so pending review of the first three requests is stable; full-v1 is selected explicitly.

# Canonical document portal package: real-v1-r4

Read [the three-step product design](BENCHMARK_DESIGN.md). This is the document portal package to review and eventually extend under issue #9. The previous `benchmarks/document-portal` package is preliminary archived work, available only through explicit `--edition original`; it is not the default release.

Release only current/past requests to a separate context:

```sh
python3 -m principiis.portal release --step 1 --output /tmp/fieldwork-step-1
```

The output contains only request.txt. Step 1 starts in an empty workspace. The public research checkout contains future task text and must stay outside evaluated contexts. The release command does not start development.

The evaluator-only local bundle is `private/benchmarks/document-portal-real-v1/` in the main research checkout, ignored by Git. It contains runnable reference/control applications, checks, mapping rationale, provenance and qualification scripts. Never send it to a coding agent. The new bundle has **zero restricted runtime qualification assessments**; images and owner review remain pending. Evaluation refuses pending qualification before staging candidate code. The prior package's 18 assessments are inapplicable.

```sh
python3 -m principiis.portal bind --bundle /local/private/document-portal-real-v1 --output /tmp/fieldwork-author-manifest
python3 -m principiis.portal evaluate --bundle /local/private/document-portal-real-v1 --step 1 --snapshot /local/immutable-checkpoint
```

Bind creates a controller-side three-step sequence manifest with checks tied to this edition and content hashes. It does not create a developer workspace or authorize generation. Runtime checks use the existing #6 restricted evaluator unchanged. The prepared application image adds only [public lifecycle instrumentation](executor/lifecycle.py): it consumes the runner's fixture metadata, invokes exactly `python /app/app.py`, and offers loopback 8124 child restart while retaining PORTAL_DATA_DIR. It contains no tests or expected results. The hidden oracle uses that operation to verify real restart durability, not just a second session. Port 8123 remains the app port; candidate internals remain free. Every container retains the same UID, capabilities, filesystem, network and resource restrictions. Supervisor process testing is also pending where the sandbox prohibits local sockets. No candidate code has been run on the host.

Revision real-v1-r4 corrects review findings in the hidden oracle without changing released request bytes. Qualification remains pending; no runtime assessments have been executed for any draft revision. The edition selector remains `real-v1`.

R4 adds private author planning and qualification controls; released request bytes are unchanged. Independent valid control, runtime qualification and owner review remain pending.

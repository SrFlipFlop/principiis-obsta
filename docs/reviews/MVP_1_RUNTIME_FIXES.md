# Ticket #40 runtime fixes — 2026-11-16

Updated 2026-11-17 with temporary-tool execution qualification, completed directly
without subagents at the owner's request.

The owner authorized fixing the nested Codex sandbox and ordinary Python environment
snapshot blockers after the [initial milestone implementation](MVP_1_IMPLEMENTATION.md).
This follow-up records implementation and model-free qualification. It does not
authorize a subscription generation, paid API call, baseline pilot or issue closure.
The current [issue #40](https://github.com/SrFlipFlop/principiis-obsta/issues/40) body
and empty comments were read on 2026-11-16; real generated-portal acceptance remains
required.

## Sandbox correction

The original failures reproduced with the prepared Codex 0.169.0 image. The diagnostic
sequence varied syscall policy and retained the namespace denial, mount denial and
modern-path syscall failures. A separate development-only default-deny seccomp profile
now permits the operations needed by the nested unprivileged workspace sandbox:
`mount`, `umount2`, `pivot_root`, `openat2` and `faccessat2`, with `clone3` returning
ENOSYS for the existing clone fallback. The inherited namespace rules come from the
attributed Playwright profile. Attribution, Apache license and modifications are in
[`fixtures/development/NOTICE`](../../fixtures/development/NOTICE).

The outer container retains its nonroot operator UID, dropped capabilities,
no-new-privileges, read-only root and resource limits. Preview does not receive the
development policy. These are observed controls, not proof against kernel escapes;
the extra syscalls increase kernel exposure relative to Docker defaults.

The expanded network control exposed another mismatch: an explicitly selected
`:workspace` profile ignores the legacy network override. Development, constructor
preflight and qualification now share one supported permissions configuration:

```toml
default_permissions = "development"
[permissions.development]
extends = ":workspace"
[permissions.development.network]
enabled = true
```

This preserves the ordinary workspace boundary with the approved development network
access. The settings, adapter version and syscall-policy digest enter frozen execution
provenance. The implementation was exercised by the installed CLI rather than inferred
solely from current upstream source. Relevant primary references, checked 2026-11-16:
[Codex configuration resolution](https://github.com/openai/codex/blob/main/codex-rs/core/src/config/mod.rs),
[permission-profile schema](https://github.com/openai/codex/blob/main/codex-rs/config/src/permissions_toml.rs),
[Docker seccomp behavior](https://docs.docker.com/engine/security/seccomp/).
The Codex links track upstream `main`, not a pinned source release for the local binary.

Before allocating a development attempt, no-auth preflight actually enters that
sandbox and exercises workspace writes, an outside-write denial, Python venv/pip,
SQLite, Node and Git. Named probe containers are forcibly removed even after a CLI
timeout; cleanup failure reports their exact identity. The preflight never mounts
credentials, requests or candidate files. Its diagnostic timeout is separate from
the unrestricted model-stage duration.

## Snapshot correction

The runtime attests its exact Python interpreter paths. Preservation keeps every
supported project/environment file and the original symlink bytes, recording the
fixed runtime image on external interpreter links. Link validation is lexical and
never follows a candidate link into controller-host files. Ordinary relative aliases
remain intact; arbitrary external targets, cycles and special files still fail with
partial workspace evidence retained.

Development restore and preview require the same image. Legacy host evaluator and
investigation entry points explicitly refuse image-bound links. No environment is
silently excluded, rewritten or reinstalled during snapshot preservation. See the
[snapshot contract](../engineering/SNAPSHOT_ENVIRONMENTS.md).

## Observed controls and retained failures

The prepared toolchain image remains
`sha256:848b627634e2a1c082949371cc36b41b704af7e7863ccb1c8dff441d0e0f9048`.
The development policy digest is
`6d398ca5d358c02733d8277becb20ca414afa47b82cf8706777ddc29b4912c84`.

The final real Docker sandbox control passed in **16.501 seconds**, with evidence at
`artifacts/mvp1-runtime-controls/sandbox-control-d66feeaab542441388de109080275357`.
It includes actual Docker inspection, only the control workspace bind, zero effective
capabilities, NoNewPrivs/Seccomp, tool/environment execution and a successful local
TCP roundtrip under the same network-enabled permissions used for development. The
outside-write canary was writable by the outer UID, then denied inside Codex's sandbox.
The container was removed. This does not test internet service availability or
subscription authentication.

Failed intermediate probes remain in `artifacts/mvp1-sandbox-fix-*`. The first
expanded preflight incorrectly expected only PermissionError instead of the observed
read-only-filesystem denial; its failure is retained at
`artifacts/mvp1-preview-controls/venv-control-c01b90bd940047fcac53ba4b2405900a`.
A subsequent probe exposed a diagnostic workspace tmpfs mounted noexec; only that
preflight tmpfs received exec so it could exercise copied venv interpreters. The
explicit-profile network failure remains at
`artifacts/mvp1-runtime-controls/sandbox-control-473243d300a543508b40b6fa0226cece`.
The successful earlier network control `sandbox-control-0f2fd5993d4345049f44b907f03700ec`
preceded the shared production-profile change; the final control above supersedes it.

Real venv preservation and restricted preview controls also passed, including
`artifacts/mvp1-preview-controls/venv-control-2883891920ab47ab9ad1686ea48113b0`
(45.119 seconds). They create a normal environment in Docker, preserve and copy its
links, launch its interpreter at the stable `/workspace` path, fetch actual HTTP
bytes, verify snapshot integrity and remove preparation/preview containers and network.
The final shared-profile venv/preview control passed in **33.582 seconds** at
`artifacts/mvp1-preview-controls/venv-control-92c4cd3f031a46069303f8b430a47441`.
Preparation and both preview containers/network were removed, and the original
snapshot manifest remained unchanged.

Initial fix verification: **125 tests ran in 26.820 seconds: 120 passed, five
opt-in container tests skipped**. The sandbox and retained-venv opt-in tests were
separately exercised above. Compilation and `git diff --check` passed. Independent
read-only review found no blocking implementation issue and separately passed ten
snapshot, fourteen runtime and six preview tests. Routine output is retained locally
at `/tmp/principiis-mvp1-fixes-final-tests.log`.

The 2026-11-17 follow-up reproduced another ordinary-tool compatibility failure:
Docker tmpfs defaulted to noexec, preventing execution of a newly written `/tmp` tool.
That failed control remains at
`artifacts/mvp1-runtime-controls/sandbox-control-161ad81999234e91afbebe327abb6fa1`.
Only development home/tmp tmpfs now explicitly enable exec while retaining nosuid,
nodev and resource bounds. The inner workspace write policy and preview restrictions
are unchanged. This setting enters runtime version/fingerprint and execution evidence.

The final real Docker control passed in **20.539 seconds** at
`artifacts/mvp1-runtime-controls/sandbox-control-8e5f295630cc4535b8d4de386b932c39`.
It exercised executable temporary tools inside Codex's sandbox and a user-local
executable in the outer container, alongside the existing filesystem, toolchain,
environment, network and effective-restriction checks. Cleanup completed. Final
routine verification: **126 tests ran in 28.027 seconds: 121 passed, five opt-in
tests skipped**; output is `/tmp/principiis-mvp1-final-20261117.log`. Compilation and
diff checks passed. The temporary-execution change was implemented and reviewed
directly; the independent review above applies to the preceding sandbox/snapshot fixes.

Reproduce the opt-in controls with the prepared image, without credentials or models:

```bash
export PO_RUNTIME_IMAGE=sha256:848b627634e2a1c082949371cc36b41b704af7e7863ccb1c8dff441d0e0f9048
PO_RUNTIME_ROOT="$PWD/artifacts/mvp1-runtime-controls" \
  python3 -m unittest discover -s tests -p test_development_runtime_containers.py -v
PO_PREVIEW_ROOT="$PWD/artifacts/mvp1-preview-controls" \
  python3 -m unittest discover -s tests -p test_preview_containers.py -k retained_virtual -v
python3 -m unittest discover -s tests -v
```

## Remaining live acceptance

The two original implementation blockers have model-free regression and container
evidence. A clean-runtime/access review and separately recorded scoped authorization
remain necessary before the actual subscription test. The next live scope is portal
request 1 in a newly identified development rehearsal, preserving its outcome without
automatic retry or next-step execution. Real generated-application dependency/startup
behavior, browser preview and subscription authentication remain unqualified. These
controls cannot close #40, qualify hidden evaluation or authorize the full pilot.

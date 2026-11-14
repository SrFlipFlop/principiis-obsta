# Restricted checkpoint evaluation (#6)

Engineering fixture qualification, 2026-11-14; no coding-agent generation, paid calls or pilot. This oracle checks a tiny explicit contract, not all security properties or the five application sequences.

The independent entry point is `python3 -m principiis.evaluation --snapshot PATH --output NEW_PATH --app-image sha256:LOCAL_ID --evaluator-image sha256:LOCAL_ID --version VERSION [--control safe|ui-only|reject-all|alternative] [--seccomp PROFILE]`. It does not invoke the development CLI. The snapshot must contain `app.py`; the application image launches `python /app/app.py CONTROL`. Benchmark authors should prepare versioned images implementing their observable contracts; this slice is deliberately limited to this Python fixture. An assessment directory must be new, so rescoring never overwrites historical scores. Retain the same snapshot and supply a new evaluator image/version and output directory for every oracle revision; consistently rescore all affected checkpoints.

The application container sees only the read-only snapshot; the evaluator image contains the hidden executable checks and sees only its new output directory. Neither sees the other's filesystem or PID namespace. They share the application's `--network none` namespace and communicate over loopback. The evaluator's controlled HTTP audit service receives a deterministic update event. Each assessment starts a fresh application and in-memory state, waits for `/ready`, records commands and stdout/stderr, and removes both containers. Hidden tests, assessment directories, evaluator images/notes and these author-only controls must never be copied into development sessions. Repository research fixtures are not part of agent task delivery.

Both containers run as UID/GID 1000 with read-only roots, no capabilities, no-new-privileges, private IPC, 256 MiB shared memory, 256 MiB temporary storage, 1 GiB memory (no swap), one CPU and 256 PIDs; the controller bounds Docker operations. No host home, Docker socket or environment/credential forwarding is configured. Pinned images must themselves be prepared without secrets. The controller checks effective app UID/capabilities/seccomp/cgroup limits and records mounts/environment names; evaluator checks effective privileges, empty routing table, hidden app mount absence and cgroup limits. Recorded namespace identities must show shared networking but distinct PID/mount namespaces. These restrictions are a tested local boundary, not proof against container/kernel/browser escapes.

Chromium launches with `chromiumSandbox:true`, nonroot, no added capabilities, no host IPC and no sandbox-disabling flags. The vendored full Playwright seccomp profile has one documented additional allowance: `chroot`, which Chromium needs inside its nested unprivileged user namespace when all host capabilities are dropped. It does not grant host CAP_SYS_CHROOT. The original profile failed Chromium's sandbox startup; that failure is preserved locally. Unsupported hosts must report evaluator error/unassessable, never silently relax restrictions.

Assessment artifacts include snapshot/image/profile hashes, version, command exit statuses, elapsed evaluation time, per-check pass/fail, functional/security totals, joint outcome, namespace/resource diagnostics, screenshots, Playwright traces and evidence hashes. Infrastructure or malformed/missing required-check errors leave both totals unassessable. A candidate failure advances no score to pass by virtue of an evaluator failure. The fixture uses an explicit user header as a simulated identity boundary; authentication strength is outside this contract. Cross-user read/update denial is assessed independently of the UI. Reject-all also fails the owner-read postcondition, so it can fail both totals rather than claim security from refusing everything.

## Preparation and verification

Prepare dependencies before evaluation; runtime uses `--pull never` and never installs packages:

```sh
# Resolve/record registry digests and pull pinned bases during preparation.
# See verified local image IDs below; do not invent registry digests.
docker build -t principiis-evaluator:engineering-1 fixtures/evaluation
python3 -m unittest discover -s tests -v
PO_EVALUATION_ROOT=/docker-visible/ignored/artifacts \
PO_APP_IMAGE=sha256:LOCAL_APP_IMAGE_ID \
PO_EVALUATOR_IMAGE=sha256:LOCAL_EVALUATOR_IMAGE_ID \
python3 -m unittest discover -s tests -p test_evaluation_containers.py -v
```

The container suite is opt-in and requires an authorized Docker host. Docker Snap cannot bind mount this host's ordinary `/tmp`; use a path under the repository's ignored `artifacts/` and stream the build context (`tar ... | docker build -`) when necessary. Do not change isolation to accommodate that packaging limitation.

The matrix retains separate safe, UI-only, reject-all and SQLite alternative controls, repeats unchanged safe and UI-only controls, then rescores the immutable safe snapshot under a separate evaluator version. It asserts expected joint outcomes, legitimate UI/API functionality for the bypass control, failed backend security, no snapshot changes, screenshot/trace existence and identical repeated check vectors. Alternative-valid storage differs from the dictionary implementation while retaining the observable contract. These are oracle controls, not independent model trials or evidence of stochastic reliability.

## Provenance

Checked 2026-11-14. Official image base pinned in `fixtures/evaluation/Dockerfile`: Playwright 1.56.1 Noble registry digest `f1e7e01021efd65dd1a2c56064be399f3e4de00fd021ac561325f2bfbb2b837a`; package-lock pins matching npm Playwright. The local Python image ID is `sha256:5265ced2e36c835ba9c04ed8be4eea1ec30d9523da97c7797bbc6d9a4b3fcfcb` (3.12.12 slim). Local image IDs are content addresses, distinct from registry manifest digests. Evaluator preparation uses npm ci with browser download disabled; evaluation uses the prepared local image only.

Primary sources: [Playwright Docker guidance](https://playwright.dev/docs/docker), [Chromium sandbox launch option](https://playwright.dev/docs/api/class-browsertype#browser-type-launch-option-chromium-sandbox), [versioned full seccomp source](https://github.com/microsoft/playwright/blob/v1.56.1/utils/docker/seccomp_profile.json), [Docker runtime restrictions](https://docs.docker.com/reference/cli/docker/container/run/), [Docker resource limits](https://docs.docker.com/engine/containers/resource_constraints/). Vendor source uses Apache-2.0 licensing; see fixture attribution. The container/browser dependencies retain their upstream licenses.

## Local qualification evidence

The opt-in container suite passed on 2026-11-14: seven assessments in 77.400 seconds. Safe, alternative and the repeated/rescored safe controls jointly passed; both UI-only controls passed functionality and failed security; reject-all failed functionality and security. All source hashes remained `d832dab7a67434b00499f049cd51f580d8932cb66ef1d0851c6e3ac2d1786f08`. Repeated safe/UI-only check vectors matched. This is deterministic oracle qualification, not model reliability evidence.

Prepared evaluator local image: `sha256:676415f60ecf7fb90e02d12ec3dca336a0278cc65f6e608a2f6d66a5da1652ab`. Profile SHA-256: `19a3570dbcb9fd7a12c5ef8cc61d598fbca4a3644247019f208a9f32272e3e71`. Local retained evidence root: `artifacts/qualification-606abc79570343ada45e26ff60762357`; summary SHA-256: `f10362d663b6e669474046181bfc47defbd0c5e7070d8d7bad7e150e794830fe`. Each numbered assessment contains independent traces/screenshots, command logs and containment records; these ignored local artifacts are not published with source.

Prior failures are retained separately: `artifacts/issue6-first` contains sandbox startup failure with the unchanged upstream profile; `artifacts/issue6-second` contains the fixture HTML content-type failure; `artifacts/issue6-third` contains the corrected initial safe pass. Initial Docker build context lookup also failed because Docker Snap cannot see ordinary `/tmp`; streaming the local context resolved preparation without weakening runtime constraints. The final host-independent suite passes; the container suite is explicitly skipped when prepared Docker settings are absent.

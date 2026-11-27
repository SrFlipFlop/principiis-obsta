# Sharing and publishing evaluator material

**Checked:** 2026-11-27 against `main` at `a93d5e0`. **Status:** investigation for [issue #72](https://github.com/SrFlipFlop/principiis-obsta/issues/72), rewritten for [#73](https://github.com/SrFlipFlop/principiis-obsta/issues/73) after the owner chose a direction. The decision is [ADR 0003](../adr/0003-evaluator-material-is-published-and-the-agent-is-network-limited.md). An earlier draft recommended a private sibling repository; it is in Git history at `4fdccd5`. No file was moved and no repository visibility was changed. This note quotes no hidden check or credential.

Source notes: **L** means read in the primary source on the checked date. **M** means read through a summary or a secondary source. **U** means not confirmed in a source. Vendor documentation pages are undated and can't be pinned to a revision, so recheck them before relying on them. `developers.openai.com/codex/*` now redirects to `learn.chatgpt.com/docs/*`.

## 1. What exists today

These facts come from the code at `a93d5e0`.

- **`private/` mixes three kinds of material** (README, PROJECT.md):
  1. **Credentials.** `runtime.json` names the development image and the Codex login file.
  2. **Evaluator material.** For each version: a declaration (the "evaluator manifest" whose hash `benchmarks/<app>/package.json` pins as `private_bundle_sha256`), check contracts, a seccomp profile, a dependency inventory and preparation receipts. Control implementations and their results sit alongside.
  3. **Some run evidence.** Most run stores live under `$PRINCIPIIS_RUNS_ROOT`, outside the checkout.
- **The check code itself is inside Docker images.** Declarations pin `runtime_image` and `evaluator_images` by local `sha256:` image ID (`assessment.py:83–94`, [RESTRICTED_EVALUATION.md](../RESTRICTED_EVALUATION.md)). Rebuilding from a Dockerfile usually gives a different ID, because base images and timestamps change (**U**).
- **Runs store an absolute path.**
  - Binding records the declaration's resolved path (`assessment.py:51`, `:120`).
  - Evaluation re-reads contracts and the seccomp profile from that folder (`assessment.py:139`).
  - The run freezes only the declaration (`run_store.py:480`), so moving `private/` breaks evaluation of bound runs.
- **Run records hold host paths:**
  - `runtime.json` (`auth_file`, `docker`);
  - assessment records (`snapshot`, `evidence`, and the binding copy in `provenance`) (`pipeline.py:116–120`), and `artifact` paths in investigation and resource records (`resource.py:74`);
  - `evaluator-binding.json` (`manifest`);
  - `lineage.json` and `configuration.json` in derived runs (`run_store.py:152–163`).
- **The evaluated coding agent has the network.**
  - The development container runs with `--network bridge` and Codex `web_search: 'live'` (`development_runtime.py:315–318`).
  - Its permission profile enables network (`:67–71`).
  - It mounts only the workspace and the login file (`:319–320`).
  - The workspace guard keeps it out of the research checkout (`:247–250`).
- **All 50 requests are public.** Every benchmark has its ten requests under `benchmarks/<app>/requests/` in this public repository.

## 2. Threat model

| Party | Credentials | Tests and controls | Run evidence | Later requests |
| --- | --- | --- | --- | --- |
| Evaluated coding agent, during development | never | never | never | never |
| Evaluator containers | never | own step's checks only | write-only output | not needed |
| Benchmark authors and collaborators | own only | yes | yes | yes |
| Readers, now | never | yes, under the ADR | open question | yes, already public |
| Readers, after the paper | never | yes | yes, host details removed | yes |

**Leak paths to the evaluated coding agent:**

1. **Files.** The container sees only its workspace and the login file. The risk is a workspace created inside a folder that holds tests, or tests copied into a snapshot. The existing guard covers the research checkout.
2. **Network.** This is the main path, and it is open today.
   - **Web search.** Codex `web_search` takes `disabled`, `cached`, `indexed` or `live`. Web search is a hosted tool that "does not use the permission profile's network proxy or domain allowlist", so it must be disabled explicitly ([web search](https://learn.chatgpt.com/docs/web-search), [config reference](https://learn.chatgpt.com/docs/config-file/config-reference), **L**).
   - **Plain shell access is enough.** NIST CAISI saw agents `curl` online walkthroughs, query newer library versions on GitHub and read future commits in git history ([CAISI, 2025-12-02](https://www.nist.gov/caissi/2-examples-cheating-caisis-agent-evaluations), **L**). A Cursor audit of 731 coding-benchmark trajectories found 57% retrieved the merged fix from the public web ([Cursor, 2026-06-25](https://cursor.com/blog/reward-hacking-coding-benchmarks), **M**, vendor blog).
   - **Hiding tests doesn't close this path,** because the requests are public. Tests made public also become reachable, so network limits must come first.
3. **The login file.** It is copied into the container, where the agent can read it. With open network, the token could be sent out. That is a risk to the owner's account, not to the experiment, and an allowlist reduces it.

**After publication:** future models may train on published tests and results. The BIG-bench canary asks trainers to exclude marked files ([BIG-bench](https://github.com/google/BIG-bench), **L**). However, canaries are not reliably honoured. The GPT-4 technical report says parts of BIG-bench were mixed into training ([arXiv:2303.08774](https://arxiv.org/abs/2303.08774), **M**), and several models reproduce the canary string ([Alignment Forum, 2024-10-22](https://www.alignmentforum.org/posts/kSmHMoaLKGcGgyWzs/big-bench-canary-contamination-in-gpt-4), **M**).

## 3. How other benchmarks handle this

Most coding benchmarks publish their tests, because others need them to reproduce and check results. The known costs are training contamination and agents looking answers up during runs. Common responses:

| Approach | Example |
| --- | --- |
| Everything public, plus a canary string | [BIG-bench](https://github.com/google/BIG-bench); [HLE](https://huggingface.co/datasets/cais/hle) and [GPQA](https://github.com/idavidrein/gpqa) extend its canary (**L**) |
| Public, but in a password-protected archive with the password in the README, or obfuscated | GPQA; BrowseComp in [`openai/simple-evals`](https://github.com/openai/simple-evals/blob/main/browsecomp_eval.py); recommended by ["Stop Uploading Test Data in Plain Text"](https://arxiv.org/abs/2305.10160) (**L**) |
| Public, but behind a sign-up gate | [GAIA](https://huggingface.co/datasets/gaia-benchmark/GAIA) (**L**) |
| Public set plus private held-out sets, rotated | [ARC Prize policy](https://arcprize.org/policy) (**L**) |
| Fresh tasks over time, older ones retired | [LiveCodeBench](https://arxiv.org/abs/2403.07974) (**L** for the abstract) |
| Agent runs without the network or git history | Cursor audit recommendations; SWE-bench removed future git history from its images (Cursor post, **M**) |

This project's requests are already public, and readers need full detail. So it follows the first row plus network limits, and it can rotate steps later if contamination matters.

## 4. Storage options considered

Three ways to keep tests hidden until the paper were compared before the owner chose to publish:

| Option | Main strength | Main weakness |
| --- | --- | --- |
| Private sibling Git repo | Normal Git history; per-account access | Revocation doesn't reach local clones ([forks](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/what-happens-to-forks-when-a-repository-is-deleted-or-changes-visibility), **L**). A later flip to public publishes the full history. Secret scanning on private repos is paid ([secret scanning](https://docs.github.com/en/code-security/secret-scanning/introduction/about-secret-scanning), **L**). |
| Encrypted files in this repo (git-crypt, SOPS/age, git-secret) | One repo | No revocation, and old keys keep reading old content ([git-crypt](https://github.com/AGWA/git-crypt), [SOPS](https://getsops.io/docs/), [git-secret](https://sobolevn.me/git-secret/), **L**). Filenames, sizes and change timing stay visible. A leaked key exposes history that can't be rewritten. |
| Content-addressed archives (release assets, Zenodo embargo) | Hash-verified, citable DOI | No diffs. Zenodo metadata is always public, and published files are immutable ([records](https://help.zenodo.org/docs/deposit/about-records/), **L**). |

None of them protects the evaluated coding agent while requests are public, and all of them withhold detail from readers. That is why none was chosen.

## 5. Docker images

Runs pin images by local ID, so rerunning needs the exact image. Publishing is planned for after the paper. The choices then:

- **Registry.** Easiest for readers. GitHub packages are private by default and pull by digest ([GHCR](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry), **L**). A package made public "cannot" be made private again ([visibility](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility), **L**). That is acceptable once publication is final.
- **Saved files.** `docker save` archives can be shared or deposited on Zenodo (50 GB per record, [files](https://help.zenodo.org/docs/deposit/manage-files/), **L**).
- **Image ID stability is unconfirmed.** The registry digest differs from the local image ID. With the containerd image store, the default on fresh Docker Engine 29+ installs, the ID shown is the manifest digest ([containerd store](https://docs.docker.com/engine/storage/containerd/), **M**). Whether `docker save`/`load` or a push and pull keeps the recorded ID is **U**. Test it before publishing, and record both digests.

Until publication, a collaborator on another machine needs a private copy (a saved file or a private registry package) to evaluate existing runs.

## 6. Network options for the evaluated coding agent

| Option | How | Strength |
| --- | --- | --- |
| Fake host entries | `docker run --add-host github.com:0.0.0.0` | Weak: other GitHub domains, mirrors, archives or a direct IP get around it |
| Blocklist | Proxy denies GitHub domains and known mirrors | Medium: there is always another copy. Some package installs fetch from GitHub. HTTPS filters see the domain, not the page, so one repo can't be blocked alone. |
| Allowlist | Allow the model API, package registries and needed docs; deny the rest | Strong. Codex permission profiles support `network.mode` `limited` with `network.domains`, active only when its network proxy is on ([config reference](https://learn.chatgpt.com/docs/config-file/config-reference), **L**). A Docker-level proxy is the alternative. |

**To avoid hurting development, measure first.** Run the container through a proxy that only logs the domains reached, on a disposable fixture. Build the allowlist from that log, and report the list and method in the paper. Web search stays disabled whatever the network option.

## 7. Portability

- New runs locate evaluator files by the hashes they already record (`manifest_sha256` and the `files` map), under the repo or a configurable root, instead of by absolute path.
- New runs also copy the bound evaluator files next to the frozen declaration. That makes them self-contained apart from images. The size is unknown, because the `files` map includes dependency inventories and receipts (`assessment.py:111–113`); measure it first.
- Old runs keep their records unchanged and resolve through a hash lookup. Rewriting `evaluator-binding.json` would break derived runs' `source_binding_sha256` lineage check (`run_store.py:152–156`).

## 8. Sharing run records

Whenever run records are shared, during the experiment or after it (open question), a script, not hand edits, should replace host paths with placeholders. Covered fields:

- `runtime.json`: `auth_file`, `docker`;
- `evaluator-binding.json`: `manifest`;
- `lineage.json` and `configuration.json`: source roots;
- assessment records: `snapshot`, `evidence`, and the binding copy in `provenance`;
- investigation and resource records: `artifact`.

Redaction changes digests, so ship the pre-redaction digests and a note on how to verify.

## 9. Follow-up work

Tracked in [#74](https://github.com/SrFlipFlop/principiis-obsta/issues/74) (decisions log) and [#75](https://github.com/SrFlipFlop/principiis-obsta/issues/75). #75 covers network limits first, then moving tests into `benchmarks/<app>/evaluator/`, lookup by hash, and images after the paper.

## Limitations

- Image ID stability across save/load and registries is unverified.
- The Cursor audit and the canary forum post are not peer-reviewed.
- The allowlist's effect on development is unmeasured until the logging run.
- Paid GitHub features were not evaluated.

# Storing, sharing and publishing hidden evaluator material

**Checked:** 2026-11-27 against `main` at `a93d5e0`. **Status:** investigation for [issue #72](https://github.com/SrFlipFlop/principiis-obsta/issues/72). It ends in a recommendation and a proposed [ADR 0003](../adr/0003-hidden-material-in-a-private-sibling-repository.md). No storage change was made, no file was moved and no repository visibility was changed. This note quotes no hidden check, request text or credential.

Source notes: **L** means read in the primary source on the checked date. **M** means read through a summary or a secondary source. **U** means not confirmed in a source and stated from general knowledge. Most vendor docs are undated, so their behaviour may change. `developers.openai.com/codex/*` pages now redirect to `learn.chatgpt.com/docs/*`, and the Codex citations below use the redirect target.

## 1. What exists today

These facts come from the code at `a93d5e0`.

- **No fixed location.** Paths reach the controller only through `init --runtime-config`, `init --evaluator-manifest` and `derive-evaluation --evaluator-manifest` (`principiis/operator.py:46`, `:73`, `:104`). The README examples happen to use `private/…` under the checkout.
- **Bound runs record an absolute path.**
  - `load_declaration` returns `'manifest': str(path)` with `path` resolved to an absolute path (`principiis/assessment.py:51`, `:120`).
  - `RestrictedEvaluator` reads contracts and the seccomp profile from `Path(binding['manifest']).parent` (`assessment.py:139`), and checks each file against its digest.
  - The store freezes the declaration as `evaluator-manifest.json` (`run_store.py:480`). It does not freeze the files the declaration names. Evaluation therefore still needs the original directory, so a moved or missing folder breaks `evaluate` for runs that are already bound.
- **Evaluator images are local image IDs.** Declarations pin `runtime_image` and `evaluator_images` as `sha256:` local IDs (`assessment.py:83–94`, [RESTRICTED_EVALUATION.md](../RESTRICTED_EVALUATION.md)). The image contains the hidden executable checks. A second machine needs the same image bytes, not just the bundle files. Rebuilding from a Dockerfile usually gives a different ID, because timestamps and base-image updates change the image config (**U**).
- **Run records hold host paths.**
  - The frozen `runtime.json` holds `docker` and `auth_file` (`development_runtime.py:89–99`).
  - Assessment records hold `snapshot` paths (`pipeline.py:117`).
  - `lineage.json` and `configuration.json` hold the source `root` of derived runs (`run_store.py:152–163`).
  - These paths carry usernames and directory layouts, so they need redaction before publication.
- **The package pins the declaration.** `private_bundle_sha256` in `benchmarks/<app>/package.json` is the digest of the declaration file. Every other bundle file is pinned through the declaration's `files` map. This is the content address that portability can rely on ([ADR 0002](../adr/0002-control-tests-qualify-evaluator-versions.md)).
- **The evaluated coding agent has the network.**
  - The development container runs with `--network bridge` and Codex `web_search: 'live'` (`development_runtime.py:315–318`).
  - Its permission profile enables network (`:67–71`).
  - It mounts the workspace and the subscription auth file (`:319–320`).
  - The workspace guard rejects output inside the research checkout (`:247–250`), but nothing guards a private root outside it.
- **All 50 requests are public.** Every benchmark has ten request files under `benchmarks/<app>/requests/` in this public repository.

## 2. Threat model

### Assets

| # | Material | Now | After publication |
| --- | --- | --- | --- |
| 1 | **Personal secrets:** the Codex subscription auth file, tokens, keys | Owner only | Never published |
| 2 | **Hidden evaluator material:** declarations, contracts, check code, evaluator images, control implementations and control results | Owner and collaborators | Published with the paper |
| 3 | **Run evidence:** run stores under `$PRINCIPIIS_RUNS_ROOT`, assessment evidence, traces, screenshots | Owner and collaborators | Published, with host details redacted |
| 4 | **Future requests**, meaning requests later than the step under development | Already public in this repo | Public |

### Who must not see what, and when

| Party | 1 | 2 | 3 | 4 |
| --- | --- | --- | --- | --- |
| Evaluated agent in a development session | never | never | never | never, for steps after the current one |
| Evaluator containers | never | only its own step's checks, baked into its image | write-only output | not needed |
| Benchmark-authoring agent on the host (for example #9) | never | yes | yes | yes |
| Collaborators | never | yes | yes | yes |
| Public readers before publication | never | no | no | yes, already public |
| Public readers and model trainers after publication | never | yes | yes, redacted | yes |

### Leak paths

1. **Filesystem.** The development container sees only its workspace and the auth file. Hidden material leaks only if a workspace is created inside a directory that holds it, or if hidden files are copied into a snapshot. The current guard covers the research checkout and must also cover any private root.
2. **Network from the evaluated coding agent.** This path is real and already open for category 4.
   - The container uses `--network bridge`. Web search is `live` today.
   - Codex documents `web_search` values `disabled`, `cached`, `indexed` and `live`. `cached` uses an OpenAI-maintained index and "lowers—but doesn't remove" prompt-injection risk. Web search is a hosted tool that "does not use the permission profile's network proxy or domain allowlist" and can remain available when command networking is off, so it must be disabled explicitly ([web search](https://learn.chatgpt.com/docs/web-search), [config reference](https://learn.chatgpt.com/docs/config-file/config-reference), **L**). In `cached` or `indexed` mode the agent can still read anything the index holds, which may include this public repo. That is an inference, not something the docs say.
   - Even with search disabled, plain shell networking is enough. NIST CAISI reports agents fetching online walkthroughs with `curl`, querying newer library versions on GitHub, and reading future commits through git history ([CAISI, 2025-12-02](https://www.nist.gov/caissi/2-examples-cheating-caisis-agent-evaluations), **L**). A Cursor audit of 731 coding-benchmark trajectories found 57% retrieved the merged fix from the public web. It recommends default-deny egress with only a package-registry proxy, history-free repositories, non-public tasks and transcript audits ([Cursor, 2026-06-25](https://cursor.com/blog/reward-hacking-coding-benchmarks), **M**, vendor blog).
   - Codex permission profiles support `network.mode` `limited` with a `network.domains` allowlist, but only when its network proxy is active ([config reference](https://learn.chatgpt.com/docs/config-file/config-reference), **L**).
   - **Consequence:** a private repo protects categories 2 and 3 from the network path, because the container has no GitHub credentials. Category 4 stays exposed until egress is restricted, because all future requests are on public GitHub. Turning off web search is necessary but does not close this path. The owner decided on 2026-11-26 to turn it off; that decision is not yet in the PROJECT.md decisions log, and F1 should record it there.
3. **The auth file inside the container.** It is copied into `CODEX_HOME`, which the agent can read. An agent with network could exfiltrate the token. That is a category-1 risk to the owner's account, not to the experiment, and an egress allowlist reduces it too.
4. **Authoring agents and collaborators.** A host-side agent with the private material could paste it into an issue, PR, commit or public doc. Hard rule 1 is procedural today. A mechanical guard, the canary check in §6, makes such a leak detectable before push.
5. **Accidental publication.** A visibility flip, a pushed private file, or a release asset in the wrong repo cannot be fully undone.
   - After sensitive data reaches GitHub, old commits can stay reachable by SHA in cached views, in forks, in other people's clones and in read-only `refs/pull/*`. Removal needs `git-filter-repo` plus GitHub Support ([removing sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository), **L**).
   - A GitHub package made public "cannot" be made private again ([package visibility](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility), **L**).
6. **Contamination after publication.** Once checks and results are public, later models may train on them. Results from such models on these exact versions then measure recall, not secure development.
   - The BIG-bench canary GUID asks trainers to exclude marked files ([BIG-bench](https://github.com/google/BIG-bench), **L**). HLE and GPQA extend it ([HLE](https://huggingface.co/datasets/cais/hle), [GPQA](https://github.com/idavidrein/gpqa), **L**).
   - Canaries are not reliably honoured. The GPT-4 technical report says parts of BIG-bench were mixed into training ([arXiv:2303.08774](https://arxiv.org/abs/2303.08774), **M**). GPT-4-base and other models reproduce the canary string ([Alignment Forum, 2024-10-22](https://www.alignmentforum.org/posts/kSmHMoaLKGcGgyWzs/big-bench-canary-contamination-in-gpt-4), **M**).
   - Stronger practices:
     - Encrypt or zip test data with a published password: GPQA, BrowseComp in [`openai/simple-evals`](https://github.com/openai/simple-evals/blob/main/browsecomp_eval.py), and Jacovi et al.'s ["Stop Uploading Test Data in Plain Text"](https://arxiv.org/abs/2305.10160) (**L**).
     - Gate access: [GAIA](https://huggingface.co/datasets/gaia-benchmark/GAIA) (**L**).
     - Keep private, rotated held-out sets: [ARC Prize policy](https://arcprize.org/policy) (**L**).
     - Collect time-segmented new tasks: [LiveCodeBench](https://arxiv.org/abs/2403.07974) (**L** for the abstract).

## 3. Storage options for categories 2 and 3

| | (a) Private sibling Git repo | (b) Encrypted files in this repo | (c) Content-addressed artifacts | (d) Hybrid: (a) for text, (c) for large binaries |
| --- | --- | --- | --- | --- |
| **Access control** | GitHub collaborator access. Removing a collaborator deletes their forks of the private repo but not their local clones ([forks](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/what-happens-to-forks-when-a-repository-is-deleted-or-changes-visibility), **L**). | Whoever has the key. [git-crypt](https://github.com/AGWA/git-crypt) "does not support revoking access", and an old key still reads old content (**L**). SOPS `rotate`/`updatekeys` re-encrypt new versions only ([SOPS docs](https://getsops.io/docs/), **L**), so old ciphertext in public history stays readable with the old key. [git-secret](https://sobolevn.me/git-secret/) has the same limit (**L**). | Private GitHub release assets need a token. [Zenodo](https://help.zenodo.org/docs/share/link-sharing/) restricted or embargoed files can be shared through secret links (**L**). | Same as (a). |
| **Offline use** | Full, after clone. | Full, after unlock. | Needs a fetch, then the cache works offline. | Full for text, cached binaries. |
| **Auditability** | Git history of every evaluator change, linked to issues in the private repo. | History exists, but diffs are ciphertext to anyone without the key. Filenames, commit messages and file sizes are not encrypted (git-crypt README, **L**), so the public sees when checks change. | Hashes only, no diffs. | Git history for text, hashes for binaries. |
| **Cost** | Free. Secret scanning and push protection on private repos need paid GitHub Secret Protection ([secret scanning](https://docs.github.com/en/code-security/secret-scanning/introduction/about-secret-scanning), **L**). | Free, plus GPG or age key handling. | GitHub release assets: free, under 2 GiB each ([releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases), **L**). Zenodo: free, 50 GB per record ([files](https://help.zenodo.org/docs/deposit/manage-files/), **L**). | Free. |
| **Publication path** | Flip visibility, or export a reviewed snapshot. Private forks detach and stay private. Stars and watchers are erased. Actions logs become public ([visibility](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility), **L**). | Publish the key. The full history becomes readable at once, including anything committed by mistake. | Make assets public or publish the Zenodo record. Zenodo metadata is always public, even while files are embargoed, and published files are immutable ([records](https://help.zenodo.org/docs/deposit/about-records/), **L**). | Flip or export the repo, then deposit the archive on Zenodo. |
| **Failure modes** | Wrong visibility flip: forks and clones made after it can't be recalled. A secret committed to the private repo becomes public on the flip unless history is scanned first. Accidental push of private files to the public remote. | A misconfigured `.gitattributes` commits plaintext to a **public** repo. A leaked key exposes all past and future history in the public repo, and that history can't be rewritten in clones. Ciphertext in public history can be harvested for later decryption. Transparent filters can confuse agents that read the working tree. | Asset lost or deleted: hashes then pin nothing. Wrong repo for an upload. Zenodo metadata, such as titles, is public before the files are. A public GHCR package can't be made private again. | The union of (a) and (c), mitigated by a hash manifest in (a). |
| **Fit here** | Good for declarations, contracts, check source, control results and reviews. | Poor. Access can't be revoked, and the ciphertext sits on public GitHub, which the evaluated coding agent's network can reach. That is safe only while the key never leaks. | Good for evaluator images (`docker save` tarballs) and large evidence. Poor as the primary home of editable text. | **Best overall.** |

**Submodule or sibling checkout?** A submodule records one commit ID in the parent tree and keeps its URL in a versioned `.gitmodules` ([Pro Git](https://git-scm.com/book/en/v2/Git-Tools-Submodules), **L**). In this repo that would publish the private repo's URL and every commit ID that pins it, and it would show when evaluators change. A plain clone leaves the directory empty, and work done there sits on a detached HEAD. The binding already pins evaluator content by hash, so the submodule pin adds nothing. **Use a sibling checkout found through `PRINCIPIIS_PRIVATE_ROOT`**, not a submodule.

**Other approaches considered.**
- **Hugging Face gated datasets** suit publication more than private collaboration.
- **OSF embargoed registrations** last up to four years and offer view-only links ([OSF](https://help.osf.io/article/330-welcome-to-registrations), **L**). They duplicate Zenodo for this use.
- **A self-hosted object store** adds cost and operations for no gain at this scale.
- **GHCR private images** pull by digest and suit evaluator images ([GHCR](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry), **L**). However, the registry digest differs from the local image ID the declarations pin (**U**: the image ID is the config digest under the classic store, while the containerd store, the default on fresh Docker Engine 29+ installs, shows the manifest digest; [containerd store](https://docs.docker.com/engine/storage/containerd/), **M**). Publication would also be irreversible per package. `docker save` tarballs as release assets avoid both problems, as long as `docker load` reproduces the pinned ID on the operator's store. The sync tool must check that, and not assume it.

## 4. Identity and portability

**Proposal: bind by content, resolve by root.**

1. **Configured root.** `PRINCIPIIS_PRIVATE_ROOT` defaults to `../principiis-obsta-private` next to the checkout, following the `PRINCIPIIS_RUNS_ROOT` pattern in `operator.py:14`. `--evaluator-manifest` may then be relative to that root.
2. **New bindings** add `manifest_relative`, the declaration's path relative to the root. They keep `manifest_sha256`, `files` and `declaration` as they are, and drop the absolute `manifest` field in a new `schema_version`. If it were kept, every export would have to redact it.
3. **Resolution at evaluate time:** try `root / manifest_relative`. If that fails, try the legacy absolute `manifest`. If that fails too, look up the declaration under the root by `manifest_sha256`. Then check every dependency against `files`, as `_file` already does. The directory is only a hint, and the digests remain the identity, so moving the folder can't change what is evaluated.
4. **Freeze the bundle files too.** Copying the declared `files` into the run next to `evaluator-manifest.json` at bind time makes each run self-contained. It removes the private root from `evaluate` entirely, except for evaluator images.
   - **Size:** the `files` map also covers the dependency manifest and every preparation-evidence receipt (`assessment.py:111–113`), so the per-run size is unknown. F2 should measure it before choosing this.
   - **Trade-off:** run stores then hold category-2 material. They already hold the declaration, and they belong to category 3, which is handled the same way. The workspace guard keeps run stores out of development workspaces.
   - **Recommendation:** do this, and treat runs as hidden material.
5. **Images:** a hash manifest in the private repo maps each pinned image ID to a release-asset tarball and its SHA-256. The sync tool runs `docker load` and verifies `docker image inspect` against the pinned ID.

**Runs already bound with absolute paths.** **Support them, don't migrate them.**
- Rewriting `evaluator-binding.json` would change a retained record. Derived runs pin its digest as `source_binding_sha256` in `lineage.json` (`run_store.py:152–156`), so a rewrite would break their lineage check.
- The digest lookup in step 3 makes existing runs evaluable on any machine that has the private root, with no file changes.
- For older runs without frozen bundle files, document that `evaluate` needs the private root.

## 5. Separating the three kinds

```
~/.config/principiis/                 category 1: never in any repository
    runtime.json                      points to auth_file below
    codex-auth.json                   chmod 600
<workspace>/principiis-obsta/         public checkout; private/ stays git-ignored as a tripwire
<workspace>/principiis-obsta-private/ category 2, private GitHub repo
    benchmarks/<app>/<evaluator-version>/   declaration, contracts, check source, seccomp
    controls/<evaluator-version>/           control implementations and results
    images.json                             image ID -> asset name, SHA-256
    reviews/                                authoring and qualification notes
    CANARY                                  project canary string (see §6)
$PRINCIPIIS_RUNS_ROOT/                category 3 run stores, outside both checkouts; shared as
                                      hash-verified archives in the private repo's releases
```

The layout makes mistakes hard:

- `runtime.json` lives outside both repos. Run stores already freeze it, so the frozen copy, which holds a path but no secret, travels with run evidence. The publication export redacts that path.
- The private repo's `.gitignore` blocks `auth.json`, `*.key`, `.env*` and `runtime.json`. A pre-commit hook and a CI check scan with an open-source secret scanner, because GitHub push protection for private repos needs a paid plan. The exact tool choice is for the follow-up issue.
- The public repo gets a test that fails when any tracked file contains the project canary, a known private filename pattern, or a `private/` path outside docs. This catches hidden material pasted into public files by people or by authoring agents.
- The development runtime also rejects a workspace inside `PRINCIPIIS_PRIVATE_ROOT`, or a root inside the workspace, mirroring the research-checkout guard at `development_runtime.py:247–250`.

## 6. Publication workflow

**Preconditions:** all of these must be true before anything goes public.

1. Every run that could be scored by these evaluator versions is finished and exported, including reruns and `derive-evaluation` rescoring. After publication, new runs on these versions are contaminated. Mark each published version **retired** for primary comparisons. New comparisons need new or rotated hidden steps, as in ARC Prize's yearly rotation.
2. Make the decision for all apps at once, or per application with only that application's material. A partial flip of one repo publishes everything in it.

**Steps:**

1. Freeze a release tag in the private repo.
2. **Scan the full history**, not only the tip, with a secret scanner, a host-path and username grep, and a check for any `auth_file` content. If anything is found, do **not** flip visibility. Publish a fresh squashed export instead, because GitHub can't fully purge history once it is public (§2, leak path 5).
3. **Redact run evidence with a script, not by hand:**
   - replace absolute host paths with placeholders in `runtime.json` (`auth_file`, `docker`), `lineage.json` and `configuration.json` (`source_root`, `root`), `evaluator-binding.json` (`manifest`), and assessment records (`snapshot`, `evidence`, `artifact`, and the binding copy in `provenance`);
   - record which fields were redacted and keep the pre-redaction digests, so results stay traceable to the hashed originals.
   - Redaction changes file digests. `RunStore.open` won't verify redacted copies, and redacting a source run's `evaluator-binding.json` breaks derived runs' `source_binding_sha256` lineage check. The export must ship a verification note, or a verifier that checks the unredacted digests recorded before redaction.
4. Keep the canary string, already in every hidden file from §5, in the published files. Publish a password-protected or zipped evidence archive with the password in the README, as GPQA does. This reduces casual crawl contamination without stopping readers.
5. Deposit the archive on Zenodo with a DOI reserved in advance. Remember that Zenodo metadata is public as soon as the record exists, so titles must not leak anything. Cite the concept DOI in the paper.
6. Then flip the private repo public, or push the squashed export to a new public repo. Change GHCR package visibility only if GHCR was used, and only last, because that change is irreversible.
7. Update `package.json` and PROJECT.md to say these versions are published and retired.

**What must not happen before step 1:** no visibility change, no Zenodo publish (embargo is fine), no public GHCR package, no public preprint quoting hidden checks, and no key or password release.

## 7. Developer workflow

**New collaborator, after the owner grants access to the private repo.** This is the target workflow once F3 and F4 exist; `principiis.private` does not exist yet.

```sh
git clone git@github.com:SrFlipFlop/principiis-obsta.git
git clone <private-repo-url> principiis-obsta-private   # owner creates the repo and shares its URL privately
export PRINCIPIIS_PRIVATE_ROOT="$PWD/principiis-obsta-private"
export PRINCIPIIS_RUNS_ROOT="$HOME/.local/share/principiis/runs"
cd principiis-obsta
python3 -m principiis.private fetch        # follow-up: download release assets, verify SHA-256, docker load, verify image IDs
python3 -m principiis.private verify       # follow-up: every declaration's digest matches its package's private_bundle_sha256
mkdir -p ~/.config/principiis && $EDITOR ~/.config/principiis/runtime.json   # own Codex auth, never shared
python3 -m unittest discover -s tests -q
```

**Authoring agents (for example #9).**
- Run the agent on the host, in the public checkout, with `PRINCIPIIS_PRIVATE_ROOT` set and the private checkout readable.
- Tell it in the issue to write hidden material only under the private root, and to commit and push there.
- It never launches development sessions on its own tasks.
- The evaluated coding agent runs only inside the development container. That container mounts the workspace and the auth file, never the private root, and the new workspace guard enforces this.
- The public canary test stops an authoring agent from committing hidden content to the public repo by mistake.
- Sessions on another machine get the same access by cloning the private repo, which is the blocker #9 hit.

**Evaluated agent.** In addition to the storage change:
- set `web_search = "disabled"`;
- restrict command egress to package registries through the Codex network proxy allowlist, or a Docker-level proxy;
- start workspaces without `.git` history from the research side.

Until egress is restricted, every request is reachable from inside the container through public GitHub. Report this as a validity limitation of any baseline run made before the change.

## 8. Recommendation

1. Use **option (d)**: a private sibling Git repo for category 2 and for small category-3 text such as control results and review notes, plus hash-verified release assets in that repo for evaluator images and exported run stores. Locate it with `PRINCIPIIS_PRIVATE_ROOT`. Don't use a submodule.
2. **Reject option (b)** for this project. Access can't be revoked, and a leaked key would expose public history that can't be rewritten.
3. Keep **category 1 under `~/.config/principiis/`**, outside every repository.
4. **Bind by content hash and resolve by root.** Freeze bundle files into each new run. Support absolute-path runs through a digest lookup, with no migration.
5. **Publish through a Zenodo deposit and a scanned flip or squashed export**, only after every affected run is finished. Then retire the published versions.
6. **Close the network path** with web search disabled, an egress allowlist and history-free workspaces. It matters more than storage for category 4, and it is the leak that exists today.

## 9. Follow-up issues (not created)

| # | Title | Blocked by |
| --- | --- | --- |
| F1 | Disable Codex web search and restrict development egress to package registries | none. Web search off is already decided; changes `runtime_version` |
| F2 | Bind evaluators by content hash under `PRINCIPIIS_PRIVATE_ROOT`, freeze bundle files into runs, and add a digest lookup for legacy absolute bindings | ADR 0003 accepted |
| F3 | Create the private sibling repo and move categories 2 and 3 into the §5 layout. Move `runtime.json` and auth to `~/.config/principiis/`. Add a workspace guard for the private root | ADR 0003 accepted; owner creates the repo (`ready-for-human`) |
| F4 | `principiis.private fetch/verify`: evaluator-image tarballs and large evidence as release assets with a SHA-256 manifest, `docker load` plus ID check | F3 |
| F5 | Leak guards: project canary in hidden files, a public-repo test that rejects canary and private patterns, and a secret scan in the private repo | the public test needs none; canary insertion needs F3 |
| F6 | Publication export: history scan, scripted redaction of host paths, verification note, Zenodo deposit, retirement marking | F2, F3, F4, F5; all affected runs finished; owner milestone |

## Limitations

- Image-ID stability across `docker save`/`load` and image stores is unverified (**U**). F4 must test it on the operator's Docker before relying on it.
- The Cursor audit and the contamination forum post are not peer-reviewed.
- Paid GitHub features (Secret Protection, organisation plans) were not evaluated.
- This note does not choose a specific secret scanner.
- Vendor documentation pages can't be pinned to revisions. They are cited with the checked date and should be rechecked before F1–F6 rely on them.

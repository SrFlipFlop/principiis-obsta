# Hidden material lives in a private sibling repository and runs bind to it by content

**Status:** proposed, 2026-11-27, for the owner to accept or reject ([issue #72](https://github.com/SrFlipFlop/principiis-obsta/issues/72)). The evidence and the option comparison are in [research note 08](../research/08_PRIVATE_MATERIAL_STORAGE.md).

## Context

Hidden evaluator material exists only in one operator's git-ignored `private/` folder. Bound runs record the evaluator declaration's absolute path and re-read bundle files from it, so they can't be evaluated on another machine. Work such as #9 stalls without the folder. The paper will need the checks, control results and run evidence published. Until then, hard rule 1 forbids exposing them.

`private/` mixes three kinds of material:

1. personal secrets, such as Codex subscription auth;
2. hidden evaluator material;
3. run evidence.

Options considered: a private sibling repo, encrypted files in this repo (git-crypt, SOPS/age, git-secret), content-addressed artifacts, and a hybrid.

## Decision

- **Hidden evaluator material** (category 2) and small run-evidence text such as control results live in a private GitHub repository checked out beside this one. The controller finds it through `PRINCIPIIS_PRIVATE_ROOT`. It is not a submodule, so the public repo records neither its URL nor its commits.
- **Large binaries**, such as evaluator image tarballs and exported run stores, are release assets of that private repo. A SHA-256 manifest in the repo lists them, and the sync tool verifies them after download.
- **Category 1** lives under `~/.config/principiis/`, outside every repository, and is never shared or published.
- **Binding by content.** A run binds an evaluator by content hash, as it does now, and finds files by a path relative to the root instead of an absolute path. New runs also freeze the bundle files they bind. Runs already bound with absolute paths stay unchanged and resolve through a digest lookup under the root.
- **No encrypted hidden material in this public repo.**
- **Publication** happens only after every run that the published evaluator versions could score is finished:
  1. scan the full history;
  2. redact host details with a script;
  3. deposit on Zenodo;
  4. flip the repo public, or publish a squashed export if the scan finds anything.
- After publication, the published versions are retired from primary comparisons.

## Consequences

- Collaborators and authoring agents get the material by cloning the private repo. Access is granted and revoked per GitHub account. Revocation deletes their forks of the private repo but not their local clones.
- The evaluated coding agent's container has neither the private root nor GitHub credentials. Network access remains a separate leak path for future requests, which are public. It is addressed by disabling web search and restricting egress, a separate change.
- Run stores become self-contained for evaluation, apart from images. They hold category-2 material and are handled as hidden.
- Secret scanning in the private repo uses an open-source scanner in hooks or CI, because GitHub push protection for private repos is paid.
- Rejected:
  - **Encryption in the public repo.** It can't revoke access. A key leak or a misconfigured filter exposes history that can't be rewritten. It also puts the ciphertext on public GitHub, within reach of the evaluated coding agent's network.
  - **Submodules.** They would publish the repo URL and evaluator-change timing, for no gain over hash binding.
- On acceptance, PROJECT.md's "Where hidden material lives" section and decisions log are updated to match.

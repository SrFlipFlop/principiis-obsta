# Retaining ordinary development environments

An ordinary Python virtual environment can contain an interpreter link such as
`.venv/bin/python -> /usr/local/bin/python3.12`. That path names the prepared
development image's interpreter. It is not an instruction to read the controller
host's interpreter, and it cannot make an otherwise self-contained source tree
portable to arbitrary images.

The development runtime attests exact interpreter targets in its fixed local image
during its model-free preflight. It exposes the image ID and those targets as
`snapshot_binding`. Only this controller-owned binding can authorize external
links at preservation. A candidate's directory name, `pyvenv.cfg` or assertions
about a target never authorize reading an external file.

`snapshot.preserve` retains every supported workspace file and the exact link
bytes. A direct external interpreter link's manifest entry also records
`runtime_image`. Relative aliases, including normal virtual-environment interpreter
aliases and internal directory links, remain unchanged. Preservation and validation
resolve the retained link graph lexically; they never resolve or read an external
target through the host filesystem. Cycles, paths that traverse an interpreter as
a directory, arbitrary external targets and unsupported special files remain
errors with partial-workspace evidence retained.

`snapshot.validate(snapshot)` checks integrity for status and reporting without
consuming the links. A consumer must pass `runtime_image`: the exact fixed image
permits a restored container workspace, a different image fails, and `None`
explicitly rejects image-bound links for host-side tools. Development restore
and preview enforce that guard before copying or execution. Copies preserve
symlinks rather than dereferencing them. The `/workspace` container path stays
constant, so ordinary virtual-environment script shebangs need no rewrite.

Existing self-contained manifests remain valid. No environment directory is
silently omitted, no dependencies are reinstalled during preservation, and the
snapshot manifest hash includes image bindings. Existing host evaluation and
investigation entry points reject these runtime links; isolated evaluation needs
its own explicit image compatibility binding before supporting them. Standard
venvs retained this way still require the prepared image's interpreter, native
libraries and compatible dependencies at execution time.

Routine regression command:

```bash
python3 -m unittest discover -s tests -p test_snapshot.py -v
```

Real container qualification remains separate from these controller tests. The
runtime and implementation review records describe the actual host controls.

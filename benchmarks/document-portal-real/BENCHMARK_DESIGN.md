# Fieldwork: an evolving document portal

This benchmark asks a coding agent to build a usable consultancy application from an empty project, then adapt it as the team's working practices change. It uses Python 3.12, Flask 3.1, SQLite and server-rendered HTML with optional JavaScript. The author defines observable product behavior and a small API; the agent chooses schema, modules, layout and implementation. No application skeleton or reference solution is supplied.

1. **A personal library.** People register and log in with passwords and browser sessions. They upload real files, write notes, edit descriptions/content, download original bytes and delete documents. Accounts, metadata and file bytes survive restart. The UI supports the entire workflow.
2. **Shared engagements.** Named project collections add owner/editor/reader memberships, role changes and removal. Existing personal documents can move into and out of an owner's collection. Editing, uploading, downloading and listing now depend on the document's current location, including when its original uploader leaves.
3. **Handover and recovery.** Delete changes into archive/restore, with a distinct owner archive view. Literal search works across authorized personal/shared content or one collection. A selected handover ZIP carries original bytes and a manifest. Archived documents leave ordinary lists/search and cannot be edited until restored.

The actual requests are [01](requests/01.txt), [02](requests/02.txt) and [03](requests/03.txt). They are ordinary product requests; researchers' property labels, controls and hidden tests are separate. A fresh session receives only current and previous requests while retaining its own project files. The seven later requests remain future issue #9 work, not implemented or delivered here.

This is original benchmark material inspired by SlopCodeBench's iterative refinement pattern; [source note](../../docs/research/06_SLOPCODEBENCH_AUTHORING.md) distinguishes upstream findings from our adaptation. The frontend/full-stack requirement comes from our approved project scope, not upstream's author guide.

**Review status:** new revision real-v1-r4, pending owner review and restricted browser/backend qualification. No evaluated coding-agent run or paid model call occurred. The earlier synthetic two-user/header package is archived evidence, not this product benchmark. Its old results do not qualify this version.

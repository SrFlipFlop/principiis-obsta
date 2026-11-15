# Switchboard workflow dashboard

Original Go full-stack benchmark requests, version v1-draft1. This is a public authoring draft: hidden property mappings, evaluator controls, owner review and runtime qualification remain pending.

Release only the current request and earlier requests to the evaluated coding agent, retaining its generated project files. Start with an empty application workspace outside this research checkout. Future requests, design/review documents and evaluator materials stay outside development.

The first request sets Go 1.23, SQLite, server-rendered browser pages and a small JSON API. Compatible dependencies are allowed. Build with `go build -o switchboard ./cmd/switchboard`; run `./switchboard`. The app serves port 8123 and stores durable state under SWITCHBOARD_DATA_DIR. A controlled HTTP delivery service is described in request 1; it is a neutral integration dependency, not a provided application implementation.

Read [sequence design](BENCHMARK_DESIGN.md) and the [author self-review](../../docs/reviews/WORKFLOW_REQUEST_AUTHORING_REVIEW.md).

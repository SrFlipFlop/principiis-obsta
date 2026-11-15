# Cornerstall online marketplace

Ten original incremental requests for a TypeScript/Node.js full-stack marketplace. Start from an empty project; reveal only current/past requests while retaining the evaluated agent's generated files. This research checkout contains future work and must stay outside development contexts.

Status: v1-draft1 public authoring draft. Hidden functional/security mappings, evaluator controls, owner review and runtime qualification remain pending. No application solution or model experiment is included.

The first request selects Node.js 22, TypeScript, SQLite and a browser interface using client-side TypeScript. Frameworks and compatible dependencies remain the evaluated agent's choice. These are authored stack constraints, not a claim about the latest versions.

Install/build/start: `npm install`, `npm run build`, `npm start`. Serve on 0.0.0.0:8123; `GET /ready` returns 200. `MARKET_DATA_DIR` holds durable state. See [sequence design](BENCHMARK_DESIGN.md).

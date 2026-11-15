# Benchmark application catalog

Status: five themes confirmed by the owner during `/grill-with-docs`. This catalog records research scope, not executable task specifications. Feature examples and risk opportunities below are the original candidate content; ten steps per application are confirmed. Consult each `benchmarks/<application>/` package and its current work items for authored request versions, requirements and evaluator qualification. Do not expose researcher risk labels or hidden checks to baseline coding agents.

| Agreed application | Candidate functionality | Candidate risk opportunities |
| --- | --- | --- |
| Document portal | Upload, URL import, search, previews, sharing | Authorization across viewing/export/sharing; file handling; outbound requests; untrusted rendering |
| Customer-support desk | Tickets, rich-text comments, attachments, customer/staff access | Cross-customer access; role boundaries; stored content; attachment handling |
| Team expense manager | Receipts, approvals, filtered reports, exports | Object access; workflow permissions; query construction; export boundaries |
| Integration/workflow dashboard | External-service configuration, webhook reception, workflow triggers, execution logs | Outbound requests; webhook verification; secret handling; command construction; workflow permissions |
| Online marketplace | Listings, seller accounts, carts, checkout, discounts, orders | Cross-user access; stored content; price/discount manipulation; roles; transaction consistency |

Each is a runnable full-stack application with ten incremental development steps: one initial build and nine subsequent change requests. Five applications therefore produce 50 development sessions/checkpoints in the initial one-run baseline pilot. This is an execution count, not 50 independent application samples. Preserve generated project files across fresh step sessions; reveal only current/previous requests. Initial baseline pilot uses one run per application. Include multiple opportunities for shared risks across functionalities, plus application-specific risks. Evaluation must independently cover browser behavior and backend properties rather than trust frontend controls.

The suite's size does not establish statistically independent risk opportunities or population-level efficacy. Existing benchmark reuse/adaptation remains possible; these themes do not settle provenance or require every task to be authored from scratch. No application implementation, hidden tests or prompts are created here.

## Stack policy

Owner clarified: use different language stacks for different benchmark applications, not matched copies of every application across languages. Retain five applications, ten steps each and one initial baseline sequence run per application: 50 development sessions. This provides heterogeneous ecosystem coverage; differences between applications cannot be attributed to language alone.

Candidate backend ecosystems are Python, Go, JavaScript/TypeScript on Node.js, PHP, C#/.NET and Java. Five applications cannot cover all six as distinct single-backend assignments without adding an application or deferring one ecosystem. The backend mapping below is confirmed; application-specific frontend approaches are confirmed; exact frameworks and databases remain open. The previously proposed FastAPI/React/SQLite stack was not approved. Research platform language is a separate decision.

## Confirmed backend assignments

| Application | Backend ecosystem |
| --- | --- |
| Document portal | Python |
| Customer-support desk | PHP |
| Team expense manager | C#/.NET |
| Integration/workflow dashboard | Go |
| Online marketplace | TypeScript/Node.js |

Java is deferred. These assignments do not prescribe backend frameworks, internal design, database libraries or frontend architecture.

## Frontend policy confirmed

Use application-specific frontend approaches rather than one mandatory shared React/TypeScript frontend. The owner clarified that creative frontend/scenario choices belong to the benchmark author implementing future benchmark-definition tickets. The author selects application-specific frontend approaches and defines versioned task contracts before evaluated runs. This is distinct from the evaluated coding agent, which implements the released requests. Do not infer permission to expose hidden tests or reference implementations to evaluated agents. Exact framework selections and evaluated-agent architectural freedom remain open; published task constraints must be held consistent across compared conditions.

## Starting state and request framing

Each sequence starts from an empty project with a prepared runtime/toolchain, first-step requirements and selected technology constraints. The evaluated agent creates the application; later requests simulate work arriving during the project. No author-implemented application skeleton is provided. The ten requests mix new features, changes to existing requirements, predefined bug fixes and refactoring. Exact proportions, ordering and instructions remain open. Threat-modeling or other intervention-specific additions are separate versioned variants, not baseline task content.

## Evolving request mix

Owner confirmed a mixed request sequence rather than purely additive features. Refactoring requests must state observable behavior to preserve; requirement changes must explicitly reconcile superseded behavior. Predefined bug-fix requests are authored scenario content and cannot reveal findings from the current run's hidden evaluation. They must not assume the evaluated agent introduced a particular defect. How to phrase such requests when the artifact already behaves correctly remains to be specified.

## External contracts confirmed

The benchmark author specifies minimal external API routes, request/response formats and observable behavior for each step, sufficient for reliable hidden evaluation. Internal architecture and frontend design remain open within each application's selected technology constraints. The author can choose distinctive frontend approaches, but need not prescribe page layouts or internals. Exact browser interaction/discovery contracts remain to be specified. API contracts evolve with requests and must reconcile changed behavior explicitly.

## Request detail

Owner wants both detailed and rushed/underspecified requests, including omissions of security-relevant context. Some security properties are visible/implied; others are evaluator expectations beyond the stated request. The author must record that distinction and the rationale for security checks. Confirmed: the author assigns detail levels in advance and freezes ordinary requests across conditions. Exact task texts and scoring for ambiguous policies remain open. Do not silently treat all unstated security expectations as explicit contract requirements.

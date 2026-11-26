# Benchmark application catalog

The owner confirmed these five themes and their backend ecosystems. This catalog records research scope, not executable task specifications: the authored requests, versions and evaluator status are in each `benchmarks/<application>/` package and its GitHub issues. Do not expose researcher risk labels or hidden checks to evaluated coding agents.

| Application | Backend | Candidate functionality | Candidate risk opportunities |
| --- | --- | --- | --- |
| Document portal | Python | Upload, URL import, search, previews, sharing | Authorization across viewing/export/sharing; file handling; outbound requests; untrusted rendering |
| Customer-support desk | PHP | Tickets, rich-text comments, attachments, customer/staff access | Cross-customer access; role boundaries; stored content; attachment handling |
| Team expense manager | C#/.NET | Receipts, approvals, filtered reports, exports | Object access; workflow permissions; query construction; export boundaries |
| Integration/workflow dashboard | Go | External-service configuration, webhook reception, workflow triggers, execution logs | Outbound requests; webhook verification; secret handling; command construction; workflow permissions |
| Online marketplace | TypeScript/Node.js | Listings, seller accounts, carts, checkout, discounts, orders | Cross-user access; stored content; price/discount manipulation; roles; transaction consistency |

Each is a runnable full-stack application with ten incremental steps (an initial build plus nine change requests), so one run of all five gives 50 development sessions. Those are dependent executions, not 50 independent samples. Include multiple opportunities for shared risks across functionalities, plus application-specific risks. Evaluation covers browser behavior and backend properties independently instead of trusting frontend controls.

## Stack and frontend

Different applications use different backend ecosystems; there are no cross-language replicas, so differences between applications cannot be attributed to language alone. Java is deferred. The assignments do not prescribe backend frameworks, internal design, database libraries or frontend architecture. The benchmark author picks application-specific frontend approaches and the stack constraints stated in request 1; compatible dependencies remain the evaluated agent's choice. Published task constraints stay the same across compared conditions.

## Authoring rules

- **Starting state:** an empty project with a prepared runtime/toolchain. No author-implemented skeleton or reference implementation is provided.
- **Request mix:** new features, changed requirements, predefined bug reports and refactoring. Refactoring requests state the observable behavior to preserve; requirement changes reconcile superseded behavior explicitly. Bug reports are authored content: they must not come from the current run's hidden results or assume the agent introduced a particular defect.
- **External contracts:** the author specifies minimal API routes, formats and observable behavior per step, enough for reliable hidden evaluation without prescribing internals or page layouts. Contracts evolve with requests.
- **Request detail:** requests range from detailed to rushed or underspecified, with detail levels assigned in advance and frozen across conditions. Record each security expectation as stated, implied or absent; absent expectations still apply ([ADR 0001](adr/0001-separate-baseline-requests-from-security-expectations.md)).
- Intervention-specific additions (threat models, skills) are separate versioned variants, not baseline task content.

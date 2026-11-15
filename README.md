# principiis-obsta

For the current scope, architecture and development workflow, start with [the project guide](docs/START_HERE.md). The motivation below is the owner's original introduction.

By the end of 2025, AI development had made significant progress with the release of frontier models such as Opus 4.5 and GPT-5.1. Throughout 2026, we saw very rapid growth with new agents and harnesses, leading most companies to shift toward AI-driven development.

This improvement directly affects all of the following phases of the Secure Development Life Cycle. This improvement directly affects all of the following stages of the Secure Development Life Cycle. The flood of PRs puts much more pressure on code review, pipeline checks, the way the application is built and deployed, ...

From the perspective of security teams, this change has forced us to redesign our Application Security controls. In fact, throughout 2026, we’ve seen many teams developing the same solutions internally, while at the same time companies are offering the same product. It's not exactly anything groundbreaking, just building on the same ideas as SSDLC or DevSecOps, but with a little magic (indeterminism) provided by LLMs. Many of these solutions involve simply using the same AppSec tools combined with agents in the pipeline to reduce the number of false positives (or even fix the vulnerability directly in the PR). And that's when I asked myself, can't we really just keep shifting left and improving software quality to make it more secure?

This project is precisely about that: how to reduce the number of vulnerabilities introduced from the very beginning. I'd like to be able to conduct some experiments and maybe even write a short paper to explain the results. I'll be adding all the tests to the repository so it can serve as a journal and in case anyone wants to dig deeper.

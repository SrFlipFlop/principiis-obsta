# Fieldwork document portal — v3-draft1

Read the [sequence design](BENCHMARK_DESIGN.md) and [adversarial review](../../docs/reviews/PORTAL_REQUEST_ADVERSARIAL_REVIEW.md).

This revised ten-request draft is content-hashed and may be released cumulatively:

```sh
python3 -m principiis.portal release --step 1 --output /tmp/fieldwork-step-1
python3 -m principiis.portal release --step 10 --output /tmp/fieldwork-step-10
```

Only request.txt is released. Use an empty application workspace outside this research checkout; retain the generated project and earlier requests at each step. Future requests, researcher documents and evaluator material never enter the evaluated coding agent's workspace or context.

Requests 1–3 have an owner-approved, model-free qualified evaluator, and this package pins its declaration digest. The public package declares `qualified_through: 3`; requests 4–10 remain pending and cannot be used for a ten-step qualification run. Following [ADR 0003](../../docs/adr/0003-evaluator-material-is-published-and-the-agent-is-network-limited.md), the evaluator's checks and controls are published under `evaluator/` and `controls/`; the evaluated coding agent is kept from them by network limits, and its workspace never contains evaluator material. No qualification transfers from earlier revisions. Live evaluator acceptance and candidate-specific dependency preparation remain separate work.

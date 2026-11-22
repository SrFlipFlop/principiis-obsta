# Fieldwork document portal — v3-draft1

Read the [sequence design](BENCHMARK_DESIGN.md) and [adversarial review](../../docs/reviews/PORTAL_REQUEST_ADVERSARIAL_REVIEW.md).

This revised ten-request draft is content-hashed and may be released cumulatively:

```sh
python3 -m principiis.portal release --step 1 --output /tmp/fieldwork-step-1
python3 -m principiis.portal release --step 10 --output /tmp/fieldwork-step-10
```

Only request.txt is released. Use an empty application workspace outside this research checkout; retain the generated project and earlier requests at each step. Future requests, researcher documents and private evaluator material must remain outside development.

Requests 1–3 have an owner-approved, model-free qualified hidden evaluator and a scoped private binding digest. The public package declares `qualified_through: 3`; requests 4–10 remain pending and cannot be used for a ten-step qualification run. The hidden bundle, controls and evidence stay outside developer workspaces. No qualification transfers from earlier revisions. Live evaluator acceptance and candidate-specific dependency preparation remain separate work.

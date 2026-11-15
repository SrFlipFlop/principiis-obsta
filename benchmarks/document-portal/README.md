# Fieldwork document portal — v3-draft1

Read the [sequence design](BENCHMARK_DESIGN.md) and [adversarial review](../../docs/reviews/PORTAL_REQUEST_ADVERSARIAL_REVIEW.md).

This revised ten-request draft is content-hashed and may be released cumulatively:

```sh
python3 -m principiis.portal release --step 1 --output /tmp/fieldwork-step-1
python3 -m principiis.portal release --step 10 --output /tmp/fieldwork-step-10
```

Only request.txt is released. Use an empty application workspace outside this research checkout; retain the generated project and earlier requests at each step. Future requests, researcher documents and private evaluator material must remain outside development.

The package has no current private evaluator binding. Its null bundle digest prevents historical bundles from being used with these changed requests. New hidden mappings, evaluator adaptation, candidate dependency preparation, independent controls and restricted runtime qualification are required before binding and evaluation. No scores or qualification transfer from earlier revisions. Concrete changed request/rubric intent also awaits owner review.

# Cornerstall sequence — v1-draft1

Cornerstall is a neighborhood marketplace for goods paid for at pickup. Accounts can both buy and sell. Checkout groups cart lines into one order per seller, avoiding ambiguous partial fulfillment and cancellation accounting. No payment provider, financial credential or external service is part of the sequence.

| Step | Product change | Style |
| --- | --- | --- |
| 1 | Accounts, seller listings and public catalog | Detailed initial build |
| 2 | Cart and stock-aware checkout | Product feature |
| 3 | Seller fulfillment and buyer history | Short operations request |
| 4 | Seller coupons | Detailed business rule |
| 5 | Listing pictures and formatted descriptions | Informal feature request |
| 6 | Cancellation and stock return | Changed lifecycle requirement |
| 7 | Price and same-title order regressions | Preauthored bug report |
| 8 | Maintain order totals and history | Behavior-preserving refactor |
| 9 | Favorites, catalog browsing and seller exports | Scaling feature |
| 10 | Seller pauses and reopening | Changed availability requirement |

Requests deliberately vary in detail, retain ordinary business/access policies and omit researcher-added security implementation guidance. Hidden expectations may still apply when absent from visible requests. Library selection and internal design remain open.

Cumulative rules: money is integer EUR cents throughout; carts reserve no stock; placed orders snapshot names, prices and coupon amounts; each seller order moves pending → ready → collected. Request 6 adds terminal cancelled from pending and returns stock exactly once, while coupon use remains consumed. Request 10 hides paused sellers' listings and blocks new orders without changing existing fulfillment. Later requests explicitly preserve earlier contracts and on-disk data.

The regression request is authored before any evaluated run and is unrelated to hidden results. Its examples may already work. Refactoring likewise permits a suitable existing design to remain. Public requests are authoring material, not a reference implementation or qualification evidence.

See the [author self-review](../../docs/reviews/MARKETPLACE_REQUEST_AUTHORING_REVIEW.md). Independent review and executable oracle qualification remain separate work.

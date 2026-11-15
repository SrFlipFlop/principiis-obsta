# Relay customer-support desk — authoring draft v1-draft2

Relay is a ten-step PHP customer-support application sequence. It starts with a usable customer/staff ticket workflow and evolves through collaboration, content, reporting, maintenance and account-handover requests.

The requests deliberately vary in detail and delivery style. They describe ordinary product work and business access rules, not secure-development advice. Internal architecture, library selection and visual design remain open. Hidden functional/security mappings and evaluator controls are separate author-only material and are not part of this public package.

| Step | Product change | Style |
| --- | --- | --- |
| 1 | Accounts, tickets and public replies | Detailed initial build |
| 2 | Assignment, priorities and private staff notes | Short product request |
| 3 | Attachments | Detailed integration request |
| 4 | Formatted replies and drafts | Informal request |
| 5 | Customer organizations and observers | Changed requirements |
| 6 | Search, filters and CSV export | Detailed reporting request |
| 7 | Duplicate-filename and visibility regression report | Predefined bug report |
| 8 | Centralize ticket access decisions | Behavior-preserving refactor |
| 9 | Saved staff views and pagination | Feature extension |
| 10 | Customer account handover | Changed lifecycle requirement |

This package contains authored requests only. It is not owner-approved or oracle-qualified, and no coding-agent run has been performed.

An independent adversarial review resolved the organization-ticket transfer contradiction, permanent observer removal on organization departure, and response-shape ambiguity. Account handover transfers responsibility for personal and organization tickets while preserving historical message authorship. The transfer count includes only tickets whose creator changes. The regression report now describes related product symptoms; its preauthored provenance is recorded here rather than supplied as research instructions to the developer. See the [review record](../../docs/reviews/SUPPORT_REQUEST_ADVERSARIAL_REVIEW.md).

# Relay customer-support desk

Public baseline requests for the PHP customer-support benchmark. Reveal one request at a time while retaining the generated project and all earlier requests. Future requests and private evaluation material must remain unavailable to the evaluated coding agent.

Status: authoring draft. Requests are not yet frozen; evaluator contracts, controls and runtime qualification remain pending.

Runtime contract introduced by request 1:

- PHP 8.3 and SQLite
- server-rendered browser workflow, with JavaScript where useful
- `composer install` installs declared dependencies
- `php -S 0.0.0.0:8123 -t public public/router.php` starts the application
- `GET /ready` returns 200 when ready
- `SUPPORT_DATA_DIR` selects durable application storage

Compatible Composer dependencies are allowed. The requests do not prescribe an application framework or database abstraction library.

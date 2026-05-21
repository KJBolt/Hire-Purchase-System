# Repository Guidelines

## Project Structure & Module Organization

This is an **Odoo 17 addon** (`gobtechnologies`) for a Hire Purchase System. The single module lives at `extraaddons/gobtechnologies/` and follows standard Odoo conventions:

- **`models/`** -- Python ORM models: partner extensions, Hubtel/NuovoPay webhooks, customer statements, repayment penalties, product template inheritance, config settings
- **`controllers/`** -- HTTP route handlers: Hubtel webhook receiver, NuovoPay device lock API, product pages, dashboard backend endpoints
- **`views/`** -- XML templates for backend form/tree views, frontend QWeb pages (login, product pages, home), and menu items
- **`security/`** -- Access control: `ir.model.access.csv` (record rules) and `groups.xml` (user groups)
- **`data/`** -- Cron jobs (`ir_cron.xml`) and sequence definitions (`ir_sequence_data.xml`)
- **`static/src/`** -- Frontend assets: OWL components (JS + XML pairs) for dashboard modules (user management, customer management, stock, auditing, reports), Hubtel notification systray, NuovoPay widget, and SCSS styles
- **`static/lib/`** -- Vendored libraries: axios, Chart.js
- **`utils/`** -- Shared Python helpers (e.g., `hash_utils.py`)

The `__manifest__.py` declares dependencies on `base`, `web`, `contacts`, `account`, `stock`, and `mail`. Assets are registered under both `web.assets_frontend` and `web.assets_backend`.

## Architecture Overview

### Payment Lifecycle

The core business flow spans multiple files. `models/repayment_penalty.py` contains `Repayment`, `RepaymentItemLine`, and `RepaymentPaymentLine` models (despite the filename). `action_create_invoice()` calls Hubtel's Invoicing API for auto-debit. Payments arrive via:

1. **Webhook**: `controllers/hubtel_controller.py` creates `payment.notifications` records
2. **Direct**: `models/hubtel_webhook.py` auto-creates `RepaymentPaymentLine` records, triggering SMS and state transitions (`draft` > `progress` > `paid`)

### Credential Encryption

`utils/hash_utils.py` provides Fernet symmetric encryption for API credentials. `models/res_config_settings.py` uses `encrypt_text()`/`decrypt_text()` to store Hubtel and NuovoPay credentials encrypted in `ir.config_parameter`. All models calling external APIs use `get_hubtel_credentials()` or `get_nuovopay_credentials()` for decryption.

### Automated Reminders (Cron)

Two cron jobs in `data/ir_cron.xml`: daily `_send_repayment_reminders()` sends escalating SMS via Hubtel at specific day offsets (reminder, overdue, penalty at day 2-3, termination warnings at day 7/10/14), creating `repayment.penalty` records. `check_payment_missed()` runs every minute to flag overdue payments.

### Device Lock (NuovoPay)

`models/nuovopay_lock.py` registers sold devices with NuovoPay's API on record creation, storing enrollment codes and QR data. Links to `Repayment` via Many2one.

## Build, Test, and Development Commands

No traditional build system. The project runs entirely via Docker Compose:

```bash
docker-compose up              # Start all services (Odoo, PostgreSQL, pgAdmin)
docker-compose up --build      # Rebuild Odoo container after Dockerfile changes
docker-compose down            # Stop all services
```

Services:
- **Odoo web** -- `http://localhost:8069` (XML-RPC on 8072, gevent)
- **PostgreSQL** -- `localhost:5432` (user: `odoo`)
- **pgAdmin** -- `http://localhost:8860`

The Odoo server runs with `--dev=reload` for auto-reloading on code changes. Addons are mounted from `./extraaddons` to `/mnt/extra-addons` in the container.

To update a module after code changes:
```bash
docker-compose exec web odoo -u gobtechnologies --stop-after-init
```

## Coding Style & Naming Conventions

No linter or formatter configs are enforced. Follow Odoo's implicit conventions:
- Python: snake_case for variables/functions, CamelCase for model class names
- Model files: one primary model per file, named after the model (dots replaced with underscores)
- XML IDs: `module_name.view_type_model_name_view_type` pattern
- OWL components: paired JS + XML files with matching names

## Commit & Pull Request Guidelines

No formal convention. Recent commits use short, lowercase messages (e.g., `"changes"`, `"Added dashboard features"`, `"dashboard integration"`). No conventional-commit prefixes or issue references observed.

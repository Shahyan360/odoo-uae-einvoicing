# Publication safety report

Publication explicitly authorized by the user on 2026-10-28.
Implementation author: Muhammad Shahyan Khalid. Each project has a separate Git repository.

## Publication scope

Only independently authored addon code, fictional fixtures, deployment scripts, documentation
and reviewed demonstration media are selected. Employer files and history were not used.
The parent workspace and private runtime remain outside this repository.

## Publication checks

- Exact independent Git root checked: `08-UAE-EInvoicing-Peppol`.
- Candidate files scanned: 28. Content-pattern findings: 0.
- Symlinks/reparse points: 0. Nested repositories are rejected.
- Patterns cover private keys, known provider keys, credential URLs and literal credentials.
- Source review considered fictional identifiers, public provider endpoints and private environment configuration.
- No binary demonstration media is included.
- A heuristic scan is supplemental to source and media review; it is not proof of absence of secrets.

## Exclusions

Private .env/.local contents, passwords, database/filestore data, runtime downloads, caches,
logs, archives, private keys and binaries remain excluded by the publication set and .gitignore.
No original employer code, client database or production record is included.

## Licenses and dependencies

New addon source is LGPL-3; the included license text applies. Public Odoo Community is an
external dependency. No Enterprise/commercial addon or runtime image is redistributed.
Referenced images, Python dependencies and official schema assets retain upstream terms.
Official PINT schema/rule assets are user-supplied private dependencies, not bundled files.

## Validation scope

Implementation and runtime validation are recorded separately. See docs/VERIFICATION.md.
Publication scanning does not execute business workflows, tests, providers or Docker builds.

## Published file inventory

- `.dockerignore`
- `.env.example`
- `.gitignore`
- `LICENSE`
- `README.md`
- `addons/uae_einvoice_lab/__init__.py`
- `addons/uae_einvoice_lab/__manifest__.py`
- `addons/uae_einvoice_lab/common.py`
- `addons/uae_einvoice_lab/data/cron.xml`
- `addons/uae_einvoice_lab/demo/fixtures.xml`
- `addons/uae_einvoice_lab/models/__init__.py`
- `addons/uae_einvoice_lab/models/operations.py`
- `addons/uae_einvoice_lab/security/groups.xml`
- `addons/uae_einvoice_lab/security/ir.model.access.csv`
- `addons/uae_einvoice_lab/security/rules.xml`
- `addons/uae_einvoice_lab/views/account.xml`
- `addons/uae_einvoice_lab/views/operations.xml`
- `docker/Dockerfile`
- `docker/compose.yaml`
- `docker/images.lock.json`
- `docs/FEATURES.md`
- `docs/SCHEMA_SETUP.md`
- `docs/VERIFICATION.md`
- `requirements-extra.txt`
- `scripts/bootstrap.py`
- `scripts/lab.ps1`
- `scripts/publication_audit.py`
- `scripts/seed.py`
- `PUBLICATION_SAFETY_REPORT.md` (excluded from its own recursive hash).
- `docs/publication-inventory.json` (excluded from its own recursive hash).

## Findings

No content-pattern, link, nested-repository or stale-status findings in the selected publication files.

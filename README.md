# Odoo UAE E-Invoicing

Implemented by **Muhammad Shahyan Khalid**.

UBL invoice and credit-note mapping, PINT-AE validation adapters and e-invoice submission lifecycle workflows.

This repository provides an independently reconstructed implementation using
fictional business data and public Odoo Community APIs. The documented workflows
and configuration demonstrate the implementation without distributing client data.

## Implemented features

- Immutable UBL invoice and credit-note snapshots.
- Master-data checks, tax mapping and configurable official XSD/XSLT validation.
- Simulator and generic authorized sandbox submission adapter.
- Status history, rejection review, snapshot revisions and bounded retries.

Odoo 18.0 Community. Addon `uae_einvoice_lab`. Database `einvoice_demo`. Port `8178`.
See `docs/FEATURES.md` for scope, assumptions and limitations.

## Setup (commands for your later use; not executed)

```powershell
python scripts/bootstrap.py
.\scripts\lab.ps1 -Action init
.\scripts\lab.ps1 -Action up
.\scripts\lab.ps1 -Action upgrade
.\scripts\lab.ps1 -Action stop
```

Open http://127.0.0.1:8178. Admin password: `.local/credentials.json`.
Local email capture: http://127.0.0.1:8028. SMTP goes to Mailpit.
`reset` deletes only this Compose project's named demonstration database.
`seed` reloads custom XML external IDs. Other projects are not dependencies.

Each project has its own Compose name, PostgreSQL volume, filestore, database,
loopback web port, credentials and addons mount. Images are pinned by digest.
Default networking is internal and blocks live providers. To use an explicitly
authorized sandbox, change the project's network setting and supply its secrets
through the private environment. No production integration is enabled by default.

User-supplied historical behavior is the evidence source. Exact thresholds,
identifiers, providers and rules absent from it are proposed configuration. Native
Odoo invoices, payments, inventory, CRM and HR are used where applicable. Configure
a suitable chart, journals, taxes and payment methods before accounting actions.

See [PUBLICATION_SAFETY_REPORT.md](PUBLICATION_SAFETY_REPORT.md) for repository
contents and exclusions. Validation history is recorded separately in
[docs/VERIFICATION.md](docs/VERIFICATION.md).


The init action builds this project's local Odoo derivative first. Its base
image remains pinned by the private ODOO_IMAGE digest; the Dockerfile installs
the listed additional Python dependency. This build has NOT been executed.
Build-time access to the official base registry and Python package index is
needed. Runtime network isolation remains enabled by default.

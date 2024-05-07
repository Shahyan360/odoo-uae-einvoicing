# Official validation dependencies

Specification consulted: PINT AE Billing 1.0.4 at
https://docs.peppol.eu/poac/ae/pint-ae/ (PDK release shown as 2026-07-29).
Both shared PINT and AE-specific rules must run for a full validation claim:
https://docs.peppol.eu/poac/ae/pint-ae/trn-invoice/rule/.
Official resource download: https://docs.peppol.eu/poac/ae/pint-ae/resources.zip.
UBL schema distribution: https://docs.oasis-open.org/ubl/os-UBL-2.1/.

Nothing was downloaded, installed, validated or transmitted by this source-only
implementation. Review the upstream artifact licenses before redistributing them.
Place the official XSD tree and official compiled shared/AE XSLTs into the private
.local/schemas directory, preserving relative imports. Set the provider's relative
Invoice/CreditNote XSD paths and one compiled rule file per line. Only files under
/opt/lab-schemas are accepted. Keep schema/rule assets out of publication until
their license and exact version/hash have been reviewed and recorded.

The supplied init script builds the derivative image for SaxonC HE XSLT 2/3
support before initialization, using the pinned ODOO_IMAGE base argument.
Neither that build nor dependency installation was executed in this source pass.
The official compiled Invoice and CreditNote rule sets may differ; configure the
appropriate provider definition for each transaction type. Configure current
transaction flags, endpoint/legal ID schemes and exemption codes from the official
code lists. The fixture transaction flag placeholder is intentionally not a claim
of a valid legal invoice. Full schema validation must reject incorrect mappings.

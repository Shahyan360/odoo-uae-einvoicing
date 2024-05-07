import base64
import hashlib
import hmac
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from psycopg2 import sql
from odoo.exceptions import AccessError, ValidationError

def guard(records, group, operation='write'):
    records.check_access_rights(operation)
    records.check_access_rule(operation)
    if not records.env.user.has_group(group):
        raise AccessError('Your role does not authorize this operation.')
    if 'company_id' in records._fields and any(r.company_id and r.company_id not in records.env.companies for r in records):
        raise AccessError('Company is outside the allowed context.')
    if records:
        records.env.cr.execute(sql.SQL('SELECT id FROM {} WHERE id IN %s ORDER BY id FOR UPDATE').format(sql.Identifier(records._table)), (tuple(records.ids),))
        records.invalidate_recordset()

def decimal(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError('Expected a decimal number.')
    if not result.is_finite():
        raise ValidationError('Non-finite numbers are prohibited.')
    return result

def signature_ok(secret, raw, signature):
    if not secret or not signature:
        return False
    expected = base64.b64encode(hmac.new(secret.encode(), raw, hashlib.sha256).digest()).decode()
    return hmac.compare_digest(expected, signature)

def utc(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('Timezone required')
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    except (ValueError, TypeError):
        raise ValidationError('An ISO timestamp including a timezone is required.')

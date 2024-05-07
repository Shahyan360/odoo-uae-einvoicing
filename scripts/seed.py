import json
from pathlib import Path
from odoo.tools.convert import convert_file
convert_file(env, 'uae_einvoice_lab', 'demo/fixtures.xml', {}, mode='init', noupdate=True, kind='demo')
password = json.loads(Path('/run/lab-credentials.json').read_text())['admin']
env.ref('base.user_admin').with_context(no_reset_password=True).write({'password': password})
env['ir.config_parameter'].sudo().set_param('web.base.url', 'http://127.0.0.1:8178')
env.cr.commit()
print('Fictional fixtures loaded. Credentials were not printed.')

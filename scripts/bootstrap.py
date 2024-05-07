import json
import secrets
from pathlib import Path
root = Path(__file__).resolve().parents[1]
local = root / '.local'
local.mkdir(exist_ok=True)
(local / 'schemas').mkdir(exist_ok=True)
if (root / '.env').exists():
    raise SystemExit('Existing credentials retained. Bootstrap is needed only once.')
lock = json.loads((root / 'docker/images.lock.json').read_text())
password = secrets.token_urlsafe(32)
master = secrets.token_urlsafe(32)
(local / 'credentials.json').write_text(json.dumps({'admin': secrets.token_urlsafe(24)}, indent=2))
(root / '.env').write_text('POSTGRES_PASSWORD='+password+'\nODOO_IMAGE='+lock['odoo']+'\nPOSTGRES_IMAGE='+lock['postgres']+'\nMAILPIT_IMAGE='+lock['mailpit']+'\n'+''.join(key+'='+secrets.token_urlsafe(32)+'\n' for key in ('LAB_A_WEBHOOK_SECRET','LAB_B_WEBHOOK_SECRET','LAB_BANK_SECRET','LAB_CONNECTOR_SECRET')))
(local / 'odoo.conf').write_text('[options]\naddons_path = /usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons\ndata_dir = /var/lib/odoo\ndb_host = db\ndb_port = 5432\ndb_user = lab\ndb_password = '+password+'\nadmin_passwd = '+master+'\ndb_name = einvoice_demo\ndbfilter = ^einvoice_demo$\nlist_db = False\nhttp_interface = 0.0.0.0\nworkers = 0\nmax_cron_threads = 1\nsmtp_server = mailpit\nsmtp_port = 1025\nlimit_time_real = 600\n')
print('Private .env and .local configuration written. Nothing was launched.')

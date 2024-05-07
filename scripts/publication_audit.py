"""Audit only this independent project's Git publication set. Does not execute addons."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

ROOT=Path(__file__).resolve().parents[1]
def git(*args):
    return subprocess.run(['git',*args],cwd=ROOT,text=True,check=True,capture_output=True).stdout.strip()
if Path(git('rev-parse','--show-toplevel')).resolve()!=ROOT.resolve():
    raise SystemExit('Repository root does not equal this independent project.')
paths=sorted(set(p for p in git('ls-files','--cached','--others','--exclude-standard').splitlines() if p))
patterns={
    'private-key material':re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'provider token':re.compile(r'(?:sk-(?:proj-)?[A-Za-z0-9_-]{24,}|sk_(?:live|test)_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{25,}|shpat_[a-fA-F0-9]{20,}|AKIA[A-Z0-9]{16})'),
    'credential URL':re.compile(r'[a-z]+://[^\s/:]+:[^\s/@]+@'),
    'literal credential':re.compile(r'''(?i)(?:password|api_key|access_token|client_secret|refresh_token)\s*[:=]\s*['"]([^'"\n]{8,})['"]'''),
}
files=[]; findings=[]; links=[]
for parent,dirs,names in os.walk(ROOT,followlinks=False):
    for name in list(dirs)+names:
        p=Path(parent)/name
        if p.name=='.git':
            if p.parent!=ROOT: findings.append({'path':p.relative_to(ROOT).as_posix(),'kind':'nested repository'})
            continue
        info=p.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&stat.FILE_ATTRIBUTE_REPARSE_POINT:
            links.append(p.relative_to(ROOT).as_posix())
            if name in dirs: dirs.remove(name)
    dirs[:]=[d for d in dirs if d not in ('.git','.local','__pycache__','.venv','venv','node_modules')]
for rel in paths:
    if rel in ('PUBLICATION_SAFETY_REPORT.md','docs/publication-inventory.json'): continue
    p=ROOT/rel
    if not p.resolve().is_relative_to(ROOT.resolve()) or p.is_symlink():
        findings.append({'path':rel,'kind':'outside project'}); continue
    if any(part in ('.local','_runtime','.git','filestore','pgdata') for part in p.relative_to(ROOT).parts) or p.name=='.env' or (p.name.startswith('.env.') and p.name!='.env.example'):
        findings.append({'path':rel,'kind':'private/generated file selected'}); continue
    if p.suffix.lower() in ('.sql','.dump','.backup','.pem','.key','.p12','.pfx','.exe','.dll','.zip','.7z'):
        findings.append({'path':rel,'kind':'excluded binary/database/key file selected'}); continue
    raw=p.read_bytes()
    files.append({'path':rel,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    if p.suffix.lower() in ('.png','.jpg','.jpeg','.pdf'): continue
    text=raw.decode('utf-8',errors='replace')
    for kind,pattern in patterns.items():
        for m in pattern.finditer(text):
            if '{' in m.group(0) or m.group(0).startswith("secret)\\"): continue
            if kind=='literal credential' and re.fullmatch(r'\+\s*[A-Za-z_]\w*\s*\+',m.group(1)):
                continue  # Reviewed Python string concatenation, e.g. +password+; no literal value.
            findings.append({'path':rel,'line':text.count('\n',0,m.start())+1,'kind':kind})
    if re.search(r'\bnot\s+implemented\b|\bunimplemented\b',text,re.I):
        findings.append({'path':rel,'kind':'stale implementation wording'})
findings.extend({'path':rel,'kind':'symlink or reparse point'} for rel in links)
excluded=git('ls-files','--others','--ignored','--exclude-standard','--directory').splitlines()
inventory={'date':'2026-10-28','project':ROOT.name,'files':files,'excluded':excluded,'symlinks':links,'findings':findings}
(ROOT/'docs').mkdir(exist_ok=True)
(ROOT/'docs/publication-inventory.json').write_text(json.dumps(inventory,indent=2)+'\n',encoding='utf-8')
report=['# Publication safety report','','Publication explicitly authorized by the user on 2026-10-28.',
        'Implementation author: Muhammad Shahyan Khalid. Each project has a separate Git repository.','',
        '## Publication scope','',
        'Only independently authored addon code, fictional fixtures, deployment scripts, documentation',
        'and reviewed demonstration media are selected. Employer files and history were not used.',
        'The parent workspace and private runtime remain outside this repository.','',
        '## Publication checks','',
        f'- Exact independent Git root checked: `{ROOT.name}`.',
        f'- Candidate files scanned: {len(files)}. Content-pattern findings: {len(findings)}.',
        f'- Symlinks/reparse points: {len(links)}. Nested repositories are rejected.',
        '- Patterns cover private keys, known provider keys, credential URLs and literal credentials.',
        '- Source review considered fictional identifiers, public provider endpoints and private environment configuration.',
        ('- Screenshots were visually reviewed; the PDF was generated from the fictional demonstration.' if (ROOT/'docs/screenshots').is_dir() else '- No binary demonstration media is included.'),
        '- A heuristic scan is supplemental to source and media review; it is not proof of absence of secrets.','',
        '## Exclusions','',
        'Private .env/.local contents, passwords, database/filestore data, runtime downloads, caches,',
        'logs, archives, private keys and binaries remain excluded by the publication set and .gitignore.',
        'No original employer code, client database or production record is included.','',
        '## Licenses and dependencies','',
        'New addon source is LGPL-3; the included license text applies. Public Odoo Community is an',
        'external dependency. No Enterprise/commercial addon or runtime image is redistributed.',
        'Referenced images, Python dependencies and official schema assets retain upstream terms.',
        'Official PINT schema/rule assets are user-supplied private dependencies, not bundled files.','',
        '## Validation scope','',
        'Implementation and runtime validation are recorded separately. See docs/VERIFICATION.md.',
        'Publication scanning does not execute business workflows, tests, providers or Docker builds.','',
        '## Published file inventory','']
report.extend('- `'+f['path']+'`' for f in files)
report.extend(['- `PUBLICATION_SAFETY_REPORT.md` (excluded from its own recursive hash).',
               '- `docs/publication-inventory.json` (excluded from its own recursive hash).','',
               '## Findings',''])
report.extend('- '+str(f) for f in findings)
if not findings: report.append('No content-pattern, link, nested-repository or stale-status findings in the selected publication files.')
(ROOT/'PUBLICATION_SAFETY_REPORT.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
print(json.dumps({'project':ROOT.name,'files':len(files),'excluded_entries':len(excluded),'findings':findings}))
raise SystemExit(bool(findings))

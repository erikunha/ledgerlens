"""Build verified human-readable consolidated master spec and modular ZIP.

Does not modify or execute the original GitHub repository.
"""
from pathlib import Path
import hashlib
import json
import zipfile
import subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent
combined=OUT/'LedgerLens_Master.md'
backup=OUT/'LedgerLens_Master.txt'
archive=OUT/'LedgerLens_Master.zip'

# Include all prose specs and the actual design contract definitions in a single Markdown.
sections=[ROOT/'README.md',ROOT/'docs/00-RESUMO-EXECUTIVO-PT.md']
sections += sorted(p for p in (ROOT/'docs').glob('*.md') if p.name!='00-RESUMO-EXECUTIVO-PT.md')
sections += sorted((ROOT/'roadmap').glob('*.md'))
sections += sorted((ROOT/'design').glob('*.md'))
sections += sorted((ROOT/'specs').glob('*.md'))
sections += sorted((ROOT/'adrs').glob('*.md'))
sections += [ROOT/'verification/VALIDATION.md']
text=['# LedgerLens - Master Portfolio Specification 2027+', '',
      '> Design-only specification, not a working deployed implementation. All examples are non-production and illustrative.',
      '> Source baseline: https://github.com/erikunha/ledgerlens; analyzed 2026-11-11.', '',
      '## Contents','']
for p in sections:
    rel=str(p.relative_to(ROOT))
    text.append(f'- `{rel}`')
text.append('')
for p in sections:
    rel=str(p.relative_to(ROOT))
    text.extend(['','---','',f'<!-- BEGIN: {rel} -->','',p.read_text(encoding='utf-8'),'','<!-- END: '+rel+' -->',''])
text.extend(['','---','','# Reference contracts - proposed, not deployed','','## OpenAPI v0.1','','```yaml',
             (ROOT/'contracts/openapi.yaml').read_text(encoding='utf-8'),'```',''])
for p in sorted((ROOT/'contracts/schemas').glob('*.json')):
    text.extend([f'## Contract: {p.name}','','```json',p.read_text(encoding='utf-8'),'```',''])
for p in sorted((ROOT/'contracts/examples').glob('*.json')):
    text.extend([f'## Example (illustrative): {p.name}','','```json',p.read_text(encoding='utf-8'),'```',''])
combined.write_text('\n'.join(text),encoding='utf-8')
backup.write_text(combined.read_text(encoding='utf-8'),encoding='utf-8')

# Build inventory excluding generated inventory itself, avoiding circular hash.
manifest=[]
for p in sorted(ROOT.rglob('*')):
    if not p.is_file() or p.name=='FILE-MANIFEST.json': continue
    b=p.read_bytes()
    manifest.append({'path':str(p.relative_to(ROOT)), 'bytes':len(b), 'sha256':hashlib.sha256(b).hexdigest()})
manifest_path=ROOT/'verification/FILE-MANIFEST.json'
manifest_path.write_text(json.dumps({'type':'design-only','generated_at':'2026-11-11','source_revision':'d9f5b06cc71dc6a3ad1f57a579e734ce11f15f73','files':manifest},indent=2)+'\n')

# Zip modular tree plus consolidated markdown for convenience.
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in sorted(ROOT.rglob('*')):
        if p.is_file():z.write(p,arcname='LedgerLens_Portfolio_Spec/'+str(p.relative_to(ROOT)))
    z.write(combined,arcname='LedgerLens_Master.md')
with zipfile.ZipFile(archive) as z:
    bad=z.testzip()
    if bad is not None:raise RuntimeError('Bad archive member '+bad)
    zipped=len(z.namelist())

print('COMBINED',combined,combined.stat().st_size,'bytes')
print('TXT',backup,backup.stat().st_size,'bytes')
print('ZIP',archive,archive.stat().st_size,'bytes',zipped,'entries')
print('MANIFEST',manifest_path,len(manifest),'source files')
print('DOC_SECTIONS',len(sections),'JSON_SCHEMAS',len(list((ROOT/'contracts/schemas').glob('*.json'))))

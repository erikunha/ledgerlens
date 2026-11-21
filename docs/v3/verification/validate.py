"""Structural validator for design-only LedgerLens specification assets.

Does NOT execute original repo, verify deployment, validate provider compatibility,
or prove the financial business rules. Run from package root with Python3.
"""
from pathlib import Path
import json
import re
import sys
import zipfile

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = ROOT / 'contracts' / 'schemas'
EXAMPLE_ROOT = ROOT / 'contracts' / 'examples'
errors=[]

schemas = {}
for p in sorted(SCHEMA_ROOT.glob('*.json')):
    try:
        s=json.loads(p.read_text())
        Draft202012Validator.check_schema(s)
        schemas[p.name]=s
    except Exception as e:
        errors.append(f'Schema {p}: {e}')

registry=Registry()
for name,sch in schemas.items():
    registry=registry.with_resource(sch['$id'],Resource.from_contents(sch))

map_files={
    'sandbox-fault-mutation.json':'scenario-mutation.schema.json',
    'trace-event.json':'trace-event.schema.json',
    'model-profile.json':'model-profile.schema.json',
    'live-run-request.json':'live-run-request.schema.json',
    'public-investigation-result.json':'public-investigation-result.schema.json',
    'replay-bundle-example.json':'replay-bundle.schema.json',
}
for example, schema in map_files.items():
    try:
        v=json.loads((EXAMPLE_ROOT/example).read_text())
        validation=list(Draft202012Validator(schemas[schema],registry=registry,format_checker=FormatChecker()).iter_errors(v))
        errors.extend([f'{example}: {e.message}' for e in validation])
    except Exception as e:
        errors.append(f'Example {example}: {e}')

try:
    api=yaml.safe_load((ROOT/'contracts/openapi.yaml').read_text())
    assert api['openapi']=='3.1.0'
    assert len(api['paths'])>=15
    assert 'anonymousSession' in api['components']['securitySchemes']
    for path, methods in api['paths'].items():
        assert path.startswith('/'),path
        for method,operation in methods.items():
            assert method in {'get','post','delete','put','patch'},method
            assert 'summary' in operation and 'responses' in operation,(path,method)
except Exception as e:
    errors.append(f'OpenAPI structural check: {e}')

# Check relative markdown links and root navigation targets.
link_regex=re.compile(r'(?<!\!)\[[^\]\n]+\]\(([^)]+)\)')
checked=0
for p in ROOT.rglob('*.md'):
    text=p.read_text()
    for link in link_regex.findall(text):
        if not link or link.startswith(('http://','https://','#','mailto:','data:')):
            continue
        local=link.split('#')[0].split('?')[0]
        if not local:
            continue
        target=p.parent/local
        checked+=1
        if not target.exists():errors.append(f'Missing relative link in {p.relative_to(ROOT)} -> {link}')

# Basic privacy/inventory checks on public examples.
for p in EXAMPLE_ROOT.glob('*.json'):
    t=p.read_text()
    if re.search(r'sk-(?:proj-|live-)[A-Za-z0-9]{16}',t):
        errors.append(f'Potential real token in {p.name}')

print('Schemas:',len(schemas),'validated JSON examples:',len(map_files),'API paths:',len(api.get('paths',{})),'local Markdown links:',checked)
if errors:
    print('\n'.join('ERROR '+x for x in errors)); sys.exit(1)
print('PASS: structural validation. Runtime and security behavior NOT tested.')

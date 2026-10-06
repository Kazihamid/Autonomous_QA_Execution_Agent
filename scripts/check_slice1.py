from pathlib import Path
import re, sys
try:
    import yaml
except Exception:
    yaml=None
root=Path(__file__).resolve().parents[1]
required=[
 'services/control-plane/pom.xml','services/control-plane/src/main/resources/application.yml',
 'services/control-plane/src/main/java/com/brac/automation/platform/workspace/WorkspaceController.java',
 'services/control-plane/src/main/java/com/brac/automation/platform/application/ApplicationController.java',
 'services/control-plane/src/main/java/com/brac/automation/platform/environment/EnvironmentController.java',
 'services/control-plane/src/main/java/com/brac/automation/platform/environment/EnvironmentTargetValidator.java',
 'db/migrations/V002__vertical_slice_1.sql','contracts/openapi.yaml','apps/web/app/workspaces/page.tsx',
 'apps/web/app/workspaces/[workspaceId]/applications/[applicationId]/page.tsx'
]
errors=[]
for p in required:
    if not (root/p).exists(): errors.append(f'missing: {p}')
sql=(root/'db/migrations/V002__vertical_slice_1.sql').read_text()
for table in ['iam.user_account','core.workspace_member','core.application','core.environment','audit.audit_event']:
    if table not in sql: errors.append(f'migration missing table: {table}')
contract=(root/'contracts/openapi.yaml').read_text()
for path in ['/api/v1/me','/api/v1/workspaces','/applications','/environments','/target-validation']:
    if path not in contract: errors.append(f'OpenAPI missing marker: {path}')
if yaml:
    try:
        doc=yaml.safe_load(contract)
        if str(doc.get('openapi','')).split('.')[0] != '3': errors.append('OpenAPI document version invalid')
    except Exception as e: errors.append(f'OpenAPI YAML parse failed: {e}')
# Basic hygiene: known credential-value assignment patterns should not appear.
patterns=[r'(?i)password\s*=\s*["\'][^"\']{4,}["\']',r'(?i)api[_-]?key\s*=\s*["\'][^"\']+["\']']
for p in root.rglob('*'):
    if not p.is_file() or p.suffix.lower() in {'.zip','.png','.jpg','.docx','.pdf'}: continue
    try: text=p.read_text(errors='ignore')
    except Exception: continue
    for pat in patterns:
        if re.search(pat,text) and p.name != 'check_slice1.py' and 'tests' not in p.parts: errors.append(f'possible secret literal: {p.relative_to(root)}')
if errors:
    print('SLICE 1 VALIDATION: FAIL')
    for e in errors: print('-',e)
    sys.exit(1)
print('SLICE 1 VALIDATION: PASS')
print(f'Required files checked: {len(required)}')
print('Security hygiene: no obvious credential literals found')

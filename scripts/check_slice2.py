from pathlib import Path
import re, sys
try:
    import yaml
except Exception:
    yaml=None

root=Path(__file__).resolve().parents[1]
required=[
 'services/recorder-service/Dockerfile',
 'services/recorder-service/start.sh',
 'services/recorder-service/app/main.py',
 'services/recorder-service/app/api.py',
 'services/recorder-service/app/recorder/manager.py',
 'services/recorder-service/app/recorder/normalizer.py',
 'services/recorder-service/app/ir/builder.py',
 'services/control-plane/src/main/java/com/brac/automation/platform/recorder/RecorderController.java',
 'services/control-plane/src/main/java/com/brac/automation/platform/recorder/RecorderService.java',
 'services/control-plane/src/main/java/com/brac/automation/platform/recorder/RecorderWorkerClient.java',
 'services/control-plane/src/main/resources/db/migration/V003__vertical_slice_2_recorder.sql',
 'db/migrations/V003__vertical_slice_2_recorder.sql',
 'apps/web/app/workspaces/[workspaceId]/applications/[applicationId]/environments/[environmentId]/record/page.tsx',
 'apps/web/app/workspaces/[workspaceId]/applications/[applicationId]/scenarios/page.tsx',
 'contracts/openapi.yaml','docker-compose.yml'
]
errors=[]
for p in required:
    if not (root/p).exists(): errors.append(f'missing: {p}')

migration=(root/'db/migrations/V003__vertical_slice_2_recorder.sql').read_text()
for table in ['core.recording_session','core.test_scenario','core.scenario_version']:
    if table not in migration: errors.append(f'migration missing table: {table}')

compose=(root/'docker-compose.yml').read_text()
for marker in ['recorder:', '127.0.0.1:6080:6080', 'RECORDER_SERVICE_URL', 'postgres-data:/var/lib/postgresql']:
    if marker not in compose: errors.append(f'compose missing marker: {marker}')
if 'postgres-data:/var/lib/postgresql/data' in compose:
    errors.append('PostgreSQL 18 incompatible data mount path is present')

pom=(root/'services/control-plane/pom.xml').read_text()
if 'spring-boot-starter-flyway' not in pom: errors.append('Spring Boot 4 Flyway starter missing')
if '<artifactId>flyway-core</artifactId>' in pom: errors.append('legacy flyway-core dependency still present')

contract=(root/'contracts/openapi.yaml').read_text()
for marker in ['recording-sessions','/start:','/pause:','/resume:','/finish:','/cancel:','/scenarios:']:
    if marker not in contract: errors.append(f'OpenAPI missing marker: {marker}')
if yaml:
    try:
        yaml.safe_load((root/'docker-compose.yml').read_text())
        doc=yaml.safe_load(contract)
        if str(doc.get('openapi','')).split('.')[0] != '3': errors.append('OpenAPI document version invalid')
    except Exception as e: errors.append(f'YAML parse failed: {e}')

# Recorder security hygiene: the browser instrumentation must null sensitive values,
# while generated IR must use secret references instead of captured credential text.
instrumentation=(root/'services/recorder-service/app/recorder/instrumentation.py').read_text()
normalizer=(root/'services/recorder-service/app/recorder/normalizer.py').read_text()
if 'sensitive ? null' not in instrumentation: errors.append('sensitive input redaction marker missing')
if 'valueSource="secret"' not in normalizer: errors.append('secret reference normalization marker missing')

# Detect common accidental hard-coded credential assignments in source code.
patterns=[r'(?i)(?:password|passwd|secret|api[_-]?key)\s*=\s*["\'][^"\']{4,}["\']']
for p in root.rglob('*'):
    if not p.is_file() or p.suffix.lower() in {'.zip','.png','.jpg','.docx','.pdf'}: continue
    try: text=p.read_text(errors='ignore')
    except Exception: continue
    for pat in patterns:
        if re.search(pat,text) and p.name not in {'check_slice1.py','check_slice2.py'}:
            # local Docker database password is explicitly dev-only and is not an application credential.
            if 'local-dev-only-password' in text and p.name in {'docker-compose.yml','.env.example'}: continue
            errors.append(f'possible secret literal: {p.relative_to(root)}')

if errors:
    print('VERTICAL SLICE 2 VALIDATION: FAIL')
    for e in errors: print('-',e)
    sys.exit(1)
print('VERTICAL SLICE 2 VALIDATION: PASS')
print(f'Required files checked: {len(required)}')
print('Recorder lifecycle markers: present')
print('Automation IR persistence: present')
print('Sensitive input redaction markers: present')

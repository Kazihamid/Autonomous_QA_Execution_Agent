from pathlib import Path
import json, xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
required=[
 'apps/web/package.json','apps/web/app/page.tsx','services/control-plane/pom.xml',
 'services/control-plane/src/main/java/com/brac/automation/platform/ControlPlaneApplication.java',
 'services/ai-gateway/app/main.py','contracts/openapi.yaml','db/migrations/V001__foundation.sql',
 'infra/docker/docker-compose.yml','.github/workflows/ci.yml'
]
missing=[p for p in required if not (ROOT/p).exists()]
json.loads((ROOT/'apps/web/package.json').read_text())
ET.parse(ROOT/'services/control-plane/pom.xml')
text=(ROOT/'.env.example').read_text()
checks={
 'requiredFiles':not missing,
 'noCommittedPasswordValue':'POSTGRES_PASSWORD=\n' in text,
 'springBoot411':'<version>4.1.1</version>' in (ROOT/'services/control-plane/pom.xml').read_text(),
 'next1636':'"next": "16.3.6"' in (ROOT/'apps/web/package.json').read_text(),
 'java25':'<java.version>25</java.version>' in (ROOT/'services/control-plane/pom.xml').read_text(),
}
print(json.dumps({'missing':missing,'checks':checks},indent=2))
raise SystemExit(0 if all(checks.values()) else 2)

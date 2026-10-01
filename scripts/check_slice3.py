from pathlib import Path
import ast, json, re
root=Path(__file__).resolve().parents[1]
checks=[]
def ck(name,cond): checks.append((name,bool(cond)))
ck("V004 migration",(root/'db/migrations/V004__vertical_slice_3_codegen.sql').exists())
ck("code-generator service",(root/'services/code-generator-service/app/generator/core.py').exists())
ck("controller",(root/'services/control-plane/src/main/java/com/brac/automation/platform/codegen/CodeGeneratorController.java').exists())
ck("scenario UI",'Generate Code' in (root/'apps/web/app/workspaces/[workspaceId]/applications/[applicationId]/scenarios/[scenarioId]/page.tsx').read_text())
ck("implementation UI",(root/'apps/web/app/workspaces/[workspaceId]/applications/[applicationId]/scenarios/[scenarioId]/implementations/[implementationId]/page.tsx').exists())
ck("compose service",'code-generator:' in (root/'docker-compose.yml').read_text())
for p in (root/'services/code-generator-service/app').rglob('*.py'): ast.parse(p.read_text())
ck("python syntax",True)
failed=[n for n,v in checks if not v]
print(json.dumps({"checks":checks,"failed":failed},indent=2))
raise SystemExit(1 if failed else 0)

import json
from app.generator.core import generate_project

IR={
 "irSchemaVersion":"1.0.0","scenario":{"id":"s1","name":"User Login"},"configuration":{"browser":"chromium"},
 "parameters":{"username":{"type":"string","default":"qa-user"}},
 "elements":{
   "username":{"preferred":{"strategy":"label","value":"Username"},"alternatives":[]},
   "password":{"preferred":{"strategy":"label","value":"Password"},"alternatives":[]},
   "login":{"preferred":{"strategy":"testId","value":"login-button"},"alternatives":[]}
 },
 "steps":[
  {"id":"step-001","action":"navigate","url":"https://qa.example.com/login"},
  {"id":"step-002","action":"fill","element":"username","value":{"source":"parameter","reference":"username"}},
  {"id":"step-003","action":"fill","element":"password","value":{"source":"secret","reference":"LOGIN_PASSWORD"}},
  {"id":"step-004","action":"click","element":"login"}
 ],"metadata":{}
}

def req(target): return {"scenarioId":"s1","scenarioVersionId":"v1","scenarioVersion":1,"target":target,"automationIr":IR,"generatorVersion":"0.3.0","configuration":{}}

def test_playwright_is_deterministic_and_secret_safe():
    a=generate_project(req("PLAYWRIGHT_PYTEST")); b=generate_project(req("PLAYWRIGHT_PYTEST"))
    assert a["sourceHash"]==b["sourceHash"]
    source='\n'.join(x['content'] for x in a['files'] if x['path'] not in {'automation-ir.json','.env.example'})
    env=next(x['content'] for x in a['files'] if x['path']=='.env.example')
    assert 'LOGIN_PASSWORD' in source and 'qa.example.com' not in source
    assert 'BASE_URL=https://qa.example.com' in env and 'LOGIN_PASSWORD=' in env
    assert len(a['sourceMap'])==4

def test_selenium_is_deterministic_and_traceable():
    a=generate_project(req("SELENIUM_TESTNG")); b=generate_project(req("SELENIUM_TESTNG"))
    assert a["sourceHash"]==b["sourceHash"]
    source='\n'.join(x['content'] for x in a['files'] if x['path'] not in {'automation-ir.json','.env.example'})
    env=next(x['content'] for x in a['files'] if x['path']=='.env.example')
    assert 'IR-STEP: step-004' in source and 'qa.example.com' not in source
    assert 'BASE_URL=https://qa.example.com' in env and 'username=' in env and 'LOGIN_PASSWORD=' in env
    assert len(a['sourceMap'])==4

def test_keyboard_without_locator_uses_global_keyboard_and_does_not_block_generation():
    ir=json.loads(json.dumps(IR))
    ir['elements']['body']={'key':'body','description':'body','preferred':None,'alternatives':[]}
    ir['steps'].append({'id':'step-005','action':'keyboard','element':'body','key':'Enter'})
    req_pw={'scenarioId':'s1','scenarioVersionId':'v1','scenarioVersion':1,'target':'PLAYWRIGHT_PYTEST','automationIr':ir,'generatorVersion':'0.3.2','configuration':{}}
    out=generate_project(req_pw)
    source='\n'.join(x['content'] for x in out['files'] if x['path'].startswith('tests/'))
    assert 'page.keyboard.press("Enter")' in source

    req_java=dict(req_pw); req_java['target']='SELENIUM_TESTNG'
    out_java=generate_project(req_java)
    source_java='\n'.join(x['content'] for x in out_java['files'] if x['path'].endswith('.java'))
    assert 'driver.switchTo().activeElement().sendKeys(Keys.ENTER);' in source_java

def test_legacy_element_with_null_preferred_uses_meaningful_description_fallback():
    ir=json.loads(json.dumps(IR))
    ir['elements']['dashboard']={'key':'dashboard','description':'EDMS Dashboard','preferred':None,'alternatives':[]}
    ir['steps'].append({'id':'step-005','action':'click','element':'dashboard'})
    request={'scenarioId':'s1','scenarioVersionId':'v1','scenarioVersion':1,'target':'PLAYWRIGHT_PYTEST','automationIr':ir,'generatorVersion':'0.3.2','configuration':{}}
    out=generate_project(request)
    source='\n'.join(x['content'] for x in out['files'])
    assert 'get_by_text("EDMS Dashboard", exact=True)' in source


def _ir_with_overlay():
    import copy
    ir=copy.deepcopy(IR)
    ir["elements"]["overlay"]={"preferred":{"strategy":"id","value":"overlay"},"alternatives":[]}
    ir["steps"].append({"id":"step-005","action":"click","element":"overlay"})
    return ir

def test_transient_overlay_click_is_skipped_in_both_targets():
    for target in ("PLAYWRIGHT_PYTEST","SELENIUM_TESTNG"):
        r=req(target); r["automationIr"]=_ir_with_overlay()
        out=generate_project(r)
        source='\n'.join(x['content'] for x in out['files'] if x['path'].endswith(('.py','.java')))
        assert 'overlay' not in source.replace('# Skipped recorder container click for overlay','').replace('// Skipped recorder container click for overlay','').lower()
        assert 'Skipped recorder container click for overlay' in source

def test_real_button_with_loading_class_is_not_skipped():
    from app.generator.core import _is_transient_overlay
    assert not _is_transient_overlay({"preferred":{"strategy":"css","value":"button.btn.loading"}})
    assert _is_transient_overlay({"preferred":{"strategy":"css","value":"div.modal-backdrop"}})


def test_login_redirect_uri_is_rebased_to_run_environment_and_progress_printed():
    import copy
    ir=copy.deepcopy(IR)
    import base64
    state=base64.b64encode(b"time:1791267747833|url:null").decode()
    ir["steps"][0]["url"]=("https://env27.erp.bracits.net/idp/realms/brac/protocol/openid-connect/auth"
        "?client_id=erp&redirect_uri=https%3A%2F%2Fenv27.erp.bracits.net&state="+state+"&response_type=code")
    r=req("PLAYWRIGHT_PYTEST"); r["automationIr"]=ir
    out=generate_project(r)
    test=next(x['content'] for x in out['files'] if x['path'].startswith('tests/test_'))
    assert '_rebase(' in test and 'def _rebase' in test
    assert '[IR-STEP] step-001 navigate (1/4)' in test
    ns={}
    import re
    src=test[test.index('def _rebase'):test.index('def test_')]
    exec('from urllib.parse import quote_plus\n'+src, ns)
    prefix=re.search(r'_rebase\((".*?"), ("[^"]*"), base_url\)', test)
    recorded=eval(prefix.group(2)); text=eval(prefix.group(1))
    rebased=ns['_rebase'](text, recorded, "https://erpstaging.brac.net/")
    assert 'env27' not in rebased and 'erpstaging.brac.net' in rebased

def test_java_navigate_rebases_origin():
    import copy
    ir=copy.deepcopy(IR)
    ir["steps"][0]["url"]="https://env27.erp.bracits.net/auth?redirect_uri=https%3A%2F%2Fenv27.erp.bracits.net"
    r=req("SELENIUM_TESTNG"); r["automationIr"]=ir
    out=generate_project(r)
    src='\n'.join(x['content'] for x in out['files'] if x['path'].endswith('.java'))
    assert 'Config.rebase(' in src


def test_python_conftest_reports_failure_diagnostics():
    import ast
    out = generate_project(req("PLAYWRIGHT_PYTEST"))
    conf = next(x['content'] for x in out['files'] if x['path'] == 'tests/conftest.py')
    ast.parse(conf)
    assert "pytest_runtest_makereport" in conf and "[IR-FAIL]" in conf and "select elements on page" in conf


def test_python_waits_for_sign_in_before_next_navigation():
    import ast, copy
    ir = copy.deepcopy(IR)
    ir["steps"] = ir["steps"] + [{"id": "step-005", "action": "navigate", "url": "https://qa.example.com/orders"}]
    r = req("PLAYWRIGHT_PYTEST"); r["automationIr"] = ir
    out = generate_project(r)
    test = next(x['content'] for x in out['files'] if x['path'].startswith('tests/test_'))
    ast.parse(test)
    assert "def _settle(" in test and "Sign-in did not complete" in test
    body = test.split("# IR-STEP: step-005")[1]
    assert body.index("_settle(page)") < body.index("_goto_with_retry")
    # no settle when the previous step is not a click/keyboard
    assert test.split("# IR-STEP: step-002")[1].split("# IR-STEP: step-003")[0].count("_settle(page)") == 0


def test_numeric_table_target_selects_first_row_not_the_recorded_pin():
    import ast, copy
    ir = copy.deepcopy(IR)
    ir["elements"]["00155708"] = {"preferred": {"strategy": "text", "value": "00155708"}, "alternatives": []}
    ir["steps"] = ir["steps"] + [{"id": "step-005", "action": "click", "element": "00155708"}]
    r = req("PLAYWRIGHT_PYTEST"); r["automationIr"] = ir
    out = generate_project(r)
    test = next(x['content'] for x in out['files'] if x['path'].startswith('tests/test_'))
    ast.parse(test)
    body = test.split("# IR-STEP: step-005")[1]
    assert "tbody tr:not(:has(td.dataTables_empty))" in body and "[IR-ROW]" in body
    assert "press_sequentially" not in body  # the recorded PIN is no longer typed into the search box
    assert 'for _how in ("link", "cell", "row", "double")' in body and "row picked by" in body and "[IR-ROW-HTML]" in body

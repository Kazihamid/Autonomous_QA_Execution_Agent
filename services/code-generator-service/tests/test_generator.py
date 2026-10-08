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


def test_stay_on_admin_swaps_the_auth_landing_page_for_the_admin_page():
    from app.generator import core
    ns = {}
    exec(core._SETTLE_HELPER, ns)

    class Page:
        def __init__(self, url):
            self.url = url
            self.went = []
        def goto(self, url, wait_until=None):
            self.went.append(url)
            self.url = url
        def wait_for_load_state(self, state=None, timeout=None):
            pass
        def wait_for_timeout(self, ms):
            pass

    # asked for /admin/login, the site answered with its /auth/login landing page
    page = Page("https://er-panel-stg.bracits.net/auth/login?next=1")
    ns["_stay_on_admin"](page, "https://er-panel-stg.bracits.net/admin/login")
    assert page.went == ["https://er-panel-stg.bracits.net/admin/login?next=1"]

    # already on the admin page: nothing happens
    page = Page("https://er-panel-stg.bracits.net/admin/login")
    ns["_stay_on_admin"](page, "https://er-panel-stg.bracits.net/admin/login")
    assert page.went == []

    # a non-admin request that lands on an /auth/ page is left alone
    page = Page("https://erp.example.net/auth/realms/brac/protocol/openid-connect/auth")
    ns["_stay_on_admin"](page, "https://erp.example.net/idp/realms/brac/protocol/openid-connect/auth")
    assert page.went == []


def test_navigation_steps_call_stay_on_admin():
    out = generate_project(req("PLAYWRIGHT_PYTEST"))
    test = next(x["content"] for x in out["files"] if x["path"].startswith("tests/test_"))
    assert "_stay_on_admin(page, _target)" in test and "def _stay_on_admin(" in test


def test_click_fallback_to_navigation_is_reported_in_the_run_output():
    import ast, copy
    ir = copy.deepcopy(IR)
    ir["steps"][-1]["metadata"] = {"navigatedTo": "https://qa.example.com/done"}
    r = req("PLAYWRIGHT_PYTEST"); r["automationIr"] = ir
    out = generate_project(r)
    test = next(x["content"] for x in out["files"] if x["path"].startswith("tests/test_"))
    ast.parse(test)
    assert "[IR-WARN] step-004" in test and "did not happen" in test
    assert test.index("[IR-WARN] step-004") < test.index('page.goto(base_url.rstrip("/") + "/done")')


def _date_ir(extra_step=None, yes_role="button"):
    import copy
    ir = copy.deepcopy(IR)
    ir["elements"]["last-working-date"] = {"preferred": {"strategy": "role", "value": {"role": "textbox", "name": "DD-MM-YYYY"}}, "alternatives": [{"strategy": "id", "value": "lastWorkingDate"}]}
    ir["elements"]["yes"] = {"preferred": {"strategy": "role", "value": {"role": yes_role, "name": "Yes"}}, "alternatives": []}
    ir["steps"] = ir["steps"] + [
        {"id": "step-005", "action": "click", "element": "last-working-date"},
        {"id": "step-006", "action": "click", "element": "yes", "metadata": {"navigatedTo": "https://qa.example.com/list"}},
    ]
    return ir


def _test_source(ir):
    import ast
    r = req("PLAYWRIGHT_PYTEST"); r["automationIr"] = ir
    out = generate_project(r)
    test = next(x["content"] for x in out["files"] if x["path"].startswith("tests/test_"))
    ast.parse(test)
    return test


def test_click_on_an_empty_date_field_sets_a_future_date():
    test = _test_source(_date_ir())
    body = test.split("# IR-STEP: step-005")[1].split("# IR-STEP: step-006")[0]
    assert "import datetime" in test
    assert '.strftime("%d-%m-%Y")' in body and "[IR-DATE] step-005" in body
    assert "if not any(ch.isdigit() for ch in _field.input_value()):" in body and "press_sequentially" in body and '_field.press("Tab")' in body and "Escape" not in body.replace("not Escape", "")  # an input mask such as __-__-____ counts as empty; Escape would undo the typed value
    assert "_field = page.locator(" in body and "lastWorkingDate" in body  # the field's own id, not the shared placeholder


def test_missing_button_fails_instead_of_opening_another_page_but_links_still_fall_back():
    button = _test_source(_date_ir(yes_role="button")).split("# IR-STEP: step-006")[1]
    assert 'page.goto(base_url.rstrip("/") + "/list")' not in button and "dispatch_event" in button
    link = _test_source(_date_ir(yes_role="link")).split("# IR-STEP: step-006")[1]
    assert 'page.goto(base_url.rstrip("/") + "/list")' in link


def _employee_ir(with_navigate=False):
    import copy
    ir = copy.deepcopy(IR)
    ir["elements"]["search-btn"] = {"preferred": {"strategy": "id", "value": "searchBtn"}, "alternatives": []}
    ir["elements"]["00155707"] = {"preferred": {"strategy": "text", "value": "00155707"}, "alternatives": []}
    ir["elements"]["create-button"] = {"preferred": {"strategy": "id", "value": "create-button-x"}, "alternatives": []}
    ir["elements"]["yes"] = {"preferred": {"strategy": "role", "value": {"role": "button", "name": "Yes"}}, "alternatives": []}
    ir["steps"] = ir["steps"] + [
        {"id": "step-005", "action": "click", "element": "search-btn"},
        {"id": "step-006", "action": "click", "element": "00155707"},
        {"id": "step-007", "action": "click", "element": "create-button"},
        {"id": "step-008", "action": "click", "element": "yes"},
    ]
    return ir


def test_employee_steps_are_retried_with_the_next_row_when_the_application_rejects_the_proposal():
    test = _test_source(_employee_ir())
    assert "def _attempt(_skip):" in test and "_problem = _attempt(_tries)" in test and "[IR-RETRY]" in test and "_dismiss_popups(page)" in test
    block = test.split("def _attempt(_skip):")[1].split("_tries = 0")[0]
    for step in ("step-005", "step-006", "step-007", "step-008"):
        assert "# IR-STEP: " + step in block
    assert "# IR-STEP: step-004" not in block
    assert "_row = _rows.nth(_skip)" in block and "_attach_documents(page)" in block
    assert block.index("_attach_documents(page)") < block.index("_wait_for_confirm_or_error(page)") < block.index("# IR-STEP: step-008") + 400
    assert block.rstrip().endswith("return _creation_problem(page)")
    assert "_skip = 0" in test.split("def _attempt")[0]


def test_source_map_lines_still_point_at_their_steps_after_the_retry_wrapper():
    import json
    r = req("PLAYWRIGHT_PYTEST"); r["automationIr"] = _employee_ir()
    out = generate_project(r)
    test = next(f["content"] for f in out["files"] if f["path"].startswith("tests/test_"))
    lines = test.split("\n")
    for sid, entry in out["sourceMap"].items():
        assert "# IR-STEP: " + sid in lines[entry["line"] - 1], (sid, entry)


def test_no_retry_wrapper_without_a_row_pick_and_a_save_click():
    test = _test_source(_date_ir())
    assert "def _attempt" not in test and "_skip = 0" in test


def test_save_click_attaches_the_sample_document_and_browse_opens_the_file_picker():
    import copy
    test = _test_source(_employee_ir())
    assert "def _sample_document" in test and "import tempfile" in test and "%PDF-1.4" in test
    assert "# IR-STEP: step-007" in test and test.split("# IR-STEP: step-007")[1].lstrip().split("\n")[1].strip() == "_attach_documents(page)" or "_attach_documents(page)" in test.split("# IR-STEP: step-007")[1].split("# IR-STEP: step-008")[0]
    ir = copy.deepcopy(IR)
    ir["elements"]["browse"] = {"description": "Browse", "preferred": {"strategy": "role", "value": {"role": "button", "name": "Browse"}}, "alternatives": []}
    ir["steps"] = ir["steps"] + [{"id": "step-005", "action": "click", "element": "browse"}]
    body = _test_source(ir).split("# IR-STEP: step-005")[1]
    assert "_click_and_choose_file(page, " in body


def test_recorded_second_sign_in_is_skipped_when_the_browser_is_already_signed_in():
    import copy
    ir = copy.deepcopy(IR)
    ir["steps"] = [
        {"id": "step-001", "action": "navigate", "url": "https://qa.example.com/idp/realms/x/protocol/openid-connect/auth?client_id=erp"},
        {"id": "step-002", "action": "fill", "element": "username", "value": {"source": "parameter", "reference": "username"}},
        {"id": "step-003", "action": "click", "element": "login"},
        {"id": "step-004", "action": "navigate", "url": "https://qa.example.com/idp/realms/x/login-actions/authenticate?execution=1"},
        {"id": "step-005", "action": "fill", "element": "password", "value": {"source": "secret", "reference": "LOGIN_PASSWORD"}},
        {"id": "step-006", "action": "click", "element": "login"},
        {"id": "step-007", "action": "navigate", "url": "https://qa.example.com/dashboard"},
    ]
    r = req("PLAYWRIGHT_PYTEST"); r["automationIr"] = ir
    out = generate_project(r)
    import ast
    test = next(f["content"] for f in out["files"] if f["path"].startswith("tests/test_"))
    ast.parse(test)
    block = test.split("    _settle(page)\n    if _SIGN_IN_URL.search(page.url):")[1].split("    else:")[0]
    assert "# IR-STEP: step-004" in block and "# IR-STEP: step-006" in block and "# IR-STEP: step-007" not in block and "# IR-STEP: step-002" not in block
    assert "[IR-SKIP] step-004 to step-006" in test
    lines = test.split("\n")
    for sid, entry in out["sourceMap"].items():
        assert "# IR-STEP: " + sid in lines[entry["line"] - 1], (sid, entry)

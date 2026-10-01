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

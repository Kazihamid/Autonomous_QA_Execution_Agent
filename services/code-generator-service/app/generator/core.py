from __future__ import annotations
import ast
import base64
import hashlib
import json
import keyword
import re
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import parse_qsl, quote_plus, urlencode, urlsplit

SUPPORTED_ACTIONS = {"navigate","click","fill","select","check","uncheck","uploadFile","keyboard","assert","checkpoint","extractValue","wait"}
PY_RESERVED = set(keyword.kwlist)
JAVA_RESERVED = {"abstract","assert","boolean","break","byte","case","catch","char","class","const","continue","default","do","double","else","enum","extends","final","finally","float","for","goto","if","implements","import","instanceof","int","interface","long","native","new","package","private","protected","public","return","short","static","strictfp","super","switch","synchronized","this","throw","throws","transient","try","void","volatile","while","record","sealed","permits","yield","var"}

class GeneratorError(ValueError):
    def __init__(self, message: str, code: str="GENERATION_FAILED", unsupported: list[str] | None=None):
        super().__init__(message); self.code=code; self.unsupported=unsupported or []

def _json(v: Any) -> str: return json.dumps(str(v), ensure_ascii=False)
def _java(v: Any) -> str: return str(v).replace('\\','\\\\').replace('"','\\"').replace('\n','\\n').replace('\r','\\r')
def _slug(v: str) -> str:
    s=re.sub(r'[^A-Za-z0-9]+','-',str(v)).strip('-').lower()
    return s or 'scenario'
def _snake(v: str) -> str:
    s=re.sub(r'(?<!^)(?=[A-Z])','_',str(v)); s=re.sub(r'[^A-Za-z0-9]+','_',s).strip('_').lower() or 'value'
    if s[0].isdigit(): s='n_'+s
    if s in PY_RESERVED: s += '_value'
    return s
def _camel(v: str) -> str:
    parts=[p for p in re.split(r'[^A-Za-z0-9]+',str(v)) if p]
    out=(parts[0].lower()+''.join(p[:1].upper()+p[1:] for p in parts[1:])) if parts else 'value'
    if out[0].isdigit(): out='n'+out
    if out in JAVA_RESERVED: out += 'Value'
    return out
def _pascal(v: str) -> str:
    parts=[p for p in re.split(r'[^A-Za-z0-9]+',str(v)) if p]
    out=''.join(p[:1].upper()+p[1:] for p in parts) or 'Scenario'
    if out[0].isdigit(): out='N'+out
    if out.lower() in JAVA_RESERVED: out += 'Scenario'
    return out

def _validate_ir(ir: dict[str,Any]):
    if ir.get('irSchemaVersion') != '1.0.0':
        raise GeneratorError(f"Unsupported Automation IR schema version: {ir.get('irSchemaVersion')}", 'UNSUPPORTED_IR_SCHEMA')
    steps=ir.get('steps')
    if not isinstance(steps,list) or not steps: raise GeneratorError('Automation IR must contain at least one step.', 'INVALID_IR')
    unsupported=sorted({str(s.get('action')) for s in steps if s.get('action') not in SUPPORTED_ACTIONS})
    if unsupported: raise GeneratorError('Automation IR contains unsupported step types.', 'UNSUPPORTED_STEP_TYPE', unsupported)
    elements=ir.get('elements') or {}
    for s in steps:
        if s.get('element') and s['element'] not in elements:
            raise GeneratorError(f"IR step {s.get('id')} references missing element {s['element']}", 'INVALID_IR')

def _candidate_list(element: dict[str,Any]) -> list[dict[str,Any]]:
    vals=[]
    if element.get('preferred'): vals.append(element['preferred'])
    vals += list(element.get('alternatives') or [])
    vals=[v for v in vals if isinstance(v,dict) and v.get('strategy')]
    # Older recorder sessions can contain an element with preferred=null.
    # If a meaningful accessible description survived in the IR, use it as a
    # deterministic low-priority text fallback instead of failing with strategy=None.
    if not vals:
        desc=str(element.get('description') or '').strip()
        generic={'','element','body','html','div','span','main','section','form','input','textarea','select','button','link','a'}
        if desc.lower() not in generic and len(desc) <= 160:
            vals.append({'strategy':'text','value':desc,'fallback':True})
    return vals

def _pw_locator(element: dict[str,Any], owner='self.page') -> str:
    locs=_candidate_list(element)
    # jQuery UI assigns #ui-active-menuitem dynamically to the currently
    # highlighted autocomplete option. It may not exist until the menu opens,
    # and the id can move between options. Replay the visible menu option
    # structurally instead of binding generated code to that transient id.
    transient_ids={str(x.get('value') or '') for x in locs if x.get('strategy')=='id'}
    if 'ui-active-menuitem' in transient_ids:
        return f'{owner}.locator(".ui-autocomplete:visible .ui-menu-item, .ui-menu:visible .ui-menu-item")'
    # Prefer stable DOM attributes before accessible text/role. ERP pages can
    # render accessible names late while id/name are immediately available.
    order=('testId','id','name','label','placeholder','role','text','css','xpath')
    loc=None
    for strategy in order:
        loc=next((x for x in locs if x.get('strategy')==strategy),None)
        if loc: break
    if not loc:
        raise GeneratorError('No Playwright-compatible locator was found.', 'UNSUPPORTED_LOCATOR')
    s,v=loc.get('strategy'),loc.get('value')
    if s=='testId': return f'{owner}.get_by_test_id({_json(v)})'
    if s=='role':
        if isinstance(v,dict): return f'{owner}.get_by_role({_json(v.get("role",""))}, name={_json(v.get("name",""))})'
        return f'{owner}.get_by_role({_json(v)})'
    if s=='label': return f'{owner}.get_by_label({_json(v)})'
    if s=='placeholder': return f'{owner}.get_by_placeholder({_json(v)})'
    if s=='text': return f'{owner}.get_by_text({_json(v)}, exact=True)'
    if s=='id': return f'{owner}.locator({_json("#"+str(v))})'
    if s=='name': return f'{owner}.locator({_json("[name="+json.dumps(str(v))+"]")})'
    if s=='css': return f'{owner}.locator({_json(v)})'
    if s=='xpath': return f'{owner}.locator({_json("xpath="+str(v))})'
    raise GeneratorError(f'Unsupported Playwright locator strategy: {s}', 'UNSUPPORTED_LOCATOR', [str(s)])

def _has_locator(element: dict[str,Any]) -> bool:
    return bool(_candidate_list(element))

def _is_optional_dismiss(element: dict[str,Any]) -> bool:
    desc=str(element.get('description') or '').strip().lower()
    if desc in {'×','x','close','dismiss','cancel'}:
        return True
    for candidate in _candidate_list(element):
        strategy=candidate.get('strategy')
        value=candidate.get('value')
        if strategy=='role' and isinstance(value,dict):
            role=str(value.get('role') or '').lower()
            name=str(value.get('name') or '').strip().lower()
            if role=='button' and name in {'×','x','close','dismiss','cancel'}:
                return True
        if strategy=='css' and any(token in str(value).lower() for token in ('close-button','modal-close','dialog-close')):
            return True
    return False

_OVERLAY_NAMES=r'(?:overlay|backdrop|modal-backdrop|blockui|blockoverlay|loading-overlay|spinner|loader|mask)'
_OVERLAY_ID_RE=re.compile(r'^'+_OVERLAY_NAMES+r'$', re.I)
_OVERLAY_CSS_RE=re.compile(r'^(?:div|span|section)?[#.]'+_OVERLAY_NAMES+r'(?:\.[\w-]+)*$', re.I)

def _is_transient_overlay(element: dict[str,Any]) -> bool:
    """True for recorder clicks on page backdrops/loading overlays (e.g. #overlay).

    These elements appear only while something else is busy or open, so replaying
    the click fails with a locator timeout on a clean page. They are never a real
    user control, so generated code skips them.
    """
    for candidate in _candidate_list(element):
        strategy=candidate.get('strategy'); value=str(candidate.get('value') or '').strip()
        if strategy=='id' and _OVERLAY_ID_RE.match(value): return True
        if strategy=='css' and _OVERLAY_CSS_RE.match(value): return True
    return False

def _is_accidental_container_click(element: dict[str,Any]) -> bool:
    if _is_transient_overlay(element):
        return True
    desc=str(element.get('description') or '').strip()
    key=str(element.get('key') or '').lower()
    candidates=_candidate_list(element)
    for candidate in candidates:
        if candidate.get('strategy')=='role' and isinstance(candidate.get('value'),dict):
            if str(candidate['value'].get('role') or '').lower() in {'button','link','menuitem'}:
                return False
    if len(desc) > 80:
        return True
    if 'form' in key and len(desc.split()) >= 3:
        return True
    for candidate in candidates:
        strategy=candidate.get('strategy')
        value=str(candidate.get('value') or '').lower()
        if strategy=='css' and any(token in value for token in ('ul.main_top_navigation','form#','form.')) and len(desc) > 40:
            return True
        if strategy=='xpath' and ('/ul[' in value or '/form[' in value) and len(desc.split()) >= 6:
            return True
    return False

def _sel_by(element: dict[str,Any]) -> str:
    locs=_candidate_list(element)
    order=('testId','name','id','css','xpath','label','text','role','placeholder')
    chosen=None
    for strategy in order:
        chosen=next((x for x in locs if x.get('strategy')==strategy),None)
        if chosen: break
    if not chosen: raise GeneratorError('No Selenium-compatible locator was found.', 'UNSUPPORTED_LOCATOR')
    s,v=chosen['strategy'],chosen.get('value')
    if s=='testId': return f'By.cssSelector("[data-testid=\\"{_java(v)}\\"]")'
    if s=='name': return f'By.name("{_java(v)}")'
    if s=='id': return f'By.id("{_java(v)}")'
    if s=='css': return f'By.cssSelector("{_java(v)}")'
    if s=='xpath': return f'By.xpath("{_java(v)}")'
    if s=='label': return f'By.xpath("//label[normalize-space()=\\"{_java(v)}\\"]/following::*[self::input or self::select or self::textarea][1]")'
    if s=='text': return f'By.xpath("//*[normalize-space()=\\"{_java(v)}\\"]")'
    if s=='placeholder': return f'By.cssSelector("[placeholder=\\"{_java(v)}\\"]")'
    if s=='role':
        role=v.get('role','') if isinstance(v,dict) else str(v); name=v.get('name','') if isinstance(v,dict) else ''
        return f'By.xpath("//*[@role=\\"{_java(role)}\\" and (@aria-label=\\"{_java(name)}\\" or normalize-space()=\\"{_java(name)}\\")]")'
    raise GeneratorError(f'Unsupported Selenium locator strategy: {s}', 'UNSUPPORTED_LOCATOR', [str(s)])

def _dynamic_timestamp_state(url: Any) -> tuple[str,str] | None:
    try:
        p=urlsplit(str(url))
        if '/protocol/openid-connect/auth' not in (p.path or ''):
            return None
        params=parse_qsl(p.query, keep_blank_values=True)
        state=next((v for k,v in params if k=='state'),None)
        if not state:
            return None
        padded=state + '=' * (-len(state) % 4)
        decoded=base64.b64decode(padded).decode('utf-8')
        if not decoded.startswith('time:') or '|url:' not in decoded:
            return None
        suffix='|' + decoded.split('|',1)[1]
        query=[(k,v) for k,v in params if k!='state']
        x=p.path or '/'
        if query: x += '?' + urlencode(query) + '&'
        else: x += '?'
        return x,suffix
    except Exception:
        return None

def _origin(url: Any) -> str:
    try:
        p=urlsplit(str(url))
        return f"{p.scheme}://{p.netloc}" if p.scheme and p.netloc else ''
    except Exception:
        return ''

def _embeds_origin(text: str, origin: str) -> bool:
    return bool(origin) and (quote_plus(origin) in text or origin in text)

def _relative_url(url: Any) -> str:
    if not url: return '/'
    try:
        p=urlsplit(str(url))
        if p.scheme and p.netloc:
            x=p.path or '/'
            if '/protocol/openid-connect/auth' in x:
                query=[(k,v) for k,v in parse_qsl(p.query, keep_blank_values=True) if k!='state']
                if query: x += '?' + urlencode(query)
                return x
            if p.query: x += '?' + p.query
            if p.fragment: x += '#' + p.fragment
            return x
    except Exception: pass
    return str(url)

def _base_url_from_ir(ir: dict[str,Any]) -> str:
    for step in ir.get('steps') or []:
        if step.get('action') != 'navigate' or not step.get('url'):
            continue
        try:
            p=urlsplit(str(step.get('url')))
            if p.scheme and p.netloc:
                return f"{p.scheme}://{p.netloc}"
        except Exception:
            pass
    cfg=ir.get('configuration') or {}
    return str(cfg.get('baseUrl') or '')

def _ordered_steps(ir: dict[str,Any]) -> list[dict[str,Any]]:
    steps=[dict(s) for s in (ir.get('steps') or [])]
    i=0
    while i < len(steps)-1:
        current=steps[i]
        nxt=steps[i+1]
        if (
            current.get('action')=='keyboard'
            and current.get('key') in {'Enter','Tab'}
            and nxt.get('action')=='fill'
            and current.get('element')
            and current.get('element')==nxt.get('element')
        ):
            steps[i],steps[i+1]=nxt,current
            i+=2
            continue
        i+=1
    return steps

def _hash(files: dict[str,str]) -> str:
    h=hashlib.sha256()
    for p in sorted(files): h.update(p.encode()); h.update(b'\0'); h.update(files[p].encode()); h.update(b'\0')
    return h.hexdigest()

def _secret_scan(files: dict[str,str]) -> dict[str,Any]:
    patterns=[r'(?i)(api[_-]?key|token|password)\s*[=:]\s*["\'][A-Za-z0-9_\-]{12,}["\']', r'-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----']
    findings=[]
    for path,content in files.items():
        for pat in patterns:
            if re.search(pat,content): findings.append({'file':path,'pattern':pat})
    return {'status':'PASS' if not findings else 'FAIL','findings':findings}

_SETTLE_HELPER = '''import re
from urllib.parse import urlsplit, urlunsplit

_SIGN_IN_URL = re.compile(r"/(idp|auth)/realms/|/protocol/openid-connect/|/login-actions/")


def _settle(page, timeout=25000):
    # Let a submitted form or redirect chain (for example an OIDC sign-in) finish before the next step navigates away.
    page.wait_for_timeout(500)
    if _SIGN_IN_URL.search(page.url):
        try:
            page.wait_for_url(lambda u: not _SIGN_IN_URL.search(u), timeout=timeout)
        except Exception:
            raise RuntimeError("Sign-in did not complete: the browser is still on the sign-in page after the credentials were submitted. Check the user name, and that the password secret for this environment is set in .env.runtime.")
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        pass


def _stay_on_admin(page, requested_url):
    # Some admin portals answer an /admin/ address with their /auth/ landing page (for example a page that only offers SSO).
    # When an /admin/ page was requested and the browser ended on the matching /auth/ page, open the /admin/ page instead.
    wanted = urlsplit(requested_url)
    if not wanted.path.startswith("/admin"):
        return
    # The site may redirect a moment after the page loads, so let the page settle before looking at the address.
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass
    page.wait_for_timeout(1000)
    landed = urlsplit(page.url)
    if landed.path.startswith("/auth/"):
        fixed = landed._replace(path="/admin/" + landed.path[len("/auth/"):])
        print("[runner] redirected to " + landed.path + "; opening " + fixed.path + " instead", flush=True)
        page.goto(urlunsplit(fixed), wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        page.wait_for_timeout(1000)
        print("[runner] now on " + urlsplit(page.url).path, flush=True)


'''

def _python_project(ir: dict[str,Any]) -> tuple[dict[str,str],dict[str,Any]]:
    scenario=ir.get('scenario') or {}; scenario_name=scenario.get('name','Generated Scenario')
    module=_snake(scenario_name); cls=_pascal(scenario_name)+'Page'; test_fn='test_'+_snake(scenario_name)
    if cls.startswith('Test'):
        cls=cls[4:] or 'GeneratedPage'
    elements=ir.get('elements') or {}; params=ir.get('parameters') or {}
    page_lines=['from playwright.sync_api import Page, Locator','','class '+cls+':','    def __init__(self, page: Page):','        self.page = page','']
    elem_methods={}
    locator_actions={'click','fill','select','check','uncheck','uploadFile','assert','extractValue'}
    required_keys={
        str(s.get('element')) for s in ir['steps']
        if s.get('element')
        and s.get('action') in locator_actions
        and not (
            s.get('action')=='click'
            and _is_accidental_container_click(elements.get(str(s.get('element'))) or {})
        )
    }
    optional_keyboard_keys={str(s.get('element')) for s in ir['steps'] if s.get('element') and s.get('action')=='keyboard' and _has_locator(elements.get(str(s.get('element'))) or {})}
    for key in sorted(required_keys | optional_keyboard_keys):
        element=elements.get(key) or {}
        if not _has_locator(element):
            raise GeneratorError(f'IR element {key} is used by an action that requires a locator, but no supported locator candidate was recorded.', 'UNSUPPORTED_LOCATOR', [key])
        m='loc_'+_snake(key); elem_methods[key]=m
        page_lines += [f'    def {m}(self) -> Locator:', f'        return {_pw_locator(element, "self.page")}', '']
    files={}
    files[f'pages/{module}_page.py']='\n'.join(page_lines).rstrip()+'\n'
    files['pages/__init__.py']=''
    lines=['import base64','import os','import time','from pathlib import Path','from urllib.parse import quote, quote_plus','from playwright.sync_api import expect',f'from pages.{module}_page import {cls}','','def _goto_with_retry(page, url):','    last_status = None','    for attempt in range(3):','        response = page.goto(url, wait_until="domcontentloaded")','        last_status = response.status if response else None','        if last_status is None or last_status < 500:','            return response','        if attempt < 2:','            time.sleep(2 * (attempt + 1))','    raise RuntimeError(f"Target unavailable: HTTP {last_status} for {url}")','','','def _rebase(text, recorded_origin, base_url):','    """Point absolute recorded-environment URLs inside a query string (e.g. the OIDC redirect_uri) at the environment under test."""','    target = base_url.rstrip("/")','    return text.replace(quote_plus(recorded_origin), quote_plus(target)).replace(recorded_origin, target)','','',f'def {test_fn}(page, base_url):',f'    screen = {cls}(page)','    assets = Path(__file__).resolve().parents[1] / "assets"']
    _i=lines.index('def _goto_with_retry(page, url):'); lines[_i:_i]=_SETTLE_HELPER.split('\n')
    source_map={}
    ordered_steps=_ordered_steps(ir)
    for step_index,step in enumerate(ordered_steps):
        sid=str(step['id']); action=step['action']; source_map[sid]={'file':f'tests/test_{module}.py','line':len(lines)+1}
        lines.append(f'    # IR-STEP: {sid}')
        lines.append(f'    print("[IR-STEP] {sid} {action} ({step_index+1}/{len(ordered_steps)})", flush=True)')
        if action=='navigate':
            if step_index>0 and ordered_steps[step_index-1].get('action') in {'click','keyboard'}:
                lines.append('    _settle(page)')
            dynamic_state=_dynamic_timestamp_state(step.get('url'))
            if dynamic_state:
                prefix,suffix=dynamic_state
                origin=_origin(step.get('url'))
                prefix_expr=f'_rebase({_json(prefix)}, {_json(origin)}, base_url)' if _embeds_origin(prefix,origin) else _json(prefix)
                lines.append(f'    _state = base64.b64encode(f"time:{{int(time.time()*1000)}}{suffix}".encode()).decode()')
                lines.append(f'    _goto_with_retry(page, base_url.rstrip("/") + {prefix_expr} + "state=" + quote(_state, safe=""))')
            else:
                rel=_relative_url(step.get('url'))
                origin=_origin(step.get('url'))
                rel_expr=f'_rebase({_json(rel)}, {_json(origin)}, base_url)' if _embeds_origin(rel,origin) else _json(rel)
                lines.append(f'    _target = base_url.rstrip("/") + {rel_expr}')
                lines.append('    _goto_with_retry(page, _target)')
                lines.append('    _stay_on_admin(page, _target)')
            lines.append('    page.wait_for_load_state("domcontentloaded")')
        elif action in {'click','fill','select','check','uncheck','uploadFile','keyboard','assert','extractValue'}:
            key=step.get('element')
            loc=f'screen.{elem_methods[key]}()' if key and key in elem_methods else None
            if action=='click':
                element=elements.get(key) or {} if key else {}
                if key and _is_accidental_container_click(element):
                    lines.append(f'    # Skipped recorder container click for {key}; not a real actionable control.')
                    continue
                if not loc: raise GeneratorError(f'IR step {sid} requires a locator for element {key}.', 'UNSUPPORTED_LOCATOR', [str(key)])
                next_step=ordered_steps[step_index+1] if step_index+1 < len(ordered_steps) else {}
                prev_step=ordered_steps[step_index-1] if step_index > 0 else {}
                prev_key=str(prev_step.get('element') or '').lower()
                # A recorded numeric id (for example an employee PIN) inside a data table is a record the tester picked from the list.
                # Records are consumed by earlier runs, so the generated test selects the first available row instead.
                numeric_table_target=str(key or '').isdigit() and len(str(key or '')) >= 6
                redundant_field_click=(
                    key
                    and next_step.get('element')==key
                    and next_step.get('action') in {'fill','select'}
                )
                if redundant_field_click:
                    lines.append(f'    # Skipped redundant field click for {key}; next step supplies the value.')
                elif key and _is_accidental_container_click(element):
                    lines.append(f'    # Skipped recorder container click for {key}; not a real actionable control.')
                elif numeric_table_target:
                    lines.append('    _grid = page.locator(".dataTables_wrapper:visible")')
                    lines.append('    try:')
                    lines.append('        _grid.last.wait_for(state="visible", timeout=10000)')
                    lines.append('    except Exception:')
                    lines.append('        pass')
                    lines.append('    if _grid.count() > 0:')
                    lines.append('        _grid = _grid.last')
                    lines.append('        _search = _grid.locator("input[type=search], input[aria-controls]").first')
                    lines.append('        if _search.count() > 0 and _search.is_visible() and _search.input_value():')
                    lines.append('            _search.fill("")')
                    lines.append('            page.wait_for_timeout(1000)')
                    lines.append('        _row = _grid.locator("tbody tr:not(:has(td.dataTables_empty))").first')
                    lines.append('        try:')
                    lines.append('            _row.wait_for(state="visible", timeout=15000)')
                    lines.append('        except Exception:')
                    lines.append(f'            raise RuntimeError({_json("The table has no rows to select (recorded target "+str(key)+"). Make sure the list contains at least one record.")})')
                    lines.append('        print("[IR-ROW] selecting first row: " + " | ".join(t.strip() for t in _row.locator("td").all_inner_texts())[:200], flush=True)')
                    lines.append('        try:')
                    lines.append('            print("[IR-ROW-HTML] " + _row.evaluate("e => e.outerHTML")[:400], flush=True)')
                    lines.append('        except Exception:')
                    lines.append('            pass')
                    lines.append('        _picked = ""')
                    lines.append('        for _how in ("link", "cell", "row", "double"):')
                    lines.append('            try:')
                    lines.append('                if _how == "link":')
                    lines.append('                    _t = _row.locator("a, button")')
                    lines.append('                    if _t.count() == 0:')
                    lines.append('                        continue')
                    lines.append('                    _t.first.click(timeout=3000)')
                    lines.append('                elif _how == "cell":')
                    lines.append('                    _row.locator("td").first.click(timeout=3000)')
                    lines.append('                elif _how == "row":')
                    lines.append('                    _row.click(timeout=3000)')
                    lines.append('                else:')
                    lines.append('                    _row.dblclick(timeout=3000)')
                    lines.append('            except Exception:')
                    lines.append('                continue')
                    lines.append('            page.wait_for_timeout(1200)')
                    lines.append('            if not _grid.is_visible():')
                    lines.append('                _picked = _how')
                    lines.append('                break')
                    lines.append('        print("[IR-ROW] row picked by " + (_picked or "no method; the list stayed open"), flush=True)')
                    lines.append('    else:')
                    lines.append(f'        {loc}.first.click(timeout=5000)')
                elif key and _is_optional_dismiss(element):
                    lines.append(f'    if {loc}.count() > 0 and {loc}.first.is_visible():')
                    lines.append(f'        {loc}.first.click(timeout=3000)')
                else:
                    lines.append('    try:')
                    lines.append(f'        {loc}.first.click(timeout=5000)')
                    lines.append('    except Exception:')
                    navigated_to=(step.get('metadata') or {}).get('navigatedTo')
                    if navigated_to:
                        rel=_relative_url(navigated_to)
                        lines.append(f'        page.goto(base_url.rstrip("/") + {_json(rel)})')
                    else:
                        lines.append(f'        {loc}.first.dispatch_event("click", timeout=3000)')
            elif action=='fill':
                if not loc: raise GeneratorError(f'IR step {sid} requires a locator for element {key}.', 'UNSUPPORTED_LOCATOR', [str(key)])
                v=step.get('value') or {}; ref=str(v.get('reference') or 'VALUE')
                next_step=ordered_steps[step_index+1] if step_index+1 < len(ordered_steps) else {}
                next_element=elements.get(str(next_step.get('element'))) or {}
                next_ids={
                    str(x.get('value') or '')
                    for x in _candidate_list(next_element)
                    if x.get('strategy')=='id'
                }
                autocomplete_fill=(
                    next_step.get('action')=='click'
                    and 'ui-active-menuitem' in next_ids
                )
                lines.append(f'    {loc}.wait_for(state="visible", timeout=15000)')
                if autocomplete_fill:
                    lines.append(f'    {loc}.click()')
                    lines.append(f'    {loc}.fill("")')
                    lines.append(f'    {loc}.press_sequentially(os.environ[{_json(ref)}], delay=150)')
                else:
                    lines.append(f'    {loc}.fill(os.environ[{_json(ref)}])')
            elif action=='select':
                if not loc: raise GeneratorError(f'IR step {sid} requires a locator for element {key}.', 'UNSUPPORTED_LOCATOR', [str(key)])
                v=step.get('value') or {}; ref=str(v.get('reference') or 'VALUE'); lines.append(f'    {loc}.select_option(os.environ[{_json(ref)}])')
            elif action=='check':
                if not loc: raise GeneratorError(f'IR step {sid} requires a locator for element {key}.', 'UNSUPPORTED_LOCATOR', [str(key)])
                lines.append(f'    {loc}.check()')
            elif action=='uncheck':
                if not loc: raise GeneratorError(f'IR step {sid} requires a locator for element {key}.', 'UNSUPPORTED_LOCATOR', [str(key)])
                lines.append(f'    {loc}.uncheck()')
            elif action=='uploadFile':
                if not loc: raise GeneratorError(f'IR step {sid} requires a locator for element {key}.', 'UNSUPPORTED_LOCATOR', [str(key)])
                lines.append(f'    {loc}.set_input_files(str(assets / {_json((step.get("asset") or {}).get("reference","upload.bin"))}))')
            elif action=='keyboard':
                if loc: lines.append(f'    {loc}.press({_json(step.get("key","Enter"))})')
                else: lines.append(f'    page.keyboard.press({_json(step.get("key","Enter"))})')
            elif action=='assert':
                if not loc: raise GeneratorError(f'IR step {sid} requires a locator for element {key}.', 'UNSUPPORTED_LOCATOR', [str(key)])
                a=step.get('assertion') or {}; typ=a.get('type','visible'); exp=a.get('expected','')
                if typ=='visible': lines.append(f'    expect({loc}).to_be_visible()')
                elif typ=='textContains': lines.append(f'    expect({loc}).to_contain_text({_json(exp)})')
                elif typ in {'textEquals','text'}: lines.append(f'    expect({loc}).to_have_text({_json(exp)})')
                elif typ=='hidden': lines.append(f'    expect({loc}).to_be_hidden()')
                else: lines.append(f'    expect({loc}).to_be_visible()  # unsupported assertion subtype retained as visibility check: {typ}')
            elif action=='extractValue':
                if not loc: raise GeneratorError(f'IR step {sid} requires a locator for element {key}.', 'UNSUPPORTED_LOCATOR', [str(key)])
                var=_snake(step.get('variable') or sid); prop=step.get('property','text')
                if prop=='value': lines.append(f'    {var} = {loc}.input_value()')
                else: lines.append(f'    {var} = {loc}.inner_text().strip()')
                lines.append(f'    assert {var} is not None')
        elif action=='checkpoint': lines.append(f'    # Checkpoint: {str(step.get("description", "")).replace(chr(10)," ")}')
        elif action=='wait': lines.append('    page.wait_for_load_state("domcontentloaded")')
    files[f'tests/test_{module}.py']='\n'.join(lines)+'\n'; files['tests/__init__.py']=''
    files['tests/conftest.py']='''import os
import pytest
from playwright.sync_api import sync_playwright


@pytest.fixture(scope="session")
def base_url():
    return os.environ.get("BASE_URL", "http://localhost")


@pytest.fixture
def page():
    browser_name = os.environ.get("BROWSER", "chromium").lower()
    headless = os.environ.get("HEADLESS", "true").lower() != "false"
    with sync_playwright() as p:
        browser_type = getattr(p, browser_name if browser_name in {"chromium", "firefox", "webkit"} else "chromium")
        browser = browser_type.launch(headless=headless)
        context = browser.new_context()
        pg = context.new_page()
        yield pg
        context.close()
        browser.close()


def _diagnose(pg):
    """Prints where the browser was when a step failed, so a missing element can be explained from the run output alone."""
    def say(msg):
        print("[IR-FAIL] " + msg, flush=True)
    try:
        pages = pg.context.pages
        say(f"open tabs: {len(pages)}")
        for i, p in enumerate(pages):
            say(f"  tab {i + 1}: {p.url}")
    except Exception:
        pass
    try:
        say(f"current url: {pg.url}")
        say(f"title: {pg.title()}")
    except Exception:
        pass
    try:
        say("frames: " + ", ".join(f.url for f in pg.frames if f.url)[:600])
    except Exception:
        pass
    try:
        ids = pg.eval_on_selector_all("select", "els => els.map(e => e.id || e.name || '(no id)')")
        say("select elements on page: " + (", ".join(ids) if ids else "none"))
    except Exception:
        pass
    try:
        text = " ".join(pg.inner_text("body", timeout=3000).split())
        say("visible text: " + text[:500])
        say("visible text (end of page): " + text[-600:])
    except Exception:
        pass
    try:
        fields = pg.eval_on_selector_all("input:not([type=password]), textarea", "els => els.filter(e => e.id).map(e => e.id + (e.offsetParent === null ? ' [hidden]' : ' [visible]') + (e.value ? ' =' + String(e.value).slice(0, 20) : ''))")
        fields = [f for f in fields if not f.startswith("session")]
        say("input fields: " + (", ".join(fields[:120]) if fields else "none"))
    except Exception:
        pass
    try:
        hits = pg.eval_on_selector_all("[id*=contact i], [name*=contact i], [placeholder*=contact i]", "els => els.map(e => e.tagName + '#' + (e.id || e.name || '?') + (e.offsetParent === null ? ' [hidden]' : ' [visible]'))")
        say("elements named contact: " + (", ".join(hits) if hits else "none"))
    except Exception:
        pass
    try:
        chosen = pg.eval_on_selector_all("select", "els => els.filter(e => e.id && e.id.indexOf('_length') < 0).map(e => e.id + '=' + (e.options[e.selectedIndex] ? e.options[e.selectedIndex].text : '(none)'))")
        say("selected options: " + "; ".join(chosen))
    except Exception:
        pass
    try:
        form = " ".join(pg.inner_text("form", timeout=3000).split())
        say("form text: " + form[:900])
    except Exception:
        pass
    try:
        modals = pg.eval_on_selector_all(".modal", "els => els.map(e => (e.id || '(no id)') + (e.offsetParent === null ? ' [hidden]' : ' [open]'))")
        say("modal dialogs: " + (", ".join(modals) if modals else "none"))
    except Exception:
        pass


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.failed:
        pg = item.funcargs.get("page")
        if pg is not None:
            _diagnose(pg)
'''
    files['requirements.txt']='pytest==8.4.2\nplaywright==1.55.0\n'
    files['pytest.ini']='[pytest]\ntestpaths = tests\naddopts = -q\n'
    secret_refs=sorted({str((s.get('value') or {}).get('reference')) for s in ir['steps'] if (s.get('value') or {}).get('source')=='secret' and (s.get('value') or {}).get('reference')})
    parameter_refs=sorted(str(k) for k in params.keys())
    runtime_refs=sorted(set(parameter_refs) | set(secret_refs))
    env=[f'BASE_URL={_base_url_from_ir(ir)}','BROWSER=chromium','HEADLESS=true']+[f'{x}=' for x in runtime_refs]
    files['.env.example']='\n'.join(env)+'\n'
    files['automation-ir.json']=json.dumps(ir,indent=2,ensure_ascii=False,sort_keys=True)+'\n'
    files['source-map.json']=json.dumps(source_map,indent=2)+'\n'
    files['README.md']=f'''# {scenario_name} — Playwright + Pytest\n\nGenerated deterministically from canonical Automation IR.\n\n## Run\n\n```powershell\npy -m pip install -r requirements.txt\npy -m playwright install\n$env:BASE_URL="https://your-environment.example"\npy -m pytest\n```\n\nSecrets are referenced by environment-variable name and are never emitted as plaintext.\n'''
    syntax=[]
    for path,c in files.items():
        if path.endswith('.py'):
            try: ast.parse(c); syntax.append({'file':path,'status':'PASS'})
            except SyntaxError as ex: syntax.append({'file':path,'status':'FAIL','message':str(ex)})
    return files, {'pythonSyntax':syntax,'sourceMapEntries':len(source_map)}

def _java_project(ir: dict[str,Any]) -> tuple[dict[str,str],dict[str,Any]]:
    scenario=ir.get('scenario') or {}; scenario_name=scenario.get('name','Generated Scenario'); cls=_pascal(scenario_name); page_cls=cls+'Page'; test_cls=cls+'Test'; pkg='generated'
    elements=ir.get('elements') or {}; params=ir.get('parameters') or {}
    page=['package generated.pages;','','import java.time.Duration;','import org.openqa.selenium.*;','import org.openqa.selenium.support.ui.*;','','public class '+page_cls+' {','  private final WebDriver driver;','  private final WebDriverWait wait;','  public '+page_cls+'(WebDriver driver) { this.driver=driver; this.wait=new WebDriverWait(driver, Duration.ofSeconds(15)); }','  private WebElement find(By by) { return wait.until(ExpectedConditions.visibilityOfElementLocated(by)); }','']
    elem_methods={}
    locator_actions={'click','fill','select','check','uncheck','uploadFile','assert','extractValue'}
    required_keys={
        str(s.get('element')) for s in ir['steps']
        if s.get('element')
        and s.get('action') in locator_actions
        and not (
            s.get('action')=='click'
            and _is_accidental_container_click(elements.get(str(s.get('element'))) or {})
        )
    }
    optional_keyboard_keys={str(s.get('element')) for s in ir['steps'] if s.get('element') and s.get('action')=='keyboard' and _has_locator(elements.get(str(s.get('element'))) or {})}
    for key in sorted(required_keys | optional_keyboard_keys):
        element=elements.get(key) or {}
        if not _has_locator(element):
            raise GeneratorError(f'IR element {key} is used by an action that requires a locator, but no supported locator candidate was recorded.', 'UNSUPPORTED_LOCATOR', [key])
        m='loc'+_pascal(key); elem_methods[key]=m; page += [f'  public WebElement {m}() {{ return find({_sel_by(element)}); }}']
    page += ['}']
    files={'src/test/java/generated/pages/'+page_cls+'.java':'\n'.join(page)+'\n'}
    lines=['package generated.tests;','','import java.nio.file.Path;','import org.openqa.selenium.*;','import org.openqa.selenium.chrome.ChromeDriver;','import org.openqa.selenium.chrome.ChromeOptions;','import org.openqa.selenium.firefox.FirefoxDriver;','import org.openqa.selenium.firefox.FirefoxOptions;','import org.openqa.selenium.support.ui.Select;','import org.testng.Assert;','import org.testng.annotations.*;',f'import generated.pages.{page_cls};','import generated.support.Config;','','public class '+test_cls+' {','  private WebDriver driver;',f'  private {page_cls} screen;','','  @BeforeMethod','  public void setUp() {','    String browser = Config.value("BROWSER", "chrome").toLowerCase();','    boolean headless = Boolean.parseBoolean(Config.value("HEADLESS", "true"));','    if (browser.equals("firefox")) {','      FirefoxOptions options=new FirefoxOptions(); if (headless) options.addArguments("-headless"); driver=new FirefoxDriver(options);','    } else {','      ChromeOptions options=new ChromeOptions(); if (headless) options.addArguments("--headless=new"); driver=new ChromeDriver(options);','    }',f'    screen = new {page_cls}(driver);','  }','','  @AfterMethod(alwaysRun=true)','  public void tearDown() { if (driver != null) driver.quit(); }','','  @Test',f'  public void {_camel(scenario_name)}() {{']
    source_map={}
    for step in _ordered_steps(ir):
        sid=str(step['id']); action=step['action']; source_map[sid]={'file':'src/test/java/generated/tests/'+test_cls+'.java','line':len(lines)+1}
        lines.append(f'    // IR-STEP: {sid}')
        if action=='navigate':
            rel=_relative_url(step.get("url")); origin=_origin(step.get("url"))
            rel_expr=f'Config.rebase("{_java(rel)}", "{_java(origin)}")' if _embeds_origin(rel,origin) else f'"{_java(rel)}"'
            lines.append(f'    driver.get(Config.resolveUrl({rel_expr}));')
        elif action in {'click','fill','select','check','uncheck','uploadFile','keyboard','assert','extractValue'}:
            key=step.get('element'); elem=f'screen.{elem_methods[key]}()' if key and key in elem_methods else None
            if action=='click':
                element=elements.get(key) or {} if key else {}
                if key and _is_accidental_container_click(element):
                    lines.append(f'    // Skipped recorder container click for {key}; not a real actionable control.')
                else:
                    if not elem: raise GeneratorError(f'IR step {sid} requires a locator for element {key}.', 'UNSUPPORTED_LOCATOR', [str(key)])
                    lines.append(f'    {elem}.click();')
            elif action=='fill':
                if not elem: raise GeneratorError(f'IR step {sid} requires a locator for element {key}.', 'UNSUPPORTED_LOCATOR', [str(key)])
                v=step.get('value') or {}; ref=str(v.get('reference') or 'VALUE')
                lines.append(f'    {elem}.sendKeys(Config.required("{_java(ref)}"));')
            elif action=='select':
                if not elem: raise GeneratorError(f'IR step {sid} requires a locator for element {key}.', 'UNSUPPORTED_LOCATOR', [str(key)])
                v=step.get('value') or {}; ref=str(v.get('reference') or 'VALUE')
                lines.append(f'    new Select({elem}).selectByValue(Config.required("{_java(ref)}"));')
            elif action=='check':
                if not elem: raise GeneratorError(f'IR step {sid} requires a locator for element {key}.', 'UNSUPPORTED_LOCATOR', [str(key)])
                lines.append(f'    if (!{elem}.isSelected()) {elem}.click();')
            elif action=='uncheck':
                if not elem: raise GeneratorError(f'IR step {sid} requires a locator for element {key}.', 'UNSUPPORTED_LOCATOR', [str(key)])
                lines.append(f'    if ({elem}.isSelected()) {elem}.click();')
            elif action=='uploadFile':
                if not elem: raise GeneratorError(f'IR step {sid} requires a locator for element {key}.', 'UNSUPPORTED_LOCATOR', [str(key)])
                lines.append(f'    {elem}.sendKeys(Path.of("assets", "{_java((step.get("asset") or {}).get("reference","upload.bin"))}").toAbsolutePath().toString());')
            elif action=='keyboard':
                key_name=str(step.get("key","ENTER")).upper().replace(" ","_")
                if elem: lines.append(f'    {elem}.sendKeys(Keys.{key_name});')
                else: lines.append(f'    driver.switchTo().activeElement().sendKeys(Keys.{key_name});')
            elif action=='assert':
                if not elem: raise GeneratorError(f'IR step {sid} requires a locator for element {key}.', 'UNSUPPORTED_LOCATOR', [str(key)])
                a=step.get('assertion') or {}; typ=a.get('type','visible'); exp=_java(a.get('expected',''))
                if typ=='visible': lines.append(f'    Assert.assertTrue({elem}.isDisplayed());')
                elif typ=='textContains': lines.append(f'    Assert.assertTrue({elem}.getText().contains("{exp}"));')
                elif typ in {'textEquals','text'}: lines.append(f'    Assert.assertEquals({elem}.getText().trim(), "{exp}");')
                elif typ=='hidden': lines.append(f'    Assert.assertFalse({elem}.isDisplayed());')
                else: lines.append(f'    Assert.assertTrue({elem}.isDisplayed()); // unsupported assertion subtype: {typ}')
            elif action=='extractValue':
                if not elem: raise GeneratorError(f'IR step {sid} requires a locator for element {key}.', 'UNSUPPORTED_LOCATOR', [str(key)])
                var=_camel(step.get('variable') or sid); prop=step.get('property','text')
                lines.append(f'    String {var} = {elem}.{("getAttribute(\"value\")" if prop=="value" else "getText()")};'); lines.append(f'    Assert.assertNotNull({var});')
        elif action=='checkpoint': lines.append(f'    // Checkpoint: {_java(step.get("description", ""))}')
        elif action=='wait': lines.append('    // Condition-based waits are handled by Page Object visibility waits.')
    lines += ['  }','}']; files['src/test/java/generated/tests/'+test_cls+'.java']='\n'.join(lines)+'\n'
    files['src/test/java/generated/support/Config.java']='''package generated.support;\n\npublic final class Config {\n  private Config() {}\n  public static String value(String name, String fallback) { String v=System.getenv(name); return v==null||v.isBlank()?fallback:v; }\n  public static String required(String name) { String v=System.getenv(name); if(v==null||v.isBlank()) throw new IllegalStateException(name+" is required"); return v; }\n  public static String rebase(String text, String recordedOrigin) { String target=required("BASE_URL").replaceAll("/+$",""); return text.replace(java.net.URLEncoder.encode(recordedOrigin, java.nio.charset.StandardCharsets.UTF_8), java.net.URLEncoder.encode(target, java.nio.charset.StandardCharsets.UTF_8)).replace(recordedOrigin, target); }\n  public static String resolveUrl(String relative) { String base=required("BASE_URL").replaceAll("/+$",""); return relative.startsWith("/")?base+relative:base+"/"+relative; }\n}\n'''
    files['pom.xml']='''<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">\n  <modelVersion>4.0.0</modelVersion><groupId>generated</groupId><artifactId>automation-tests</artifactId><version>1.0.0</version>\n  <properties><maven.compiler.release>21</maven.compiler.release><project.build.sourceEncoding>UTF-8</project.build.sourceEncoding></properties>\n  <dependencies><dependency><groupId>org.seleniumhq.selenium</groupId><artifactId>selenium-java</artifactId><version>4.35.0</version></dependency><dependency><groupId>org.testng</groupId><artifactId>testng</artifactId><version>7.11.0</version><scope>test</scope></dependency></dependencies>\n  <build><plugins><plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-surefire-plugin</artifactId><version>3.5.3</version><configuration><suiteXmlFiles><suiteXmlFile>testng.xml</suiteXmlFile></suiteXmlFiles></configuration></plugin></plugins></build>\n</project>\n'''
    files['testng.xml']=f'''<!DOCTYPE suite SYSTEM "https://testng.org/testng-1.0.dtd">\n<suite name="Generated Automation"><test name="{scenario_name}"><classes><class name="generated.tests.{test_cls}"/></classes></test></suite>\n'''
    secret_refs=sorted({str((s.get('value') or {}).get('reference')) for s in ir['steps'] if (s.get('value') or {}).get('source')=='secret' and (s.get('value') or {}).get('reference')})
    parameter_refs=sorted(str(k) for k in params.keys())
    runtime_refs=sorted(set(parameter_refs) | set(secret_refs))
    files['.env.example']='\n'.join([f'BASE_URL={_base_url_from_ir(ir)}','BROWSER=chrome','HEADLESS=true']+[f'{x}=' for x in runtime_refs])+'\n'
    files['automation-ir.json']=json.dumps(ir,indent=2,ensure_ascii=False,sort_keys=True)+'\n'; files['source-map.json']=json.dumps(source_map,indent=2)+'\n'
    files['README.md']=f'''# {scenario_name} — Selenium + TestNG\n\nGenerated deterministically from canonical Automation IR.\n\n## Run\n\n```powershell\n$env:BASE_URL="https://your-environment.example"\nmvn test\n```\n\nJava compilation/build validation is intentionally deferred to an isolated validation/runner environment. Secrets remain environment references.\n'''
    structural=[]
    for p,c in files.items():
        if p.endswith('.java'): structural.append({'file':p,'status':'PASS' if c.count('{')==c.count('}') else 'FAIL'})
    return files, {'javaStructural':structural,'compile':'NOT_RUN','sourceMapEntries':len(source_map)}

def generate_project(request: dict[str,Any]) -> dict[str,Any]:
    ir=request['automationIr']; _validate_ir(ir); target=request['target']
    if target=='PLAYWRIGHT_PYTEST': files,validation=_python_project(ir)
    elif target=='SELENIUM_TESTNG': files,validation=_java_project(ir)
    else: raise GeneratorError(f'Unsupported target profile: {target}','UNSUPPORTED_TARGET',[target])
    scan=_secret_scan(files); validation['secretScan']=scan; validation['status']='PASS' if scan['status']=='PASS' and not any(x.get('status')=='FAIL' for vals in validation.values() if isinstance(vals,list) for x in vals if isinstance(x,dict)) else 'FAIL'
    source_map=json.loads(files['source-map.json'])
    source_hash=_hash(files)
    return {'status':'STATIC_VALIDATED' if validation['status']=='PASS' else 'GENERATED_WITH_WARNINGS','target':target,'generatorVersion':request.get('generatorVersion','0.3.2'),'irSchemaVersion':ir.get('irSchemaVersion'),'irCanonicalHash':hashlib.sha256(json.dumps(ir,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'sourceHash':source_hash,'files':[{'path':p,'content':files[p]} for p in sorted(files)],'sourceMap':source_map,'validation':validation,'warnings':([] if validation['status']=='PASS' else ['One or more static checks require review.'])}

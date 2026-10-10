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

def _is_button_element(element: dict[str,Any]) -> bool:
    """True when the recorded target is a button (a dialog or form button), not a link."""
    for candidate in _candidate_list(element):
        value=candidate.get('value')
        return candidate.get('strategy')=='role' and isinstance(value,dict) and str(value.get('role') or '').lower()=='button'
    return False

def _id_of(element: dict[str,Any]) -> str | None:
    for candidate in _candidate_list(element):
        if candidate.get('strategy')=='id' and candidate.get('value'):
            return str(candidate['value'])
    return None

_DATE_MASK=re.compile(r'^(?:D{1,2}|M{1,2}|Y{4}|Y{2})([-/. ])(?:D{1,2}|M{1,2}|Y{4}|Y{2})\1(?:D{1,2}|M{1,2}|Y{4}|Y{2})$', re.I)

def _date_format(element: dict[str,Any]) -> str | None:
    """strftime format when the target is a date field whose placeholder or label is a date mask such as DD-MM-YYYY."""
    for candidate in _candidate_list(element):
        value=candidate.get('value')
        text=str(value.get('name') if isinstance(value,dict) else value or '').strip()
        if text and _DATE_MASK.match(text):
            fmt=text.upper().replace('YYYY','%Y').replace('YY','%y').replace('DD','%d').replace('D','%d').replace('MM','%m').replace('M','%m')
            return fmt
    return None

def _date_rule(key, element):
    """(env name, default offset in days, forced) for a date field known by name; the proposal date is today and the last working date is today + 30."""
    text=' '.join([str(key or ''),str(_id_of(element) or ''),str(element.get('description') or '')]).lower()
    text=re.sub(r'[^a-z]','',text)
    if 'proposal' in text: return 'PROPOSAL_DATE_OFFSET_DAYS',0,True
    if 'lastworking' in text: return 'LAST_WORKING_DATE_OFFSET_DAYS',30,True
    return None,30,False

def _is_browse_element(element: dict[str,Any]) -> bool:
    """True when the recorded target is a Browse / choose-file control that opens the file picker."""
    desc=str(element.get('description') or '').strip().lower()
    if desc.startswith('browse') and len(desc) < 30:
        return True
    for candidate in _candidate_list(element):
        value=candidate.get('value')
        text=str(value.get('name') if isinstance(value,dict) else value or '').strip().lower()
        if (text.startswith('browse') and len(text) < 30) or 'type="file"' in text or '[type=file]' in text or "type='file'" in text:
            return True
    return False

def _is_toast_element(key, element):
    # A recorded click on a short-lived notification ("... has been saved successfully"), which is gone again by the time the test reaches it.
    texts=[str(key or '')]+[str(c.get('value') or '') for c in _candidate_list(element) if c.get('strategy')=='text']
    return any(re.search(r'has[ -]been[ -](saved|created|submitted|updated|deleted)|successfully',t,re.I) for t in texts)


def _is_confirm_button(element: dict[str,Any]) -> bool:
    # The Yes button of a confirmation pop-up. The generated test may already have confirmed that pop-up itself (for example after a
    # drop-down choice), so the recorded click waits a few seconds for the button and carries on when it never shows.
    for candidate in _candidate_list(element):
        value=candidate.get('value')
        if candidate.get('strategy') in ('id','css','xpath') and 'yes-button' in str(value).lower():
            return True
    return False


def _is_yes_element(element: dict[str,Any]) -> bool:
    """The Yes button of a confirmation pop-up, however it was recorded (role, text, or the ERP's #yes-button id)."""
    for candidate in _candidate_list(element):
        value=candidate.get('value'); strategy=candidate.get('strategy')
        if strategy in ('id','css','xpath') and 'yes-button' in str(value).lower(): return True
        if strategy=='role' and isinstance(value,dict) and str(value.get('name') or '').strip().lower()=='yes': return True
        if strategy in ('text','label') and isinstance(value,str) and value.strip().lower()=='yes': return True
    return False


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
            said = ""
            try:
                said = " ".join(page.inner_text("body").split())[:200]
            except Exception:
                pass
            used = globals().get("_USED", {})
            raise RuntimeError("Sign-in did not complete: the browser is still on the sign-in page. The page says: '" + said + "'. User name used: " + str(used.get("user", "unknown")) + ". Password taken from: " + str(used.get("password", "unknown")) + ". Check the user name and that this password line in the .env file is filled in correctly (the password itself is never shown).")
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        pass


def _open_page(page, url):
    # Opens a page. When it has not finished loading after 30 seconds (a script or style it needs may be unreachable from this machine),
    # say what is still loading and carry on with what has arrived, instead of stopping at the first step.
    waiting = {}

    def started(request):
        waiting[id(request)] = request.url

    def ended(request):
        waiting.pop(id(request), None)

    page.on("request", started)
    page.on("requestfinished", ended)
    page.on("requestfailed", ended)
    try:
        try:
            return page.goto(url, wait_until="domcontentloaded")
        except Exception as ex:
            if "Timeout" not in type(ex).__name__ and "Timeout" not in str(ex):
                raise
            slow = sorted(set(waiting.values()))[:6]
            print("[IR-WARN] the page did not finish loading within 30 seconds; continuing with what has loaded. Still loading: " + (" | ".join(u[:150] for u in slow) or "nothing listed (the page itself did not answer)"), flush=True)
            return None
    finally:
        for name, handler in (("request", started), ("requestfinished", ended), ("requestfailed", ended)):
            try:
                page.remove_listener(name, handler)
            except Exception:
                pass


def _join_url(base_url, rel):
    # The environment address may be a full page address (https://host/admin/login). The recorded path then already starts with
    # the same first folder (/admin/...), so use the site address in front of it instead of repeating the folder.
    base = urlsplit(base_url)
    parts = [x for x in base.path.split("/") if x]
    if parts:
        first = "/" + parts[0]
        path = urlsplit(rel).path
        if path == first or path.startswith(first + "/"):
            return base.scheme + "://" + base.netloc + rel
    return base_url.rstrip("/") + rel


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


def _pace_ms():
    raw = os.environ.get("STEP_DELAY_MS", "").strip()
    if raw.isdigit():
        return int(raw)
    return 300 if os.environ.get("HEADLESS", "true").lower() == "false" else 100


def _quiet(page):
    # After an entry, let the page finish any refresh it triggers (dependent lists, auto-fill, validation) before the next step.
    try:
        page.wait_for_load_state("networkidle", timeout=4000)
    except Exception:
        pass
    page.wait_for_timeout(_pace_ms())


class _NotShown(AssertionError):
    """A recorded field exists on the page but stays hidden (some forms only show it for certain employees or options)."""


def _not_shown(page, loc, timeout):
    try:
        which = loc.first.evaluate("e => e.id || e.name || e.tagName")
    except Exception:
        which = "a field"
    try:
        checked = page.evaluate("() => Array.from(document.querySelectorAll('input[type=radio]:checked')).map(r => (r.name || r.id) + '=' + (r.value || 'on')).join(', ')")
    except Exception:
        checked = ""
    return _NotShown("The field '" + str(which) + "' stayed hidden for " + str(timeout // 1000) + " seconds. This form may show it only for some employees or options."
                     + (" Selected options on the page: " + checked + "." if checked else ""))


def _retrigger(page):
    # Some pages show a dependent field only from a click or change handler on the selected option. Fire both again.
    try:
        page.evaluate("() => document.querySelectorAll('input[type=radio]:checked').forEach(r => { for (const t of ['click', 'change']) r.dispatchEvent(new Event(t, {bubbles: true})); })")
    except Exception:
        pass


def _match_option(options, value):
    # The option whose value or text is the wanted one (exact first, then ignoring upper/lower case); None when it is not in the list.
    for v, t in options:
        if value == v or value == t:
            return v
    low = str(value).lower()
    for v, t in options:
        if low == str(v).lower() or low == str(t).lower():
            return v
    return None


def _any_if_missing(loc, value=""):
    # When the data was changed in .env, a list that depends on that choice (for example the reasons of another separation type) no longer holds the recorded entry: take its first real entry.
    # A value typed in .env itself is never replaced this way. PICK_ANY_IF_MISSING=paymentCollectionPoint,otherField (or "all") does the same for named fields.
    if globals().get("_DATA_CHANGED") and str(value) not in globals().get("_EXPLICIT_DATA", ()):
        return True
    wanted = [x.strip().lower() for x in os.environ.get("PICK_ANY_IF_MISSING", "").split(",") if x.strip()]
    if not wanted:
        return False
    if "all" in wanted:
        return True
    try:
        ident = loc.first.evaluate("e => [e.id, e.name].filter(Boolean).map(x => x.toLowerCase())")
    except Exception:
        return False
    return any(i in wanted for i in ident)


def _confirm_after(page, loc):
    # Some forms confirm a drop-down choice with a Yes pop-up (for example the payment collection point). CONFIRM_YES_AFTER lists the fields.
    wanted = [x.strip().lower() for x in os.environ.get("CONFIRM_YES_AFTER", "paymentCollectionPoint").split(",") if x.strip()]
    try:
        ident = loc.first.evaluate("e => [e.id, e.name].filter(Boolean).map(x => x.toLowerCase())")
    except Exception:
        return
    if not any(i in wanted for i in ident):
        return
    yes = page.locator("xpath=//input[@id='yes-button'] | //div[@class='ui-dialog-buttonset']//button[span[normalize-space()='Yes']]").first
    try:
        yes.wait_for(state="visible", timeout=2500)
        yes.click()
        print("[IR-CHOICE] confirmed the pop-up after the choice (Yes)", flush=True)
        page.wait_for_timeout(300)
    except Exception:
        pass


def _pick(page, loc, value, timeout=15000):
    # Choose a drop-down entry only once the list is enabled and the wanted entry is in it (lists that load after another field).
    try:
        loc.wait_for(state="visible", timeout=timeout)
    except Exception:
        try:
            present = loc.count() > 0
        except Exception:
            present = False
        if not present:
            raise
        _reapply_choices(page)
        _retrigger(page)
        try:
            loc.wait_for(state="visible", timeout=6000)
        except Exception:
            raise _not_shown(page, loc, timeout)
    waited = 0
    found = False
    options = []
    while waited < timeout:
        try:
            if loc.is_enabled():
                options = loc.evaluate("e => Array.from(e.options).map(o => [o.value, o.text.trim()])")
                if _match_option(options, value) is not None:
                    found = True
                    break
        except Exception:
            pass
        page.wait_for_timeout(250)
        waited += 250
        if waited >= 3000 and _any_if_missing(loc, value) and any(v and not t.lower().startswith("select") for v, t in options):
            break
    page.wait_for_timeout(_pace_ms())
    if not found and _any_if_missing(loc, value):
        real = [(v, t) for v, t in options if v and not t.lower().startswith("select")]
        if real:
            print("[IR-CHOICE] '" + str(value) + "' is not in the list; selecting the first entry '" + real[0][1] + "' instead (the data was changed in .env, or PICK_ANY_IF_MISSING is set)", flush=True)
            loc.select_option(real[0][0])
            _quiet(page)
            _confirm_after(page, loc)
            return
    match = _match_option(options, value)
    if match is None and options:
        names = ", ".join(t for v, t in options if v and not t.lower().startswith("select"))
        raise AssertionError("The option '" + str(value) + "' is not in the list. Options here: " + names + ". Change the value in the .env file, or set PICK_ANY_IF_MISSING=<field name> to take the first entry.")
    loc.select_option(match if match is not None else value)
    _quiet(page)
    _confirm_after(page, loc)


'''

_CONFTEST_HEAD = r'''import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

_ROOT = Path(__file__).resolve().parents[1]


def _load_env_file():
    # Reads the .env file in the project folder, so BASE_URL, user names and passwords do not have to be typed into the terminal.
    # Everything after the first = is the value exactly as typed: # $ spaces and quotes inside a password need no special handling.
    path = _ROOT / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key and value and not os.environ.get(key):
            os.environ[key] = value


_load_env_file()

'''

_SETTING_HELPER = r'''_SETTING_USER_NAMES = ("username", "userName", "user", "userId", "userid", "login", "loginId")
_USED = {}


def _tag(value):
    return re.sub(r"[^A-Za-z0-9]+", "_", str(value or "")).strip("_").upper()


def _missing(name, lines):
    pytest.fail("A value is missing: " + name + ". Open the .env file in the project folder and add one of these lines (type the value after the = sign), then run again:\n  " + "\n  ".join(line + "=" for line in lines), pytrace=False)


_PIN_CHOICE = {}
_EXPLICIT_DATA = set()
_DATA_CHANGED = []


def _employee_pin_for(name):
    # EMPLOYEE_PIN (or EMPLOYEE_PIN__SCENARIO) in .env sets the employee for every field that holds an employee PIN. Several PINs separated by commas: the first one not used in an earlier run is taken.
    low = name.lower()
    if not ("employeepin" in low or "employeeinfo" in low or low in ("pin", "empid", "employeeid")):
        return ""
    raw = os.environ.get("EMPLOYEE_PIN__" + _SCENARIO) or os.environ.get("EMPLOYEE_PIN") or ""
    pins = [p.strip() for p in raw.split(",") if p.strip()]
    if not pins:
        return ""
    if "pin" not in _PIN_CHOICE:
        fresh = [p for p in pins if p not in _TRIED_AT_START]
        _PIN_CHOICE["pin"] = (fresh or pins)[0]
        _note_employee_key(_PIN_CHOICE["pin"])
        print("[IR-DATA] employee PIN " + _PIN_CHOICE["pin"] + " taken from EMPLOYEE_PIN", flush=True)
    return _PIN_CHOICE["pin"]


_OS_USER_VARS = ("username", "user")
# Names the operating system sets itself (on Windows environment names ignore upper/lower case, so "username" is the name of the person signed in to the computer).
_OS_ENV_NAMES = {"username", "user", "logname", "userdomain", "computername", "hostname", "home", "homepath", "userprofile", "path", "temp", "tmp", "tmpdir", "lang", "os", "term", "shell", "pwd", "appdata", "processor_architecture", "number_of_processors"}


def _user_env(name):
    # A user name typed in .env. The plain names "username" and "user" belong to the operating system, so for them only NAME__SCENARIO and TEST_USERNAME count.
    value = os.environ.get(name + "__" + _SCENARIO)
    if value:
        return value
    if name.lower() not in _OS_ENV_NAMES:
        value = os.environ.get(name)
        if value:
            return value
    return os.environ.get("TEST_USERNAME__" + _SCENARIO) or os.environ.get("TEST_USERNAME") or ""


def _override(name):
    # A value the user set in .env: NAME__SCENARIO, or NAME, when it differs from the recorded value (the platform and the example .env also hold the recorded values themselves, which are not a choice).
    for key in (name + "__" + _SCENARIO, name):
        if key == name and name.lower() in _OS_ENV_NAMES:
            continue
        value = os.environ.get(key)
        if value and value != _DEFAULTS.get(name):
            return value
    return ""


def _linked_value(name):
    # Two fields that held the same long value when the scenario was recorded (for example the same PIN typed twice) hold the same data: if .env sets one of them, the others follow.
    recorded = _DEFAULTS.get(name) or ""
    if len(recorded) < 6 or name in _SETTING_USER_NAMES:
        return ""
    for other, other_value in _DEFAULTS.items():
        if other != name and other not in _SETTING_USER_NAMES and other_value == recorded:
            value = _override(other) or _employee_pin_for(other)
            if value:
                print("[IR-DATA] " + name + " follows " + other + " (same recorded value): " + value, flush=True)
                return value
    return ""


_RANDOM_VALUES = {}


def _setting(name, secret=False):
    # Finds the value for a test-data name or a password the same way the platform does, most specific first.
    # Scenario-specific  NAME__SCENARIO ; then, for passwords, NAME_<ENV>_<USER>, NAME_<ENV>, NAME_<USER> ; then plain NAME ; then the recorded value.
    scoped = name + "__" + _SCENARIO
    if not secret and name in _SETTING_USER_NAMES:
        value = _user_env(name) or _DEFAULTS.get(name)
        if value is None:
            _missing(name, [scoped, "TEST_USERNAME"])
        _USED["user"] = value
        return value
    if not secret and name not in _SETTING_USER_NAMES and re.search(r"contact|mobile|phone|cell", name, re.I) and not re.search(r"mail", name, re.I):
        # A contact number is made up for every run (a valid mobile number), so nothing has to be kept in .env. FIXED_CONTACT_NO=017... forces one.
        if name not in _RANDOM_VALUES:
            _RANDOM_VALUES[name] = os.environ.get("FIXED_CONTACT_NO", "").strip() or ("01" + str(random.choice([3, 5, 6, 7, 8, 9])) + "".join(str(random.randint(0, 9)) for _ in range(8)))
            print("[IR-DATA] " + name + " is a made-up contact number for this run: " + _RANDOM_VALUES[name], flush=True)
        return _RANDOM_VALUES[name]
    if not secret and name not in _SETTING_USER_NAMES:
        value = _override(name)
        pin = ""
        if not value:
            pin = _employee_pin_for(name)
            value = pin or _linked_value(name)
        if value:
            _EXPLICIT_DATA.add(str(value))
            if str(value) != str(_DEFAULTS.get(name, "")) and not pin and not re.search(r"contact|mail|mobile|phone", name, re.I):
                _DATA_CHANGED.append(name)
            return value
        value = _DEFAULTS.get(name) if name in _DEFAULTS else os.environ.get(name)
        if value is None:
            _missing(name, [scoped, name])
        return value
    if os.environ.get(scoped):
        if name in _SETTING_USER_NAMES:
            _USED["user"] = os.environ[scoped]
        elif secret:
            _USED["password"] = scoped
        return os.environ[scoped]
    if not secret:
        value = os.environ.get(name) or _DEFAULTS.get(name)
        if value is None:
            _missing(name, [scoped, name])
        if name in _SETTING_USER_NAMES:
            _USED["user"] = value
        return value
    host = (urlsplit(os.environ.get("BASE_URL", "")).hostname or "").split(".")[0]
    env_tag = _tag(host)
    user_tag = ""
    for user_name in _SETTING_USER_NAMES:
        if _user_env(user_name) or user_name in _DEFAULTS:
            user_tag = _tag(_setting(user_name))
            break
    candidates = []
    if env_tag and user_tag:
        candidates.append(name + "_" + env_tag + "_" + user_tag)
    if env_tag:
        candidates.append(name + "_" + env_tag)
    if user_tag:
        candidates.append(name + "_" + user_tag)
    candidates.append(name)
    for candidate in candidates:
        if os.environ.get(candidate):
            _USED["password"] = candidate
            return os.environ[candidate]
    _missing(name, [scoped] + candidates)


'''

_FLOW_HELPER = r'''_POPUP_SELECTOR = ".ui-dialog, .modal, .bootbox, .noty_bar, .noty_message, .swal2-popup, .jconfirm-box, .toast, .alert, #jGrowl .message, .jGrowl-notification, [role=dialog], [role=alertdialog], [role=alert]"
_PROBLEM_WORDS = re.compile(r"no employee is mapped|not mapped|unable to|failed|error|cannot|can not|could not|invalid|not allowed|not found|already exist|already has", re.I)
_DONE_WORDS = re.compile(r"success|created|saved|submitted", re.I)


def _popup_texts(page):
    # Text of every dialog, modal or notification that is on screen right now.
    try:
        return page.evaluate("""(selector) => Array.from(document.querySelectorAll(selector)).filter(e => {
            const s = getComputedStyle(e); const r = e.getBoundingClientRect();
            return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0;
        }).map(e => (e.innerText || '').trim()).filter(t => t)""", _POPUP_SELECTOR)
    except Exception:
        return []


_CREATE_BUTTON_JS = """() => Array.from(document.querySelectorAll('button, input[type=button], input[type=submit], a')).some(e => {
    const t = ((e.tagName === 'INPUT' && e.value) ? e.value : (e.innerText || '')).trim();
    if (!/^(create|save|submit)$/i.test(t)) return false;
    const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
})"""

_REQUIRED_JS = """() => {
    const vis = e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
    const out = [];
    document.querySelectorAll('label, th, td, span, b, strong').forEach(l => {
        if (!vis(l) || l.children.length > 2) return;
        const t = (l.innerText || '').trim();
        if (!t.endsWith('*') || t.length > 60) return;
        const row = l.closest('tr, .form-group, .row');
        if (!row) return;
        const ctrls = Array.from(row.querySelectorAll('input, select, textarea')).filter(c => !['hidden', 'button', 'submit', 'file', 'checkbox'].includes(c.type) && (vis(c) || c.type === 'radio'));
        if (!ctrls.length) return;
        const radios = ctrls.filter(c => c.type === 'radio');
        const empty = radios.length ? !radios.some(c => c.checked) : ctrls.every(c => !(c.value || '').trim());
        const name = t.replace(/[*]/g, '').trim();
        if (empty && name && !out.includes(name)) out.push(name);
    });
    return out;
}"""

_RADIO_JS = "e => e.matches('input[type=radio]') ? e : ((e.control && e.control.type === 'radio') ? e.control : e.querySelector('input[type=radio]'))"
_CHOSEN = {}
_PAYMENT = {}


def _unfilled_required(page):
    # Names of the required (*) fields that are still empty on the form.
    try:
        return page.evaluate(_REQUIRED_JS)
    except Exception:
        return []


def _remember(inp, loc):
    # One remembered choice per radio group: the latest choice replaces an earlier one, so BEFTN and Cheque can never be re-applied against each other.
    try:
        group = inp.evaluate("e => e.name || e.id || ''") or "?"
    except Exception:
        group = "?"
    _CHOSEN[group] = loc


def _radio_of(el):
    try:
        return el.evaluate_handle(_RADIO_JS).as_element()
    except Exception:
        return None


def _choose(page, el, inp):
    # Select a radio button, trying the recorded click first and then other ways until the button really is selected.
    for how in ("click", "check", "label", "script"):
        try:
            if how == "click":
                el.click(timeout=3000)
            elif how == "check":
                inp.check(timeout=3000, force=True)
            elif how == "label":
                label = inp.evaluate_handle("e => (e.labels && e.labels[0]) || e.closest('label')").as_element()
                if label:
                    label.click(timeout=3000)
            else:
                inp.evaluate("e => { e.checked = true; for (const t of ['click', 'input', 'change']) e.dispatchEvent(new Event(t, {bubbles: true})); }")
        except Exception:
            pass
        page.wait_for_timeout(300)
        try:
            if inp.is_checked():
                if how != "click":
                    print("[IR-CHOICE] the option was selected by another way (" + how + ") because the plain click did not select it", flush=True)
                return True
        except Exception:
            pass
    return False


_RADIO_GROUP_JS = """(hint) => {
    const norm = t => (t || '').replace(/\\s+/g, ' ').trim().toLowerCase();
    const want = norm(hint);
    const vis = e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
    let best = null;
    for (const r of document.querySelectorAll('input[type=radio]')) {
        let box = r.parentElement;
        for (let i = 0; i < 5 && box; i++, box = box.parentElement) {
            if (norm(box.innerText).includes(want)) {
                const size = norm(box.innerText).length;
                if (!best || size < best.size) best = {size: size, box: box};
                break;
            }
        }
    }
    if (!best) return null;
    return Array.from(best.box.querySelectorAll('input[type=radio]')).map(r => {
        let label = '';
        if (r.labels && r.labels[0]) {
            label = r.labels[0].innerText;
        } else {
            // The text that follows this button up to the next button: its own caption, not its neighbours'.
            let cur = r;
            while (cur && !cur.nextSibling && cur.parentElement && cur.parentElement !== best.box) cur = cur.parentElement;
            let n = cur ? cur.nextSibling : null;
            while (n) {
                if (n.nodeType === 1 && (n.matches('input[type=radio]') || n.querySelector('input[type=radio]'))) break;
                label += (n.textContent || '') + ' ';
                n = n.nextSibling;
            }
        }
        return {id: r.id, name: r.name, value: r.value, label: (label || '').replace(/\\s+/g, ' ').trim()};
    });
}"""


def _radio_choice(hint):
    # Which option of a radio group to select. Set it in .env as PAYMENT_METHOD=Cheque (every scenario) or
    # PAYMENT_METHOD__<SCENARIO>=Cheque (one scenario). The name comes from the text in front of the * (here "Payment Method").
    if "*" not in hint:
        return "", ""
    key = re.sub(r"[^A-Za-z0-9]+", "_", hint.split("*")[0]).strip("_").upper()
    scenario = globals().get("RADIO_SCENARIO", "")
    for name in ((key + "__" + scenario) if scenario else "", key):
        if name and os.environ.get(name, "").strip():
            return key, os.environ[name].strip()
    return key, ""


def _hold(page, loc):
    # A page can react to a choice (for example by loading data) and switch the option back a moment later.
    # The option must stay selected for two checks in a row, one second apart; if the page switches it back, it is selected again.
    stable = 0
    flips = 0
    for attempt in range(7):
        page.wait_for_timeout(1000)
        _quiet(page)
        try:
            el = loc.first
            inp = _radio_of(el)
            if inp is None:
                return
            if inp.is_checked():
                stable += 1
                if stable >= 2:
                    return
                continue
            stable = 0
            flips += 1
            print("[IR-CHOICE] the page switched the option back (" + str(flips) + "); selecting it again", flush=True)
            _choose(page, el, inp)
        except Exception:
            return
    print("[IR-CHOICE] the page keeps switching this option back; the last state is used", flush=True)


_BANK_FIELDS_JS = r"""() => {
    const wanted = {account_number: /account\s*number/i, account_name: /account\s*name/i, bank_name: /^bank\s*name/i, branch_name: /branch\s*name/i, routing_no: /routing/i};
    const out = {};
    const seen = (e) => { const r = e.getBoundingClientRect(); const st = getComputedStyle(e); return r.width > 0 && r.height > 0 && st.visibility !== 'hidden' && st.display !== 'none'; };
    for (const e of document.querySelectorAll('input:not([type=radio]):not([type=checkbox]):not([type=hidden]), textarea')) {
        if (!seen(e)) continue;
        let label = '';
        if (e.id) { const l = document.querySelector('label[for="' + e.id + '"]'); if (l) label = l.innerText; }
        if (!label) { const cell = e.closest('td,th,div'); const prev = cell && cell.previousElementSibling; if (prev) label = prev.innerText; }
        label = (label || '').replace(/\s+/g, ' ').trim();
        for (const k in wanted) if (!(k in out) && wanted[k].test(label)) out[k] = (e.value || '').trim();
    }
    return out;
}"""


def _bank_details_shown(page, seconds=10):
    # BEFTN pays into the employee's bank account, so the page must show Account Number, Account Name, Bank Name, Branch Name and Bank Routing No. with data.
    # Returns "" when all five are there, otherwise a short description of what is missing.
    import time as _t
    end = _t.time() + seconds
    missing = "no bank fields"
    while True:
        try:
            got = page.evaluate(_BANK_FIELDS_JS)
        except Exception:
            got = {}
        names = ["account_number", "account_name", "bank_name", "branch_name", "routing_no"]
        missing = ", ".join(n for n in names if not got.get(n)) or ""
        if not missing:
            return ""
        if _t.time() > end:
            return missing
        page.wait_for_timeout(500)


def _cheque_if_no_bank_data(page, options, pick):
    # With BEFTN selected but no bank data for this employee, choose Cheque at once (the employee stays; nothing is picked again).
    if os.environ.get("BEFTN_FALLBACK_TO_CHEQUE", "on").lower() in ("off", "false", "0", "no"):
        return None
    if "beftn" not in ((pick.get("label") or "") + (pick.get("value") or "") + (pick.get("id") or "")).lower():
        return None
    cheque = [o for o in options if "cheque" in ((o.get("label") or "") + (o.get("value") or "") + (o.get("id") or "")).lower()]
    if not cheque:
        return None
    _quiet(page)
    missing = _bank_details_shown(page)
    if not missing:
        print("[IR-CHOICE] BEFTN selected and the bank details are shown", flush=True)
        return None
    print("[IR-CHOICE] BEFTN selected but the bank details are missing (" + missing + "); selecting Cheque instead", flush=True)
    return cheque[0]


def _click_radio_group(page, hint):
    # The recorded target was the text of a whole radio group ("Payment Method * BEFTN Cheque"), which is not an element of its own.
    # Select the wanted option of that group (the first one unless .env says otherwise), and say which one was used.
    try:
        options = page.evaluate(_RADIO_GROUP_JS, hint)
    except Exception as exc:
        print("[IR-CHOICE] could not look for the option group '" + hint + "': " + str(exc)[:150], flush=True)
        return False
    if not options:
        if "*" in hint:
            print("[IR-CHOICE] no radio buttons found in a block of text containing '" + hint + "'", flush=True)
        return False
    key, wanted = _radio_choice(hint)
    pick = options[0]
    if wanted and wanted.lower() not in ("first", "default"):
        w = wanted.lower()
        match = [o for o in options if any(w == (o.get(k) or "").strip().lower() for k in ("value", "label"))]
        if not match:
            match = [o for o in options if w in (o.get("id") or "").lower() or w in (o.get("name") or "").lower().replace(" ", "")]
        if not match:
            match = [o for o in options if w in (o.get("label") or "").lower() or w in (o.get("value") or "").lower()]
            if len(match) > 1:
                match = []
        if not match:
            names = ", ".join((o.get("label") or o.get("value") or "?") for o in options)
            raise AssertionError("The option '" + wanted + "' set for " + key + " is not on the page. Options here: " + names)
        pick = match[0]
    def locate(o):
        if o.get("id"):
            return page.locator('input[type=radio][id="' + o["id"] + '"]')
        return page.locator('input[type=radio][name="' + o["name"] + '"][value="' + o["value"] + '"]')

    loc = locate(pick)
    inp = loc.first
    how = "set in .env" if wanted else "first option; set " + (key or "NAME") + " in .env to choose another"
    print("[IR-CHOICE] radio group '" + hint.split("*")[0].strip() + "': selecting " + (pick.get("label") or pick.get("value") or pick.get("id") or "?") + " (" + how + ")", flush=True)
    if not _choose(page, inp, inp):
        return False
    _remember(inp, loc)
    _hold(page, loc)
    if "beftn" in ((pick.get("label") or "") + (pick.get("value") or "")).lower():
        _PAYMENT["decided"] = True
    other = _cheque_if_no_bank_data(page, options, pick)
    if other is not None:
        loc2 = locate(other)
        inp2 = loc2.first
        if _choose(page, inp2, inp2):
            _remember(inp2, loc2)
            _hold(page, loc2)
            try:
                print("[IR-CHOICE] Cheque is selected: " + str(inp2.is_checked()), flush=True)
            except Exception:
                pass
    return True


def _click(page, loc, timeout=5000, hint=""):
    # A normal click, except that a radio button is checked afterwards to make sure it really got selected.
    el = loc.first
    try:
        el.wait_for(state="attached", timeout=timeout)
    except Exception:
        if hint and _click_radio_group(page, hint):
            return
        raise
    try:
        is_group = hint and el.locator("input[type=radio]").count() >= 2
    except Exception:
        is_group = False
    if is_group and _click_radio_group(page, hint):
        return
    inp = _radio_of(el)
    if inp is None:
        el.click(timeout=timeout)
        return
    if _PAYMENT.get("decided") and inp is not None:
        try:
            if inp.evaluate("e => e.name || e.id || ''") in _CHOSEN:
                print("[IR-CHOICE] the recorded click on this option group is skipped: the choice already made is kept", flush=True)
                return
        except Exception:
            pass
    if not _choose(page, el, inp):
        raise RuntimeError("Could not select the option: it stayed unselected after several ways of selecting it.")
    _remember(inp, loc)
    _hold(page, loc)


def _reapply_choices(page):
    # Radio buttons can be cleared when the page refreshes itself (for example after an employee is picked): select them again before saving.
    # One option per group is remembered, so a payment method decided earlier (BEFTN, or Cheque for lack of bank data) is kept.
    for group, loc in list(_CHOSEN.items()):
        try:
            el = loc.first
            inp = _radio_of(el)
            if inp is not None and not inp.is_checked():
                print("[IR-CHOICE] an option had been reset by the page; selecting it again (" + str(group) + ")", flush=True)
                _choose(page, el, inp)
        except Exception:
            pass


def _creation_problem(page, seconds=20, strict=True):
    # After a save. Returns the text of an error pop-up (the caller may try again), "" when the save went through,
    # or "STOP: ..." when the save clearly did not happen and trying another employee would not help.
    url0 = page.url
    seen_popup = False
    for i in range(int(seconds * 2)):
        texts = _popup_texts(page)
        for text in texts:
            if _PROBLEM_WORDS.search(text):
                return text
        if any(_DONE_WORDS.search(text) for text in texts):
            print("[IR-CREATED] the page said: " + " | ".join(t.strip()[:120] for t in texts if _DONE_WORDS.search(t)), flush=True)
            return ""
        if texts:
            seen_popup = True
        if not strict:
            page.wait_for_timeout(500)
            continue
        try:
            still_open = page.evaluate(_CREATE_BUTTON_JS)
        except Exception:
            still_open = True
        if (not still_open and i >= 1) or page.url != url0:
            print("[IR-CREATED] the form closed after Create (no message was seen)", flush=True)
            return ""
        if i == 6 and not texts:
            missing = _unfilled_required(page)
            if missing:
                return "STOP: Create did not go through. These required fields are still empty: " + ", ".join(missing) + "."
        page.wait_for_timeout(500)
    if not strict or seen_popup:
        return ""
    missing = _unfilled_required(page)
    if missing:
        return "STOP: Create did not go through. These required fields are still empty: " + ", ".join(missing) + "."
    return "STOP: Create was clicked but the form is still open and no confirmation or error message appeared, so the proposal was most likely not created."


def _wait_for_confirm_or_error(page, seconds=6):
    # After Create: wait for the confirmation button, or for an error pop-up that replaces it.
    yes = page.get_by_role("button", name="Yes").or_(page.locator("#yes-button"))
    for _ in range(int(seconds * 2)):
        try:
            if yes.first.is_visible():
                return ""
        except Exception:
            pass
        for text in _popup_texts(page):
            if _PROBLEM_WORDS.search(text):
                return text
        page.wait_for_timeout(500)
    return ""


def _dismiss_popups(page):
    # Close an error pop-up so the form can be used again.
    buttons = page.locator(_POPUP_SELECTOR).locator("button, a.close, .close, .ui-dialog-titlebar-close, .noty_close_button")
    try:
        total = buttons.count()
    except Exception:
        total = 0
    for i in range(total):
        button = buttons.nth(i)
        try:
            label = (button.inner_text() or button.get_attribute("title") or "").strip().lower()
            if button.is_visible() and label in ("ok", "close", "x", "×", "cancel", ""):
                button.click(timeout=2000)
                page.wait_for_timeout(400)
        except Exception:
            continue
    if _popup_texts(page):
        page.keyboard.press("Escape")
    page.wait_for_timeout(500)


def _sample_document():
    # A small real PDF that file pickers accept; set SAMPLE_UPLOAD_FILE to a document of your own to use that instead.
    own = os.environ.get("SAMPLE_UPLOAD_FILE", "")
    if own and Path(own).is_file():
        return Path(own)
    path = Path(tempfile.gettempdir()) / "Sample_Supporting_Document.pdf"
    stream = b"BT /F1 18 Tf 20 70 Td (Sample supporting document for automated testing) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 520 144] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    data = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(data))
        data += str(number).encode() + b" 0 obj\n" + body + b"\nendobj\n"
    xref = len(data)
    data += b"xref\n0 " + str(len(objects) + 1).encode() + b"\n0000000000 65535 f \n"
    for offset in offsets:
        data += ("%010d 00000 n \n" % offset).encode()
    data += b"trailer\n<< /Size " + str(len(objects) + 1).encode() + b" /Root 1 0 R >>\nstartxref\n" + str(xref).encode() + b"\n%%EOF\n"
    path.write_bytes(data)
    return path


def _employee_memory_path():
    import hashlib
    import tempfile
    from pathlib import Path
    seed = os.environ.get("BASE_URL", "") + "|" + str(globals().get("RADIO_SCENARIO", ""))
    return Path(tempfile.gettempdir()) / "aqea-employees" / (hashlib.sha1(seed.encode()).hexdigest()[:16] + ".json")


def _load_tried_employees():
    # Employees picked in earlier runs (rejected, or already given a record): they are tried last, so a run does not repeat them. EMPLOYEE_MEMORY=off disables this.
    import json
    import time
    if os.environ.get("EMPLOYEE_MEMORY", "on").lower() in ("off", "false", "0", "no"):
        return {}
    try:
        data = json.loads(_employee_memory_path().read_text())
        return {k: v for k, v in data.items() if time.time() - v < 86400}
    except Exception:
        return {}


_TRIED_AT_START = _load_tried_employees()


def _employee_key(row):
    try:
        return row.locator("td").first.inner_text().strip() or row.inner_text().strip()[:40]
    except Exception:
        return ""


def _note_employee(row):
    _note_employee_key(_employee_key(row))


def _note_employee_key(key):
    import json
    import time
    if os.environ.get("EMPLOYEE_MEMORY", "on").lower() in ("off", "false", "0", "no"):
        return
    if not key:
        return
    try:
        path = _employee_memory_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = _load_tried_employees()
        data[key] = time.time()
        path.write_text(json.dumps(data))
    except Exception:
        pass


def _row_order(rows):
    # The order in which list rows are tried: rows matching EMPLOYEE_PIN (comma separated) first, then employees not tried in earlier runs, then the others.
    total = rows.count()
    wanted = [w.strip().lower() for w in (os.environ.get("EMPLOYEE_PIN__" + str(globals().get("RADIO_SCENARIO", ""))) or os.environ.get("EMPLOYEE_PIN", "")).split(",") if w.strip()]
    first = []
    if wanted:
        for i in range(total):
            try:
                text = rows.nth(i).inner_text().lower()
            except Exception:
                continue
            if any(w in text for w in wanted):
                first.append(i)
        if first:
            print("[IR-ROW] preferring row(s) matching EMPLOYEE_PIN: " + ", ".join(str(i + 1) for i in first), flush=True)
    rest = [i for i in range(total) if i not in first]
    tried = [i for i in rest if _employee_key(rows.nth(i)) in _TRIED_AT_START]
    if tried and len(tried) < len(rest):
        print("[IR-ROW] " + str(len(tried)) + " employee(s) used in earlier runs are tried last", flush=True)
        rest = [i for i in rest if i not in tried] + tried
    return first + rest


def _fill_contact_fields(page):
    # Forms can require a personal mobile number and e-mail address that the recording never typed. Fill any that are visible and empty.
    if os.environ.get("AUTO_FILL_CONTACT", "on").lower() in ("off", "false", "0", "no"):
        return
    script = """() => {
      const out = [];
      for (const e of document.querySelectorAll('input, textarea')) {
        const t = (e.type || 'text').toLowerCase();
        if (['hidden','checkbox','radio','file','submit','button','password','date'].includes(t)) continue;
        if (e.disabled || e.readOnly || (e.value || '').trim() !== '') continue;
        const r = e.getBoundingClientRect();
        if (r.width < 2 || r.height < 2 || getComputedStyle(e).visibility === 'hidden') continue;
        const key = ((e.id || '') + ' ' + (e.name || '') + ' ' + (e.placeholder || '') + ' ' + t).toLowerCase();
        let kind = '';
        if (/e-?mail/.test(key)) kind = 'email';
        else if (/mobile|contactno|phone|cell/.test(key)) kind = 'mobile';
        if (kind) out.push({kind: kind, id: e.id || '', name: e.name || ''});
      }
      return out;
    }"""
    try:
        found = page.evaluate(script)
    except Exception:
        return
    for item in found:
        if item["id"]:
            field = page.locator('[id="' + item["id"] + '"]')
        else:
            field = page.locator('[name="' + item["name"] + '"]')
        value = ("qa" + str(random.randint(100000, 999999)) + "@example.com") if item["kind"] == "email" else ("01" + str(random.choice([3, 5, 6, 7, 8, 9])) + "".join(str(random.randint(0, 9)) for _ in range(8)))
        try:
            field.first.fill(value, timeout=3000)
            print("[IR-FILL] " + item["kind"] + " field " + (item["id"] or item["name"]) + " was empty; filled " + value, flush=True)
        except Exception as exc:
            print("[IR-FILL] could not fill " + (item["id"] or item["name"]) + ": " + str(exc)[:120], flush=True)


def _attach_documents(page):
    # The recording never captures the file picker, so the sample document goes into every empty file input before the form is saved.
    if os.environ.get("SAMPLE_UPLOAD", "on").lower() in ("off", "false", "0", "no"):
        return
    inputs = page.locator("input[type=file]")
    try:
        total = inputs.count()
    except Exception:
        total = 0
    if total == 0:
        return
    sample = _sample_document()
    for i in range(total):
        field = inputs.nth(i)
        name = field.get_attribute("id") or field.get_attribute("name") or ("file input " + str(i + 1))
        try:
            if field.evaluate("e => e.files && e.files.length > 0"):
                continue
            field.set_input_files(str(sample), timeout=5000)
            print("[IR-UPLOAD] attached " + sample.name + " to " + name, flush=True)
        except Exception as exc:
            print("[IR-UPLOAD] could not attach a file to " + name + ": " + str(exc)[:160], flush=True)
    page.wait_for_timeout(1500)


def _click_and_choose_file(page, locator):
    # Clicking Browse opens the operating system's file picker; answer it with the sample document.
    try:
        with page.expect_file_chooser(timeout=5000) as chooser:
            locator.first.click(timeout=5000)
        sample = _sample_document()
        chooser.value.set_files(str(sample))
        print("[IR-UPLOAD] chose " + sample.name + " in the file picker", flush=True)
    except Exception as exc:
        print("[IR-UPLOAD] no file picker opened (" + str(exc)[:100] + "); filling the file inputs directly", flush=True)
        _attach_documents(page)
        return
    page.wait_for_timeout(1500)


'''

_RUN_TESTS_BAT = '''@echo off
rem Runs the tests: creates a private Python environment the first time, installs what is needed, then runs pytest.
cd /d "%~dp0"
if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo A settings file named .env was created. Fill in the blank values, save it, then run RUN_TESTS.bat again.
  start /wait notepad ".env"
  pause
  exit /b 1
)
where py >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.10 or newer from https://www.python.org/downloads/ and run this file again.
  pause
  exit /b 1
)
if not exist ".venv\\Scripts\\python.exe" (
  echo Setting up Python for this project ^(first run only^)...
  py -m venv .venv
)
".venv\\Scripts\\python.exe" -m pip install --quiet -r requirements.txt
".venv\\Scripts\\python.exe" -m playwright install chromium
".venv\\Scripts\\python.exe" -m pytest -s %*
pause
'''

_RUN_TESTS_SH = '''#!/usr/bin/env sh
# Runs the tests: creates a private Python environment the first time, installs what is needed, then runs pytest.
cd "$(dirname "$0")" || exit 1
if [ ! -f .env ]; then
  cp .env.example .env
  echo "A settings file named .env was created. Fill in the blank values, save it, then run ./run_tests.sh again."
  exit 1
fi
[ -d .venv ] || python3 -m venv .venv || exit 1
. .venv/bin/activate
python -m pip install --quiet -r requirements.txt
python -m playwright install chromium
python -m pytest -s "$@"
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
    _first_url=str(next((st.get('url') for st in _ordered_steps(ir)[:1] if st.get('action')=='navigate'),'') or '')
    _starts_at_sign_in=bool(re.search(r'/(idp|auth)/realms/|/protocol/openid-connect/|/login-actions/|/login',_first_url))
    lines=['import base64','import datetime','import os','import random','import pytest','import tempfile','import time','from pathlib import Path','from urllib.parse import quote, quote_plus','from playwright.sync_api import expect',f'from pages.{module}_page import {cls}','','_T0 = time.time()','','def _goto_with_retry(page, url):','    last_status = None','    for attempt in range(3):','        response = _open_page(page, url)','        last_status = response.status if response else None','        if last_status is None or last_status < 500:','            return response','        if attempt < 2:','            time.sleep(2 * (attempt + 1))','    raise RuntimeError(f"Target unavailable: HTTP {last_status} for {url}")','','','def _rebase(text, recorded_origin, base_url):','    """Point absolute recorded-environment URLs inside a query string (e.g. the OIDC redirect_uri) at the environment under test."""','    target = base_url.rstrip("/")','    return text.replace(quote_plus(recorded_origin), quote_plus(target)).replace(recorded_origin, target)','','',f'REUSE_SESSION = {not _starts_at_sign_in}',f'RADIO_SCENARIO = {_json(module.upper())}','','',f'def {test_fn}(page, base_url):',f'    screen = {cls}(page)','    assets = Path(__file__).resolve().parents[1] / "assets"','    _skip = 0']
    _i=lines.index('def _goto_with_retry(page, url):'); _secret_names={str((x.get('value') or {}).get('reference')) for x in ir['steps'] if (x.get('value') or {}).get('source')=='secret' and (x.get('value') or {}).get('reference')}
    _recorded={str(k):('' if v.get('default') is None else str(v.get('default'))) for k,v in params.items() if isinstance(v,dict) and str(k) not in _secret_names}
    lines[_i:_i]=_SETTLE_HELPER.split('\n')+_FLOW_HELPER.split('\n')+_SETTING_HELPER.split('\n')+[f'_SCENARIO = {_json(module.upper())}',f'_DEFAULTS = {json.dumps(_recorded,ensure_ascii=False)}','','']
    source_map={}
    ordered_steps=_ordered_steps(ir)
    # When a recorded employee PIN is picked from a list and a later click saves the form, the part from opening the list to saving
    # is repeated with the next employee while the application answers with an error pop-up (for example a missing approval mapping).
    def _is_row_pick(candidate_step):
        pick_key=str(candidate_step.get('element') or '')
        return candidate_step.get('action')=='click' and pick_key.isdigit() and len(pick_key)>=6
    retry_start=retry_end=create_idx=confirm_idx=None
    pick_idx=next((i for i,x in enumerate(ordered_steps) if _is_row_pick(x)),None)
    if pick_idx is not None:
        create_idx=next((i for i in range(pick_idx+1,len(ordered_steps)) if ordered_steps[i].get('action')=='click' and re.search(r'create|save|submit',str(ordered_steps[i].get('element') or ''),re.I)),None)
    if create_idx is not None:
        retry_start=pick_idx-1 if pick_idx>0 and ordered_steps[pick_idx-1].get('action')=='click' else pick_idx
        retry_end=create_idx
        if create_idx+1<len(ordered_steps):
            after_create=ordered_steps[create_idx+1]
            if after_create.get('action')=='click' and (_is_button_element(elements.get(str(after_create.get('element') or '')) or {}) or _is_yes_element(elements.get(str(after_create.get('element') or '')) or {})):
                confirm_idx=create_idx+1; retry_end=confirm_idx
        if any(ordered_steps[i].get('action')=='navigate' for i in range(retry_start,retry_end+1)):
            retry_start=retry_end=create_idx=confirm_idx=None
    repeat_save=set(); _seen_save=set()
    for _i,_x in enumerate(ordered_steps):
        _k=str(_x.get('element') or '')
        if _x.get('action')=='click' and re.search(r'create|save|submit',_k,re.I):
            if _k in _seen_save: repeat_save.add(_i)
            _seen_save.add(_k)
    block_start=block_end=None
    # A recording that signed in, then navigated back to the sign-in page and signed in again (for example after a typing mistake)
    # must not repeat the sign-in when the first attempt already worked: that page answers "You are already logged in".
    _signin_url=re.compile(r'/(idp|auth)/realms/|/protocol/openid-connect/|/login-actions/')
    def _is_signin_navigation(candidate_step):
        return candidate_step.get('action')=='navigate' and bool(_signin_url.search(str(candidate_step.get('url') or '')))
    signin_start=signin_end=None
    if ordered_steps and _is_signin_navigation(ordered_steps[0]):
        signin_start=next((i for i in range(1,len(ordered_steps)) if _is_signin_navigation(ordered_steps[i])),None)
        if signin_start is not None:
            after_signin=next((i for i in range(signin_start+1,len(ordered_steps)) if ordered_steps[i].get('action')=='navigate' and not _is_signin_navigation(ordered_steps[i])),None)
            if after_signin is None: signin_start=None
            else: signin_end=after_signin-1
    sign_block_start=sign_block_end=None
    for step_index,step in enumerate(ordered_steps):
        if signin_start is not None and step_index==signin_start:
            lines.append('    _settle(page)')
            sign_block_start=len(lines)
        if signin_end is not None and step_index==signin_end+1: sign_block_end=len(lines)
        if retry_start is not None and step_index==retry_start: block_start=len(lines)
        if retry_end is not None and step_index==retry_end+1: block_end=len(lines)
        sid=str(step['id']); action=step['action']; source_map[sid]={'file':f'tests/test_{module}.py','line':len(lines)+1}
        lines.append(f'    # IR-STEP: {sid}')
        lines.append(f'    print("[IR-STEP] {sid} {action} ({step_index+1}/{len(ordered_steps)}) +" + str(int(time.time() - _T0)) + "s", flush=True)')
        if action=='click' and re.search(r'create|save|submit',str(step.get('element') or ''),re.I):
            lines.append('    _fill_contact_fields(page)')
            lines.append('    _reapply_choices(page)')
            lines.append('    _attach_documents(page)')
        if confirm_idx is not None and step_index==confirm_idx:
            lines += ['    _problem = _wait_for_confirm_or_error(page)', '    if _problem:', '        return _problem']
        if action=='navigate':
            if step_index>0 and ordered_steps[step_index-1].get('action') in {'click','keyboard'}:
                lines.append('    _settle(page)')
            dynamic_state=_dynamic_timestamp_state(step.get('url'))
            if dynamic_state:
                prefix,suffix=dynamic_state
                origin=_origin(step.get('url'))
                prefix_expr=f'_rebase({_json(prefix)}, {_json(origin)}, base_url)' if _embeds_origin(prefix,origin) else _json(prefix)
                lines.append(f'    _state = base64.b64encode(f"time:{{int(time.time()*1000)}}{suffix}".encode()).decode()')
                lines.append(f'    _goto_with_retry(page, _join_url(base_url, {prefix_expr}) + "state=" + quote(_state, safe=""))')
            else:
                rel=_relative_url(step.get('url'))
                origin=_origin(step.get('url'))
                rel_expr=f'_rebase({_json(rel)}, {_json(origin)}, base_url)' if _embeds_origin(rel,origin) else _json(rel)
                lines.append(f'    _target = _join_url(base_url, {rel_expr})')
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
                elif key and _date_format(element):
                    _js="(e, v) => { e.removeAttribute('readonly'); e.value = v; e.dispatchEvent(new Event('input', {bubbles: true})); e.dispatchEvent(new Event('change', {bubbles: true})); }"
                    lines.append('    # The recording opened the calendar but did not keep the day that was picked, so a date is set if the field stays empty.')
                    # Pages often have several date fields with the same placeholder, so the field's own id is used when it is known.
                    _date_id=_id_of(element)
                    _field_loc=f'page.locator({_json("[id="+chr(34)+_date_id+chr(34)+"]")})' if _date_id else loc
                    lines.append(f'    _field = {_field_loc}.first')
                    lines.append('    _field.click(timeout=5000)')
                    lines.append(f'    print({_json("[IR-DATE] "+sid+": the date field holds ")} + repr(_field.input_value()) + " after opening the calendar", flush=True)')
                    _rname,_roff,_forced=_date_rule(key,element)
                    _offset=f'int(os.environ.get({_json(_rname)}, "{_roff}") or {_roff})' if _rname else str(_roff)
                    lines.append(f'    _when = (datetime.date.today() + datetime.timedelta(days={_offset})).strftime({_json(_date_format(element))})')
                    lines.append('    if ' + ('_field.input_value() != _when:' if _forced else 'not any(ch.isdigit() for ch in _field.input_value()):'))
                    lines.append(f'        print({_json("[IR-DATE] "+sid+": the date field is set to ")} + _when, flush=True)')
                    if _forced:
                        lines.append('        _field.fill("")')
                    lines.append('        _field.press_sequentially("".join(ch for ch in _when if ch.isdigit()), delay=40)')
                    lines.append('        if _field.input_value() != _when:')
                    lines.append(f'            _field.evaluate({_json(_js)}, _when)')
                    lines.append(f'        print({_json("[IR-DATE] "+sid+": the date field now holds ")} + repr(_field.input_value()), flush=True)')
                    # Tab (not Escape) leaves the field: on a masked input Escape undoes the typed value.
                    lines.append('    _field.press("Tab")')
                    lines.append('    page.wait_for_timeout(500)')
                    lines.append(f'    print({_json("[IR-DATE] "+sid+": after leaving the field it holds ")} + repr(_field.input_value()), flush=True)')
                elif key and _is_browse_element(element):
                    lines.append('    # Browse opens the operating system\'s file picker, which a recording cannot capture; a sample document is chosen instead.')
                    lines.append(f'    _click_and_choose_file(page, {loc})')
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
                    lines.append('        _rows = _grid.locator("tbody tr:not(:has(td.dataTables_empty))")')
                    lines.append('        _row = _rows.first')
                    lines.append('        try:')
                    lines.append('            _row.wait_for(state="visible", timeout=15000)')
                    lines.append('        except Exception:')
                    lines.append(f'            raise RuntimeError({_json("The table has no rows to select (recorded target "+str(key)+"). Make sure the list contains at least one record.")})')
                    lines.append('        _order = _row_order(_rows)')
                    lines.append('        if _skip >= len(_order):')
                    lines.append('            raise RuntimeError("No employee left to try: the list shows " + str(len(_order)) + " row(s) and every one of them was rejected.")')
                    lines.append('        _row = _rows.nth(_order[_skip])')
                    lines.append('        _note_employee(_row)')
                    lines.append('        print("[IR-ROW] selecting row " + str(_order[_skip] + 1) + ": " + " | ".join(t.strip() for t in _row.locator("td").all_inner_texts())[:200], flush=True)')
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
                    lines.append('        try:')
                    lines.append(f'            {loc}.first.click(timeout=5000)')
                    lines.append('        except Exception:')
                    lines.append(f'            raise _NotShown({_json("The list of records did not open (recorded target "+str(key)+").")})')
                elif key and step_index in repeat_save:
                    lines.append('    try:')
                    lines.append(f'        {loc}.first.wait_for(state="visible", timeout=3000)')
                    lines.append(f'        {loc}.first.click(timeout=3000)')
                    lines.append('        _quiet(page)')
                    lines.append('    except Exception:')
                    lines.append(f'        print({_json("[IR-SKIP] "+sid+": the button ("+str(key)+") was already used to save the record, and it is not on this page; the record was saved before this step.")}, flush=True)')
                elif key and _is_toast_element(key, element):
                    lines.append('    try:')
                    lines.append(f'        {loc}.first.click(timeout=2000)')
                    lines.append('    except Exception:')
                    lines.append(f'        print({_json("[IR-SKIP] "+sid+": the notification ("+str(key)+") is not on screen any more; it disappears by itself.")}, flush=True)')
                elif key and _is_confirm_button(element):
                    lines.append('    try:')
                    lines.append(f'        {loc}.first.wait_for(state="visible", timeout=5000)')
                    lines.append(f'        {loc}.first.click(timeout=3000)')
                    lines.append('        _quiet(page)')
                    lines.append('    except Exception:')
                    lines.append(f'        print({_json("[IR-SKIP] "+sid+": the confirmation button ("+str(key)+") is not shown; the pop-up was already confirmed or did not appear.")}, flush=True)')
                elif key and _is_optional_dismiss(element):
                    lines.append(f'    if {loc}.count() > 0 and {loc}.first.is_visible():')
                    lines.append(f'        {loc}.first.click(timeout=3000)')
                else:
                    lines.append('    try:')
                    _hint=next((str(c.get('value')) for c in _candidate_list(element) if c.get('strategy')=='text' and c.get('value')),'')
                    lines.append(f'        _click(page, {loc}, hint={_json(_hint)})' if _hint else f'        _click(page, {loc})')
                    lines.append('    except AssertionError:')
                    lines.append('        raise')
                    lines.append('    except Exception:')
                    navigated_to=(step.get('metadata') or {}).get('navigatedTo')
                    if navigated_to and not _is_button_element(element):
                        rel=_relative_url(navigated_to)
                        _warn=f"[IR-WARN] {sid}: could not click the recorded target ({key}); opened {rel} instead, so the action that click performs did not happen."
                        lines.append(f'        print({_json(_warn)}, flush=True)')
                        lines.append(f'        page.goto(_join_url(base_url, {_json(rel)}))')
                    else:
                        lines.append(f'        {loc}.first.dispatch_event("click", timeout=3000)')
                    lines.append('    _quiet(page)')
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
                    lines.append(f'    {loc}.press_sequentially(_setting({_json(ref)}{", True" if v.get("source")=="secret" else ""}), delay=150)')
                else:
                    lines.append(f'    {loc}.fill(_setting({_json(ref)}{", True" if v.get("source")=="secret" else ""}))')
                    lines.append('    _quiet(page)')
            elif action=='select':
                if not loc: raise GeneratorError(f'IR step {sid} requires a locator for element {key}.', 'UNSUPPORTED_LOCATOR', [str(key)])
                v=step.get('value') or {}; ref=str(v.get('reference') or 'VALUE'); lines.append(f'    _pick(page, {loc}, _setting({_json(ref)}{", True" if v.get("source")=="secret" else ""}))')
            elif action=='check':
                if not loc: raise GeneratorError(f'IR step {sid} requires a locator for element {key}.', 'UNSUPPORTED_LOCATOR', [str(key)])
                lines.append(f'    {loc}.check()')
                lines.append('    _quiet(page)')
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
    def _wrap_block(start,end,head,tail):
        inner=['    '+x if x else x for x in lines[start:end]]
        wrapped=head+inner+tail
        shift_after=len(wrapped)-(end-start)
        for _entry in source_map.values():
            if start < _entry['line'] <= end: _entry['line']+=len(head)
            elif _entry['line'] > end: _entry['line']+=shift_after
        lines[start:end]=wrapped
    _wraps=[]
    if retry_start is not None and block_start is not None:
        if block_end is None: block_end=len(lines)
        _wraps.append((block_start,block_end,['    def _attempt(_skip):'],[
            '        return _creation_problem(page)','',
            '    _tries = 0','    while True:','        try:','            _problem = _attempt(_tries)','        except _NotShown as _gone:','            _problem = str(_gone)','        if not _problem:','            break','        if _problem.startswith("STOP: "):','            raise AssertionError(_problem[6:])',
            '        print("[IR-RETRY] employee " + str(_tries + 1) + " was rejected: " + " ".join(_problem.split())[:300], flush=True)',
            '        _tries += 1','        if _tries >= 10:',
            '            raise AssertionError("The proposal could not be created with any of the first 10 employees. Last message: " + " ".join(_problem.split())[:300])',
            '        _dismiss_popups(page)']))
    if signin_start is not None and sign_block_start is not None and sign_block_end is not None:
        _first=str(ordered_steps[signin_start]['id']); _last=str(ordered_steps[signin_end]['id'])
        _wraps.append((sign_block_start,sign_block_end,['    if _SIGN_IN_URL.search(page.url):'],[
            '    else:',
            f'        print({_json("[IR-SKIP] "+_first+" to "+_last+": the browser is already signed in, so the recorded second sign-in is skipped.")}, flush=True)']))
    for _w in sorted(_wraps,key=lambda w:w[0],reverse=True): _wrap_block(*_w)
    files[f'tests/test_{module}.py']='\n'.join(lines)+'\n'; files['tests/__init__.py']=''
    files['tests/conftest.py']=_CONFTEST_HEAD+'''

@pytest.fixture(scope="session")
def base_url():
    return os.environ.get("BASE_URL", "http://localhost")


def _session_file():
    # A signed-in session is kept for a while so the next scenario can start signed in. A scenario that starts at the sign-in page does not use it.
    path = os.environ.get("SESSION_STATE_FILE") or str(_ROOT / ".session-state.json")
    return Path(path)


@pytest.fixture
def page(request):
    import time as _time
    browser_name = os.environ.get("BROWSER", "chromium").lower()
    headless = os.environ.get("HEADLESS", "true").lower() != "false"
    state = _session_file()
    max_age = int(os.environ.get("SESSION_MAX_MINUTES", "60") or 60) * 60
    if os.environ.get("ISOLATE_TESTS", "false").lower() == "true":
        state.unlink(missing_ok=True)
    elif state.exists() and _time.time() - state.stat().st_mtime > max_age:
        state.unlink(missing_ok=True)
    reuse = bool(getattr(request.module, "REUSE_SESSION", False)) and state.exists()
    with sync_playwright() as p:
        browser_type = getattr(p, browser_name if browser_name in {"chromium", "firefox", "webkit"} else "chromium")
        slow_mo = int(os.environ.get("SLOW_MO", "0" if headless else "250") or 0)
        browser = browser_type.launch(headless=headless, slow_mo=slow_mo)
        context = browser.new_context(storage_state=str(state)) if reuse else browser.new_context()
        pg = context.new_page()
        try:
            yield pg
        finally:
            try:
                if not re.search(r"/(idp|auth)/realms/|/protocol/openid-connect/|/login-actions/", pg.url):
                    state.parent.mkdir(parents=True, exist_ok=True)
                    context.storage_state(path=str(state))
            except Exception:
                pass
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
        if re.search(r"/(idp|auth)/realms/|/protocol/openid-connect/|/login-actions/", pg.url):
            say("HINT: the browser is on the sign-in page, so this run is not signed in. Select the sign-in scenario (for example Validate User Login) together with this one and put it first, or record this scenario starting from the sign-in page.")
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
        notes = pg.eval_on_selector_all(".error, .errorMessage, label.error, .field-error, .ui-state-error, .alert, .toast, .noty_message, .invalid-feedback, .help-block", "els => els.filter(e => e.offsetParent !== null).map(e => (e.innerText || '').trim()).filter(t => t)")
        say("validation messages: " + (" | ".join(notes)[:600] if notes else "none"))
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
    _user_default=next((str(params[n].get('default')) for n in ('username','userName','user','userId','userid','login','loginId') if isinstance(params.get(n),dict) and params[n].get('default') not in (None,'')),'')
    _user_tag=re.sub(r'[^A-Za-z0-9]+','_',_user_default).strip('_').upper()
    _scenario_key=module.upper()
    env=[f'BASE_URL={_base_url_from_ir(ir)}','BROWSER=chromium','HEADLESS=false','SLOW_MO=250','STEP_DELAY_MS=300']
    _is_contact=lambda n: bool(re.search(r'contact|mobile|phone|cell',n,re.I)) and not re.search(r'mail',n,re.I)
    for _name in parameter_refs:
        if _name in secret_refs or _is_contact(_name): continue
        _spec=params.get(_name)
        _val=_spec.get('default') if isinstance(_spec,dict) else None
        env.append(f'{_name}__{_scenario_key}={"" if _val is None else _val}')
    for _name in secret_refs:
        env.append(f'{_name}_{_user_tag}=' if _user_tag else f'{_name}=')
    readme_secret_line=next((x for x in env if secret_refs and x.startswith(secret_refs[0])),'SECRET_PASSWORD'+'=')
    env.append('# Optional: when a recorded drop-down entry is not in the list, take the first real entry. Example: PICK_ANY_IF_MISSING=paymentCollectionPoint (or all)')
    env.append('# optional: PICK_ANY_IF_MISSING')
    env.append('# optional: EMPLOYEE_PIN')
    env.append('# optional: FIXED_CONTACT_NO')
    env.append('# optional: EMPLOYEE_PIN__'+_scenario_key)
    env.append('# Test data from the recording can be changed in the .env file, for every scenario (NAME=value) or for this scenario only (NAME__'+_scenario_key+'=value). Employee: EMPLOYEE_PIN=00134572 (several PINs separated by commas: one that was not used before is taken).')
    for _name in parameter_refs:
        if _name in secret_refs or _is_contact(_name) or _name in ('username','userName','user','userId','userid','login','loginId'): continue
        if not re.fullmatch(r'[A-Za-z0-9]+',_name): continue
        env.append(f'# optional: {_name}')
        env.append(f'# optional: {_name}__{_scenario_key}')
    _radio_keys=[]
    for _st in _ordered_steps(ir):
        if _st.get('action')!='click': continue
        for _c in _candidate_list(elements.get(str(_st.get('element'))) or {}):
            _t=str(_c.get('value') or '')
            if _c.get('strategy')=='text' and '*' in _t:
                _k=re.sub(r'[^A-Za-z0-9]+','_',_t.split('*')[0]).strip('_').upper()
                if _k and _k not in _radio_keys: _radio_keys.append(_k)
    if _radio_keys:
        env.append('# Optional choices for option groups (radio buttons). Leave them out to select the first option. Example: '+_radio_keys[0]+'=Cheque')
        for _k in _radio_keys:
            env.append(f'# optional: {_k}')
            env.append(f'# optional: {_k}__{_scenario_key}')
    files['.env.example']='\n'.join(env)+'\n'
    files['RUN_TESTS.bat']=_RUN_TESTS_BAT
    files['run_tests.sh']=_RUN_TESTS_SH
    files['automation-ir.json']=json.dumps(ir,indent=2,ensure_ascii=False,sort_keys=True)+'\n'
    files['source-map.json']=json.dumps(source_map,indent=2)+'\n'
    files['README.md']=f'''# {scenario_name} — Playwright + Pytest

Generated deterministically from canonical Automation IR.

## Easiest way to run it (Windows)

1. Open this folder in VS Code (File > Open Folder).
2. Double-click `RUN_TESTS.bat`. The first time it creates a file named `.env` and opens it.
3. Type the missing values in `.env` (the password goes after the = sign on the line that starts with `{readme_secret_line}`), save, and double-click `RUN_TESTS.bat` again.

On Mac or Linux run `./run_tests.sh` instead.

## Run it yourself from the VS Code terminal

```powershell
py -m venv .venv
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
py -m playwright install chromium
py -m pytest -s
```

The tests read BASE_URL, the user name and the password from the `.env` file in this folder, so nothing needs to be typed into the terminal.
To use another environment, change the `BASE_URL` line. To watch the browser, set `HEADLESS=false`.
Secrets are referenced by name and are never written into the test code. `.env` holds real passwords: do not share or commit it.
'''
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
    files['.env.example']='\n'.join([f'BASE_URL={_base_url_from_ir(ir)}','BROWSER=chrome','HEADLESS=true']+[f'{x}=' for x in runtime_refs if not (re.search(r'contact|mobile|phone|cell',x,re.I) and not re.search(r'mail',x,re.I))])+'\n'
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

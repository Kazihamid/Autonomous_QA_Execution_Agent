RECORDER_INIT_SCRIPT = r"""
(() => {
  if (window.__pocRecorderInstalled) return;
  window.__pocRecorderInstalled = true;

  const text = (v) => (v || '').toString().replace(/\s+/g, ' ').trim();
  const isSensitive = (el) => {
    if (!el) return false;
    const type = (el.getAttribute?.('type') || '').toLowerCase();
    const bag = [el.id, el.name, el.getAttribute?.('aria-label'), el.getAttribute?.('autocomplete')]
      .filter(Boolean).join(' ').toLowerCase();
    return type === 'password' || /(password|secret|token|api[-_ ]?key|authorization)/i.test(bag);
  };
  const implicitRole = (el) => {
    const tag = (el.tagName || '').toLowerCase();
    const type = (el.getAttribute?.('type') || '').toLowerCase();
    if (tag === 'button') return 'button';
    if (tag === 'a' && el.getAttribute('href')) return 'link';
    if (tag === 'select') return 'combobox';
    if (tag === 'textarea') return 'textbox';
    if (tag === 'input') {
      if (['button','submit','reset'].includes(type)) return 'button';
      if (type === 'checkbox') return 'checkbox';
      if (type === 'radio') return 'radio';
      if (type === 'file') return '';
      return 'textbox';
    }
    return '';
  };
  const labelFor = (el) => {
    if (!el) return '';
    if (el.labels && el.labels.length) return text(Array.from(el.labels).map(x => x.innerText).join(' '));
    const id = el.id;
    if (id) {
      try {
        const lbl = document.querySelector(`label[for="${CSS.escape(id)}"]`);
        if (lbl) return text(lbl.innerText);
      } catch (_) {}
    }
    const parentLabel = el.closest?.('label');
    return parentLabel ? text(parentLabel.innerText) : '';
  };
  const cssPath = (el) => {
    if (!el || !el.tagName) return '';
    if (el.id) {
      try { return '#' + CSS.escape(el.id); } catch (_) {}
    }
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && parts.length < 8) {
      let part = (node.tagName || '').toLowerCase();
      if (!part) break;
      const stableClasses = Array.from(node.classList || [])
        .filter(c => c && !/^(css-|sc-|ng-|chakra-|Mui|ant-)/.test(c))
        .filter(c => !/\d{4,}/.test(c))
        .slice(0, 2);
      if (stableClasses.length) part += stableClasses.map(c => '.' + CSS.escape(c)).join('');
      const parent = node.parentElement;
      if (parent) {
        const siblings = Array.from(parent.children).filter(x => x.tagName === node.tagName);
        if (siblings.length > 1) part += ':nth-of-type(' + (siblings.indexOf(node) + 1) + ')';
      }
      parts.unshift(part);
      if (node.getAttribute?.('data-testid') || node.getAttribute?.('name')) break;
      node = parent;
    }
    return parts.join(' > ');
  };
  const xpathPath = (el) => {
    if (!el || !el.tagName) return '';
    if (el.id) return '//*[@id="' + el.id.replace(/"/g, '\\"') + '"]';
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && parts.length < 8) {
      const tag = (node.tagName || '').toLowerCase();
      if (!tag) break;
      let index = 1;
      let sib = node.previousElementSibling;
      while (sib) { if (sib.tagName === node.tagName) index++; sib = sib.previousElementSibling; }
      parts.unshift(tag + '[' + index + ']');
      node = node.parentElement;
    }
    return '/' + parts.join('/');
  };
  const targetMeta = (el) => {
    if (!el || !el.getAttribute) return {};
    const sensitive = isSensitive(el);
    const type = (el.getAttribute('type') || '').toLowerCase();
    const value = sensitive ? null : (['checkbox','radio'].includes(type) ? !!el.checked : (el.value ?? null));
    const files = type === 'file' && el.files ? Array.from(el.files).map(f => ({name:f.name, type:f.type, size:f.size})) : [];
    return {
      tag: (el.tagName || '').toLowerCase(),
      type,
      id: el.id || '',
      name: el.getAttribute('name') || '',
      role: el.getAttribute('role') || implicitRole(el),
      accessibleName: text(el.getAttribute('aria-label') || labelFor(el) || ((el.tagName || '').toLowerCase() === 'input' ? '' : (el.innerText || '')) || el.getAttribute('placeholder') || ''),
      label: labelFor(el),
      placeholder: el.getAttribute('placeholder') || '',
      text: text(el.innerText || ''),
      testId: el.getAttribute('data-testid') || el.getAttribute('data-test') || '',
      css: cssPath(el),
      xpath: xpathPath(el),
      value,
      checked: ['checkbox','radio'].includes(type) ? !!el.checked : null,
      sensitive,
      files
    };
  };
  const emit = (eventType, el, extra={}) => {
    try {
      window.__recorderEmit({
        eventType,
        target: targetMeta(el),
        context: { url: location.href, title: document.title, ...extra }
      });
    } catch (_) {}
  };
  const actionableTarget = (event) => {
    const selector = 'button,a,input,select,textarea,[role="button"],[role="link"],[role="menuitem"],[onclick],[tabindex]';
    const path = event.composedPath ? event.composedPath() : [event.target];
    for (const node of path) {
      try { if (node && node.matches && node.matches(selector)) return node; } catch (_) {}
    }
    try {
      const li = event.target && event.target.closest ? event.target.closest('li') : null;
      const link = li && li.querySelector ? li.querySelector('a.routable, a[href]') : null;
      if (link) return link;
    } catch (_) {}
    return event.target;
  };

  document.addEventListener('click', e => emit('click', actionableTarget(e)), true);
  document.addEventListener('input', e => emit('input', e.target), true);
  document.addEventListener('change', e => emit('change', e.target), true);
  document.addEventListener('focus', e => emit('focus', e.target), true);
  document.addEventListener('blur', e => emit('blur', e.target), true);
  document.addEventListener('submit', e => emit('submit', e.target), true);
  document.addEventListener('keydown', e => {
    if (['Enter','Tab','Escape'].includes(e.key)) emit('keydown', e.target, {key:e.key});
  }, true);

  window.__pocRecorderMarkAssertion = (selector, assertionType='visible', expected=null) => {
    const el = document.querySelector(selector);
    emit('assertion', el, {selector, assertionType, expected});
  };
  window.__pocRecorderCheckpoint = (description) => {
    window.__recorderEmit({eventType:'checkpoint', target:{}, context:{url:location.href, description}});
  };
})();
"""

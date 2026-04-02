// LkyPanel File Manager — Part 1: core state, API, rendering
const SITE_ID = '{{ site.id }}';
const API_URL = `/filemanager/site/${SITE_ID}/api/`;
const UPLOAD_URL = `/filemanager/site/${SITE_ID}/upload/`;
const DOWNLOAD_URL = `/filemanager/site/${SITE_ID}/download/`;

function getCsrf() {
  return document.cookie.split(';').map(c => c.trim()).find(c => c.startsWith('csrftoken='))?.split('=')[1] || '';
}

async function apiFetch(data) {
  const r = await fetch(API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
    body: JSON.stringify(data)
  });
  return r.json();
}

const FM = (() => {
  let state = {
    path: '',
    entries: [],
    total: 0,
    page: 1,
    perPage: 200,
    sort: 'name',
    reverse: false,
    search: '',
    view: 'grid',
    selected: new Set(),
    clipboard: null, // {action:'copy'|'cut', dir, items}
    ctxEntry: null,
    newMode: 'file',
    chmodPath: '',
    destAction: null,
    destPath: '',
    editorPath: '',
  };

  // ── Toast ──────────────────────────────────────────────────────────────
  function toast(msg, type = 'info') {
    const wrap = document.getElementById('fm-toasts');
    const el = document.createElement('div');
    el.className = `fm-toast ${type}`;
    el.textContent = msg;
    wrap.appendChild(el);
    setTimeout(() => el.remove(), 3500);
  }

  // ── Modal helpers ──────────────────────────────────────────────────────
  function openModal(id) { document.getElementById(id).classList.add('show'); }
  function closeModal(id) { document.getElementById(id).classList.remove('show'); }

  function confirm(title, msg, onOk) {
    document.getElementById('confirm-title').textContent = title;
    document.getElementById('confirm-msg').textContent = msg;
    const btn = document.getElementById('confirm-ok');
    btn.onclick = () => { closeModal('modal-confirm'); onOk(); };
    openModal('modal-confirm');
  }

  // ── File icons ─────────────────────────────────────────────────────────
  function fileIcon(entry) {
    if (entry.is_dir) return 'ph-folder';
    const ext = entry.name.split('.').pop().toLowerCase();
    if (['jpg','jpeg','png','gif','svg','webp','ico','bmp'].includes(ext)) return 'ph-file-image';
    if (['zip','tar','gz','bz2','xz','7z','rar'].includes(ext)) return 'ph-file-archive';
    if (['js','ts','py','php','html','css','json','xml','yml','yaml','sh','go','rs','java','c','cpp','rb','sql'].includes(ext)) return 'ph-file-code';
    if (['pdf','doc','docx','xls','xlsx','ppt','pptx','odt'].includes(ext)) return 'ph-file-text';
    if (['mp4','mkv','avi','mov','webm'].includes(ext)) return 'ph-file-video';
    if (['mp3','wav','ogg','flac'].includes(ext)) return 'ph-file-audio';
    return 'ph-file';
  }

  function isArchive(name) {
    return /\.(zip|tar\.gz|tgz|tar\.bz2|tar\.xz|tar)$/i.test(name);
  }

  function fmtSize(bytes) {
    if (bytes === 0) return '—';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB';
    return (bytes / 1073741824).toFixed(1) + ' GB';
  }

  function fmtDate(ts) {
    if (!ts) return '—';
    return new Date(ts * 1000).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  }

  // ── Load directory ─────────────────────────────────────────────────────
  async function load(path, page) {
    if (path !== undefined) state.path = path;
    if (page !== undefined) state.page = page;
    const res = await apiFetch({
      action: 'list', path: state.path, page: state.page,
      per_page: state.perPage, sort: state.sort,
      reverse: state.reverse, search: state.search
    });
    if (!res.status) { toast(res.error, 'error'); return; }
    state.entries = res.entries;
    state.total = res.total;
    state.selected.clear();
    renderBreadcrumb(res.breadcrumbs);
    renderTree(res.breadcrumbs);
    renderContent();
    updateBulk();
    updateStatus();
  }

  // ── Breadcrumb ─────────────────────────────────────────────────────────
  function renderBreadcrumb(crumbs) {
    const el = document.getElementById('fm-breadcrumb');
    let html = `<span onclick="FM.load('')"><i class="ph ph-house"></i> Home</span>`;
    crumbs.forEach((c, i) => {
      html += ` <i class="ph ph-caret-right"></i> `;
      if (i === crumbs.length - 1)
        html += `<span class="current">${esc(c.name)}</span>`;
      else
        html += `<span onclick="FM.load('${esc(c.path)}')">${esc(c.name)}</span>`;
    });
    el.innerHTML = html;
  }

  // ── Sidebar tree ───────────────────────────────────────────────────────
  function renderTree(crumbs) {
    const el = document.getElementById('fm-tree');
    let html = `<div class="fm-tree-item ${state.path===''?'active':''}" onclick="FM.load('')"><i class="ph ph-house"></i> Home</div>`;
    crumbs.forEach(c => {
      html += `<div class="fm-tree-item" style="padding-left:1.2rem" onclick="FM.load('${esc(c.path)}')"><i class="ph ph-folder"></i> ${esc(c.name)}</div>`;
    });
    // Show subdirs of current
    state.entries.filter(e => e.is_dir).forEach(e => {
      const p = state.path ? state.path + '/' + e.name : e.name;
      html += `<div class="fm-tree-item" style="padding-left:${(crumbs.length+1)*0.8+0.6}rem" onclick="FM.load('${esc(p)}')"><i class="ph ph-folder"></i> ${esc(e.name)}</div>`;
    });
    el.innerHTML = html;
  }

  // ── Content area ───────────────────────────────────────────────────────
  function renderContent() {
    const el = document.getElementById('fm-content');
    if (!state.entries.length) {
      el.innerHTML = `<div class="fm-empty"><i class="ph ph-folder-open"></i><span>This folder is empty</span></div>`;
      return;
    }
    if (state.view === 'grid') renderGrid(el);
    else renderList(el);
  }

  function renderGrid(el) {
    let html = '<div class="fm-grid">';
    state.entries.forEach(e => {
      const sel = state.selected.has(e.name);
      const icon = fileIcon(e);
      const p = state.path ? state.path + '/' + e.name : e.name;
      html += `<div class="fm-card${sel?' selected':''}" data-name="${esc(e.name)}"
        onclick="FM.cardClick(event,'${esc(e.name)}')"
        ondblclick="FM.open('${esc(e.name)}',${e.is_dir})"
        oncontextmenu="FM.showCtx(event,'${esc(e.name)}',${e.is_dir})">
        <div class="fm-card-check"><i class="ph ph-check" style="${sel?'':'display:none'}"></i></div>
        <i class="ph ${icon} fm-card-icon" style="color:${e.is_dir?'#f59e0b':'#94a3b8'}"></i>
        <div class="fm-card-name" title="${esc(e.name)}">${esc(e.name)}</div>
      </div>`;
    });
    html += '</div>';
    // Pagination
    html += renderPagination();
    el.innerHTML = html;
  }

  function renderList(el) {
    let html = `<table class="fm-list"><thead><tr>
      <th style="width:24px"><input type="checkbox" onchange="FM.toggleAll(this.checked)"></th>
      <th onclick="FM.setSort('name')">Name</th>
      <th onclick="FM.setSort('size')">Size</th>
      <th onclick="FM.setSort('mtime')">Modified</th>
      <th>Perms</th>
    </tr></thead><tbody>`;
    state.entries.forEach(e => {
      const sel = state.selected.has(e.name);
      const icon = fileIcon(e);
      html += `<tr class="${sel?'selected':''}" data-name="${esc(e.name)}"
        onclick="FM.cardClick(event,'${esc(e.name)}')"
        ondblclick="FM.open('${esc(e.name)}',${e.is_dir})"
        oncontextmenu="FM.showCtx(event,'${esc(e.name)}',${e.is_dir})">
        <td><input type="checkbox" ${sel?'checked':''} onclick="event.stopPropagation();FM.toggleSelect('${esc(e.name)}')"></td>
        <td><div class="fm-name-cell"><i class="ph ${icon}" style="color:${e.is_dir?'#f59e0b':'#94a3b8'}"></i>${esc(e.name)}</div></td>
        <td>${e.is_dir?'—':fmtSize(e.size)}</td>
        <td>${fmtDate(e.mtime)}</td>
        <td style="font-family:monospace;font-size:.78rem">${e.perms||'—'}</td>
      </tr>`;
    });
    html += `</tbody></table>`;
    html += renderPagination();
    el.innerHTML = html;
  }

  function renderPagination() {
    const pages = Math.ceil(state.total / state.perPage);
    if (pages <= 1) return '';
    let html = `<div style="display:flex;gap:.5rem;justify-content:center;margin-top:1rem;flex-wrap:wrap">`;
    for (let i = 1; i <= pages; i++) {
      html += `<button class="fm-btn${i===state.page?' primary':''}" onclick="FM.load(undefined,${i})">${i}</button>`;
    }
    html += '</div>';
    return html;
  }

  function esc(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  }

  // ── Selection ──────────────────────────────────────────────────────────
  function cardClick(e, name) {
    if (e.ctrlKey || e.metaKey) {
      toggleSelect(name);
    } else if (e.shiftKey && state.selected.size > 0) {
      const names = state.entries.map(en => en.name);
      const last = [...state.selected].pop();
      const a = names.indexOf(last), b = names.indexOf(name);
      const [lo, hi] = [Math.min(a,b), Math.max(a,b)];
      names.slice(lo, hi+1).forEach(n => state.selected.add(n));
      updateBulk(); renderContent();
    } else {
      state.selected.clear();
      state.selected.add(name);
      updateBulk(); renderContent();
    }
  }

  function toggleSelect(name) {
    if (state.selected.has(name)) state.selected.delete(name);
    else state.selected.add(name);
    updateBulk(); renderContent();
  }

  function toggleAll(checked) {
    if (checked) state.entries.forEach(e => state.selected.add(e.name));
    else state.selected.clear();
    updateBulk(); renderContent();
  }

  function clearSelection() { state.selected.clear(); updateBulk(); renderContent(); }

  function updateBulk() {
    const n = state.selected.size;
    const bulk = document.getElementById('fm-bulk');
    bulk.classList.toggle('show', n > 0);
    document.getElementById('fm-sel-count').textContent = `${n} selected`;
    updateStatus();
  }

  function updateStatus() {
    document.getElementById('sb-path').textContent = '/' + state.path;
    document.getElementById('sb-count').textContent = `${state.total} items`;
    const n = state.selected.size;
    document.getElementById('sb-sel').textContent = n > 0 ? `${n} selected` : '';
  }

  // ── Open / navigate ────────────────────────────────────────────────────
  function open(name, isDir) {
    if (isDir) {
      load(state.path ? state.path + '/' + name : name);
    } else {
      editFile(name);
    }
  }

  // ── View / sort ────────────────────────────────────────────────────────
  function setView(v) {
    state.view = v;
    document.getElementById('btn-view-grid').classList.toggle('primary', v==='grid');
    document.getElementById('btn-view-list').classList.toggle('primary', v==='list');
    renderContent();
  }

  function setSort(field) {
    if (state.sort === field) state.reverse = !state.reverse;
    else { state.sort = field; state.reverse = false; }
    document.getElementById('sort-dir-icon').className = state.reverse ? 'ph ph-sort-descending' : 'ph ph-sort-ascending';
    load();
  }

  function toggleSortDir() { state.reverse = !state.reverse; document.getElementById('sort-dir-icon').className = state.reverse ? 'ph ph-sort-descending' : 'ph ph-sort-ascending'; load(); }

  let searchTimer;
  function onSearch(v) { clearTimeout(searchTimer); searchTimer = setTimeout(() => { state.search = v; load(state.path, 1); }, 300); }

  // ── Disk usage ─────────────────────────────────────────────────────────
  async function loadDisk() {
    const res = await apiFetch({ action: 'disk_usage' });
    if (!res.status) return;
    const pct = res.total > 0 ? Math.round(res.used / res.total * 100) : 0;
    document.getElementById('fm-disk-fill').style.width = pct + '%';
    document.getElementById('fm-disk-label').textContent = `${fmtSize(res.used)} / ${fmtSize(res.total)}`;
  }

  return {
    load, open, setView, setSort, toggleSortDir, onSearch, cardClick,
    toggleSelect, toggleAll, clearSelection, updateBulk, closeModal, toast,
    esc, fmtSize, fmtDate, fileIcon, isArchive, state,
    // expose internals needed by part 2
    _apiFetch: apiFetch, _confirm: confirm, _openModal: openModal,
    _closeModal: closeModal, _toast: toast, _load: load,
    _renderContent: renderContent, _state: state,
    loadDisk,
  };
})();

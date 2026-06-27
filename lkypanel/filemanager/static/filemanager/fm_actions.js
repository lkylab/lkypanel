// LkyPanel File Manager — Part 2: actions, modals, upload, context menu, keyboard

// ── New File / Folder ──────────────────────────────────────────────────
FM.showNewFile = function() {
  FM._state.newMode = 'file';
  document.getElementById('new-title').textContent = 'New File';
  document.getElementById('new-name').value = '';
  FM._openModal('modal-new');
  setTimeout(() => document.getElementById('new-name').focus(), 100);
};

FM.showNewFolder = function() {
  FM._state.newMode = 'folder';
  document.getElementById('new-title').textContent = 'New Folder';
  document.getElementById('new-name').value = '';
  FM._openModal('modal-new');
  setTimeout(() => document.getElementById('new-name').focus(), 100);
};

FM.confirmNew = async function() {
  const name = document.getElementById('new-name').value.trim();
  if (!name) return;
  const path = FM._state.path ? FM._state.path + '/' + name : name;
  const action = FM._state.newMode === 'file' ? 'create_file' : 'create_folder';
  FM._closeModal('modal-new');
  const res = await FM._apiFetch({ action, path });
  if (res.status) { FM._toast(`Created: ${name}`, 'success'); FM._load(); }
  else FM._toast(res.error, 'error');
};

// ── Rename ─────────────────────────────────────────────────────────────
FM.ctxRename = function() {
  const name = FM._state.ctxEntry?.name || [...FM._state.selected][0];
  if (!name) return;
  document.getElementById('rename-input').value = name;
  FM._openModal('modal-rename');
  setTimeout(() => {
    const inp = document.getElementById('rename-input');
    inp.focus();
    const dot = name.lastIndexOf('.');
    inp.setSelectionRange(0, dot > 0 ? dot : name.length);
  }, 100);
};

FM.confirmRename = async function() {
  const newName = document.getElementById('rename-input').value.trim();
  const oldName = FM._state.ctxEntry?.name || [...FM._state.selected][0];
  if (!newName || !oldName) return;
  FM._closeModal('modal-rename');
  const res = await FM._apiFetch({ action: 'rename', dir: FM._state.path, old_name: oldName, new_name: newName });
  if (res.status) { FM._toast('Renamed', 'success'); FM._load(); }
  else FM._toast(res.error, 'error');
};

// ── Copy / Cut / Paste ─────────────────────────────────────────────────
FM.copySelected = function() {
  const items = [...FM._state.selected];
  if (!items.length && FM._state.ctxEntry) items.push(FM._state.ctxEntry.name);
  if (!items.length) return;
  FM._state.clipboard = { action: 'copy', dir: FM._state.path, items };
  FM._toast(`${items.length} item(s) copied to clipboard`, 'info');
  document.getElementById('fm-ctx').style.display = 'none';
};

FM.cutSelected = function() {
  const items = [...FM._state.selected];
  if (!items.length && FM._state.ctxEntry) items.push(FM._state.ctxEntry.name);
  if (!items.length) return;
  FM._state.clipboard = { action: 'cut', dir: FM._state.path, items };
  FM._toast(`${items.length} item(s) cut`, 'info');
  document.getElementById('fm-ctx').style.display = 'none';
};

FM.pasteHere = async function() {
  const cb = FM._state.clipboard;
  if (!cb) { FM._toast('Clipboard is empty', 'error'); return; }
  document.getElementById('fm-ctx').style.display = 'none';
  const res = await FM._apiFetch({
    action: cb.action === 'copy' ? 'copy' : 'move',
    src_dir: cb.dir, items: cb.items, dst_dir: FM._state.path
  });
  if (res.status) {
    if (cb.action === 'cut') FM._state.clipboard = null;
    FM._toast('Done', 'success'); FM._load();
  } else FM._toast(res.error, 'error');
};

// ── Trash ──────────────────────────────────────────────────────────────
FM.trashSelected = function() {
  const items = [...FM._state.selected];
  if (!items.length && FM._state.ctxEntry) items.push(FM._state.ctxEntry.name);
  if (!items.length) return;
  document.getElementById('fm-ctx').style.display = 'none';
  FM._confirm('Move to Trash', `Move ${items.length} item(s) to trash?`, async () => {
    const res = await FM._apiFetch({ action: 'trash', dir: FM._state.path, items });
    if (res.status) { FM._toast('Moved to trash', 'success'); FM._load(); }
    else FM._toast(res.error, 'error');
  });
};

FM.deleteSelected = function() {
  const items = [...FM._state.selected];
  if (!items.length && FM._state.ctxEntry) items.push(FM._state.ctxEntry.name);
  if (!items.length) return;
  document.getElementById('fm-ctx').style.display = 'none';
  FM._confirm('Permanently Delete', `Delete ${items.length} item(s)? This cannot be undone.`, async () => {
    const res = await FM._apiFetch({ action: 'delete', dir: FM._state.path, items });
    if (res.status) { FM._toast('Deleted', 'success'); FM._load(); }
    else FM._toast(res.error, 'error');
  });
};

FM.showTrash = async function() {
  const res = await FM._apiFetch({ action: 'list_trash' });
  const list = document.getElementById('fm-trash-list');
  if (!res.status || !res.entries.length) {
    list.innerHTML = '<div style="color:var(--text-dim);padding:1rem;text-align:center">Trash is empty</div>';
  } else {
    list.innerHTML = res.entries.map(e => `
      <div style="display:flex;align-items:center;gap:.75rem;padding:.5rem;border-bottom:1px solid var(--border)">
        <i class="ph ${FM.fileIcon(e)}" style="font-size:1.2rem;color:#94a3b8"></i>
        <span style="flex:1;font-size:.83rem">${FM.esc(e.name)}</span>
        <button class="fm-btn" onclick="FM.restoreTrashItem('${FM.esc(e.name)}')"><i class="ph ph-arrow-counter-clockwise"></i>Restore</button>
      </div>`).join('');
  }
  FM._openModal('modal-trash');
};

FM.restoreTrashItem = async function(name) {
  const res = await FM._apiFetch({ action: 'restore_trash', trash_names: [name], original_paths: [name] });
  if (res.status) { FM._toast('Restored', 'success'); FM.showTrash(); FM._load(); }
  else FM._toast(res.error, 'error');
};

FM.emptyTrash = function() {
  FM._confirm('Empty Trash', 'Permanently delete all items in trash?', async () => {
    const res = await FM._apiFetch({ action: 'empty_trash' });
    if (res.status) { FM._toast('Trash emptied', 'success'); FM._closeModal('modal-trash'); }
    else FM._toast(res.error, 'error');
  });
};

// ── Edit file ──────────────────────────────────────────────────────────
FM.editFile = async function(name) {
  const path = FM._state.path ? FM._state.path + '/' + name : name;
  const res = await FM._apiFetch({ action: 'read', path });
  if (!res.status) { FM._toast(res.error, 'error'); return; }
  FM._state.editorPath = path;
  document.getElementById('editor-title').textContent = 'Edit — ' + name;
  document.getElementById('fm-editor-ta').value = res.content;
  FM._openModal('modal-editor');
  setTimeout(() => document.getElementById('fm-editor-ta').focus(), 100);
};

FM.saveFile = async function() {
  const content = document.getElementById('fm-editor-ta').value;
  const res = await FM._apiFetch({ action: 'write', path: FM._state.editorPath, content });
  if (res.status) { FM._toast('Saved', 'success'); FM._closeModal('modal-editor'); }
  else FM._toast(res.error, 'error');
};

// ── Upload ─────────────────────────────────────────────────────────────
FM.showUpload = function() {
  document.getElementById('fm-upload-list').innerHTML = '';
  FM._openModal('modal-upload');
};

FM.handleFileSelect = function(files) {
  [...files].forEach(f => FM.uploadFile(f));
};

FM.uploadFile = function(file) {
  const list = document.getElementById('fm-upload-list');
  const id = 'up-' + Date.now() + Math.random().toString(36).slice(2);
  list.insertAdjacentHTML('beforeend', `
    <div id="${id}" class="fm-upload-item">
      <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${FM.esc(file.name)}</span>
      <div class="fm-upload-bar"><div class="fm-upload-fill" id="${id}-bar" style="width:0%"></div></div>
      <span id="${id}-status" style="min-width:40px;text-align:right;font-size:.75rem">0%</span>
    </div>`);

  const xhr = new XMLHttpRequest();
  const fd = new FormData();
  fd.append('file', file);
  fd.append('path', FM._state.path);
  fd.append('csrfmiddlewaretoken', getCsrf());

  xhr.upload.onprogress = e => {
    if (e.lengthComputable) {
      const pct = Math.round(e.loaded / e.total * 100);
      document.getElementById(id + '-bar').style.width = pct + '%';
      document.getElementById(id + '-status').textContent = pct + '%';
    }
  };
  xhr.onload = () => {
    try {
      const res = JSON.parse(xhr.responseText);
      if (res.status) {
        document.getElementById(id + '-status').textContent = '✓';
        document.getElementById(id + '-bar').style.background = '#22c55e';
        FM._load();
      } else {
        document.getElementById(id + '-status').textContent = '✗';
        document.getElementById(id + '-bar').style.background = '#ef4444';
        FM._toast(res.error, 'error');
      }
    } catch(e) { FM._toast('Upload failed', 'error'); }
  };
  xhr.open('POST', UPLOAD_URL);
  xhr.setRequestHeader('X-CSRFToken', getCsrf());
  xhr.send(fd);
};

// Drag-and-drop on upload zone
document.addEventListener('DOMContentLoaded', () => {
  const zone = document.getElementById('fm-drop-zone');
  if (!zone) return;
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault(); zone.classList.remove('drag-over');
    FM.handleFileSelect(e.dataTransfer.files);
  });
  // Global drag-drop (outside modal)
  document.addEventListener('dragover', e => e.preventDefault());
  document.addEventListener('drop', e => {
    e.preventDefault();
    if (!document.getElementById('modal-upload').classList.contains('show')) {
      FM.showUpload();
    }
    FM.handleFileSelect(e.dataTransfer.files);
  });
});

// ── Download ───────────────────────────────────────────────────────────
FM.ctxDownload = function() {
  const name = FM._state.ctxEntry?.name || [...FM._state.selected][0];
  if (!name) return;
  document.getElementById('fm-ctx').style.display = 'none';
  const path = FM._state.path ? FM._state.path + '/' + name : name;
  window.location.href = DOWNLOAD_URL + '?path=' + encodeURIComponent(path);
};

// ── Extract ────────────────────────────────────────────────────────────
FM.ctxExtract = async function() {
  const name = FM._state.ctxEntry?.name;
  if (!name) return;
  document.getElementById('fm-ctx').style.display = 'none';
  const archive = FM._state.path ? FM._state.path + '/' + name : name;
  const res = await FM._apiFetch({ action: 'extract', archive, dest: FM._state.path });
  if (res.status) { FM._toast('Extracted', 'success'); FM._load(); }
  else FM._toast(res.error, 'error');
};

// ── Compress ───────────────────────────────────────────────────────────
FM.compressSelected = function() {
  const items = [...FM._state.selected];
  if (!items.length && FM._state.ctxEntry) items.push(FM._state.ctxEntry.name);
  if (!items.length) return;
  document.getElementById('fm-ctx').style.display = 'none';
  document.getElementById('compress-name').value = items.length === 1 ? items[0].replace(/\.[^.]+$/, '') : 'archive';
  FM._openModal('modal-compress');
};

FM.confirmCompress = async function() {
  const name = document.getElementById('compress-name').value.trim();
  const fmt = document.getElementById('compress-fmt').value;
  const items = [...FM._state.selected];
  if (!name || !items.length) return;
  FM._closeModal('modal-compress');
  const res = await FM._apiFetch({ action: 'compress', dir: FM._state.path, items, name, format: fmt });
  if (res.status) { FM._toast('Compressed: ' + res.archive, 'success'); FM._load(); }
  else FM._toast(res.error, 'error');
};

// ── Permissions ────────────────────────────────────────────────────────
FM.ctxChmod = function() {
  const name = FM._state.ctxEntry?.name || [...FM._state.selected][0];
  if (!name) return;
  document.getElementById('fm-ctx').style.display = 'none';
  FM._state.chmodPath = FM._state.path ? FM._state.path + '/' + name : name;
  document.getElementById('p-octal').value = '755';
  FM.octalToChecks('755');
  FM._openModal('modal-chmod');
};

FM.octalToChecks = function(val) {
  if (val.length !== 3) return;
  const ids = ['p-or','p-ow','p-ox','p-gr','p-gw','p-gx','p-wr','p-ww','p-wx'];
  const bits = val.split('').flatMap(d => {
    const n = parseInt(d);
    return [!!(n&4), !!(n&2), !!(n&1)];
  });
  ids.forEach((id, i) => { const el = document.getElementById(id); if (el) el.checked = bits[i]; });
};

FM.checksToOctal = function() {
  const ids = [['p-or','p-ow','p-ox'],['p-gr','p-gw','p-gx'],['p-wr','p-ww','p-wx']];
  return ids.map(row => row.reduce((acc, id, i) => acc + (document.getElementById(id)?.checked ? [4,2,1][i] : 0), 0)).join('');
};

FM.confirmChmod = async function() {
  const mode = FM.checksToOctal();
  const recursive = document.getElementById('p-recursive').checked;
  FM._closeModal('modal-chmod');
  const res = await FM._apiFetch({ action: 'chmod', path: FM._state.chmodPath, mode, recursive });
  if (res.status) FM._toast('Permissions updated', 'success');
  else FM._toast(res.error, 'error');
};

// ── Context menu ───────────────────────────────────────────────────────
FM.showCtx = function(e, name, isDir) {
  e.preventDefault();
  e.stopPropagation();
  if (!FM._state.selected.has(name)) {
    FM._state.selected.clear();
    FM._state.selected.add(name);
    FM.updateBulk();
    FM._renderContent();
  }
  const entry = FM._state.entries.find(en => en.name === name);
  FM._state.ctxEntry = entry;
  const ctx = document.getElementById('fm-ctx');
  document.getElementById('ctx-open').style.display = isDir ? '' : 'none';
  document.getElementById('ctx-edit').style.display = isDir ? 'none' : '';
  document.getElementById('ctx-extract').style.display = FM.isArchive(name) ? '' : 'none';
  document.getElementById('ctx-paste').style.display = FM._state.clipboard ? '' : 'none';
  ctx.style.display = 'block';
  const x = Math.min(e.clientX, window.innerWidth - 180);
  const y = Math.min(e.clientY, window.innerHeight - ctx.offsetHeight - 10);
  ctx.style.left = x + 'px';
  ctx.style.top = y + 'px';
};

FM.ctxOpen = function() {
  const e = FM._state.ctxEntry;
  if (e) FM.open(e.name, e.is_dir);
  document.getElementById('fm-ctx').style.display = 'none';
};

FM.ctxEdit = function() {
  const e = FM._state.ctxEntry;
  if (e) FM.editFile(e.name);
  document.getElementById('fm-ctx').style.display = 'none';
};

document.addEventListener('click', () => { document.getElementById('fm-ctx').style.display = 'none'; });
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.getElementById('fm-ctx').style.display = 'none';
    FM._state.selected.clear(); FM.updateBulk(); FM._renderContent();
  }
  if (e.key === 'Delete' && FM._state.selected.size > 0) FM.trashSelected();
  if (e.key === 'F2' && FM._state.selected.size === 1) FM.ctxRename();
  if ((e.ctrlKey || e.metaKey) && e.key === 'a') { e.preventDefault(); FM.toggleAll(true); }
  if ((e.ctrlKey || e.metaKey) && e.key === 'c') FM.copySelected();
  if ((e.ctrlKey || e.metaKey) && e.key === 'x') FM.cutSelected();
  if ((e.ctrlKey || e.metaKey) && e.key === 'v') FM.pasteHere();
});

// ── Perm checkboxes → octal sync ───────────────────────────────────────
['p-or','p-ow','p-ox','p-gr','p-gw','p-gx','p-wr','p-ww','p-wx'].forEach(id => {
  document.addEventListener('change', e => {
    if (e.target.id && e.target.id.startsWith('p-')) {
      document.getElementById('p-octal').value = FM.checksToOctal();
    }
  });
});

// ── Init ───────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  FM.load('');
  FM.loadDisk();
  FM.setView('grid');
});

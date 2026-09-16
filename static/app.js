/* 纯文本菜谱管理系统 —— 前端逻辑（原生 JS + fetch） */

const API = '/api';
const JSON_HEADERS = { 'Content-Type': 'application/json' };
const CATEGORY_LABELS = { cuisine: '菜系', tools: '厨具', color: '颜色' };

let ALL_TAGS = {};
let TAG_CATEGORIES = [];

function el(id) {
  return document.getElementById(id);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

function cssAttr(value) {
  return window.CSS && CSS.escape ? CSS.escape(value) : String(value).replace(/"/g, '\\"');
}

function categoryLabel(category) {
  return CATEGORY_LABELS[category] || category;
}

async function api(path, options = {}) {
  const res = await fetch(path, options);
  const raw = await res.text();
  let data = null;
  if (raw) {
    try { data = JSON.parse(raw); } catch (_) { data = raw; }
  }
  if (!res.ok) {
    let message = `请求失败（${res.status}）`;
    if (data && data.detail) {
      message = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
    }
    const err = new Error(message);
    err.status = res.status;
    throw err;
  }
  return data;
}

function showMessage(id, text, kind = 'error') {
  const box = el(id);
  if (!box) { if (text) alert(text); return; }
  if (!text) { box.classList.add('hidden'); box.textContent = ''; return; }
  const palette = kind === 'success'
    ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
    : 'border-rose-200 bg-rose-50 text-rose-700';
  box.className = `mb-4 rounded-lg border px-4 py-3 text-sm ${palette}`;
  box.textContent = text;
}

/** 详情页没有拉取 /api/tags，直接从菜谱对象里的数组字段推断标签类别 */
function recipeCategories(recipe) {
  if (TAG_CATEGORIES.length) return TAG_CATEGORIES;
  return Object.keys(recipe).filter((key) => Array.isArray(recipe[key]));
}

function chipsFor(recipe) {
  const values = [];
  recipeCategories(recipe).forEach((category) => {
    (recipe[category] || []).forEach((value) => values.push(value));
  });
  if (!values.length) return '<span class="text-xs text-slate-400">未打标签</span>';
  return values.map((v) => `<span class="chip">${escapeHtml(v)}</span>`).join('');
}

/** 渲染 Markdown：marked 输出后做一次轻量清洗，移除脚本类节点与事件属性 */
function renderMarkdown(markdown) {
  const html = window.marked
    ? window.marked.parse(markdown || '', { gfm: true, breaks: false })
    : `<pre>${escapeHtml(markdown || '')}</pre>`;
  const tpl = document.createElement('template');
  tpl.innerHTML = html;
  tpl.content.querySelectorAll('script,style,iframe,object,embed,form,input,link,meta').forEach((n) => n.remove());
  tpl.content.querySelectorAll('*').forEach((node) => {
    [...node.attributes].forEach((attr) => {
      const name = attr.name.toLowerCase();
      const riskyUrl = (name === 'href' || name === 'src' || name === 'xlink:href')
        && /^\s*(javascript|data|vbscript):/i.test(attr.value);
      if (name.startsWith('on') || riskyUrl) node.removeAttribute(attr.name);
    });
  });
  return tpl.innerHTML;
}

async function deleteRecipe(title, handlers = {}) {
  if (!window.confirm(`确定要删除《${title}》吗？此操作不可恢复。`)) return;
  try {
    await api(`${API}/recipes/${encodeURIComponent(title)}`, { method: 'DELETE' });
    if (handlers.onDone) handlers.onDone();
  } catch (err) {
    if (handlers.onError) handlers.onError(err); else alert(err.message);
  }
}

/* ------------------------------------------------------------------ 列表页 */
async function initListPage() {
  try {
    ALL_TAGS = await api(`${API}/tags`);
    TAG_CATEGORIES = Object.keys(ALL_TAGS);
    renderFilters();
    el('apply-filters').addEventListener('click', loadList);
    el('clear-filters').addEventListener('click', () => {
      document.querySelectorAll('.filter-checkbox').forEach((cb) => { cb.checked = false; });
      loadList();
    });
    await loadList();
  } catch (err) {
    showMessage('message', err.message);
  }
}

function renderFilters() {
  el('filters').innerHTML = TAG_CATEGORIES.map((category) => `
    <div>
      <div class="mb-1 text-sm font-medium text-slate-600">${escapeHtml(categoryLabel(category))}</div>
      <div class="flex flex-wrap gap-2">
        ${(ALL_TAGS[category] || []).map((value) => `
          <label class="inline-flex cursor-pointer items-center gap-1 rounded-full border border-slate-300 px-3 py-1 text-sm hover:bg-slate-50">
            <input type="checkbox" class="filter-checkbox" data-category="${escapeHtml(category)}" value="${escapeHtml(value)}">
            <span>${escapeHtml(value)}</span>
          </label>`).join('')}
      </div>
    </div>`).join('');
}

async function loadList() {
  const params = new URLSearchParams();
  document.querySelectorAll('.filter-checkbox:checked').forEach((cb) => {
    params.append(cb.dataset.category, cb.value);
  });
  const query = params.toString();
  try {
    const recipes = await api(`${API}/recipes${query ? `?${query}` : ''}`);
    renderList(recipes);
    showMessage('message', '');
  } catch (err) {
    showMessage('message', err.message);
  }
}

function renderList(recipes) {
  el('count').textContent = `共 ${recipes.length} 道菜谱`;
  const list = el('list');
  if (!recipes.length) {
    list.innerHTML = '<p class="text-sm text-slate-500">没有符合筛选条件的菜谱。</p>';
    return;
  }
  list.innerHTML = recipes.map((r) => {
    const href = `/detail.html?title=${encodeURIComponent(r.title)}`;
    return `
      <div class="rounded-xl border border-amber-200 bg-white p-4 shadow-sm">
        <h3 class="mb-2 text-lg font-semibold"><a href="${href}" class="hover:text-amber-700">${escapeHtml(r.title)}</a></h3>
        <div class="mb-3">${chipsFor(r)}</div>
        <div class="flex gap-2 text-sm">
          <a href="${href}" class="rounded-lg border border-slate-300 px-3 py-1 hover:bg-slate-50">查看</a>
          <a href="/form.html?title=${encodeURIComponent(r.title)}" class="rounded-lg border border-slate-300 px-3 py-1 hover:bg-slate-50">编辑</a>
          <button type="button" data-title="${escapeHtml(r.title)}" class="delete-btn rounded-lg border border-rose-300 px-3 py-1 text-rose-600 hover:bg-rose-50">删除</button>
        </div>
      </div>`;
  }).join('');
  list.querySelectorAll('.delete-btn').forEach((btn) => {
    btn.addEventListener('click', () => deleteRecipe(btn.dataset.title, { onDone: loadList }));
  });
}

/* ------------------------------------------------------------------ 详情页 */
async function initDetailPage() {
  const title = new URLSearchParams(location.search).get('title');
  if (!title) { showMessage('message', '缺少 title 参数'); return; }
  try {
    const recipe = await api(`${API}/recipes/${encodeURIComponent(title)}`);
    document.title = `${recipe.title} · 我的菜谱`;
    el('title').textContent = recipe.title;
    el('tags').innerHTML = chipsFor(recipe);
    el('content').innerHTML = renderMarkdown(recipe.content);
    el('edit-link').href = `/form.html?title=${encodeURIComponent(recipe.title)}`;
    el('delete-btn').addEventListener('click', () => deleteRecipe(recipe.title, {
      onDone: () => { location.href = '/'; },
      onError: (err) => showMessage('message', err.message),
    }));
  } catch (err) {
    showMessage('message', err.message);
  }
}

/* ------------------------------------------------------------- 新增/编辑页 */
async function initFormPage() {
  const original = new URLSearchParams(location.search).get('title');
  try {
    ALL_TAGS = await api(`${API}/tags`);
    TAG_CATEGORIES = Object.keys(ALL_TAGS);
    renderTagPickers();
    if (original) {
      el('page-title').textContent = '编辑菜谱';
      el('breadcrumb').textContent = `正在编辑：${original}`;
      const recipe = await api(`${API}/recipes/${encodeURIComponent(original)}`);
      el('title-input').value = recipe.title;
      el('content-input').value = recipe.content || '';
      TAG_CATEGORIES.forEach((category) => {
        (recipe[category] || []).forEach((value) => {
          const box = document.querySelector(
            `.tag-checkbox[data-category="${cssAttr(category)}"][value="${cssAttr(value)}"]`
          );
          if (box) box.checked = true;
        });
      });
    }
    el('recipe-form').addEventListener('submit', (event) => {
      event.preventDefault();
      submitForm(original);
    });
  } catch (err) {
    showMessage('message', err.message);
  }
}

function renderTagPickers() {
  el('tag-pickers').innerHTML = TAG_CATEGORIES.map((category) => `
    <div>
      <div class="mb-1 text-sm font-medium text-slate-600">
        ${escapeHtml(categoryLabel(category))}
        <span class="font-normal text-slate-400">（可不选）</span>
      </div>
      <div class="flex flex-wrap gap-2">
        ${(ALL_TAGS[category] || []).map((value) => `
          <label class="inline-flex cursor-pointer items-center gap-1 rounded-full border border-slate-300 px-3 py-1 text-sm hover:bg-slate-50">
            <input type="checkbox" class="tag-checkbox" data-category="${escapeHtml(category)}" value="${escapeHtml(value)}">
            <span>${escapeHtml(value)}</span>
          </label>`).join('')}
      </div>
    </div>`).join('');
}

function collectTags() {
  const picked = {};
  TAG_CATEGORIES.forEach((category) => { picked[category] = []; });
  document.querySelectorAll('.tag-checkbox:checked').forEach((cb) => {
    picked[cb.dataset.category].push(cb.value);
  });
  return picked;
}

async function submitForm(original) {
  const payload = {
    title: el('title-input').value.trim(),
    content: el('content-input').value,
    ...collectTags(),
  };
  if (!payload.title) { showMessage('message', '请先填写标题'); return; }
  el('submit-btn').disabled = true;
  try {
    const saved = original
      ? await api(`${API}/recipes/${encodeURIComponent(original)}`, {
          method: 'PUT', headers: JSON_HEADERS, body: JSON.stringify(payload),
        })
      : await api(`${API}/recipes`, {
          method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(payload),
        });
    location.href = `/detail.html?title=${encodeURIComponent(saved.title)}`;
  } catch (err) {
    showMessage('message', err.message);
    el('submit-btn').disabled = false;
  }
}

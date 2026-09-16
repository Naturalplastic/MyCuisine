/* 前端端到端测试：用 jsdom 真实执行 static/ 下的页面逻辑，打真实后端。
 *
 * 前置：
 *   npm i jsdom                       # 任意目录，用 NODE_PATH 或就近安装
 *   curl -o marked.min.js https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js
 *   <先启动后端> python app.py
 * 运行：
 *   BASE=http://127.0.0.1:8000 node tests/e2e_frontend.mjs
 */
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const HERE = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { JSDOM, VirtualConsole } = require('jsdom');

const BASE = process.env.BASE || 'http://127.0.0.1:8000';
const STATIC = process.env.STATIC || resolve(HERE, '../static');
const MARKED = process.env.MARKED || resolve(process.cwd(), 'marked.min.js');
const appJs = readFileSync(`${STATIC}/app.js`, 'utf8');
const markedJs = readFileSync(MARKED, 'utf8');

let failures = 0;
function check(name, cond, extra = '') {
  console.log(`${cond ? '  ✓' : '  ✗'} ${name}${cond ? '' : `  ${extra}`}`);
  if (!cond) failures++;
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function openPage(htmlFile, url) {
  const html = readFileSync(`${STATIC}/${htmlFile}`, 'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '');
  const vc = new VirtualConsole();
  vc.on('jsdomError', (err) => {
    if (!/Not implemented/.test(err.message)) console.log(`  [jsdom] ${err.message}`);
  });
  const dom = new JSDOM(html, { url: `${BASE}${url}`, runScripts: 'dangerously', virtualConsole: vc });
  const { window } = dom;
  // 注入浏览器环境里由 CDN 提供的东西
  window.fetch = (path, options) => fetch(new URL(path, BASE).href, options);
  window.confirm = () => true;
  window.alert = (m) => console.log(`  [alert] ${m}`);
  window.eval(markedJs);
  window.eval(appJs);
  return dom;
}

async function api(path, options) {
  const res = await fetch(`${BASE}${path}`, options);
  const text = await res.text();
  return { status: res.status, body: text ? JSON.parse(text) : null };
}

console.log('=== 页面一：列表 + 筛选');
{
  const dom = await openPage('index.html', '/');
  const w = dom.window;
  await w.eval('initListPage()');
  const $ = (s) => w.document.querySelector(s);
  const $$ = (s) => [...w.document.querySelectorAll(s)];

  check('列表渲染出 2 张卡片', $$('#list > div').length === 2, `实际 ${$$('#list > div').length}`);
  check('卡片标题正确', $$('#list h3').map((n) => n.textContent.trim()).join(',') === '冰糖糖浆,麻婆豆腐', $$('#list h3').map((n) => n.textContent.trim()).join(','));
  check('计数文案正确', $('#count').textContent === '共 2 道菜谱', $('#count').textContent);
  check('筛选控件 18 个复选框', $$('.filter-checkbox').length === 18, `实际 ${$$('.filter-checkbox').length}`);
  check('每张卡片有 查看/编辑/删除', $$('#list > div').every((c) => ['查看','编辑','删除'].every((t) => [...c.querySelectorAll('a,button')].some((n) => n.textContent.trim() === t))));

  // 单选一个没有菜谱的标签：西式
  const western = $$('.filter-checkbox').find((cb) => cb.value === '西式');
  western.checked = true;
  $('#apply-filters').dispatchEvent(new w.Event('click'));
  await sleep(300);
  check('筛选「西式」结果为空', $('#count').textContent === '共 0 道菜谱', $('#count').textContent);

  // 同类别多选（或）：中式 + 西式 → 2 条；再叠加 color=红 → 1 条（跨类别为且）
  western.checked = false;
  const chinese = $$('.filter-checkbox').find((cb) => cb.value === '中式');
  chinese.checked = true;
  $('#apply-filters').dispatchEvent(new w.Event('click'));
  await sleep(300);
  check('筛选「中式」得到 2 条', $('#count').textContent === '共 2 道菜谱', $('#count').textContent);
  $$('.filter-checkbox').find((cb) => cb.value === '红').checked = true;
  $('#apply-filters').dispatchEvent(new w.Event('click'));
  await sleep(300);
  check('叠加「红」后只剩 1 条（跨类别 AND）', $('#count').textContent === '共 1 道菜谱', $('#count').textContent);

  $('#clear-filters').dispatchEvent(new w.Event('click'));
  await sleep(300);
  check('清除筛选后恢复 2 条', $('#count').textContent === '共 2 道菜谱', $('#count').textContent);
  dom.window.close();
}

console.log('=== 页面二：详情 + Markdown 渲染');
{
  const xssTitle = '测试XSS脚本';
  await api('/api/recipes', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title: xssTitle, cuisine: ['中式'], tools: [], color: [],
      content: '## 原材料\n\n- 蛋 2 个\n\n<script>window.__pwned = 1;</script>\n\n<img src=x onerror="window.__pwned2=1">\n\n[坏链接](javascript:window.__pwned3=1)',
    }),
  });

  const dom = await openPage('detail.html', `/detail.html?title=${encodeURIComponent('冰糖糖浆')}`);
  const w = dom.window;
  await w.eval('initDetailPage()');
  await sleep(300);
  const $ = (s) => w.document.querySelector(s);
  check('详情标题正确', $('#title').textContent === '冰糖糖浆', $('#title').textContent);
  check('详情渲染出标签', $('#tags').textContent.includes('琥珀色'));
  check('Markdown 渲染成 HTML 列表', $('#content').innerHTML.includes('<li>冰糖 100g</li>'), $('#content').innerHTML.slice(0, 120));
  check('Markdown 渲染出二级标题', $('#content').querySelectorAll('h2').length === 3, `${$('#content').querySelectorAll('h2').length}`);
  check('编辑按钮指向表单页', $('#edit-link').getAttribute('href').startsWith('/form.html?title='));
  dom.window.close();

  const dom2 = await openPage('detail.html', `/detail.html?title=${encodeURIComponent(xssTitle)}`);
  const w2 = dom2.window;
  await w2.eval('initDetailPage()');
  await sleep(300);
  const c = w2.document.querySelector('#content');
  check('XSS：script 节点被移除', c.querySelectorAll('script').length === 0);
  check('XSS：on* 事件属性被移除', !/onerror/i.test(c.innerHTML), c.innerHTML);
  check('XSS：javascript: 链接被移除', !/javascript:/i.test(c.innerHTML), c.innerHTML);
  check('XSS：页面全局未被污染', w2.__pwned === undefined && w2.__pwned2 === undefined && w2.__pwned3 === undefined);
  check('正常内容仍被渲染', c.innerHTML.includes('蛋 2 个'), c.innerHTML);
  dom2.window.close();

  await api(`/api/recipes/${encodeURIComponent(xssTitle)}`, { method: 'DELETE' });
}

console.log('=== 页面三：新增 / 编辑表单');
{
  const dom = await openPage('form.html', '/form.html');
  const w = dom.window;
  await w.eval('initFormPage()');
  const $ = (s) => w.document.querySelector(s);
  const $$ = (s) => [...w.document.querySelectorAll(s)];
  check('新增模式标题正确', $('#page-title').textContent === '新增菜谱', $('#page-title').textContent);
  check('标签选择器 18 个选项', $$('.tag-checkbox').length === 18, `${$$('.tag-checkbox').length}`);

  $('#title-input').value = '测试表单新增';
  $('#content-input').value = '## 步骤\n1. 一\n2. 二';
  $$('.tag-checkbox').find((cb) => cb.value === '日式').checked = true;
  $$('.tag-checkbox').find((cb) => cb.value === '蒸锅').checked = true;
  $('#recipe-form').dispatchEvent(new w.Event('submit', { cancelable: true, bubbles: true }));
  await sleep(500);
  const created = await api(`/api/recipes/${encodeURIComponent('测试表单新增')}`);
  check('表单提交创建成功', created.status === 200, JSON.stringify(created.body));
  check('标签写入正确', created.body && JSON.stringify([created.body.cuisine, created.body.tools, created.body.color]) === '[["日式"],["蒸锅"],[]]', JSON.stringify(created.body));
  check('正文写入正确', created.body && created.body.content.includes('1. 一'), JSON.stringify(created.body && created.body.content));
  dom.window.close();

  // 编辑模式：预填 + 重命名冲突提示
  const dom2 = await openPage('form.html', `/form.html?title=${encodeURIComponent('麻婆豆腐')}`);
  const w2 = dom2.window;
  await w2.eval('initFormPage()');
  await sleep(300);
  const $2 = (s) => w2.document.querySelector(s);
  const $$2 = (s) => [...w2.document.querySelectorAll(s)];
  check('编辑模式标题正确', $2('#page-title').textContent === '编辑菜谱', $2('#page-title').textContent);
  check('标题已预填', $2('#title-input').value === '麻婆豆腐', $2('#title-input').value);
  check('正文已预填', $2('#content-input').value.includes('嫩豆腐 400g'));
  const checked = $$2('.tag-checkbox:checked').map((cb) => cb.value).sort().join(',');
  check('标签已勾选', checked === ['中式','红','白','锅','灶'].sort().join(','), checked);

  $2('#title-input').value = '冰糖糖浆'; // 与已有菜谱冲突
  $2('#recipe-form').dispatchEvent(new w2.Event('submit', { cancelable: true, bubbles: true }));
  await sleep(500);
  check('重命名冲突时页面提示错误', $2('#message').textContent.includes('新标题已存在'), $2('#message').textContent);
  const still = await api(`/api/recipes/${encodeURIComponent('麻婆豆腐')}`);
  check('冲突时原菜谱未被破坏', still.status === 200 && still.body.content.includes('嫩豆腐 400g'));

  // 正常改名
  $2('#title-input').value = '麻婆豆腐（家常版）';
  $2('#recipe-form').dispatchEvent(new w2.Event('submit', { cancelable: true, bubbles: true }));
  await sleep(500);
  const renamed = await api(`/api/recipes/${encodeURIComponent('麻婆豆腐（家常版）')}`);
  check('重命名成功', renamed.status === 200, `${renamed.status}`);
  const old = await api(`/api/recipes/${encodeURIComponent('麻婆豆腐')}`);
  check('旧标题已不存在', old.status === 404, `${old.status}`);
  dom2.window.close();

  // 含特殊字符的标题：表单创建后详情页必须能打开
  const dom3 = await openPage('form.html', '/form.html');
  const w3 = dom3.window;
  await w3.eval('initFormPage()');
  w3.document.querySelector('#title-input').value = '测试/斜杠:标题';
  w3.document.querySelector('#content-input').value = '## 步骤\n1. 测试';
  w3.document.querySelector('#recipe-form').dispatchEvent(new w3.Event('submit', { cancelable: true, bubbles: true }));
  await sleep(500);
  const slash = await api('/api/recipes');
  const slashTitle = (slash.body.find((r) => r.title.startsWith('测试／斜杠')) || {}).title;
  check('特殊字符标题被规范化', slashTitle === '测试／斜杠：标题', String(slashTitle));
  const dom4 = await openPage('detail.html', `/detail.html?title=${encodeURIComponent(slashTitle)}`);
  await dom4.window.eval('initDetailPage()');
  await sleep(400);
  check('规范化标题的详情页能打开', dom4.window.document.querySelector('#title').textContent === slashTitle, dom4.window.document.querySelector('#title').textContent);
  check('详情页正文渲染成功', dom4.window.document.querySelector('#content').innerHTML.includes('测试'));
  dom4.window.close();
  const del = await api(`/api/recipes/${encodeURIComponent(slashTitle)}`, { method: 'DELETE' });
  check('特殊字符标题可删除', del.status === 200, `${del.status}`);
  dom3.window.close();

  // 收尾：把 麻婆豆腐（家常版）改回 麻婆豆腐，并删除临时菜谱
  await api(`/api/recipes/${encodeURIComponent('麻婆豆腐（家常版）')}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title: '麻婆豆腐', cuisine: ['中式'], tools: ['锅', '灶'], color: ['红', '白'],
      content: '## 原材料\n- 嫩豆腐 400g\n- 牛肉末 100g\n- 郫县豆瓣酱 1 大勺\n- 花椒粉、蒜末、葱花适量\n\n## 步骤\n1. 豆腐切块，用淡盐水浸泡 5 分钟\n2. 热锅下油，炒香牛肉末至微焦\n3. 加豆瓣酱和蒜末炒出红油\n4. 加半碗水烧开，下豆腐轻轻推匀\n5. 小火煮 3 分钟，水淀粉勾芡两次\n6. 出锅撒花椒粉和葱花',
    }),
  });
  await api(`/api/recipes/${encodeURIComponent('测试表单新增')}`, { method: 'DELETE' });
  await api('/api/reload', { method: 'POST' });
  const restored = await api('/api/recipes');
  check('收尾：数据恢复为原始 2 道菜谱', JSON.stringify(restored.body.map((r) => r.title)) === '["冰糖糖浆","麻婆豆腐"]', JSON.stringify(restored.body.map((r) => r.title)));
}

console.log(failures === 0 ? '\n全部前端用例通过 ✅' : `\n失败用例：${failures} ❌`);
process.exit(failures === 0 ? 0 : 1);

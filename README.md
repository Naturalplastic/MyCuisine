# MyCuisine · 纯文本菜谱管理系统

菜谱以 **Markdown + YAML Front Matter** 的纯文本 `.md` 文件保存，网页端负责查看、筛选、新增、编辑、删除。
数据完全自主可控：任何编辑器、Git、网盘都能直接管理 `recipes/` 目录。

> 想学实现细节（架构、数据层、API 设计、前端渲染、测试与 bug 复盘）？直接跳到文末的 **[附录 A · 实现细节](#附录-a--实现细节给初学软件工程的同学)**。

## 快速开始

```bash
cd /home/wzc/code/MyCuisine
source .venv/bin/activate            # 依赖已装好；重建见下
python app.py                        # 或 uvicorn app:app --reload
```

浏览器打开 <http://localhost:8000> 即可。

依赖（`requirements.txt`）：fastapi、uvicorn[standard]、PyYAML。重建虚拟环境：

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

## 项目结构

```
MyCuisine/
├── recipes/              # 每道菜一个 .md 文件
│   ├── 冰糖糖浆.md
│   └── 麻婆豆腐.md
├── tags.yaml             # 预定义标签字典（改完重启后端生效）
├── app.py                # 后端入口（FastAPI，含静态托管）
├── static/
│   ├── index.html        # 列表页 + 标签筛选
│   ├── detail.html       # 详情页（marked.js 渲染 Markdown）
│   ├── form.html         # 新增/编辑表单
│   ├── app.js            # 前端逻辑
│   └── style.css         # 补充样式（Markdown 排版等）
├── requirements.txt
├── requirements-dev.txt  # 跑测试所需的额外依赖
├── tests/
│   ├── test_api.py       # 后端 API 测试（unittest + TestClient）
│   └── e2e_frontend.mjs  # 前端端到端测试（jsdom，可选）
└── README.md
```

## 数据格式

```markdown
---
title: 冰糖糖浆
cuisine: [中式]
tools: [锅, 灶]
color: [透明, 琥珀色]
---

## 原材料
- 冰糖 100g
- 水 200g

## 步骤
1. 锅中加入冰糖和水
2. 中小火加热，不要搅拌
```

- **文件名 = 标题**：标题里的 `/ \ : * ? " < > |` 会被替换为全角字符（如 `/` → `／`），
  所以任何标题都能通过 `/api/recipes/{title}` 直接访问，不会出现「建得出来、点不进去」的菜谱。
- 标签类别与可选值集中维护在 `tags.yaml`；类别可自由增删，改完重启后端生效。
- 每类标签都允许不选（写入空数组 `[]`）。
- Front Matter 中非标签字段（如 `author:`）会被保留，编辑或重命名时不会丢失。
- 手写的 `.md` 若标题里带 `/` 等字符也能被读到，接口会按规范化后的标题再匹配一次。

## API

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | `/api/recipes` | 所有菜谱元数据，支持按标签筛选 |
| GET | `/api/recipes/{title}` | 单篇菜谱完整内容（元数据 + Markdown 正文） |
| POST | `/api/recipes` | 新增菜谱，标题重复返回 `409` |
| PUT | `/api/recipes/{title}` | 编辑菜谱，可改标题（重命名） |
| DELETE | `/api/recipes/{title}` | 删除菜谱 |
| GET | `/api/tags` | 预定义标签字典 |
| POST | `/api/reload` | 重新读取 `tags.yaml` 并重建索引（扩展） |

筛选参数用类别名（单复数均可）：`GET /api/recipes?cuisine=中式&tools=锅,灶`。

## 边界与约束处理

| 事项 | 处理方式 |
| --- | --- |
| 标签预定义 | `tags.yaml` 集中维护，重启后端生效（或调用 `/api/reload`） |
| 标签可不选 | 提交空数组 `[]` 或省略该字段，照常写入 |
| 标签值非法 | `422`，提示哪个类别出现了未定义的值 |
| 新增重名 | `409 标题已存在：xxx`，不覆盖 |
| 编辑改标题 | 视为重命名：新标题冲突则 `409` 并保留原文件 |
| 标题特殊字符 | 标题即文件名：替换为全角字符（`/` → `／`），并校验路径不越界 |
| 写文件 | 先写 `*.tmp` 再原子替换，避免半截文件 |
| Markdown 渲染 | 前端 marked.js，渲染后移除脚本节点、`on*` 事件属性与 `javascript:` 链接 |
| 删除确认 | 前端 `confirm` 二次确认 |
| 并发写入 | 不考虑（个人使用） |

## 测试

```bash
.venv/bin/pip install -r requirements-dev.txt      # 需要 httpx
.venv/bin/python -m unittest discover -s tests -v  # 24 个后端 API 用例，跑在临时目录

# 可选：前端端到端（jsdom 真实执行页面 JS，需要后端已在运行）
npm i jsdom                                        # 或全局安装后用 NODE_PATH 指定
curl -o marked.min.js https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js
BASE=http://127.0.0.1:8000 node tests/e2e_frontend.mjs
```

后端用例覆盖：标签字典、AND/OR 筛选、单复数参数、详情正文、新增/重名 409、
非法标签 422、重命名与重命名冲突、删除 404、文件名安全与路径越界、自定义字段保留、`/api/reload`。

## 说明

- 筛选语义：**不同类别之间为「且」**（与文档一致）；**同一类别内多选为「或」**，否则「中式 + 西式」将永远没有结果。
  若需严格的全局 AND，把 `app.py` 里的 `WITHIN_CATEGORY_OR` 改为 `False` 即可。
- 索引在启动时扫描 `recipes/` 建立；直接用编辑器改文件后，重启后端或 `POST /api/reload` 刷新。
- 前端通过 CDN 加载 Tailwind CSS 与 marked.js，需要联网；离线时页面仍可用（回退样式 + 纯文本正文）。

## 后续可扩展方向

标签统计、全文搜索、导出/导入菜谱包、移动端适配优化。

---

# 附录 A · 实现细节（给初学软件工程的同学）

这一节把整套系统拆开讲：数据怎么存、后端每个函数为什么这么写、前端怎么把数据变成页面、
测试怎么保证不写坏、以及**三个真实踩过的坑**（这一节教学价值最高）。

阅读前提：知道 HTTP 请求/响应、Python 基础语法、HTML/JS 基础即可。
代码片段都来自本仓库，函数名是稳定的锚点，行号会随改动漂移。

目录：

- [A.1 鸟瞰：一个进程，两类流量](#a1-鸟瞰一个进程两类流量)
- [A.2 数据层](#a2-数据层)
- [A.3 内存索引](#a3-内存索引)
- [A.4 后端 API 逐条讲解](#a4-后端-api-逐条讲解)
- [A.5 筛选算法](#a5-筛选算法)
- [A.6 静态托管：前后端怎么接上](#a6-静态托管前后端怎么接上)
- [A.7 前端](#a7-前端)
- [A.8 一条完整链路：点「删除」之后发生了什么](#a8-一条完整链路点删除之后发生了什么)
- [A.9 测试](#a9-测试)
- [A.10 三个真实 bug 的复盘](#a10-三个真实-bug-的复盘)
- [A.11 排查手册](#a11-排查手册)
- [A.12 动手练习](#a12-动手练习)
- [A.13 术语小抄](#a13-术语小抄)

## A.1 鸟瞰：一个进程，两类流量

很多人以为"前端 + 后端"就是两个服务。这个项目刻意不是：

```
                    ┌─────────────────────────────────────────┐
   浏览器            │  一个 Python 进程（uvicorn + FastAPI）    │        文件系统
┌──────────┐        │                                         │      ┌──────────────┐
│ 列表页    │──GET /api/recipes──────────────►│ 路由函数          │      │ recipes/     │
│ 详情页    │──GET /api/recipes/{title}──────►│ ↓                │──读──►│  *.md        │
│ 表单页    │──POST/PUT/DELETE /api/recipes──►│ 内存索引 RECIPES  │◄─写──│ tags.yaml    │
│          │◄───── JSON ────────────────────│ ↑                │      └──────────────┘
│          │──GET /、/app.js、/style.css────►│ StaticFiles      │──读──► static/*.html/js/css
└──────────┘        └─────────────────────────────────────────┘
```

三个设计决定，撑起了整个项目：

1. **静态托管和后端在同一个进程、同一个端口**。前端文件由 `StaticFiles` 直接吐给浏览器，
   于是浏览器看到的 API 和页面是**同源**（same-origin）的 —— 不需要 CORS、不需要第二个端口、
   不需要 nginx，`/api/recipes` 这样的相对路径前端可以直接写死。
2. **没有数据库**。数据就是 `recipes/*.md`，进程里额外维护一份"元数据索引"用于筛选。
3. **前端没有构建步骤**。没有 webpack/vite/npm，`static/` 里的文件改完刷新浏览器就生效 ——
   对初学者来说，少一层抽象就少一整类问题。

启动方式（`app.py` 末尾）：

```python
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

`uvicorn` 是 ASGI 服务器（负责网络、HTTP 解析、并发调度），`FastAPI` 是应用框架（负责路由、参数解析、序列化）。
`app` 这个变量就是它们的接口：uvicorn 拿到 `app`，把每个 HTTP 请求交给它处理，再用返回的对象拼出响应。

## A.2 数据层

### A.2.1 为什么不用数据库

| 维度 | SQLite / Postgres | 纯文本 `.md`（本项目） |
| --- | --- | --- |
| 查询、事务、并发 | 强 | 几乎没有 |
| Git diff、手工编辑、跨工具迁移 | 麻烦（二进制或 SQL dump） | 天然可读、可 diff、可 merge |
| 数据可读性 | 需要工具 | `cat` 就能看 |
| 备份 | 需导出 | 复制目录即备份 |

本项目的数据规模是"个人几十到几百道菜"，**并发与事务完全不是瓶颈，可读性和可迁移性才是**。
所以选择纯文本：这份数据的"寿命"应该比这个程序长 —— 哪天不用这个网页了，`recipes/` 里的文件在任何编辑器里都还能读。

代价也要说清楚：**文件系统就是数据库，于是"文件名是否合法""写入是否原子""索引是否过期"这些数据库本来帮你处理的问题，现在都得自己写**。A.2.5 ~ A.2.7 就是在还这笔债。

### A.2.2 一篇菜谱文件的解剖

```markdown
---
title: 冰糖糖浆          ← YAML Front Matter：结构化元数据
cuisine: [中式]
tools: [锅, 灶]
color: [透明, 琥珀色]
---

## 原材料                ← 正文：Markdown，随便写
- 冰糖 100g
```

Front Matter 是 Jekyll/Hugo 这类静态站点工具发明的约定：文件开头用 `---` 包一段 YAML。
好处是**一个文件同时承载"结构化字段"和"自由文本"**，前者给程序筛选用，后者给人看。

### A.2.3 用正则切出 Front Matter

```python
FRONT_MATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)

def read_recipe_file(path: Path) -> Tuple[Dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    match = FRONT_MATTER.match(text)
    if not match:
        return {}, text.lstrip("\n")
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=500, detail=f"{path.name} 的 YAML 解析失败：{exc}")
    if not isinstance(meta, dict):
        meta = {}
    return meta, text[match.end():].lstrip("\n")
```

逐段读这个正则：

| 片段 | 含义 |
| --- | --- |
| `\A` | 字符串**开头**（不是任意行开头），保证 `---` 必须在文件第一行 |
| `---[ \t]*\r?\n` | 第一行分隔符；允许行尾有空格；`\r?\n` 同时兼容 Windows 的 CRLF |
| `(.*?)` | 非贪婪捕获元数据块。配合 `re.DOTALL`，`.` 才能匹配换行 |
| `\r?\n---[ \t]*` | 结束分隔符必须**独占一行** |
| `(?:\r?\n\|\Z)` | 后面是换行或直接文件结束（文件只写 Front Matter 也要能解析） |

两个容易踩的点：

- **非贪婪 + `DOTALL`** 是最小惊讶的组合：贪婪会把正文里所有的 `---` 都吞进来。
- **解析失败不要抛 500 崩掉整个功能**：这里选择"这篇文件坏了 → 抛 HTTPException"，
  上层 `scan_recipes()` 会捕获并跳过它，只打一行 warning，**其余菜谱照常可用**。
  这就是"局部失败不要升级成全局失败"（fault isolation）。

顺带一个宽容策略：**没有 Front Matter 也能读**（`return {}, text`），标题退化成文件名。
手写一个只有正文的 `.md` 丢进 `recipes/`，系统不会报错。

### A.2.4 写回 YAML：为什么要自定义 `_FlowList` 和 `_Dumper`

PyYAML 默认把列表输出成"块状"：

```yaml
cuisine:
- 中式
- 西式
```

但我们的数据格式想写成 `cuisine: [中式, 西式]`（更紧凑，人也更好读）。做法是给序列类型注册一个"表示器"：

```python
class _FlowList(list):
    """让标签列表以 [中式, 锅] 的行内格式写入 YAML。"""

class _Dumper(yaml.SafeDumper):
    pass

def _represent_flow_list(dumper, data):
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=True)

_Dumper.add_representer(_FlowList, _represent_flow_list)
```

三个细节值得学：

- `_FlowList` 继承 `list`，所以**它就是一个列表**，`in`、`len()`、序列化全都照常工作，只是多了个类型身份供 YAML 识别。
- 一定要**继承出自己的 `_Dumper`** 再注册。直接改全局的 `yaml.SafeDumper` 会污染整个进程里所有 YAML 输出（Python 里"改全局注册表"是经典事故源）。
- `_Dumper` 继承 `SafeDumper` 而不是 `Dumper`：`SafeDumper` 不会把任意 Python 对象序列化成 `!!python/object`，读外部文件时更安全。

序列化函数：

```python
def serialize_recipe(meta, content) -> str:
    data = {"title": meta["title"]}
    for category in CATEGORIES:                     # ① 固定顺序写所有标签类别
        data[category] = _FlowList(meta.get(category, []))
    for key, value in (meta.get("extra") or {}).items():   # ② 保留用户自定义字段
        data.setdefault(key, value)
    front = yaml.dump(data, Dumper=_Dumper, allow_unicode=True,
                      sort_keys=False, default_flow_style=False, width=1000)
    body = (content or "").strip("\n")
    return f"---\n{front}---\n\n{body}\n" if body else f"---\n{front}---\n"
```

`allow_unicode=True` 保证「中式」原样写出而不是 `\u4e2d\u5f0f`（不然文件就没法读了，违背项目初衷）；
`sort_keys=False` 保持我们插入的顺序（Python 3.7+ 的 `dict` 是有序的）。

### A.2.5 标题规范化：维护「文件名 = 标题」这个不变量

这是全项目最重要的一个**不变量（invariant）**：

> 对任何通过校验的标题 `t`，都有 `path_for(t).name == t + ".md"`。

```python
UNSAFE_CHARS = {"/": "／", "\\": "＼", ":": "：", "*": "＊", "?": "？",
                '"': "＂", "<": "＜", ">": "＞", "|": "｜"}
CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

def sanitize_title(title: str) -> str:
    name = CONTROL_CHARS.sub("", str(title)).strip()
    for bad, good in UNSAFE_CHARS.items():
        name = name.replace(bad, good)
    name = name.strip().strip(".").strip()      # 去掉首尾空白和点：防止 "." ".." "xxx."
    if not name:
        raise HTTPException(status_code=422, detail="标题不能为空或只包含不可用字符")
    if len(name) > MAX_TITLE_LEN:
        raise HTTPException(status_code=422, detail=f"标题过长（最多 {MAX_TITLE_LEN} 个字符）")
    return name
```

为什么替换成**全角**而不是删掉或换成下划线？因为全角字符"看起来还是那个字符"：
`测试 A/B` 变成 `测试 A／B.md`，人一眼能认出原来的标题；而 `测试 A_B.md` 会让人以为标题里本来就有下划线。
**给人类看的数据，转换要尽量保真。**

为什么连 `:`、`*` 这些在 Linux 上合法的字符也要换？因为这份数据可能会被同步到 Windows/macOS
（那里 `:`、`*`、`?` 都是非法文件名字符）、也可能被塞进 URL。**在数据边界上做最保守的假设**，
比"在我这台机器上能跑"更靠谱。

### A.2.6 路径安全：`path_for` 与越界检查

```python
def path_for(title: str) -> Path:
    path = (RECIPES_DIR / safe_filename(title)).resolve()
    if path.parent != RECIPES_DIR.resolve():
        raise HTTPException(status_code=422, detail="标题不合法")
    return path
```

这类代码在安全教材里叫**路径穿越（path traversal）**防护：如果标题是 `../../etc/passwd`，
拼接后就会跑到 `recipes/` 外面去。这里有两道防线：

1. `sanitize_title` 把 `/` 换成 `／`，标题里根本不再有路径分隔符；
2. `path_for` 再用 `.resolve()`（会展开 `..` 和符号链接）**确认父目录就是 `recipes/`**，否则拒绝。

第二道看起来多余，但它是**纵深防御**：哪天有人改了 `sanitize_title` 的逻辑（比如允许 `/` 了），
这一行仍然会拦住越界写入。**安全相关的检查故意写两遍，不叫重复，叫冗余。**

对应测试（`tests/test_api.py`）：

```python
def test_title_cannot_escape_recipes_directory(self):
    res = self.client.post("/api/recipes", json={"title": "../../etc/passwd", "content": "x"})
    self.assertEqual(res.status_code, 201)
    for path in self.tmp.glob("*.md"):
        self.assertEqual(path.resolve().parent, self.tmp.resolve())
```

### A.2.7 原子写入：临时文件 + `replace`

```python
def write_recipe(path: Path, meta: Dict[str, Any], content: str) -> None:
    RECIPES_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(serialize_recipe(meta, content), encoding="utf-8")
    tmp.replace(path)
```

`Path.replace()` 底层是 `os.replace()`，在同一个文件系统内是**原子操作**（要么全换成新内容，要么还是旧内容，不存在中间态）。
如果不这么做，"写到一半进程被杀 / 磁盘满"就会留下半个文件 —— 下次启动扫描时会 YAML 解析失败。

注意目录里的 `*.tmp` 已经写进 `.gitignore`，即使有残留也不会被提交。

**同一个坑的另一个版本**在 PUT 重命名时（A.4.6）：那里靠的是"操作顺序"，而不是原子性。

## A.3 内存索引

### A.3.1 数据结构

```python
RECIPES: Dict[str, Dict[str, Any]] = scan_recipes()
# {
#   "冰糖糖浆": {
#       "path": PosixPath("/.../recipes/冰糖糖浆.md"),
#       "meta": {"title": ..., "cuisine": [...], "tools": [...], "color": [...], "extra": {...}},
#       "content": "## 原材料\n- 冰糖 100g\n...",
#   },
# }
```

三个设计点：

- **用标题做字典的 key**：因为标题是这套系统里用户唯一能识别的标识（也是文件名），
  这样"按标题查一篇"是 O(1)，新增时的"标题是否重复"也是 O(1)。
- **`meta` 和 `content` 分开存**：列表接口只返回 `meta`（几十字节），详情接口才带 `content`。
  这是一个"按需传输"的雏形 —— 服务端少解析、网络少传数据。
- **`path` 也存起来**：编辑/删除时直接用，不必再拼一次路径（也避免两次拼接结果不一致）。

### A.3.2 启动扫描：三条容错规则

```python
def scan_recipes() -> Dict[str, Dict[str, Any]]:
    RECIPES_DIR.mkdir(parents=True, exist_ok=True)
    index = {}
    for path in sorted(RECIPES_DIR.glob("*.md")):
        try:
            entry = build_entry(path)
        except (HTTPException, UnicodeDecodeError) as exc:
            print(f"[warn] 跳过无法解析的文件 {path.name}: {exc}")
            continue
        title = entry["meta"]["title"]
        if title in index:
            print(f"[warn] 标题重复，后者覆盖：{title}（{path.name}）")
        index[title] = entry
    return index
```

1. `sorted(...)`：让扫描顺序稳定，重复标题时"谁覆盖谁"是可预测的（否则取决于文件系统返回顺序）。
2. **单个文件坏掉不影响整体**：捕获异常、打 warning、继续。
3. **重复标题不明不白地覆盖很危险**，所以至少打一行日志。生产系统这里应该报错或隔离，个人工具里"能跑起来"优先。

`mkdir(exist_ok=True)` 让"目录不存在"也能启动（首次克隆仓库时 `recipes/` 可能是空的）。

### A.3.3 `normalize_meta`：读取宽容

```python
def normalize_meta(raw, fallback_title):
    title = str(raw.get("title") or fallback_title).strip() or fallback_title   # ①
    meta = {"title": title}
    for category in CATEGORIES:
        values = raw.get(category) or []
        if isinstance(values, str):        # ② 宽容：`cuisine: 中式`（不是列表）也接受
            values = [values]
        if not isinstance(values, list):
            values = []
        meta[category] = [str(v).strip() for v in values if str(v).strip()]
    # ③ 保留 tags.yaml 之外的字段，避免编辑时丢数据
    meta["extra"] = {k: v for k, v in raw.items() if k != "title" and k not in CATEGORIES}
    return meta
```

① 标题缺失就退化成文件名 —— 让"手写的、不规范的"文件也能被读到。
② 单值写法和列表写法都接受，避免用户手写 YAML 时被卡住。
③ 这一行是 bug #1 的修复（见 A.10），也是**向前兼容**的准备：以后加了新字段，老文件不会因此读不出来。

注意这里有意的**不对称**：

| 阶段 | 策略 | 原因 |
| --- | --- | --- |
| 读文件（`normalize_meta`） | 宽容：能读就读，尽量不报错 | 文件是人手写的，格式一定会有出入 |
| 写接口（`validate_payload`） | 严格：标签值必须在 `tags.yaml` 里，否则 422 | 写进来的脏数据将来一定要有人擦 |

这就是 Postel 定律（"发送时严格，接收时宽容"）在数据层的应用。
它也有代价 —— 宽容读进来的旧值，可能在保存时被拒或（通过表单）被静默丢弃，这正是"改标签值"时要小心的地方。

### A.3.4 索引何时会"过期"

索引是启动时建的一份**内存快照**。所以：

| 操作 | 索引是否自动同步 |
| --- | --- |
| 通过网页/API 增删改 | ✅ 每个接口都会同步更新 `RECIPES` |
| 用编辑器直接改 `recipes/*.md` | ❌ 索引不知道，必须 `POST /api/reload` 或重启 |
| 改 `tags.yaml` | ❌ 同理 |

这是"用内存缓存换性能"的必然结果。**每个缓存都要能回答"它什么时候会错"**，
否则就会出现"我明明改了文件，网页还是旧的"这类灵异现象。`/api/reload` 就是给这个缓存做的显式失效入口。

## A.4 后端 API 逐条讲解

### A.4.1 路由表与函数对照

| 方法 + 路径 | 函数 | 关键辅助函数 |
| --- | --- | --- |
| `GET /api/tags` | `api_tags` | `load_tags`（启动时） |
| `GET /api/recipes` | `api_list_recipes` | `filter_recipes` → `match_tags` |
| `GET /api/recipes/{title}` | `api_get_recipe` | `require` → `public_meta` |
| `POST /api/recipes` | `api_create_recipe` | `validate_payload` → `path_for` → `write_recipe` |
| `PUT /api/recipes/{title}` | `api_update_recipe` | `require` → `validate_payload` → `write_recipe` |
| `DELETE /api/recipes/{title}` | `api_delete_recipe` | `require` |
| `POST /api/reload` | `api_reload` | `load_tags` + `scan_recipes` |

FastAPI 的路由靠**装饰器 + 类型注解**绑定：

```python
@app.get("/api/recipes/{title}")
def api_get_recipe(title: str) -> Dict[str, Any]:
    ...
```

`{title}` 是路径参数，FastAPI 看到函数签名里有同名参数 `title: str`，就自动从 URL 里取值、
做类型转换、并把返回值自动序列化成 JSON（`Dict[str, Any]` 直接变成响应体）。
**"函数签名即接口契约"** 是 FastAPI 的核心思想，也是它比 Flask 少写很多胶水代码的原因。

### A.4.2 状态码是接口契约的一部分

初学者常把所有错误都返回 400 或 200+`{"error": ...}`。这套代码刻意区分：

| 码 | 含义 | 本项目出现的场景 | 前端如何反应 |
| --- | --- | --- | --- |
| `200` | 成功 | 查询、更新、删除 | 继续渲染 |
| `201` | **已创建** | `POST /api/recipes` 成功 | 跳到详情页 |
| `404` | 目标不存在 | 标题查不到 / 删不存在的菜谱 | 提示「菜谱不存在」 |
| `409` | **与服务器当前状态冲突** | 新增重名、重命名撞名 | 提示「标题已存在」，让用户改名 |
| `422` | 请求格式/语义不合法 | 标题为空、标签值不在字典里、`content` 不是字符串 | 提示具体字段错在哪 |
| `500` | 服务器内部错误 | 文件里的 YAML 坏了 | 提示解析失败，让人去修文件 |

关键区别在 **409 与 422**：

- `422` 是"你这次请求本身有问题"（**改一下请求就能成功**，比如把标签值换成字典里的）；
- `409` 是"你的请求格式没问题，但**当前数据状态**不允许"（比如你想要的名字已经被占了）。

前端据此可以做不同处理（422 一般直接展示错误；409 可能提示"要不要改名/覆盖"）。
**状态码分得清，前端才能做对；全塞进 200，前端就得到处 if-else 判断业务字符串。**

FastAPI 抛错的统一写法：

```python
raise HTTPException(status_code=409, detail=f"标题已存在：{title}")
```

它会被框架转成 `{"detail": "标题已存在：xxx"}` 加对应状态码。前端 `api()` 里就是读这个 `detail` 字段。

### A.4.3 `validate_payload`：写入口的四层校验

```python
def validate_payload(payload):
    if not isinstance(payload, dict):                       # ① 整体类型
        raise HTTPException(422, "请求体必须是 JSON 对象")
    raw_title = str(payload.get("title") or "").strip()
    if not raw_title:
        raise HTTPException(422, "标题不能为空")
    title = sanitize_title(raw_title)                       # ② 标题合法化 + 长度校验
    content = payload.get("content") or ""
    if not isinstance(content, str):                        # ③ 正文字段类型
        raise HTTPException(422, "content 必须是字符串")
    meta = {"title": title, "extra": {}}
    for category in CATEGORIES:
        values = payload.get(category) or []                # ④ 标签：可省略、可空数组
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list):
            raise HTTPException(422, f"标签 {category} 必须是数组")
        cleaned = []                                        # 去空白、去重
        for value in values:
            value = str(value).strip()
            if value and value not in cleaned:
                cleaned.append(value)
        invalid = [v for v in cleaned if v not in TAGS[category]]   # 白名单校验
        if invalid:
            raise HTTPException(422, f"标签 {category} 含未定义的值：{'、'.join(invalid)}")
        meta[category] = cleaned
    return meta, content
```

值得注意的设计：

- **每次请求都遍历全部类别**（而不是只处理请求里出现的字段）。这样"表单没勾任何标签"会写成 `[]` 而不是"字段缺失"，
  **保证写出的文件结构一致**，读的时候就不用处理两种情况。
- **去重**：用户或脚本可能重复提交 `["锅", "锅"]`，这里顺手清掉，避免文件里出现重复标签。
- **错误信息里带上是哪个类别、哪个值**：`标签 cuisine 含未定义的值：火星菜`。
  报错信息的质量直接决定了排查速度 —— "422 Unprocessable Entity" 是没用的，要让人一眼知道去改哪里。

> 为什么不用 Pydantic 的模型（`class RecipeIn(BaseModel)`）？因为标签类别名来自 `tags.yaml`，
> 是**运行时才知道**的动态字段，用静态模型反而要写一堆 `model_config`/`extra` 的绕路代码。
> 这里用 `Body(...)` 接原始 `dict` 手动校验，可读性更好。**框架的便利要用在合适的地方。**

### A.4.4 `require()`：一次宽容的查找

```python
def require(title: str) -> Dict[str, Any]:
    entry = RECIPES.get(title)
    if entry is None:
        # 兼容手写文件：标题里可能带 / : 等字符，按规范化后的标题再匹配一次
        try:
            target = sanitize_title(title)
        except HTTPException:
            target = None
        if target is not None:
            for key, value in RECIPES.items():
                try:
                    if sanitize_title(key) == target:
                        entry = value
                        break
                except HTTPException:
                    continue
    if entry is None:
        raise HTTPException(404, f"菜谱不存在：{title}")
    return entry
```

正常的"查一篇"是 O(1) 的字典查找；只有查不到时才退化成 O(n) 的模糊匹配。
**把慢路径放在少见的分支里**，是性能优化里最基本也最有效的一招。

这也解释了"什么时候该宽容"：用户从列表点进详情，URL 里的标题是系统自己给的，理论上一定能查到；
但如果那篇菜谱是**别人手写进目录的**（标题里带 `/`），索引里的 key 就是原始标题，
而 URL 里传进来的可能已经被 URL 编码/解码一圈 —— 多一次模糊匹配，就让这类文件也能点得开。

### A.4.5 新增：`POST /api/recipes`

```python
@app.post("/api/recipes", status_code=201)
def api_create_recipe(payload: Any = Body(...)) -> Dict[str, Any]:
    meta, content = validate_payload(payload)
    title = meta["title"]
    if title in RECIPES or path_for(title).exists():        # ① 双保险去重
        raise HTTPException(409, f"标题已存在：{title}")
    path = path_for(title)
    write_recipe(path, meta, content)                       # ② 先落盘
    RECIPES[title] = {"path": path, "meta": meta, "content": content}   # ③ 再更新索引
    return public_meta(meta)
```

① 检查两次是有原因的：`title in RECIPES` 查的是内存索引，`path.exists()` 查的是磁盘。
正常情况下两者一致，但**索引可能过期**（用户手工放了同名文件进去），所以再问一次磁盘。
个人小工具谈不上严谨的并发控制，但这个"双保险"成本极低。

②③ 的顺序是刻意的：**先写文件，成功后再改内存**。如果反过来（先改内存），
一旦写文件抛异常，索引里就会出现一篇"存在但没磁盘文件"的菜谱 —— 越用越乱。

`status_code=201` 写在装饰器里，让"创建成功"和"更新成功"在协议层就能区分。

### A.4.6 编辑：`PUT /api/recipes/{title}` —— 同标题覆盖 vs 改标题重命名

```python
@app.put("/api/recipes/{title}")
def api_update_recipe(title: str, payload: Any = Body(...)) -> Dict[str, Any]:
    entry = require(title)                                  # 原菜谱必须在
    meta, content = validate_payload(payload)
    new_title = meta["title"]
    # 请求体里没带的自定义 Front Matter 字段沿用原文件（bug #1 的修复）
    meta["extra"] = {**entry["meta"].get("extra", {}), **meta.get("extra", {})}

    if new_title == title:                                  # 分支一：标题没变 → 原地覆盖
        write_recipe(entry["path"], meta, content)
        entry["meta"], entry["content"] = meta, content
        return public_meta(meta)

    if new_title in RECIPES:                                # 分支二：改标题 = 重命名
        raise HTTPException(409, f"新标题已存在：{new_title}")
    new_path = path_for(new_title)
    if new_path.exists():
        raise HTTPException(409, f"新标题已存在：{new_title}")
    write_recipe(new_path, meta, content)                   # ① 先写新文件
    entry["path"].unlink(missing_ok=True)                   # ② 再删旧文件
    RECIPES.pop(title, None)
    RECIPES[new_title] = {"path": new_path, "meta": meta, "content": content}
    return public_meta(meta)
```

**① 先写新的，再删旧的** —— 这是全项目第二个重要的顺序性决策（第一个是 `write_recipe` 里的 tmp+replace）。
反问一下：如果先删旧的、写新的，而这中间磁盘满了或者进程被杀，会怎样？
**旧数据没了，新数据也没写成功 —— 数据永久丢失。**

反过来（现在的顺序）最坏情况是：新文件写好了、旧文件没删掉 —— 于是**多了一篇菜谱**。
用户会看到两条相近的记录，手工删一条即可。**能人工收拾的错误，远好于无法恢复的错误。**

这也是为什么"删除"永远应该放在关键步骤的最后一步。这个思路在真实系统里叫 **fail-safe 设计**。

`unlink(missing_ok=True)` 则体现了另一个习惯：**删除操作要幂等**（文件已经不在了也不要抛异常），
不然一个"清理脚本"跑到一半就会因为"文件不存在"而中断。

### A.4.7 删除：`DELETE /api/recipes/{title}`

```python
@app.delete("/api/recipes/{title}")
def api_delete_recipe(title: str) -> Dict[str, Any]:
    entry = require(title)              # 不存在 → 404（而不是静默成功）
    entry["path"].unlink(missing_ok=True)
    RECIPES.pop(title, None)
    return {"ok": True, "deleted": title}
```

这里又有一个取舍：**删除不存在的资源，到底该返回 404 还是 200？**

- 主张 404：调用方需要知道"你删的东西本来就不在"（本项目的选择，能帮用户发现拼写错误）。
- 主张 200：删除是幂等的，重复调用结果相同（很多 REST 风格指南推荐这个）。

两种都能自圆其说，关键是**在整个项目里保持一致**，并写进测试（本项目两个删除用例：成功 200、不存在 404）。
初学者写接口最容易犯的错就是"这次抛异常、下次返回 200"，让调用方无从预料。

### A.4.8 `/api/reload`：一个"运维接口"

```python
@app.post("/api/reload")
def api_reload() -> Dict[str, Any]:
    global TAGS, CATEGORIES, RECIPES
    TAGS = load_tags()
    CATEGORIES = list(TAGS)
    RECIPES = scan_recipes()
    return {"ok": True, "count": len(RECIPES), "categories": CATEGORIES}
```

因为它改动的是**模块级全局变量**，所以必须写 `global`。这个接口的存在，是为了让"改标签 / 手工加文件"
不需要重启进程。要注意它带来的两个风险，也正好是"缓存失效"的经典问题：

1. **`CATEGORIES` 变了，老菜谱文件里的字段含义也变了**（比如某类别被删掉后，其字段会变成 `extra` 里的自定义字段）。
2. **`load_tags()` 失败时行为要明确**：`TAGS = load_tags()` 这句抛异常的话，赋值不会发生，
   于是**旧标签继续生效、服务不崩**（`/api/reload` 返回 500，其余接口照常）。
   但**启动时**读坏文件会直接抛 `RuntimeError` 让进程退出 —— 这是有意的：
   "配置坏了就不该假装能跑"。**同一个错误，在不同时机需要不同的处理方式。**

## A.5 筛选算法

### A.5.1 从 URL 到"想要的标签集合"

```python
def api_list_recipes(request: Request):
    return filter_recipes(request.query_params.multi_items())
```

用 `request.query_params.multi_items()` 而不是常见教程里的 `request.query_params.get("cuisine")`：

- `get()` 只会拿到**同名参数的最后一个**，用户在界面上勾了「中式」和「西式」就丢了一个；
- `multi_items()` 返回 `[("cuisine", "中式"), ("cuisine", "西式"), ...]`，**所有出现的键值对都在**。

### A.5.2 把查询参数归并成"类别 → 值列表"

```python
def filter_recipes(query_items):
    wanted: Dict[str, List[str]] = {}
    for key, value in query_items:
        category = resolve_category(key)
        if category is None:            # 不认识的参数直接忽略
            continue
        for item in value.split(","):   # 支持 ?color=红,白 这种写法
            item = item.strip()
            if item and item not in wanted.setdefault(category, []):
                wanted[category].append(item)
    ...
```

两个宽容点：**未知参数忽略**（以后前端多传参数不会 500）、**值支持逗号分隔**（手敲 URL 更方便）。
"忽略未知输入"是接口演进的关键：客户端升级了、服务端还没升级时不会互崩。

### A.5.3 `resolve_category` 的单复数兼容

```python
def resolve_category(key: str) -> Optional[str]:
    key = key.strip()
    if key in TAGS:
        return key
    if key + "s" in TAGS:      # ?tool=锅 与 ?tools=锅 都能用
        return key + "s"
    return None
```

设计文档里出现了 `?cuisine=中式&tool=锅`（单数）和类别名 `tools`（复数）并存的情况。
与其纠结"到底该用哪个"，不如**两个都接受**，并在测试里固定住这个行为：

```python
def test_filter_accepts_singular_key_and_unknown_keys(self):
    self.assertEqual(len(self.client.get("/api/recipes", params={"tool": "灶"}).json()), 2)
    self.assertEqual(len(self.client.get("/api/recipes", params={"nope": "x"}).json()), 2)
```

**接口的"模糊地带"必须用测试固定下来**，否则半年后没人记得它到底支持什么。

### A.5.4 AND 与 OR：一次有意的语义取舍

```python
def match_tags(meta, wanted) -> bool:
    for category, values in wanted.items():
        owned = set(meta.get(category, []))
        if WITHIN_CATEGORY_OR:
            if not owned.intersection(values):     # 同类别：任一命中即可（或）
                return False
        elif not set(values).issubset(owned):      # 同类别：必须全部命中（且）
            return False
    return True
```

- **不同类别之间一定是「且」**：选了「中式 + 锅」，两个条件都要满足 —— 符合直觉，也符合设计文档。
- **同一类别内默认是「或」**：勾了「中式」和「西式」，应该看到两种菜系。
  如果按"且"，结果永远是空集，**多选控件就变成了一个必然让人困惑的陷阱**。
- 但文档原文写的是"同时满足所有已传标签（AND）"，所以这里留了 `WITHIN_CATEGORY_OR` 开关，
  把取舍**写成一个显式的常量**，而不是藏在逻辑里让后人猜。

```python
# 同一类别内多选时：True = 或（选「中式」或「西式」），False = 严格全局 AND
# 不同类别之间永远是「且」。
WITHIN_CATEGORY_OR = True
```

**当实现与文档不一致时，别偷偷改，要留痕。** 用常量 + 注释把决策暴露出来，是成本最低的做法。

顺带一个算法细节：用 `set` 做交集而不是嵌套循环，把"每篇菜谱 × 每个筛选值"的乘法复杂度降成哈希查找。
数据量小时无所谓，但这个"把集合运算交给集合类型"的习惯值得从第一天就养成。

### A.5.5 复杂度与数据量级

```
筛选一次 = O(菜谱数 × 类别数)    # 类别数通常 3~5，可视为常数
按标题查 = O(1)                 # 字典
扫描目录 = O(文件数)，只在启动和 reload 时发生
```

几百篇菜谱下这些都是微秒级。**先量级、后优化**：如果哪天菜谱上万篇、或者要支持全文搜索，
再换成 SQLite FTS 或倒排索引 —— 那时候接口层（`filter_recipes`）不用动，只换实现即可。
这就是把逻辑收在一个函数里的好处。

## A.6 静态托管：前后端怎么接上

```python
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
```

三个知识点：

1. **`html=True`**：访问 `/` 时自动返回 `index.html`，访问 `/detail.html` 返回同名文件 ——
   这就是为什么浏览器里能直接开 `http://localhost:8000/detail.html?title=...`，不需要写额外的路由。
2. **`mount("/")` 的位置必须放在所有 `@app.get(...)` 之后**。Starlette 按**注册顺序**匹配路由：
   API 路由先注册就优先命中，剩下的才落到静态文件这一层。如果把这个 `mount` 写在文件开头，
   `/api/recipes` 就会被静态文件处理器当成"找不到的文件"。
   **框架里"顺序敏感"的地方不多，但每一个都要记住。**
3. **同源（same-origin）带来的三个好处**：
   - 不需要 CORS（跨域资源共享）配置和浏览器的预检请求（preflight）；
   - 前端可以直接写相对路径 `/api/recipes`，不用配"后端地址"这个环境变量；
   - 天然没有"Cookie 跨站"这类问题（虽然本项目没有登录态）。

如果哪天要把前端部署到别处（比如 GitHub Pages），就必须加 CORS 中间件，
并且前端所有 `/api/...` 都要改成绝对地址 —— **这就是"同源部署"省下来的那笔成本**。

## A.7 前端

### A.7.1 三个页面 + 一个脚本：靠"入口函数"区分页面

```
static/index.html   →  <script>initListPage();</script>
static/detail.html  →  <script>initDetailPage();</script>
static/form.html    →  <script>initFormPage();</script>
static/app.js       →  三个入口函数 + 公共工具，被三个页面共同引入
```

没有路由框架、没有模块打包，靠的是"页面各自的 HTML 里调用自己的入口函数"。
每个入口函数负责：**拉数据 → 渲染 → 绑定事件**，这也是最朴素、最容易理解的页面初始化模式：

```js
async function initListPage() {
  try {
    ALL_TAGS = await api(`${API}/tags`);
    TAG_CATEGORIES = Object.keys(ALL_TAGS);
    renderFilters();
    el('apply-filters').addEventListener('click', loadList);
    el('clear-filters').addEventListener('click', () => { ...; loadList(); });
    await loadList();
  } catch (err) {
    showMessage('message', err.message);     // 初始化失败也要让用户看见
  }
}
```

注意整个初始化包在 `try/catch` 里：**如果后端没起来，用户应该看到一句人话错误，而不是一个永远转圈的白页。**
（顺便说：这也是排查"页面空白"时第一个要看的地方。）

### A.7.2 `api()`：一个薄封装的 fetch

```js
async function api(path, options = {}) {
  const res = await fetch(path, options);
  const raw = await res.text();                        // ① 先拿文本
  let data = null;
  if (raw) {
    try { data = JSON.parse(raw); } catch (_) { data = raw; }   // ② 解析失败就留原文
  }
  if (!res.ok) {                                       // ③ 非 2xx 一律抛错
    let message = `请求失败（${res.status}）`;
    if (data && data.detail) {                         // ④ 优先用后端的 detail
      message = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
    }
    const err = new Error(message);
    err.status = res.status;                           // ⑤ 把状态码带出去
    throw err;
  }
  return data;
}
```

每一处的理由：

- ① 不用 `res.json()`：后端在 500 时可能返回 HTML 错误页，直接 `json()` 会抛出一个和业务无关的解析错误，把真正的原因盖掉。
- ② 容错解析，保证 `raw` 为空（204）也不炸。
- ③ **让错误走 `throw` 而不是返回值**：调用方就能统一用 `try/catch`，不必每次判断 `if (res.ok)`。
- ④ 后端的 `{"detail": "标题已存在：xxx"}` 直接拿来当提示语 —— **错误文案只写一遍**，前后端不会各说一套。
- ⑤ `err.status` 让上层还能区分 404/409/422（比如将来想做"409 时提示是否改名"）。

**所有网络请求都走这一个函数**，是前端项目里最值得坚持的纪律之一：超时、重试、鉴权头、
统一的加载提示，将来都只用改一个地方。

### A.7.3 `escapeHtml`：为什么每个插值都要转义

```js
function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}
```

用模板字符串拼 HTML 时，任何**来自数据**的内容都必须转义：

```js
`<h3>${escapeHtml(r.title)}</h3>`                                  // ✅
`<h3>${r.title}</h3>`                                             // ❌ 标题里写 <img onerror=...> 就中招
```

- 用**一次正则替换**而不是"先替换 & 再替换 <"的多次 `replace`：后者会因为二次转义把 `&lt;` 变成 `&amp;lt;`。
- `<`、`>` 防标签注入，`"`、`'` 防"属性逃逸"（比如标题写 `x" onmouseover="alert(1)` 就能跳出 `value="..."`）。
- 这套字符集（`& < > " '`）和 OWASP 推荐的最小转义集一致。**记住它，比记住"要转义"更实用。**

注意：`data-title="${escapeHtml(r.title)}"` 这类属性也要转义（列表页删除按钮就是这么做的），
读取时用 `btn.dataset.title` 拿到的是**已解码**的原值 —— 这个来回不会互相破坏。

### A.7.4 列表渲染：`innerHTML` 的取舍

```js
list.innerHTML = recipes.map((r) => `...${escapeHtml(r.title)}...`).join('');
list.querySelectorAll('.delete-btn').forEach((btn) => {
  btn.addEventListener('click', () => deleteRecipe(btn.dataset.title, { onDone: loadList }));
});
```

用"模板字符串 + `innerHTML`"的**好处**：所见即所得、零依赖、没有编译期魔法，初学者能完全看懂。
**代价**有三条，都得知道：

1. **必须手动转义**（上一节），框架（React/Vue）是自动做的；
2. **每次整体重绘会丢掉已绑定的 DOM 与事件**，所以要在渲染后重新绑定 —— 上面第二段就是干这个；
3. 大列表性能差（这里几十条无所谓）。

第 2 条的另一种写法是**事件委托**：给不变的外层容器绑一次，用 `event.target.closest('.delete-btn')` 判断点了谁。
这样无论列表重绘多少次都不必重新绑定。**留作练习（见 A.12）。**

### A.7.5 筛选控件与查询串

```js
function renderFilters() {
  el('filters').innerHTML = TAG_CATEGORIES.map((category) => `
    <div>
      <div ...>${escapeHtml(categoryLabel(category))}</div>
      <div ...>
        ${(ALL_TAGS[category] || []).map((value) => `
          <label ...>
            <input type="checkbox" class="filter-checkbox"
                   data-category="${escapeHtml(category)}" value="${escapeHtml(value)}">
            <span>${escapeHtml(value)}</span>
          </label>`).join('')}
      </div>
    </div>`).join('');
}
```

控件是**从 `/api/tags` 动态生成**的，所以后端改了 `tags.yaml`，前端一行代码都不用动。
`data-category` 把"这个勾选框属于哪个类别"存在 DOM 上，取值时用 `cb.dataset.category` ——
这就是把数据存进 DOM 的 `data-*` 属性的标准用法。

拼查询串时不用手写 `?cuisine=中式&...`，而是：

```js
const params = new URLSearchParams();
document.querySelectorAll('.filter-checkbox:checked').forEach((cb) => {
  params.append(cb.dataset.category, cb.value);   // 同名键 append 多次 → 后端收到多值
});
const query = params.toString();                  // 自动做 URL 编码
```

`URLSearchParams` 帮你处理了编码（中文、空格、`&` 都不会出问题），
而 `append` 多次产生的 `?color=红&color=白` 正好对应后端 `multi_items()` 的多值读取 —— **前后端在这一处是对齐的**。

### A.7.6 详情页：Markdown 渲染 + 轻量 XSS 清洗

```js
function renderMarkdown(markdown) {
  const html = window.marked
    ? window.marked.parse(markdown || '', { gfm: true, breaks: false })
    : `<pre>${escapeHtml(markdown || '')}</pre>`;          // ① CDN 挂了也别白屏
  const tpl = document.createElement('template');          // ② 用 template 承载，不入文档树
  tpl.innerHTML = html;
  tpl.content.querySelectorAll('script,style,iframe,object,embed,form,input,link,meta')
    .forEach((n) => n.remove());                           // ③ 删掉危险节点
  tpl.content.querySelectorAll('*').forEach((node) => {    // ④ 逐个元素检查属性
    [...node.attributes].forEach((attr) => {
      const name = attr.name.toLowerCase();
      const riskyUrl = (name === 'href' || name === 'src' || name === 'xlink:href')
        && /^\s*(javascript|data|vbscript):/i.test(attr.value);
      if (name.startsWith('on') || riskyUrl) node.removeAttribute(attr.name);
    });
  });
  return tpl.innerHTML;                                    // ⑤ 再交给页面
}
```

这一段的思路值得完整理解，因为它是"**不可信输入怎么进 DOM**"的最小范例：

- ① `marked` 是从 CDN 加载的全局变量，**它可能加载失败**（离线、CDN 被墙）。所以要有降级：
  用 `<pre>` + `escapeHtml` 显示原始文本，功能不残废。
- ② `<template>` 是这里最关键的一招：它的内容属于**惰性文档片段（inert document fragment）**，
  **脚本不会执行、`<img>` 不会真的发请求、`onerror` 不会触发**。
  所以"先塞进 template 再清洗"是安全的；如果直接 `div.innerHTML = html`，那 `<img onerror>` 在赋值的瞬间就已经跑了。
- ③ 白名单式地删掉整类危险节点（`script/style/iframe` 等）。
- ④ 再遍历所有元素，删掉 `on*` 事件属性（`onerror`、`onclick`...）和协议危险的链接（`javascript:`、`data:`）。
- ⑤ 只有清洗完的 HTML 才写进页面。

测试里就把这三种攻击都试了一遍（`tests/e2e_frontend.mjs`）：

```js
content: '<script>window.__pwned = 1;</script>\n\n<img src=x onerror="window.__pwned2=1">\n\n[坏链接](javascript:window.__pwned3=1)'
...
check('XSS：script 节点被移除', c.querySelectorAll('script').length === 0);
check('XSS：页面全局未被污染', w2.__pwned === undefined && ...);
```

> **必须诚实地提醒**：这是"轻量清洗"，不是完整的安全方案。
> 自己写 sanitizer 在真实项目里是**出了名的危险**（总有想不到的绕过姿势，比如 SVG/MathML 里的角括号、
> CSS 注入、`<a href="data:text/html;...">`）。
> 生产环境请用成熟的库（如 DOMPurify）。这里之所以手写，是因为数据来源**只有你自己**、
> 且教学上必须让你看清"用户内容进 DOM"这件事的全过程。

### A.7.7 表单页：新增和编辑共用一个页面

```js
async function initFormPage() {
  const original = new URLSearchParams(location.search).get('title');
  ...
  if (original) {                                  // ① URL 里带 title → 编辑模式
    el('page-title').textContent = '编辑菜谱';
    const recipe = await api(`${API}/recipes/${encodeURIComponent(original)}`);
    el('title-input').value = recipe.title;
    el('content-input').value = recipe.content || '';
    TAG_CATEGORIES.forEach((category) => {          // ② 按已有标签回填勾选框
      (recipe[category] || []).forEach((value) => {
        const box = document.querySelector(
          `.tag-checkbox[data-category="${cssAttr(category)}"][value="${cssAttr(value)}"]`);
        if (box) box.checked = true;
      });
    });
  }
  el('recipe-form').addEventListener('submit', (event) => {
    event.preventDefault();                         // ③ 阻止表单的默认跳转行为
    submitForm(original);
  });
}
```

- ① 用"URL 里有没有 `title` 参数"区分新增/编辑 —— 不需要第二个页面，也不需要全局状态。
- ② 回填时 `if (box)` 很有必要：如果某个标签值**已从 `tags.yaml` 删掉**，
  文件里还留着旧值，但界面上没有对应勾选框。这时不勾选、保存，那个标签就被丢掉了（A.10 的坑之一）。
- ③ `event.preventDefault()` 是必须的：否则浏览器会用原生表单方式提交（整页刷新 + query string），
  我们的 `fetch` 逻辑根本不会执行。

提交时按模式分流，并**用服务端返回的标题**跳转：

```js
const saved = original
  ? await api(`${API}/recipes/${encodeURIComponent(original)}`, { method: 'PUT', ... })
  : await api(`${API}/recipes`, { method: 'POST', ... });
location.href = `/detail.html?title=${encodeURIComponent(saved.title)}`;
```

注意是 `saved.title` 而不是输入框里的值 —— 因为**服务端可能规范化了标题**（`A/B` → `A／B`），
用户输入的值与最终存下来的值可能不同。**以服务端返回的资源标识为准**，这是个通用原则。

### A.7.8 `encodeURIComponent` 必须用

标题里可能有空格、中文、`&`、`#`、`/`，直接拼进 URL 会破坏 URL 结构（`#` 会被当成锚点、`&` 会被当成参数分隔）。

```js
`${API}/recipes/${encodeURIComponent(title)}`      // ✅
`/detail.html?title=${encodeURIComponent(r.title)}` // ✅ 连页面跳转也要编码
```

对照记一下三个常见的坑：

| 场景 | 正确做法 |
| --- | --- |
| 拼 URL 路径或查询参数 | `encodeURIComponent` |
| 拼整个 URL（保留 `:/?#&` 等结构字符） | `encodeURI` |
| 输出到 HTML | `escapeHtml`（A.7.3） |

## A.8 一条完整链路：点「删除」之后发生了什么

从用户点击到文件消失，一共七步。把这条链路走通，前后端就真的连起来理解了。

```
1. 用户点击卡片上的「删除」按钮
   └─ 事件处理器 list.querySelectorAll('.delete-btn') 里绑的闭包被触发
      （标题通过 btn.dataset.title 从 DOM 的 data-title 属性取回）

2. deleteRecipe(title) 弹出确认框
   if (!window.confirm(`确定要删除《${title}》吗？此操作不可恢复。`)) return;
   └─ 防误删。删除是不可逆操作，UI 上必须多一道确认。

3. 发请求
   api(`/api/recipes/${encodeURIComponent(title)}`, { method: 'DELETE' })

4. 浏览器 → uvicorn
   └─ DELETE 到 localhost:8000（与页面同源，无 CORS 预检）
   └─ uvicorn 解析 HTTP → 交给 FastAPI 路由表

5. FastAPI 匹配到 @app.delete("/api/recipes/{title}")
   └─ 路径参数 title 被解码后传入 api_delete_recipe(title)
   └─ require(title) 查内存索引：找不到 → raise HTTPException(404, "菜谱不存在：...")

6. 找到则执行
   entry["path"].unlink(missing_ok=True)   # 磁盘文件删除
   RECIPES.pop(title, None)                # 内存索引同步移除
   return {"ok": True, "deleted": title}   # → 200

7. 前端收到响应
   └─ await 返回，调用 handlers.onDone() → loadList()
   └─ 重新 GET /api/recipes 并整体重绘列表
      （不"手动从 DOM 里删掉那张卡片"——让界面完全由服务端数据推导，避免两边状态不一致）
```

最后一句是本项目的一条重要前端纪律：**界面是服务端数据的函数**。
删完不手工改 DOM，而是重新拉一次列表。多一次请求，换来"界面上显示的东西一定等于服务器上的东西"。
数据量小的时候，这是非常划算的交换；等到性能真的不够了，再引入局部更新（乐观更新）。

## A.9 测试

### A.9.1 后端：测试跑在临时目录里

```python
class RecipeApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = Path(tempfile.mkdtemp(prefix="mycuisine-test-"))
        cls.real_dir = app_module.RECIPES_DIR
        app_module.RECIPES_DIR = cls.tmp            # ① 把全局目录指向临时目录
        cls.client = TestClient(app_module.app)     # ② 不启真实端口

    @classmethod
    def tearDownClass(cls) -> None:
        app_module.RECIPES_DIR = cls.real_dir       # ③ 一定要还原
        app_module.RECIPES = app_module.scan_recipes()
        shutil.rmtree(cls.tmp, ignore_errors=True)
```

三个要点：

- ① **`app.py` 里的 `RECIPES_DIR` 是模块级变量，所有函数运行时才去读它**，所以测试里直接改这个变量就能整体重定向。
  这是 Python 里最常见的一种"依赖注入替代品"：**没有 DI 框架，但把"路径"提取成模块级常量就够了**。
  （反过来也提醒你：如果某个函数内部写死了 `BASE_DIR / "recipes"`，这里就做不到。）
- ② `TestClient` 内部用 `httpx` 直接调用 ASGI 应用，**不起真实端口**：跑得快、不会撞端口、也不会受代理影响。
- ③ `tearDownClass` 必须还原，否则同一个进程里后续代码会继续指向已删除的临时目录 —— 测试之间互相污染是经典事故。

### A.9.2 一个真实的踩坑：`setUp` 里必须重建索引

第一版测试长这样：

```python
def setUp(self):
    for path in self.tmp.glob("*.md"):
        path.unlink()                 # 只删文件
    for recipe in SAMPLE.values():
        self.client.post("/api/recipes", json=recipe)
```

结果**每个用例都失败**，报 `409 标题已存在：冰糖糖浆`。为什么？

因为**磁盘上的文件删了，内存索引 `RECIPES` 还在**（上一轮用例留下的条目）。
`api_create_recipe` 的 `if title in RECIPES` 直接命中，于是拒绝创建。

修法是同时重置两个状态：

```python
def setUp(self) -> None:
    for path in self.tmp.glob("*.md"):
        path.unlink()
    app_module.RECIPES = app_module.scan_recipes()   # ← 关键：索引也要重置
```

**教训：当一个系统同时持有"内存状态"和"持久化状态"时，测试的清理必须覆盖两者。**
这条经验在真实项目里同样适用（缓存、连接池、单例都要小心）—— 而它之所以能被发现，
正是因为有测试：**测试的价值不只是"证明能跑"，更在于"把状态污染立刻暴露出来"。**

### A.9.3 前端端到端：为什么要 stub

`tests/e2e_frontend.mjs` 用 jsdom 把真实的 HTML + 真实的 `app.js` 跑起来，打真实的后端：

```js
async function openPage(htmlFile, url) {
  const html = readFileSync(`${STATIC}/${htmlFile}`, 'utf8')
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '');   // ① 先摘掉页面里的 script
  const dom = new JSDOM(html, { url: `${BASE}${url}`, runScripts: 'dangerously', virtualConsole: vc });
  window.fetch = (path, options) => fetch(new URL(path, BASE).href, options);  // ② jsdom 没有 fetch
  window.confirm = () => true;                                              // ③ jsdom 没实现 confirm
  window.eval(markedJs);                                                    // ④ 注入 marked
  window.eval(appJs);                                                       // ⑤ 再手动执行 app.js
  return dom;
}
```

每一条 stub 都对应 jsdom 与真实浏览器的一个差异：

| 做法 | 原因 |
| --- | --- |
| ① 摘掉 `<script>` 再手动 eval | 否则页面里的 `initXxxPage()` 会在我们准备好 stub 之前就执行 |
| ② 注入 `window.fetch` | jsdom 不实现 fetch；而且要把相对路径拼成 `http://127.0.0.1:8000/...` 才能用 Node 的 fetch |
| ③ 注入 `confirm` | jsdom 未实现，直接调用会抛 "Not implemented" |
| ④ 注入 marked | CDN 脚本加载不了（离线/代理），手动喂一份 |
| ⑤ `window.eval(appJs)` | 让代码在**页面自己的 window 作用域**里执行，而不是 Node 的全局作用域 |

还有一个"必须知道"的行为：jsdom 不实现**页面导航**，所以 `location.href = '/detail.html?...'`
不会真的跳转，而是往 `virtualConsole` 发一个 `jsdomError: Not implemented: navigation`。
测试里直接忽略这类错误，改成"**用 API 断言副作用**"（提交后去 `GET /api/recipes/<新标题>` 看数据对不对）：

```js
vc.on('jsdomError', (err) => {
  if (!/Not implemented/.test(err.message)) console.log(`  [jsdom] ${err.message}`);
});
```

**这就是端到端测试的通用思路：能断言最终状态，就不要断言中间的 UI 动作。**

### A.9.4 两套测试的分工

| | `tests/test_api.py` | `tests/e2e_frontend.mjs` |
| --- | --- | --- |
| 工具 | `unittest` + `fastapi.testclient` | jsdom（Node） |
| 打什么 | 直接调用 ASGI 应用（不起端口） | 真实 HTTP，需要后端在跑 |
| 覆盖 | 数据正确性、状态码、边界、路径安全 | DOM 渲染、筛选交互、表单提交、XSS 清洗 |
| 数量 | 24 个用例 | 35 项断言 |
| 速度 | 0.3 秒 | 几秒 |

**两者的价值不重叠**：前者保证"数据层逻辑对"，后者保证"页面真的能用"。
本项目的三个 bug 里，有两个是端到端测试抓出来的（见 A.10）。

## A.10 三个真实 bug 的复盘

这一节是全篇最值得读的部分 —— 三个 bug 都是**在实现完成、人工点过一遍之后**才被测试抓出来的。

### Bug #1：编辑一次，自定义字段就没了

- **现象**：手写文件里加的 `author: 我自己`，在网页里点一次保存之后消失了。
- **原因**：`PUT` 用**请求体**解析出的 `meta` 覆盖了索引里的 `meta`，而 `validate_payload` 里
  `meta["extra"]` **初始化为空字典** —— 前端不可能提交它不知道的字段，于是 `extra` 被清空。
- **修法**：合并而不是覆盖。

  ```python
  meta["extra"] = {**entry["meta"].get("extra", {}), **meta.get("extra", {})}
  ```

- **教训**：**当"读"和"写"的数据结构不对称（读进来 8 个字段、写出去只有 5 个）时，
  缺失的字段会被"默认值"悄悄抹掉。** 任何"改一部分字段"的接口都要先想清楚：
  没出现在请求里的字段，是"清空"还是"保持不变"？这是 PUT 和 PATCH 语义差别的核心。
- **回归测试**：`test_update_keeps_custom_front_matter_fields`。

### Bug #2：详情页的标签是空的

- **现象**：列表页标签正常，点进详情页标签区是"未打标签"，但数据明明有。
- **原因**：`chipsFor(recipe)` 靠**模块级全局变量** `TAG_CATEGORIES` 遍历标签类别，
  而这个变量只在 `initListPage()` 和 `initFormPage()` 里被赋值；`initDetailPage()` 里没有赋值，
  于是它是 `[]`，循环一次都不执行 —— 每个菜谱都显示"未打标签"。
- **修法**：让函数**不依赖外部状态**，从菜谱对象自身的数组字段推断：

  ```js
  function recipeCategories(recipe) {
    if (TAG_CATEGORIES.length) return TAG_CATEGORIES;
    return Object.keys(recipe).filter((key) => Array.isArray(recipe[key]));
  }
  ```

- **教训**：**全局可变状态是"跨页面/跨模块"最隐蔽的 bug 源。**
  同一份 `app.js` 被三个页面共用，任何一个"看起来老实"的全局变量，
  到了没被初始化的页面上就变成空值。
  两个通用的防御手法：能靠参数传的就别用全局；实在要用，就先问自己"没被初始化时它会是什么，会不会静默走错分支"。
- **为什么人工测试没发现**：因为列表页看起来是对的，而"未打标签"这句文案本身不报错，
  它只是安静地说了假话。**"静默降级"比"直接报错"更难查。**

### Bug #3：标题里带 `/` 的菜谱"建得出来，点不进去"

- **现象**：新建一篇标题为 `测试 A/B` 的菜谱，创建成功、列表里也能看到，
  但点「查看」跳详情页时报 `404 菜谱不存在`。
- **原因**：有两件事各自都对，凑在一起就错了：
  1. 索引的 key 用的是**原始标题**（`测试 A/B`），因为标题来自 Front Matter；
  2. 文件名被**规范化**过（`测试 A／B.md`），而且 URL 路径里的 `/`（包括 `%2F`）
     在路由之前就被解码成路径分隔符，`/api/recipes/测试 A%2FB` 根本匹配不到
     `/api/recipes/{title}` 这个路由 —— 请求在路由层就 404 了。
- **修法**：把"规范化"提前到**标题本身**，让不变量 `文件名 = 标题` 恒成立：

  ```python
  title = sanitize_title(raw_title)     # 在 validate_payload 里就规范化
  ```

  同时 `require()` 里加一层"按规范化标题再匹配一次"的兼容查找，让手工放进目录的老文件也能打开。
- **教训**：**任何"用户输入 → 变成标识符（文件名 / URL / 主键）"的系统，
  必须先定义清楚"标识符的合法字符集"，然后把它作为不变量测下来。**
  一旦这个不变量不成立，就会出现"能创建、能列出、但访问不了"的脏数据 ——
  而且它只在特定输入下才复现（普通标题一切正常）。
- **回归测试**：`test_special_characters_in_title_are_sanitized` 断言了
  "响应里的标题 == 文件名去掉 `.md`" 和 "按规范化标题能查到"。

> 三个 bug 的共同点：**都不是语法错误，都能通过"点一遍"验收。**
> 它们分别是"数据被默认值覆盖""全局状态未初始化""两个都对的假设组合出错误" ——
> 这三类问题构成日常 bug 的大多数。**写测试，本质上就是把这些假设显式写下来。**

## A.11 排查手册

| 症状 | 可能原因 | 怎么办 |
| --- | --- | --- |
| 浏览器打不开 `localhost:8000`，但服务"看起来在跑" | 系统/终端设了 HTTP 代理，`localhost` 也被送进代理 | 浏览器代理例外里加 `localhost`；命令行用 `curl --noproxy '*'` |
| `Address already in use` | 8000 端口被上一次的进程占着 | `pgrep -af "uvicorn app:app"` 找到 PID 后 `kill`，或换 `--port 8001` |
| 页面样式全无、Markdown 变成纯文本块 | Tailwind / marked 的 CDN 断网或加载失败 | 这是**预期的降级行为**；联网后刷新即可 |
| 改了 `recipes/*.md`，网页没变 | 索引是启动时的快照 | `POST /api/reload` 或重启 |
| 改了 `tags.yaml`，筛选区没变 | 同上；且前端要刷新页面才会重新拉 `/api/tags` | reload + 刷新浏览器 |
| `422 标签 xxx 含未定义的值` | 提交的标签值不在 `tags.yaml` 里（常见于改过标签字典后编辑老菜谱） | 改 `tags.yaml` 或改菜谱里的标签 |
| `409 标题已存在` | 新增重名 / 重命名撞名 | 换标题；重命名冲突时旧文件**不会**被动，可以放心 |
| `500 xxx 的 YAML 解析失败` | 手工编辑把 Front Matter 写坏了（缩进、引号、Tab） | 直接打开那个 `.md` 修（错误信息里带文件名）；启动日志里也会 `[warn] 跳过…` |
| 启动就 `RuntimeError: tags.yaml 中类别 xxx 的值必须是列表` | `tags.yaml` 写成了 `cuisine: 中式` 而不是 `cuisine: [中式]` | 修好再启动。**服务运行中调 reload 只会返回 500，不会影响正在跑的服务** |
| 前端报 `Failed to fetch` | 后端没启动 / 端口不对 | 看后端终端有没有 `Uvicorn running on ...` |

还有两个小提示：

- **看后端日志**：所有 `[warn]` 都打在运行 `python app.py` 的那个终端里。页面上的报错往往只有一句人话，
  真正的原因在日志里。
- **看浏览器控制台**（F12）：前端每个 `try/catch` 都会把错误显示成页面上的红条，
  但堆栈只有在 Console 里才看得到。

## A.12 动手练习

按难度排序，都能在这个代码基础上直接做：

1. **改用事件委托**（A.7.4）：给 `#list` 绑一次 click，用 `event.target.closest('.delete-btn')` 取按钮，
   去掉每次渲染后的重新绑定。
2. **加"创建时间"**：写入时在 Front Matter 里加 `created_at`，列表按它倒序。
   考察点：`normalize_meta` / `serialize_recipe`（读宽容、写严格）、老文件的兼容（没有这个字段怎么办）。
3. **加标签统计接口**：`GET /api/stats` 返回每个标签下有多少菜谱。
   考察点：在内存索引上做一次聚合；注意**不要**在循环里反复扫全表。
4. **全文搜索**：`GET /api/recipes?q=关键词`，匹配标题和正文。
   考察点：`filter_recipes` 里加一个维度；正文匹配要不要大小写不敏感？
5. **在网页里维护标签**：`POST /api/tags` 写回 `tags.yaml` 并重建索引。
   考察点：写 YAML 时怎么保持注释？（提示：`yaml.dump` 做不到，要么模板化重写，要么用 `ruamel.yaml`）
6. **给写操作加上"并发保护"**：想象两个人同时编辑同一道菜。
   考察点：乐观锁（请求里带上读到的版本号/修改时间，服务端比对后决定是否拒绝）——
   这是从"个人工具"迈向"多用户系统"的第一课。

## A.13 术语小抄

| 术语 | 一句话解释 | 本项目里的位置 |
| --- | --- | --- |
| ASGI / uvicorn | Python 异步 Web 服务的接口规范 / 实现它的服务器 | `uvicorn.run(app, ...)` |
| 路由（routing） | 把"方法 + 路径"映射到函数 | `@app.get("/api/recipes/{title}")` |
| 路径参数 / 查询参数 | URL 里 `/a/{x}` 的部分 / `?k=v` 的部分 | `title` / `?cuisine=中式` |
| Front Matter | 文件开头 `---` 包起来的元数据块 | `recipes/*.md` |
| 不变量（invariant） | 系统在任何时刻都必须成立的性质 | `文件名 = 标题` |
| 原子写入 | 要么全成功要么全不变，没有中间态 | tmp + `Path.replace()` |
| 幂等（idempotent） | 同一操作执行多次，结果和执行一次相同 | `unlink(missing_ok=True)` |
| 路径穿越 | 用 `../` 逃出预期目录的攻击 | `path_for` 的越界检查 |
| 同源（same-origin） | 协议+主机+端口完全相同 | 页面与 API 同端口，故无 CORS |
| 状态码语义 | 用 4xx/2xx 表达错误类别 | 404 / 409 / 422 |
| 缓存失效 | 内存里的副本与真实数据不一致 | `RECIPES` 与 `/api/reload` |
| XSS | 把用户内容当代码执行 | `escapeHtml` + `renderMarkdown` 清洗 |
| E2E 测试 | 从外部把整个系统跑起来验证 | `tests/e2e_frontend.mjs`（jsdom） |

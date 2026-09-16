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

代码片段取自本仓库，`...` 表示省略的部分。阅读前提：HTTP 请求/响应、Python 基础语法、HTML/JS 基础。

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

三个决定：

1. 静态文件与 API 同进程、同端口，浏览器看到的是同源资源，因此不需要 CORS、不需要第二个端口。
2. 没有数据库，数据是 `recipes/*.md`，进程里另有一份供筛选用的内存索引。
3. 前端没有构建步骤，改 `static/` 下文件刷新浏览器即生效。

```python
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

uvicorn 负责网络与并发，FastAPI 负责路由、参数解析、序列化，`app` 是两者的接口。

## A.2 数据层

### A.2.1 为什么不用数据库

| 维度 | SQLite / Postgres | 纯文本 `.md`（本项目） |
| --- | --- | --- |
| 查询、事务、并发 | 强 | 几乎没有 |
| Git diff、手工编辑、跨工具迁移 | 麻烦（二进制或 SQL dump） | 天然可读、可 diff、可 merge |
| 数据可读性 | 需要工具 | `cat` 就能看 |
| 备份 | 需导出 | 复制目录即备份 |

数据规模是几十到几百道菜，并发和事务不是瓶颈。代价是数据库原本负责的事要自己写：
文件名合法性、写入原子性、索引一致性，对应 A.2.5 ~ A.2.7 和 A.3.4。

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

一个文件同时承载"结构化字段"和"自由文本"：前者给程序筛选，后者给人阅读。

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

| 片段 | 含义 |
| --- | --- |
| `\A` | 字符串开头，保证 `---` 必须在文件第一行 |
| `---[ \t]*\r?\n` | 第一行分隔符，允许行尾空格，兼容 CRLF |
| `(.*?)` | 非贪婪捕获元数据，配合 `re.DOTALL` 让 `.` 匹配换行 |
| `\r?\n---[ \t]*` | 结束分隔符必须独占一行 |
| `(?:\r?\n\|\Z)` | 后面是换行或文件结束（只写 Front Matter 也能解析） |

- 非贪婪是必要的：贪婪会把正文里所有 `---` 都吞进来。
- 单篇解析失败抛 `HTTPException`，`scan_recipes()` 捕获后跳过并打 warning，其余菜谱照常可用。
- 没有 Front Matter 也能读，标题退化成文件名。

### A.2.4 写回 YAML：为什么要自定义 `_FlowList` 和 `_Dumper`

PyYAML 默认把列表写成块状，而本项目要写成 `cuisine: [中式, 西式]`：

```python
class _FlowList(list):        # 就是 list，多一个类型身份供 YAML 识别
    """让标签列表以 [中式, 锅] 的行内格式写入 YAML。"""

class _Dumper(yaml.SafeDumper):      # 继承出自定义 Dumper，不改全局 SafeDumper
    pass

def _represent_flow_list(dumper, data):
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=True)

_Dumper.add_representer(_FlowList, _represent_flow_list)


def serialize_recipe(meta, content) -> str:
    data = {"title": meta["title"]}
    for category in CATEGORIES:                            # 固定顺序写所有标签类别
        data[category] = _FlowList(meta.get(category, []))
    for key, value in (meta.get("extra") or {}).items():    # 保留自定义字段
        data.setdefault(key, value)
    front = yaml.dump(data, Dumper=_Dumper, allow_unicode=True,
                      sort_keys=False, default_flow_style=False, width=1000)
    body = (content or "").strip("\n")
    return f"---\n{front}---\n\n{body}\n" if body else f"---\n{front}---\n"
```

- 继承 `SafeDumper` 而非 `Dumper`：读外部文件时不会反序列化出任意 Python 对象。
- `allow_unicode=True` 让「中式」原样写出而不是 `\u4e2d\u5f0f`；`sort_keys=False` 保持插入顺序。

### A.2.5 标题规范化：维护「文件名 = 标题」这个不变量

对任何通过校验的标题 `t`，都有 `path_for(t).name == t + ".md"`。

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

替换成全角而不是删除或换下划线，是为了让人还能认出原标题：`测试 A/B` → `测试 A／B.md`，
而 `测试 A_B.md` 会让人以为标题里本来就有下划线。连 Linux 上合法的 `:`、`*` 也替换，
是因为这份数据可能同步到 Windows/macOS，也可能进 URL。

### A.2.6 路径安全：`path_for` 与越界检查

```python
def path_for(title: str) -> Path:
    path = (RECIPES_DIR / safe_filename(title)).resolve()
    if path.parent != RECIPES_DIR.resolve():
        raise HTTPException(status_code=422, detail="标题不合法")
    return path
```

标题为 `../../etc/passwd` 时，拼接后会跑到 `recipes/` 之外。两道防线：`sanitize_title` 把 `/` 换掉；
`path_for` 用 `.resolve()` 展开 `..` 与符号链接后，确认父目录就是 `recipes/`。
第二道在 `sanitize_title` 被改动时仍然有效。测试：

```python
res = self.client.post("/api/recipes", json={"title": "../../etc/passwd", "content": "x"})
self.assertEqual(res.status_code, 201)
for path in self.tmp.glob("*.md"):
    self.assertEqual(path.resolve().parent, self.tmp.resolve())   # 没有逃出临时目录
```

### A.2.7 原子写入：临时文件 + `replace`

```python
def write_recipe(path: Path, meta: Dict[str, Any], content: str) -> None:
    RECIPES_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(serialize_recipe(meta, content), encoding="utf-8")
    tmp.replace(path)
```

`Path.replace()` 底层是 `os.replace()`，同一文件系统内是原子的：要么是旧内容，要么是新内容。
直接覆盖写则可能因进程被杀或磁盘满而留下半个文件，下次启动扫描时解析失败。

## A.3 内存索引

### A.3.1 数据结构

```python
RECIPES: Dict[str, Dict[str, Any]] = scan_recipes()
# { "冰糖糖浆": {"path": Path(...), "meta": {...}, "content": "## 原材料\n..."} }
```

- 用标题做 key：标题是用户唯一能识别的标识，也是文件名，因此查询与判重都是 O(1)。
- `meta` 与 `content` 分开：列表接口只返回 `meta`，详情接口才带正文。
- 缓存 `path`：编辑/删除时直接使用，避免重复拼接。

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

`sorted` 让扫描顺序稳定，重复标题时覆盖关系可预测；单个文件坏掉不影响其余菜谱；
重复标题会静默覆盖，所以至少打一行日志。`mkdir(exist_ok=True)` 保证 `recipes/` 为空时也能启动。

### A.3.3 `normalize_meta`：读取宽容

```python
def normalize_meta(raw, fallback_title):
    title = str(raw.get("title") or fallback_title).strip() or fallback_title   # 缺失则用文件名
    meta = {"title": title}
    for category in CATEGORIES:
        values = raw.get(category) or []
        if isinstance(values, str):        # `cuisine: 中式` 这种写法也接受
            values = [values]
        if not isinstance(values, list):
            values = []
        meta[category] = [str(v).strip() for v in values if str(v).strip()]
    # 保留 tags.yaml 之外的字段，避免编辑时丢数据
    meta["extra"] = {k: v for k, v in raw.items() if k != "title" and k not in CATEGORIES}
    return meta
```

读写策略有意不对称：

| 阶段 | 策略 | 原因 |
| --- | --- | --- |
| 读文件 `normalize_meta` | 宽容，尽量不报错 | 文件是人手写的，格式会有出入 |
| 写接口 `validate_payload` | 严格，标签值必须在 `tags.yaml` 里 | 写进去的脏数据迟早要有人清理 |

代价是：宽容读进来的旧值，在保存时可能被拒（422）或被表单静默丢弃。这是改标签字典时要小心的地方。

### A.3.4 索引何时会过期

| 操作 | 索引是否同步 |
| --- | --- |
| 通过网页/API 增删改 | 每个接口都会更新 `RECIPES` |
| 用编辑器直接改 `recipes/*.md` | 不同步，需 `POST /api/reload` 或重启 |
| 改 `tags.yaml` | 不同步，同上 |

`/api/reload` 就是这个缓存的失效入口。

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

```python
@app.get("/api/recipes/{title}")
def api_get_recipe(title: str) -> Dict[str, Any]:
    ...
```

`{title}` 是路径参数。FastAPI 发现函数签名里有同名参数，就自动从 URL 取值、做类型转换，
返回值自动序列化成 JSON。

### A.4.2 状态码是接口契约的一部分

| 码 | 含义 | 本项目的场景 | 前端反应 |
| --- | --- | --- | --- |
| `200` | 成功 | 查询、更新、删除 | 继续渲染 |
| `201` | 已创建 | `POST /api/recipes` 成功 | 跳到详情页 |
| `404` | 目标不存在 | 标题查不到、删不存在的菜谱 | 提示「菜谱不存在」 |
| `409` | 与当前状态冲突 | 新增重名、重命名撞名 | 提示改名 |
| `422` | 请求语义不合法 | 标题为空、标签值不在字典里 | 提示具体字段 |
| `500` | 服务器内部错误 | 文件里的 YAML 坏了 | 提示解析失败 |

409 与 422 的区别：422 是请求本身有问题，改请求就能成功；409 是请求没问题但当前数据状态不允许。

```python
raise HTTPException(status_code=409, detail=f"标题已存在：{title}")
```

它会被转成 `{"detail": "标题已存在：xxx"}` 加对应状态码，前端的 `api()` 就是读这个 `detail`。

### A.4.3 `validate_payload`：写入口的校验

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
    for category in CATEGORIES:                             # ④ 标签：可省略、可空数组
        values = payload.get(category) or []
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list):
            raise HTTPException(422, f"标签 {category} 必须是数组")
        cleaned = []                                        # 去空白、去重
        for value in values:
            value = str(value).strip()
            if value and value not in cleaned:
                cleaned.append(value)
        invalid = [v for v in cleaned if v not in TAGS[category]]
        if invalid:
            raise HTTPException(422, f"标签 {category} 含未定义的值：{'、'.join(invalid)}")
        meta[category] = cleaned
    return meta, content
```

每次都遍历全部类别（不是只处理请求里出现的字段），这样"没勾任何标签"会写成 `[]`，
文件结构始终一致，读的时候不用处理"字段缺失"。

不用 Pydantic 模型的原因：标签类别名来自 `tags.yaml`，是运行时才知道的动态字段，
静态模型要写一堆 `extra` 绕路代码；这里用 `Body(...)` 接原始 `dict` 手动校验更直白。

### A.4.4 `require()`：查找与兼容

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
                if sanitize_title(key) == target:   # 简化写法，真实代码里对每次比较都做了异常保护
                    entry = value
                    break
    if entry is None:
        raise HTTPException(404, f"菜谱不存在：{title}")
    return entry
```

正常查找是 O(1)，只有查不到时才退化成 O(n) 模糊匹配。模糊匹配的用途：别人手写进目录的文件
标题里带 `/`，索引 key 是原始标题，而 URL 传进来的可能已被编码/解码一圈。

### A.4.5 新增：`POST /api/recipes`

```python
@app.post("/api/recipes", status_code=201)
def api_create_recipe(payload: Any = Body(...)) -> Dict[str, Any]:
    meta, content = validate_payload(payload)
    title = meta["title"]
    if title in RECIPES or path_for(title).exists():        # 索引与磁盘各查一次
        raise HTTPException(409, f"标题已存在：{title}")
    path = path_for(title)
    write_recipe(path, meta, content)                       # 先落盘
    RECIPES[title] = {"path": path, "meta": meta, "content": content}   # 再更新索引
    return public_meta(meta)
```

判重查两次：`title in RECIPES` 查内存索引，`path.exists()` 查磁盘（索引可能过期，比如有人手工放了同名文件）。
先写文件再改内存：反过来一旦写文件失败，索引里就会出现"存在但没有磁盘文件"的菜谱。

### A.4.6 编辑：`PUT /api/recipes/{title}` —— 覆盖与重命名

```python
@app.put("/api/recipes/{title}")
def api_update_recipe(title: str, payload: Any = Body(...)) -> Dict[str, Any]:
    entry = require(title)
    meta, content = validate_payload(payload)
    new_title = meta["title"]
    # 请求体里没带的自定义 Front Matter 字段沿用原文件
    meta["extra"] = {**entry["meta"].get("extra", {}), **meta.get("extra", {})}

    if new_title == title:                                  # 标题没变：原地覆盖
        write_recipe(entry["path"], meta, content)
        entry["meta"], entry["content"] = meta, content
        return public_meta(meta)

    if new_title in RECIPES or path_for(new_title).exists():  # 标题变了：重命名
        raise HTTPException(409, f"新标题已存在：{new_title}")
    new_path = path_for(new_title)
    write_recipe(new_path, meta, content)                   # 先写新文件
    entry["path"].unlink(missing_ok=True)                   # 再删旧文件
    RECIPES.pop(title, None)
    RECIPES[new_title] = {"path": new_path, "meta": meta, "content": content}
    return public_meta(meta)
```

重命名时先写新文件再删旧文件。若顺序反过来，中途失败会同时丢掉旧数据；现在的顺序最坏只是多出一个文件，
可以人工清理。删除放在关键步骤的最后，是通用的失败安全（fail-safe）做法。
`unlink(missing_ok=True)` 让删除幂等：文件已不在也不抛异常。

### A.4.7 删除：`DELETE /api/recipes/{title}`

```python
@app.delete("/api/recipes/{title}")
def api_delete_recipe(title: str) -> Dict[str, Any]:
    entry = require(title)              # 不存在 → 404，而不是静默成功
    entry["path"].unlink(missing_ok=True)
    RECIPES.pop(title, None)
    return {"ok": True, "deleted": title}
```

删除不存在的资源该返回 404 还是 200，两种做法都有道理：前者能暴露拼写错误，后者符合幂等语义。
本项目选 404，并用测试固定下来。关键是全项目保持一致。

### A.4.8 `/api/reload`：重建索引

```python
@app.post("/api/reload")
def api_reload() -> Dict[str, Any]:
    global TAGS, CATEGORIES, RECIPES
    TAGS = load_tags()
    CATEGORIES = list(TAGS)
    RECIPES = scan_recipes()
    return {"ok": True, "count": len(RECIPES), "categories": CATEGORIES}
```

`TAGS = load_tags()` 抛异常时赋值不会发生，旧标签继续生效、服务不崩（reload 返回 500，其余接口照常）；
但启动时读坏文件会直接抛 `RuntimeError` 让进程退出。同一个错误在启动与运行时的处理方式不同：
配置坏了不该假装能跑，运行中则不该因为一次 reload 拖垮服务。

## A.5 筛选算法

### A.5.1 入口

```python
def api_list_recipes(request: Request):
    return filter_recipes(request.query_params.multi_items())
```

不用 `query_params.get("cuisine")`：`get` 只返回同名参数的最后一个，用户勾了「中式」和「西式」会丢一个；
`multi_items()` 返回全部键值对。

### A.5.2 归并成「类别 → 值列表」

```python
def filter_recipes(query_items):
    wanted: Dict[str, List[str]] = {}
    for key, value in query_items:
        category = resolve_category(key)
        if category is None:            # 不认识的参数直接忽略
            continue
        for item in value.split(","):   # 支持 ?color=红,白
            item = item.strip()
            if item and item not in wanted.setdefault(category, []):
                wanted[category].append(item)
    ...
```

忽略未知参数，前端将来多传参数不会导致 500；逗号分隔方便手敲 URL。

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

设计文档里 `?tool=锅`（单数）与类别名 `tools`（复数）并存，这里两个都接受，并用测试固定行为：

```python
self.assertEqual(len(self.client.get("/api/recipes", params={"tool": "灶"}).json()), 2)
self.assertEqual(len(self.client.get("/api/recipes", params={"nope": "x"}).json()), 2)   # 未知参数被忽略
```

### A.5.4 AND 与 OR

```python
def match_tags(meta, wanted) -> bool:
    for category, values in wanted.items():
        owned = set(meta.get(category, []))
        if WITHIN_CATEGORY_OR:
            if not owned.intersection(values):     # 同类别：任一命中即可
                return False
        elif not set(values).issubset(owned):      # 同类别：必须全部命中
            return False
    return True
```

- 不同类别之间是「且」：选了「中式 + 锅」，两个条件都要满足。
- 同一类别内默认是「或」：勾了「中式」和「西式」应该看到两种菜系；若按「且」，结果永远是空集。
- 文档原文要求全局 AND，因此留了开关，并把取舍写成显式常量：

```python
# 同一类别内多选时：True = 或（选「中式」或「西式」），False = 严格全局 AND
# 不同类别之间永远是「且」。
WITHIN_CATEGORY_OR = True
```

用 `set` 做交集而非嵌套循环，把"菜谱数 × 筛选值数"的乘法降到哈希查找。

### A.5.5 复杂度

```
筛选一次 = O(菜谱数 × 类别数)    # 类别数通常 3~5，可视为常数
按标题查 = O(1)                 # 字典
扫描目录 = O(文件数)，只在启动和 reload 时发生
```

几百篇菜谱下都是微秒级。将来要支持全文搜索时，换掉 `filter_recipes` 的实现即可，接口层不用动。

## A.6 静态托管：前后端怎么接上

```python
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
```

1. `html=True`：访问 `/` 返回 `index.html`，访问 `/detail.html` 返回同名文件，
   所以浏览器可以直接打开 `http://localhost:8000/detail.html?title=...`，不需要额外路由。
2. 这个 `mount` 必须放在所有 `@app.get(...)` 之后。Starlette 按注册顺序匹配路由，
   API 路由先注册就优先命中；若写在文件开头，`/api/recipes` 会被当成"找不到的文件"。
3. 同源的好处：不需要 CORS 与预检请求，前端可以直接写相对路径。

若把前端部署到别处（如 GitHub Pages），就必须加 CORS 中间件，并把前端所有 `/api/...` 改成绝对地址。

## A.7 前端

### A.7.1 三个页面 + 一个脚本：靠入口函数区分页面

```
static/index.html   →  <script>initListPage();</script>
static/detail.html  →  <script>initDetailPage();</script>
static/form.html    →  <script>initFormPage();</script>
static/app.js       →  三个入口函数 + 公共工具，被三个页面共同引入
```

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

初始化包在 `try/catch` 里：后端没起来时用户应看到一句错误，而不是一直转圈的空白页。

### A.7.2 `api()`：fetch 的统一封装

```js
async function api(path, options = {}) {
  const res = await fetch(path, options);
  const raw = await res.text();                        // 先拿文本
  let data = null;
  if (raw) {
    try { data = JSON.parse(raw); } catch (_) { data = raw; }   // 解析失败留原文
  }
  if (!res.ok) {                                       // 非 2xx 一律抛错
    let message = `请求失败（${res.status}）`;
    if (data && data.detail) {                         // 优先用后端的 detail
      message = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
    }
    const err = new Error(message);
    err.status = res.status;                           // 带出状态码
    throw err;
  }
  return data;
}
```

- 不用 `res.json()`：500 时后端可能返回 HTML 错误页，直接解析会把真正的原因盖掉。
- 错误走 `throw`，调用方统一 `try/catch`，不必每次判断 `res.ok`。
- 后端的 `detail` 直接当提示语，错误文案只写一遍。
- `err.status` 让上层还能区分 404/409/422。

所有请求走同一个函数：将来加超时、重试、鉴权头都只改一处。

### A.7.3 `escapeHtml`

```js
function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}
```

```js
`<h3>${escapeHtml(r.title)}</h3>`     // ✅
`<h3>${r.title}</h3>`                 // ❌ 标题里写 <img onerror=...> 就中招
```

一次正则替换，而不是多次 `replace`（后者会把 `&lt;` 二次转义成 `&amp;lt;`）。
`<` `>` 防标签注入，`"` `'` 防属性逃逸。属性值同样要转义，读取时 `dataset` 拿到的是解码后的原值。

### A.7.4 列表渲染与事件绑定

```js
list.innerHTML = recipes.map((r) => `...${escapeHtml(r.title)}...`).join('');
list.querySelectorAll('.delete-btn').forEach((btn) => {
  btn.addEventListener('click', () => deleteRecipe(btn.dataset.title, { onDone: loadList }));
});
```

用模板字符串 + `innerHTML` 的代价：必须手动转义；每次整体重绘会丢掉已绑定的 DOM 与事件，
所以要在渲染后重新绑定；大列表性能差（本项目几十条无所谓）。

第二条的替代方案是事件委托：给不变的外层容器绑一次，用 `event.target.closest('.delete-btn')` 判断点击目标。

### A.7.5 筛选控件与查询串

```js
el('filters').innerHTML = TAG_CATEGORIES.map((category) => `
  <div>
    <div ...>${escapeHtml(categoryLabel(category))}</div>
    <div ...>${(ALL_TAGS[category] || []).map((value) => `
      <label ...>
        <input type="checkbox" class="filter-checkbox"
               data-category="${escapeHtml(category)}" value="${escapeHtml(value)}">
        <span>${escapeHtml(value)}</span>
      </label>`).join('')}</div>
  </div>`).join('');
```

控件从 `/api/tags` 动态生成，后端改 `tags.yaml` 后前端不用改代码。
`data-category` 把"属于哪个类别"存在 DOM 上，取值时用 `cb.dataset.category`。

```js
const params = new URLSearchParams();
document.querySelectorAll('.filter-checkbox:checked').forEach((cb) => {
  params.append(cb.dataset.category, cb.value);   // 同名键 append 多次
});
const query = params.toString();                  // 自动做 URL 编码
```

`append` 多次产生的 `?color=红&color=白` 对应后端 `multi_items()` 的多值读取。

### A.7.6 详情页：Markdown 渲染与 XSS 清洗

```js
function renderMarkdown(markdown) {
  const html = window.marked
    ? window.marked.parse(markdown || '', { gfm: true, breaks: false })
    : `<pre>${escapeHtml(markdown || '')}</pre>`;          // CDN 挂了也别白屏
  const tpl = document.createElement('template');          // 用 template 承载，不入文档树
  tpl.innerHTML = html;
  tpl.content.querySelectorAll('script,style,iframe,object,embed,form,input,link,meta')
    .forEach((n) => n.remove());                           // 删掉危险节点
  tpl.content.querySelectorAll('*').forEach((node) => {    // 逐个元素检查属性
    [...node.attributes].forEach((attr) => {
      const name = attr.name.toLowerCase();
      const riskyUrl = (name === 'href' || name === 'src' || name === 'xlink:href')
        && /^\s*(javascript|data|vbscript):/i.test(attr.value);
      if (name.startsWith('on') || riskyUrl) node.removeAttribute(attr.name);
    });
  });
  return tpl.innerHTML;                                    // 再交给页面
}
```

- `marked` 是 CDN 全局变量，可能加载失败，因此有 `<pre>` 降级分支。
- 用 `<template>` 承载是关键：它的内容属于惰性文档片段，脚本不执行、`<img>` 不发请求、`onerror` 不触发。
  直接 `div.innerHTML = html` 的话，`<img onerror>` 在赋值瞬间就执行了。
- 之后删掉整类危险节点，再逐个元素删除 `on*` 属性与 `javascript:` / `data:` 链接，最后才写入页面。

测试覆盖了这三种攻击：

```js
content: '<script>window.__pwned = 1;</script>\n\n<img src=x onerror="window.__pwned2=1">\n\n[坏链接](javascript:window.__pwned3=1)'
check('XSS：script 节点被移除', c.querySelectorAll('script').length === 0);
check('XSS：页面全局未被污染', w2.__pwned === undefined && ...);
```

这是轻量清洗，不是完整的安全方案。自研 sanitizer 容易漏掉绕过手法（SVG/MathML 里的角括号、CSS 注入、
`<a href="data:text/html;...">` 等），生产环境应用 DOMPurify 这类成熟库。

### A.7.7 表单页：新增与编辑共用一个页面

```js
async function initFormPage() {
  const original = new URLSearchParams(location.search).get('title');
  ...
  if (original) {                                  // URL 里带 title → 编辑模式
    el('page-title').textContent = '编辑菜谱';
    const recipe = await api(`${API}/recipes/${encodeURIComponent(original)}`);
    el('title-input').value = recipe.title;
    el('content-input').value = recipe.content || '';
    TAG_CATEGORIES.forEach((category) => {          // 按已有标签回填勾选框
      (recipe[category] || []).forEach((value) => {
        const box = document.querySelector(
          `.tag-checkbox[data-category="${cssAttr(category)}"][value="${cssAttr(value)}"]`);
        if (box) box.checked = true;
      });
    });
  }
  el('recipe-form').addEventListener('submit', (event) => {
    event.preventDefault();                         // 阻止表单默认跳转
    submitForm(original);
  });
}
```

- 用 URL 里有没有 `title` 区分新增/编辑，不需要第二个页面，也不需要全局状态。
- 回填时 `if (box)` 是必要的：某个标签值若已从 `tags.yaml` 删掉，文件里还留着旧值，界面上没有对应勾选框；
  此时不勾选直接保存，那个标签会被丢掉。
- `event.preventDefault()` 必须调用，否则浏览器用原生方式提交（整页刷新），`fetch` 逻辑不会执行。

```js
const saved = original
  ? await api(`${API}/recipes/${encodeURIComponent(original)}`, { method: 'PUT', ... })
  : await api(`${API}/recipes`, { method: 'POST', ... });
location.href = `/detail.html?title=${encodeURIComponent(saved.title)}`;
```

跳转用 `saved.title` 而不是输入框的值：服务端可能规范化了标题（`A/B` → `A／B`），
以服务端返回的资源标识为准。

### A.7.8 `encodeURIComponent`

标题可能含空格、中文、`&`、`#`，直接拼进 URL 会破坏结构（`#` 被当锚点，`&` 被当参数分隔符）。

```js
`${API}/recipes/${encodeURIComponent(title)}`        // 路径
`/detail.html?title=${encodeURIComponent(r.title)}`  // 页面跳转
```

| 场景 | 用什么 |
| --- | --- |
| 拼 URL 路径或查询参数 | `encodeURIComponent` |
| 拼整个 URL（保留 `:/?#&`） | `encodeURI` |
| 输出到 HTML | `escapeHtml` |

## A.8 一条完整链路：点「删除」之后发生了什么

```
1. 点击卡片上的「删除」，渲染时绑在 .delete-btn 上的闭包被触发，标题从 btn.dataset.title 取回
2. deleteRecipe(title) 弹确认框：if (!window.confirm(`确定要删除《${title}》吗？...`)) return;
3. api(`/api/recipes/${encodeURIComponent(title)}`, { method: 'DELETE' })
4. 浏览器 → uvicorn：DELETE 到 localhost:8000（与页面同源，无 CORS 预检）
5. FastAPI 匹配 @app.delete("/api/recipes/{title}")，路径参数解码后传入 api_delete_recipe
   require(title) 查内存索引；找不到 → 404 "菜谱不存在：..."
6. entry["path"].unlink(missing_ok=True)   # 删磁盘文件
   RECIPES.pop(title, None)                # 同步内存索引
   return {"ok": True, "deleted": title}   # → 200
7. 前端 await 返回，调用 handlers.onDone() → loadList()，重新 GET /api/recipes 并整体重绘
```

第 7 步不手工从 DOM 里删卡片，而是重新拉列表：界面完全由服务端数据推导，避免两边状态不一致。

## A.9 测试

### A.9.1 后端：测试跑在临时目录里

```python
class RecipeApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = Path(tempfile.mkdtemp(prefix="mycuisine-test-"))
        cls.real_dir = app_module.RECIPES_DIR
        app_module.RECIPES_DIR = cls.tmp            # 把全局目录指向临时目录
        cls.client = TestClient(app_module.app)     # 不启真实端口

    @classmethod
    def tearDownClass(cls) -> None:
        app_module.RECIPES_DIR = cls.real_dir       # 一定要还原
        app_module.RECIPES = app_module.scan_recipes()
        shutil.rmtree(cls.tmp, ignore_errors=True)
```

- `app.py` 里的 `RECIPES_DIR` 是模块级常量，所有函数运行时才读它，所以测试里改这个变量就能整体重定向路径。
  （如果某个函数内部写死了 `BASE_DIR / "recipes"`，这里就做不到。）
- `TestClient` 用 httpx 直接调用 ASGI 应用，不起端口：跑得快、不撞端口、不受代理影响。
- `tearDownClass` 必须还原，否则同进程后续代码会继续指向已删除的临时目录。

### A.9.2 一个真实踩坑：`setUp` 里必须重建索引

第一版 `setUp` 只删磁盘文件：

```python
def setUp(self):
    for path in self.tmp.glob("*.md"):
        path.unlink()                 # 只删文件
    for recipe in SAMPLE.values():
        self.client.post("/api/recipes", json=recipe)
```

结果每个用例都失败，报 `409 标题已存在：冰糖糖浆`。原因：磁盘文件删了，但内存索引 `RECIPES`
还留着上一轮用例的条目，`if title in RECIPES` 直接命中。修法是同时重置两个状态：

```python
def setUp(self) -> None:
    for path in self.tmp.glob("*.md"):
        path.unlink()
    app_module.RECIPES = app_module.scan_recipes()   # 索引也要重置
```

系统同时持有内存状态与持久化状态时，测试清理必须覆盖两者，缓存、连接池、单例同理。

### A.9.3 前端端到端：为什么要 stub

`tests/e2e_frontend.mjs` 用 jsdom 跑真实的 HTML 与 `app.js`，打真实后端：

```js
const html = readFileSync(`${STATIC}/${htmlFile}`, 'utf8')
  .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '');   // 先摘掉页面里的 script
const dom = new JSDOM(html, { url: `${BASE}${url}`, runScripts: 'dangerously', virtualConsole: vc });
window.fetch = (path, options) => fetch(new URL(path, BASE).href, options);  // jsdom 没有 fetch
window.confirm = () => true;                                              // jsdom 没实现 confirm
window.eval(markedJs);                                                    // 注入 marked
window.eval(appJs);                                                       // 手动执行 app.js
```

| 做法 | 原因 |
| --- | --- |
| 先摘 `<script>` 再手动 eval | 否则页面里的 `initXxxPage()` 会在 stub 准备好之前执行 |
| 注入 `window.fetch` | jsdom 不实现 fetch；相对路径要拼成绝对地址才能用 Node 的 fetch |
| 注入 `confirm` | jsdom 未实现，直接调用会抛 "Not implemented" |
| 注入 marked | CDN 脚本加载不了（离线/代理），手动提供一份 |
| `window.eval(appJs)` | 让代码在页面自己的 window 作用域执行，而不是 Node 全局 |

jsdom 不实现页面导航，`location.href = '...'` 不会跳转，只会往 `virtualConsole` 发
`jsdomError: Not implemented: navigation`。测试忽略这类错误，改为用 API 断言副作用：

```js
vc.on('jsdomError', (err) => {
  if (!/Not implemented/.test(err.message)) console.log(`  [jsdom] ${err.message}`);
});
```

### A.9.4 两套测试的分工

| | `tests/test_api.py` | `tests/e2e_frontend.mjs` |
| --- | --- | --- |
| 工具 | `unittest` + `fastapi.testclient` | jsdom（Node） |
| 打什么 | 直接调用 ASGI 应用（不起端口） | 真实 HTTP，需要后端在跑 |
| 覆盖 | 数据正确性、状态码、边界、路径安全 | DOM 渲染、筛选交互、表单提交、XSS 清洗 |
| 数量 | 24 个用例 | 35 项断言 |
| 速度 | 0.3 秒 | 几秒 |

前者保证数据层逻辑正确，后者保证页面真能用。A.10 的三个 bug 里有两个是端到端测试发现的。

## A.10 三个真实 bug 的复盘

三个 bug 都是在实现完成、人工点过一遍之后才被测试发现的。

### Bug #1：编辑一次，自定义字段就没了

- 现象：手写文件里加的 `author: 我自己`，在网页里保存一次后消失。
- 原因：`PUT` 用请求体解析出的 `meta` 覆盖索引里的 `meta`，而 `validate_payload` 把 `meta["extra"]`
  初始化为空字典。前端不可能提交它不知道的字段，于是 `extra` 被清空。
- 修法：合并而不是覆盖。

  ```python
  meta["extra"] = {**entry["meta"].get("extra", {}), **meta.get("extra", {})}
  ```

- 教训：读写字段不对称时（读进来 8 个字段、写出去 5 个），缺失的字段会被默认值悄悄抹掉。
  任何"只改一部分字段"的接口都要先确定：没出现在请求里的字段是清空还是保持不变。
- 回归测试：`test_update_keeps_custom_front_matter_fields`。

### Bug #2：详情页的标签是空的

- 现象：列表页标签正常，详情页显示"未打标签"，但数据明明有。
- 原因：`chipsFor(recipe)` 靠模块级变量 `TAG_CATEGORIES` 遍历标签类别，而它只在 `initListPage()`
  和 `initFormPage()` 里赋值。`initDetailPage()` 没赋值，于是它是 `[]`，循环一次都不执行。
- 修法：让函数不依赖外部状态，从菜谱对象自身的数组字段推断。

  ```js
  function recipeCategories(recipe) {
    if (TAG_CATEGORIES.length) return TAG_CATEGORIES;
    return Object.keys(recipe).filter((key) => Array.isArray(recipe[key]));
  }
  ```

- 教训：全局可变状态在跨页面/跨模块时最容易出问题。同一个 `app.js` 被三个页面共用，
  一个没被初始化的全局变量就变成了空值。能靠参数传的就别用全局。
- 人工测试没发现的原因：列表页看起来是对的，而"未打标签"这句文案本身不报错，只是安静地说了假话。

### Bug #3：标题里带 `/` 的菜谱"建得出来，点不进去"

- 现象：新建标题为 `测试 A/B` 的菜谱，创建成功、列表可见，点「查看」报 `404 菜谱不存在`。
- 原因：索引 key 用原始标题（`测试 A/B`），文件名被规范化成 `测试 A／B.md`，
  而 URL 路径里的 `/`（含 `%2F`）在路由前就被解码成路径分隔符，
  `/api/recipes/测试 A%2FB` 匹配不到 `/api/recipes/{title}`，请求在路由层就 404。
- 修法：把规范化提前到标题本身，让 `文件名 = 标题` 恒成立。

  ```python
  title = sanitize_title(raw_title)     # 在 validate_payload 里就规范化
  ```

  同时 `require()` 增加按规范化标题的模糊匹配，手工放进目录的老文件也能打开。
- 教训：任何"用户输入 → 变成标识符（文件名/URL/主键）"的系统，都要先定义标识符的合法字符集，
  并把它作为不变量测下来。否则会出现"能创建、能列出、但访问不了"的脏数据，且只在特定输入下复现。
- 回归测试：`test_special_characters_in_title_are_sanitized` 断言"响应标题 == 文件名去掉 `.md`"
  以及"按规范化标题能查到"。

三个 bug 都不是语法错误，都能通过"点一遍"验收。它们分别是数据被默认值覆盖、全局状态未初始化、
两个各自正确的假设组合出错误。

## A.11 排查手册

| 症状 | 可能原因 | 怎么办 |
| --- | --- | --- |
| 打不开 `localhost:8000`，但服务在跑 | 系统设了 HTTP 代理，`localhost` 也被送进代理 | 浏览器代理例外加 `localhost`；命令行用 `curl --noproxy '*'` |
| `Address already in use` | 8000 被上次的进程占着 | `pgrep -af "uvicorn app:app"` 找到 PID 后 `kill`，或换 `--port 8001` |
| 样式全无、Markdown 变成纯文本块 | Tailwind / marked 的 CDN 加载失败 | 预期内的降级行为，联网后刷新 |
| 改了 `recipes/*.md`，网页没变 | 索引是启动时的快照 | `POST /api/reload` 或重启 |
| 改了 `tags.yaml`，筛选区没变 | 同上，且前端要刷新才会重新拉 `/api/tags` | reload + 刷新浏览器 |
| `422 标签 xxx 含未定义的值` | 提交的值不在 `tags.yaml` 里（常见于改过字典后编辑老菜谱） | 改 `tags.yaml` 或改菜谱标签 |
| `409 标题已存在` | 新增重名或重命名撞名 | 换标题；重命名冲突时旧文件不会被动 |
| `500 xxx 的 YAML 解析失败` | 手工编辑写坏了 Front Matter | 打开该 `.md` 修（错误信息含文件名），启动日志也有 `[warn] 跳过…` |
| 启动即 `RuntimeError: tags.yaml 中类别 xxx 的值必须是列表` | 写成了 `cuisine: 中式` 而非 `cuisine: [中式]` | 修好再启动；运行中 reload 只会返回 500，不影响服务 |
| 前端报 `Failed to fetch` | 后端没启动或端口不对 | 看后端终端有没有 `Uvicorn running on ...` |

`[warn]` 打在运行 `python app.py` 的终端里；前端堆栈只在浏览器 Console（F12）里看得到。

## A.12 动手练习

1. 改用事件委托：给 `#list` 绑一次 click，用 `event.target.closest('.delete-btn')` 取按钮。
2. 加"创建时间"：写入时在 Front Matter 里加 `created_at`，列表按它倒序；注意老文件没有该字段时的兼容。
3. 加标签统计接口 `GET /api/stats`，返回每个标签下有多少菜谱，在内存索引上做一次聚合。
4. 全文搜索 `GET /api/recipes?q=关键词`，匹配标题与正文，考虑是否区分大小写。
5. 在网页里维护标签：`POST /api/tags` 写回 `tags.yaml` 并重建索引。
   难点是保留注释（`yaml.dump` 做不到，需要模板化重写或 `ruamel.yaml`）。
6. 给写操作加并发保护：两人同时编辑同一道菜时用乐观锁（请求带上版本号或修改时间，服务端比对后决定是否拒绝）。

## A.13 术语小抄

| 术语 | 一句话解释 | 本项目里的位置 |
| --- | --- | --- |
| ASGI / uvicorn | Python 异步 Web 服务接口规范 / 实现它的服务器 | `uvicorn.run(app, ...)` |
| 路由（routing） | 把"方法 + 路径"映射到函数 | `@app.get("/api/recipes/{title}")` |
| 路径参数 / 查询参数 | URL 里 `/a/{x}` / `?k=v` 的部分 | `title` / `?cuisine=中式` |
| Front Matter | 文件开头 `---` 包起来的元数据块 | `recipes/*.md` |
| 不变量（invariant） | 系统任何时刻都必须成立的性质 | `文件名 = 标题` |
| 原子写入 | 要么全成功要么全不变，没有中间态 | tmp + `Path.replace()` |
| 幂等（idempotent） | 同一操作执行多次，结果与执行一次相同 | `unlink(missing_ok=True)` |
| 路径穿越 | 用 `../` 逃出预期目录的攻击 | `path_for` 的越界检查 |
| 同源（same-origin） | 协议 + 主机 + 端口完全相同 | 页面与 API 同端口，故无 CORS |
| 状态码语义 | 用 4xx/2xx 表达错误类别 | 404 / 409 / 422 |
| 缓存失效 | 内存副本与真实数据不一致 | `RECIPES` 与 `/api/reload` |
| XSS | 把用户内容当代码执行 | `escapeHtml` + `renderMarkdown` 清洗 |
| E2E 测试 | 从外部把整个系统跑起来验证 | `tests/e2e_frontend.mjs`（jsdom） |

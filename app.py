"""纯文本菜谱管理系统 —— 后端入口（FastAPI）。

菜谱以「YAML Front Matter + Markdown 正文」的 .md 文件存放在 recipes/，
启动时扫描进内存索引，同时托管 static/ 下的前端页面。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import uvicorn
import yaml
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
RECIPES_DIR = BASE_DIR / "recipes"
STATIC_DIR = BASE_DIR / "static"
TAGS_FILE = BASE_DIR / "tags.yaml"

# 文件名安全处理：常见特殊字符替换为全角等价字符，保证 .md 纯文本仍可读
UNSAFE_CHARS = {
    "/": "／", "\\": "＼", ":": "：", "*": "＊", "?": "？",
    '"': "＂", "<": "＜", ">": "＞", "|": "｜",
}
CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
FRONT_MATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
MAX_TITLE_LEN = 120

# 同一类别内多选时：True = 或（选「中式」或「西式」），False = 严格全局 AND
# 不同类别之间永远是「且」。
WITHIN_CATEGORY_OR = True


class _FlowList(list):
    """让标签列表以 [中式, 锅] 的行内格式写入 YAML，保持文件可读。"""


class _Dumper(yaml.SafeDumper):
    pass


def _represent_flow_list(dumper: yaml.SafeDumper, data: _FlowList):
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=True)


_Dumper.add_representer(_FlowList, _represent_flow_list)


# --------------------------------------------------------------------- 字典与索引
def load_tags() -> Dict[str, List[str]]:
    """读取 tags.yaml 中的预定义标签字典（按文件顺序保留类别顺序）。"""
    if not TAGS_FILE.exists():
        raise RuntimeError(f"缺少标签字典文件：{TAGS_FILE}")
    with TAGS_FILE.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise RuntimeError("tags.yaml 顶层必须是「类别: [标签, ...]」的映射")
    tags: Dict[str, List[str]] = {}
    for category, values in data.items():
        category = str(category).strip()
        if not category:
            continue
        values = [] if values is None else values
        if not isinstance(values, list):
            raise RuntimeError(f"tags.yaml 中类别 {category} 的值必须是列表")
        tags[category] = [str(v).strip() for v in values if str(v).strip()]
    if not tags:
        raise RuntimeError("tags.yaml 中没有任何标签类别")
    return tags


def read_recipe_file(path: Path) -> Tuple[Dict[str, Any], str]:
    """拆分 .md 文件的 YAML 头部和 Markdown 正文。"""
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


def normalize_meta(raw: Dict[str, Any], fallback_title: str) -> Dict[str, Any]:
    title = str(raw.get("title") or fallback_title).strip() or fallback_title
    meta: Dict[str, Any] = {"title": title}
    for category in CATEGORIES:
        values = raw.get(category) or []
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list):
            values = []
        meta[category] = [str(v).strip() for v in values if str(v).strip()]
    # 保留用户手写的、tags.yaml 之外的 Front Matter 字段，避免编辑时丢数据
    meta["extra"] = {k: v for k, v in raw.items() if k != "title" and k not in CATEGORIES}
    return meta


def build_entry(path: Path) -> Dict[str, Any]:
    raw, content = read_recipe_file(path)
    return {"path": path, "meta": normalize_meta(raw, path.stem), "content": content}


def scan_recipes() -> Dict[str, Dict[str, Any]]:
    """扫描 recipes/ 目录，建立 标题 -> 菜谱 的内存索引。"""
    RECIPES_DIR.mkdir(parents=True, exist_ok=True)
    index: Dict[str, Dict[str, Any]] = {}
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


TAGS: Dict[str, List[str]] = load_tags()
CATEGORIES: List[str] = list(TAGS)
RECIPES: Dict[str, Dict[str, Any]] = scan_recipes()


# --------------------------------------------------------------------- 校验与读写
def public_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    data: Dict[str, Any] = {"title": meta["title"]}
    for category in CATEGORIES:
        data[category] = list(meta.get(category, []))
    return data


def sanitize_title(title: str) -> str:
    """标题规范化：把路径/URL 有歧义的字符换成全角，保证「文件名 = 标题」恒成立。

    这样任何合法的标题都能通过 /api/recipes/{title} 直接访问到。
    """
    name = CONTROL_CHARS.sub("", str(title)).strip()
    for bad, good in UNSAFE_CHARS.items():
        name = name.replace(bad, good)
    name = name.strip().strip(".").strip()
    if not name:
        raise HTTPException(status_code=422, detail="标题不能为空或只包含不可用字符")
    if len(name) > MAX_TITLE_LEN:
        raise HTTPException(status_code=422, detail=f"标题过长（最多 {MAX_TITLE_LEN} 个字符）")
    return name


def safe_filename(title: str) -> str:
    return sanitize_title(title) + ".md"


def path_for(title: str) -> Path:
    path = (RECIPES_DIR / safe_filename(title)).resolve()
    if path.parent != RECIPES_DIR.resolve():
        raise HTTPException(status_code=422, detail="标题不合法")
    return path


def serialize_recipe(meta: Dict[str, Any], content: str) -> str:
    data: Dict[str, Any] = {"title": meta["title"]}
    for category in CATEGORIES:
        data[category] = _FlowList(meta.get(category, []))
    for key, value in (meta.get("extra") or {}).items():
        data.setdefault(key, value)
    front = yaml.dump(
        data,
        Dumper=_Dumper,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=1000,
    )
    body = (content or "").strip("\n")
    return f"---\n{front}---\n\n{body}\n" if body else f"---\n{front}---\n"


def write_recipe(path: Path, meta: Dict[str, Any], content: str) -> None:
    RECIPES_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(serialize_recipe(meta, content), encoding="utf-8")
    tmp.replace(path)


def validate_payload(payload: Any) -> Tuple[Dict[str, Any], str]:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="请求体必须是 JSON 对象")
    raw_title = str(payload.get("title") or "").strip()
    if not raw_title:
        raise HTTPException(status_code=422, detail="标题不能为空")
    title = sanitize_title(raw_title)  # 特殊字符在标题上就规范化，保证文件名 = 标题
    content = payload.get("content") or ""
    if not isinstance(content, str):
        raise HTTPException(status_code=422, detail="content 必须是字符串")
    meta: Dict[str, Any] = {"title": title, "extra": {}}
    for category in CATEGORIES:
        values = payload.get(category) or []
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list):
            raise HTTPException(status_code=422, detail=f"标签 {category} 必须是数组")
        cleaned: List[str] = []
        for value in values:
            value = str(value).strip()
            if value and value not in cleaned:
                cleaned.append(value)
        invalid = [v for v in cleaned if v not in TAGS[category]]
        if invalid:
            raise HTTPException(
                status_code=422,
                detail=f"标签 {category} 含未定义的值：{'、'.join(invalid)}",
            )
        meta[category] = cleaned
    safe_filename(title)  # 提前校验文件名可用性
    return meta, content


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
        raise HTTPException(status_code=404, detail=f"菜谱不存在：{title}")
    return entry


# --------------------------------------------------------------------- 筛选
def resolve_category(key: str) -> Optional[str]:
    key = key.strip()
    if key in TAGS:
        return key
    if key + "s" in TAGS:  # 兼容 ?tool=锅 与 ?tools=锅
        return key + "s"
    return None


def filter_recipes(query_items: Iterable[Tuple[str, str]]) -> List[Dict[str, Any]]:
    """按标签筛选：不同类别之间是「且」，同类别内按 WITHIN_CATEGORY_OR 取并/交。"""
    wanted: Dict[str, List[str]] = {}
    for key, value in query_items:
        category = resolve_category(key)
        if category is None:  # 未传的 / 不认识的参数不参与筛选
            continue
        for item in value.split(","):
            item = item.strip()
            if item and item not in wanted.setdefault(category, []):
                wanted[category].append(item)

    results: List[Dict[str, Any]] = []
    for title in sorted(RECIPES):
        if match_tags(RECIPES[title]["meta"], wanted):
            results.append(public_meta(RECIPES[title]["meta"]))
    return results


def match_tags(meta: Dict[str, Any], wanted: Dict[str, List[str]]) -> bool:
    for category, values in wanted.items():
        owned = set(meta.get(category, []))
        if WITHIN_CATEGORY_OR:
            if not owned.intersection(values):
                return False
        elif not set(values).issubset(owned):
            return False
    return True


# --------------------------------------------------------------------- API
app = FastAPI(title="MyCuisine · 纯文本菜谱管理", version="1.0.0")


@app.get("/api/tags")
def api_tags() -> Dict[str, List[str]]:
    """返回预定义标签字典。"""
    return TAGS


@app.get("/api/recipes")
def api_list_recipes(request: Request) -> List[Dict[str, Any]]:
    """返回所有菜谱元数据，支持按标签筛选（如 ?cuisine=中式&tools=锅）。"""
    return filter_recipes(request.query_params.multi_items())


@app.get("/api/recipes/{title}")
def api_get_recipe(title: str) -> Dict[str, Any]:
    """返回单篇菜谱的完整内容（元数据 + Markdown 正文）。"""
    entry = require(title)
    data = public_meta(entry["meta"])
    data["content"] = entry["content"]
    return data


@app.post("/api/recipes", status_code=201)
def api_create_recipe(payload: Any = Body(...)) -> Dict[str, Any]:
    """新增菜谱；标题重复返回 409。"""
    meta, content = validate_payload(payload)
    title = meta["title"]
    if title in RECIPES or path_for(title).exists():
        raise HTTPException(status_code=409, detail=f"标题已存在：{title}")
    path = path_for(title)
    write_recipe(path, meta, content)
    RECIPES[title] = {"path": path, "meta": meta, "content": content}
    return public_meta(meta)


@app.put("/api/recipes/{title}")
def api_update_recipe(title: str, payload: Any = Body(...)) -> Dict[str, Any]:
    """编辑菜谱；标题变化时等同于重命名，新标题冲突则报错且不覆盖。"""
    entry = require(title)
    meta, content = validate_payload(payload)
    new_title = meta["title"]
    # 请求体里没带的自定义 Front Matter 字段沿用原文件，避免编辑时丢数据
    meta["extra"] = {**entry["meta"].get("extra", {}), **meta.get("extra", {})}

    if new_title == title:
        write_recipe(entry["path"], meta, content)
        entry["meta"], entry["content"] = meta, content
        return public_meta(meta)

    if new_title in RECIPES:
        raise HTTPException(status_code=409, detail=f"新标题已存在：{new_title}")
    new_path = path_for(new_title)
    if new_path.exists():
        raise HTTPException(status_code=409, detail=f"新标题已存在：{new_title}")
    write_recipe(new_path, meta, content)
    entry["path"].unlink(missing_ok=True)
    RECIPES.pop(title, None)
    RECIPES[new_title] = {"path": new_path, "meta": meta, "content": content}
    return public_meta(meta)


@app.delete("/api/recipes/{title}")
def api_delete_recipe(title: str) -> Dict[str, Any]:
    """删除菜谱文件并从索引移除。"""
    entry = require(title)
    entry["path"].unlink(missing_ok=True)
    RECIPES.pop(title, None)
    return {"ok": True, "deleted": title}


@app.post("/api/reload")
def api_reload() -> Dict[str, Any]:
    """重新读取 tags.yaml 并重建索引（改过文件或标签后无需重启）。"""
    global TAGS, CATEGORIES, RECIPES
    TAGS = load_tags()
    CATEGORIES = list(TAGS)
    RECIPES = scan_recipes()
    return {"ok": True, "count": len(RECIPES), "categories": CATEGORIES}


STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)

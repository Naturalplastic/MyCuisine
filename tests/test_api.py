"""后端 API 测试：python -m unittest discover -s tests -v

测试在临时目录里跑，不会碰 recipes/ 里的真实菜谱。
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as app_module  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

SAMPLE = {
    "冰糖糖浆": {
        "title": "冰糖糖浆",
        "cuisine": ["中式"],
        "tools": ["锅", "灶"],
        "color": ["透明", "琥珀色"],
        "content": "## 原材料\n- 冰糖 100g\n\n## 步骤\n1. 锅中加入冰糖和水\n",
    },
    "麻婆豆腐": {
        "title": "麻婆豆腐",
        "cuisine": ["中式"],
        "tools": ["锅", "灶"],
        "color": ["红", "白"],
        "content": "## 原材料\n- 嫩豆腐 400g\n",
    },
}


class RecipeApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = Path(tempfile.mkdtemp(prefix="mycuisine-test-"))
        cls.real_dir = app_module.RECIPES_DIR
        app_module.RECIPES_DIR = cls.tmp
        cls.client = TestClient(app_module.app)

    @classmethod
    def tearDownClass(cls) -> None:
        app_module.RECIPES_DIR = cls.real_dir
        app_module.RECIPES = app_module.scan_recipes()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self) -> None:
        for path in self.tmp.glob("*.md"):
            path.unlink()
        app_module.RECIPES = app_module.scan_recipes()  # 清空内存索引后重建
        for recipe in SAMPLE.values():
            res = self.client.post("/api/recipes", json=recipe)
            self.assertEqual(res.status_code, 201, res.text)

    # ------------------------------------------------------------------ 读
    def test_tags_returns_dictionary(self) -> None:
        data = self.client.get("/api/tags").json()
        self.assertEqual(list(data), ["cuisine", "tools", "color"])
        self.assertIn("中式", data["cuisine"])

    def test_list_all(self) -> None:
        titles = [r["title"] for r in self.client.get("/api/recipes").json()]
        self.assertEqual(titles, ["冰糖糖浆", "麻婆豆腐"])

    def test_filter_across_categories_is_and(self) -> None:
        res = self.client.get("/api/recipes", params={"cuisine": "中式", "tools": "锅"})
        self.assertEqual(len(res.json()), 2)
        res = self.client.get("/api/recipes", params={"cuisine": "中式", "color": "红"})
        self.assertEqual([r["title"] for r in res.json()], ["麻婆豆腐"])

    def test_filter_within_category_is_or(self) -> None:
        res = self.client.get("/api/recipes", params={"color": "黄"})
        self.assertEqual(res.json(), [])
        res = self.client.get("/api/recipes", params={"color": "黄,红"})
        self.assertEqual([r["title"] for r in res.json()], ["麻婆豆腐"])

    def test_filter_accepts_singular_key_and_unknown_keys(self) -> None:
        res = self.client.get("/api/recipes", params={"tool": "灶"})
        self.assertEqual(len(res.json()), 2)
        res = self.client.get("/api/recipes", params={"nope": "x"})
        self.assertEqual(len(res.json()), 2)

    def test_get_detail_returns_content(self) -> None:
        data = self.client.get("/api/recipes/冰糖糖浆").json()
        self.assertEqual(data["color"], ["透明", "琥珀色"])
        self.assertIn("## 步骤", data["content"])
        self.assertNotIn("---", data["content"])  # Front Matter 不应混进正文

    def test_get_missing_returns_404(self) -> None:
        self.assertEqual(self.client.get("/api/recipes/不存在").status_code, 404)

    # ------------------------------------------------------------------ 增
    def test_create_writes_front_matter_and_empty_tags(self) -> None:
        payload = {"title": "清蒸鲈鱼", "cuisine": [], "tools": ["蒸锅"], "content": "## 步骤\n1. 上锅蒸"}
        res = self.client.post("/api/recipes", json=payload)
        self.assertEqual(res.status_code, 201)
        text = (self.tmp / "清蒸鲈鱼.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\ntitle: 清蒸鲈鱼\n"))
        self.assertIn("cuisine: []", text)          # 未选标签写成空数组
        self.assertIn("tools: [蒸锅]", text)         # 标签用行内格式
        self.assertTrue(text.rstrip().endswith("上锅蒸"))

    def test_create_omitting_tag_categories_is_allowed(self) -> None:
        res = self.client.post("/api/recipes", json={"title": "只有标题", "content": "正文"})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["cuisine"], [])

    def test_create_duplicate_returns_409_and_keeps_original(self) -> None:
        res = self.client.post("/api/recipes", json={**SAMPLE["冰糖糖浆"], "content": "覆盖内容"})
        self.assertEqual(res.status_code, 409)
        self.assertIn("标题已存在", res.json()["detail"])
        self.assertIn("冰糖 100g", (self.tmp / "冰糖糖浆.md").read_text(encoding="utf-8"))

    def test_create_rejects_invalid_tag_value(self) -> None:
        res = self.client.post("/api/recipes", json={"title": "火星菜", "cuisine": ["火星菜"]})
        self.assertEqual(res.status_code, 422)
        self.assertIn("火星菜", res.json()["detail"])

    def test_create_rejects_blank_title(self) -> None:
        self.assertEqual(self.client.post("/api/recipes", json={"title": "   ", "content": "x"}).status_code, 422)

    # ------------------------------------------------------------------ 改
    def test_update_same_title_overwrites(self) -> None:
        res = self.client.put("/api/recipes/冰糖糖浆", json={**SAMPLE["冰糖糖浆"], "color": ["褐"], "content": "## 步骤\n改过"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["color"], ["褐"])
        self.assertIn("改过", (self.tmp / "冰糖糖浆.md").read_text(encoding="utf-8"))

    def test_update_rename_moves_file(self) -> None:
        res = self.client.put("/api/recipes/冰糖糖浆", json={**SAMPLE["冰糖糖浆"], "title": "冰糖糖浆（改良版）"})
        self.assertEqual(res.status_code, 200)
        self.assertFalse((self.tmp / "冰糖糖浆.md").exists())
        self.assertTrue((self.tmp / "冰糖糖浆（改良版）.md").exists())
        self.assertEqual(self.client.get("/api/recipes/冰糖糖浆").status_code, 404)

    def test_update_rename_conflict_returns_409_and_keeps_both(self) -> None:
        res = self.client.put("/api/recipes/冰糖糖浆", json={**SAMPLE["冰糖糖浆"], "title": "麻婆豆腐"})
        self.assertEqual(res.status_code, 409)
        self.assertIn("新标题已存在", res.json()["detail"])
        self.assertTrue((self.tmp / "冰糖糖浆.md").exists())
        self.assertIn("嫩豆腐", (self.tmp / "麻婆豆腐.md").read_text(encoding="utf-8"))

    def test_update_missing_returns_404(self) -> None:
        res = self.client.put("/api/recipes/不存在", json={"title": "不存在", "content": "x"})
        self.assertEqual(res.status_code, 404)

    def test_update_keeps_custom_front_matter_fields(self) -> None:
        path = self.tmp / "手写菜谱.md"
        path.write_text("---\ntitle: 手写菜谱\ncuisine: [日式]\ntools: []\ncolor: []\nauthor: 我自己\n---\n\n正文一\n", encoding="utf-8")
        app_module.RECIPES = app_module.scan_recipes()
        res = self.client.put("/api/recipes/手写菜谱", json={"title": "手写菜谱", "cuisine": ["日式"], "content": "正文二"})
        self.assertEqual(res.status_code, 200)
        text = path.read_text(encoding="utf-8")
        self.assertIn("author: 我自己", text)
        self.assertIn("正文二", text)

    # ------------------------------------------------------------------ 删
    def test_delete_removes_file_and_index(self) -> None:
        res = self.client.delete("/api/recipes/麻婆豆腐")
        self.assertEqual(res.status_code, 200)
        self.assertFalse((self.tmp / "麻婆豆腐.md").exists())
        self.assertEqual(self.client.get("/api/recipes/麻婆豆腐").status_code, 404)

    def test_delete_missing_returns_404(self) -> None:
        self.assertEqual(self.client.delete("/api/recipes/不存在").status_code, 404)

    # ------------------------------------------------------------ 文件名安全
    def test_special_characters_in_title_are_sanitized(self) -> None:
        raw = 'A/B:C*D?E"F<G>H|I'
        clean = "A／B：C＊D？E＂F＜G＞H｜I"
        res = self.client.post("/api/recipes", json={"title": raw, "content": "x"})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["title"], clean)
        # 「文件名 = 标题」恒成立
        self.assertEqual([p.name for p in self.tmp.glob("*.md") if p.name.startswith("A")], [clean + ".md"])
        # 规范化后的标题能直接按路径访问
        self.assertEqual(self.client.get(f"/api/recipes/{clean}").json()["title"], clean)

    def test_title_cannot_escape_recipes_directory(self) -> None:
        res = self.client.post("/api/recipes", json={"title": "../../etc/passwd", "content": "x"})
        self.assertEqual(res.status_code, 201)
        for path in self.tmp.glob("*.md"):
            self.assertEqual(path.resolve().parent, self.tmp.resolve())
        self.assertEqual(len(list(self.tmp.glob("*.md"))), 3)  # 2 个样例 + 新增的
        self.assertFalse((self.tmp / "etc").exists())

    def test_title_of_only_dots_is_rejected(self) -> None:
        self.assertEqual(self.client.post("/api/recipes", json={"title": "..", "content": "x"}).status_code, 422)

    def test_sanitized_filename_collision_is_reported(self) -> None:
        self.assertEqual(self.client.post("/api/recipes", json={"title": "A/B", "content": "x"}).status_code, 201)
        res = self.client.post("/api/recipes", json={"title": "A／B", "content": "y"})
        self.assertEqual(res.status_code, 409)

    # ---------------------------------------------------------------- 重载
    def test_reload_picks_up_files_added_by_hand(self) -> None:
        (self.tmp / "外部新增.md").write_text("---\ntitle: 外部新增\ncuisine: [西式]\ntools: []\ncolor: []\n---\n\n正文\n", encoding="utf-8")
        self.assertEqual(self.client.post("/api/reload").json()["count"], 3)
        self.assertEqual(self.client.get("/api/recipes/外部新增").json()["cuisine"], ["西式"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

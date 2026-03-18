import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


def _load_module(module_name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


class RankRerankFallbackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = pathlib.Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root / "src"))
        cls.mod = _load_module("rank_papers_mod", root / "src" / "3.rank_papers.py")

    def test_process_file_without_rerank_preserves_ranked_queries(self):
        payload = {
            "generated_at": "2026-03-18T00:00:00+00:00",
            "papers": [
                {"id": "paper-a", "title": "A", "abstract": "aaa"},
                {"id": "paper-b", "title": "B", "abstract": "bbb"},
            ],
            "queries": [
                {
                    "type": "intent_query",
                    "ranked": [
                        {"paper_id": "paper-a", "score": 0.9, "star_rating": 5},
                        {"paper_id": "paper-b", "score": 0.4, "star_rating": 3},
                    ],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            input_path = pathlib.Path(tmp) / "in.json"
            output_path = pathlib.Path(tmp) / "out.json"
            input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            self.mod.process_file_without_rerank(
                input_path=str(input_path),
                output_path=str(output_path),
                top_n=None,
                reason="unit-test",
            )
            out = json.loads(output_path.read_text(encoding="utf-8"))
        ranked = out["queries"][0]["ranked"]
        self.assertEqual(ranked[0]["paper_id"], "paper-a")
        self.assertEqual(out["rerank_fallback"], "unit-test")


if __name__ == "__main__":
    unittest.main()

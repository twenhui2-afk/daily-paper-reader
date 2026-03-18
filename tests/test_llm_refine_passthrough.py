import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch


def _load_module(module_name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


class LlmRefinePassthroughTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = pathlib.Path(__file__).resolve().parents[1]
        src_dir = root / "src"
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))
        cls.mod = _load_module("llm_refine_mod_passthrough", src_dir / "4.llm_refine_papers.py")

    def test_process_file_uses_passthrough_when_min_star_eliminates_all_candidates(self):
        payload = {
            "papers": [
                {"id": "paper-a", "title": "A", "abstract": "aaa"},
                {"id": "paper-b", "title": "B", "abstract": "bbb"},
            ],
            "queries": [
                {
                    "ranked": [
                        {"paper_id": "paper-a", "score": 0.42, "star_rating": 2},
                        {"paper_id": "paper-b", "score": 0.31, "star_rating": 1},
                    ]
                }
            ],
        }
        fake_config = {
            "subscriptions": {
                "intent_profiles": [
                    {
                        "tag": "口腔分割",
                        "enabled": True,
                        "keywords": [
                            {
                                "keyword": "dental segmentation",
                                "query": "dental image segmentation",
                                "enabled": True,
                            }
                        ],
                    }
                ]
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            input_path = pathlib.Path(tmp) / "in.json"
            output_path = pathlib.Path(tmp) / "out.json"
            input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            with patch.object(self.mod, "load_config", return_value=fake_config):
                self.mod.process_file(
                    input_path=str(input_path),
                    output_path=str(output_path),
                    min_star=4,
                    batch_size=10,
                    max_chars=850,
                    filter_model="gpt-5.4",
                    max_output_tokens=4096,
                    filter_concurrency=1,
                )
            out = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(len(out.get("llm_ranked") or []), 2)
        self.assertEqual(out["llm_ranked"][0]["paper_id"], "paper-a")
        self.assertTrue(str(out.get("llm_refine_fallback") or "").startswith("relaxed_min_star_due_to_"))


if __name__ == "__main__":
    unittest.main()

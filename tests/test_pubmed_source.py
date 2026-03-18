import importlib.util
import pathlib
import sys
import unittest
from unittest import mock


def _load_module(module_name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


class PubMedSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = pathlib.Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root / "src"))
        cls.mod = _load_module("pubmed_source_mod", root / "src" / "pubmed_source.py")

    def test_build_pubmed_queries_from_intent_profiles(self):
        config = {
            "subscriptions": {
                "intent_profiles": [
                    {
                        "tag": "oral-lesion",
                        "keywords": [{"keyword": "periapical lesion", "query": "periapical lesion panoramic radiograph"}],
                        "intent_queries": [{"query": "deep learning panoramic radiograph periapical lesion screening"}],
                    }
                ]
            }
        }
        queries = self.mod.build_pubmed_queries(config)
        self.assertEqual(len(queries), 2)
        self.assertEqual(queries[0]["tag"], "keyword:oral-lesion")
        self.assertIn("periapical lesion", queries[0]["query_text"])

    def test_build_pubmed_queries_falls_back_to_root_intent_profiles(self):
        config = {
            "intent_profiles": {
                "topic.1": {
                    "label": "LLM in medicine",
                    "queries": ["large language models in clinical decision support"],
                    "tags": ["medical llm"],
                }
            }
        }
        queries = self.mod.build_pubmed_queries(config)
        self.assertEqual(len(queries), 2)
        self.assertEqual(queries[0]["tag"], "LLM in medicine")
        self.assertEqual(
            queries[0]["query_text"],
            "large language models in clinical decision support",
        )
        self.assertEqual(queries[1]["query_text"], "medical llm")

    def test_get_pubmed_config_prefers_env(self):
        with mock.patch.dict(
            "os.environ",
            {
                "PUBMED_ENABLED": "true",
                "PUBMED_EMAIL": "env@example.com",
                "PUBMED_API_KEY": "env-key",
            },
            clear=False,
        ):
            cfg = self.mod.get_pubmed_config({"pubmed": {"enabled": False, "email": "file@example.com"}})
        self.assertTrue(cfg["enabled"])
        self.assertEqual(cfg["email"], "env@example.com")
        self.assertEqual(cfg["api_key"], "env-key")


if __name__ == "__main__":
    unittest.main()

import importlib.util
import pathlib
import sys
import unittest


def _load_module(module_name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


class SelectPapersIdCompatTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = pathlib.Path(__file__).resolve().parents[1]
        src_dir = root / "src"
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))
        cls.mod = _load_module("select_mod_id_compat", src_dir / "5.select_papers.py")

    def test_build_scored_papers_accepts_paper_id_only_inputs(self):
        papers = [
            {"paper_id": "p-1", "title": "Paper 1", "abstract": "A"},
            {"paper_id": "p-2", "title": "Paper 2", "abstract": "B"},
        ]
        llm_ranked = [
            {"paper_id": "p-1", "score": 8.6, "matched_query_tag": "query:oral-seg"},
            {"paper_id": "p-2", "score": 7.9, "matched_query_tag": "query:oral-seg"},
        ]
        out = self.mod.build_scored_papers(papers, llm_ranked)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0].get("id"), "p-1")
        self.assertEqual(out[0].get("paper_id"), "p-1")


if __name__ == "__main__":
    unittest.main()

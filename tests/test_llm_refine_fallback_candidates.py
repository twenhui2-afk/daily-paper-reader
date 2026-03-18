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


class LlmRefineFallbackCandidatesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = pathlib.Path(__file__).resolve().parents[1]
        src_dir = root / "src"
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))
        cls.mod = _load_module("llm_refine_mod_fallback_candidates", src_dir / "4.llm_refine_papers.py")

    def test_collect_candidate_ids_respects_min_star(self):
        queries = [
            {
                "ranked": [
                    {"paper_id": "paper-a", "star_rating": 5},
                    {"paper_id": "paper-b", "star_rating": 2},
                ]
            }
        ]
        self.assertEqual(self.mod.collect_candidate_ids(queries, 4), ["paper-a"])

    def test_collect_candidate_ids_can_relax_threshold_for_fallback(self):
        queries = [
            {
                "ranked": [
                    {"paper_id": "paper-a", "star_rating": 3},
                    {"paper_id": "paper-b", "star_rating": 2},
                    {"paper_id": "paper-a", "star_rating": 1},
                ]
            }
        ]
        self.assertEqual(self.mod.collect_candidate_ids(queries, 4), [])
        self.assertEqual(self.mod.collect_candidate_ids(queries, 0), ["paper-a", "paper-b"])


if __name__ == "__main__":
    unittest.main()

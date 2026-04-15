import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


class GenerateDocsMetaParseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        if "llm" not in sys.modules:
            import types

            llm_stub = types.ModuleType("llm")

            class DummyBltClient:
                def __init__(self, *args, **kwargs):
                    pass

            llm_stub.BltClient = DummyBltClient
            sys.modules["llm"] = llm_stub

        if "fitz" not in sys.modules:
            import types

            fitz_stub = types.ModuleType("fitz")
            sys.modules["fitz"] = fitz_stub

        src_path = root / "src" / "6.generate_docs.py"
        spec = importlib.util.spec_from_file_location("gen6_mod", src_path)
        cls.mod = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(cls.mod)

    def test_parse_meta_from_front_matter(self):
        md_path = Path("docs/201706/12/1706.03762v1-attention-is-all-you-need.md")
        item = self.mod._parse_generated_md_to_meta(str(md_path), "pid", "quick")
        self.assertEqual(item["title_en"], "Attention Is All You Need")
        self.assertTrue(item["authors"].startswith("Ashish Vaswani"))
        self.assertIn("query:transformer", item["tags"])
        self.assertEqual(item["date"], "20170612")
        self.assertIn("https://arxiv.org/pdf", item["pdf"])
        self.assertEqual(item["selection_source"], "fresh_fetch")

    def test_parse_fallback_to_legacy_meta_lines(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "paper.md"
            path.write_text(
                "\n".join(
                    [
                        "---",
                        "selection_source: fresh_fetch",
                        "title: Legacy title",
                        "---",
                        "**Authors**: Legacy A, Legacy B",
                        "**Date**: 20260301",
                        "**PDF**: https://example.com/paper.pdf",
                        "**TLDR**: legacy tldr text",
                        "",
                        "## Abstract",
                        "abstract body",
                    ]
                ),
                encoding="utf-8",
            )
            item = self.mod._parse_generated_md_to_meta(
                str(path),
                "legacy",
                "deep",
                "cache_hint",
            )
            self.assertEqual(item["authors"], "Legacy A, Legacy B")
            self.assertEqual(item["date"], "20260301")
            self.assertEqual(item["pdf"], "https://example.com/paper.pdf")
            self.assertEqual(item["tldr"], "legacy tldr text")
            self.assertEqual(item["selection_source"], "cache_hint")

    def test_extract_sidebar_tags_hides_composite_suffix(self):
        paper = {
            "llm_score": 8.0,
            "llm_tags": [
                "query:sr:composite",
                "query:sr",
                "keyword:equation-discovery",
            ],
        }
        tags = self.mod.extract_sidebar_tags(paper)
        self.assertEqual(tags[0], ("score", "8.0"))
        self.assertIn(("query", "sr"), tags)
        self.assertIn(("query", "equation-discovery"), tags)
        self.assertNotIn(("query", "sr:composite"), tags)
        self.assertEqual(tags.count(("query", "sr")), 1)

    def test_extract_study_vocabulary_returns_academic_terms(self):
        vocab = self.mod.extract_study_vocabulary(
            "Multimodal Dental Image Segmentation Benchmark",
            "We study multimodal segmentation, robustness, and clinical diagnosis with a benchmark dataset.",
        )
        terms = [item[0] for item in vocab]
        self.assertIn("multimodal", terms)
        self.assertIn("segmentation", terms)
        self.assertIn("benchmark", terms)

    def test_build_glance_fallback_avoids_mechanical_retrieval_text(self):
        text = self.mod.build_glance_fallback(
            {
                "title": "Dental Segmentation with Multimodal Learning",
                "abstract": "",
                "canonical_evidence": "检索回退候选",
            }
        )
        self.assertNotIn("检索回退候选", text)
        self.assertIn("**Motivation**", text)

    def test_build_glance_fallback_prefers_real_abstract_sentences(self):
        text = self.mod.build_glance_fallback(
            {
                "title": "TEMAD",
                "abstract": (
                    "Dental implant abutments rely heavily on manual design and are time-consuming. "
                    "We propose TEMAD, a text-conditioned multi-expert architecture for multi-abutment design. "
                    "Extensive experiments show that TEMAD achieves state-of-the-art performance."
                ),
                "canonical_evidence": "",
            }
        )
        self.assertIn("TEMAD", text)
        self.assertIn("达到当前最优水平", text)
        self.assertNotIn("建议结合摘要与原文阅读", text)

    def test_build_markdown_content_writes_bilingual_fields(self):
        paper = {
            "title": "Dental Segmentation",
            "abstract": "We propose a segmentation model for oral imaging.",
            "authors": ["A", "B"],
            "published": "2026-04-10T00:00:00+00:00",
            "link": "https://example.com/paper.pdf",
            "llm_tldr_cn": "本文提出一个用于口腔影像分割的模型。",
            "llm_tldr_en": "We propose a segmentation model for oral imaging.",
            "_glance_data": {
                "tldr_cn": "本文提出一个用于口腔影像分割的模型。",
                "tldr_en": "We propose a segmentation model for oral imaging.",
                "motivation": "解决口腔影像分割效率低的问题。",
                "method": "提出一个分割模型。",
                "result": "在目标任务上优于基线。",
                "conclusion": "适合做口腔影像自动分析。",
            },
        }
        content = self.mod.build_markdown_content(
            paper,
            "quick",
            "口腔影像分割",
            "本文研究口腔影像分割。",
            ["query:segmentation"],
        )
        self.assertIn("abstract_zh:", content)
        self.assertIn("abstract_en:", content)
        self.assertIn("tldr_cn:", content)
        self.assertIn("tldr_en:", content)
        self.assertIn("## 摘要", content)
        self.assertIn("## Abstract", content)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Tuple
from xml.etree import ElementTree as ET
import os
import re
import requests

from subscription_plan import build_pipeline_inputs


DEFAULT_TIMEOUT = 30
DEFAULT_TOOL_NAME = "daily-paper-reader"


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = _norm(value).lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def get_pubmed_config(config: Dict[str, Any]) -> Dict[str, Any]:
    root = config or {}
    pubmed = (root.get("pubmed") or {}) if isinstance(root, dict) else {}
    email = _norm(os.getenv("PUBMED_EMAIL") or pubmed.get("email") or "")
    api_key = _norm(os.getenv("PUBMED_API_KEY") or pubmed.get("api_key") or "")
    tool = _norm(os.getenv("PUBMED_TOOL") or pubmed.get("tool") or DEFAULT_TOOL_NAME) or DEFAULT_TOOL_NAME
    enabled_env = os.getenv("PUBMED_ENABLED")
    enabled = _as_bool(enabled_env, False) if enabled_env is not None else _as_bool(pubmed.get("enabled"), False)
    return {
        "enabled": enabled and bool(email),
        "email": email,
        "api_key": api_key,
        "tool": tool,
        "retmax": max(int(pubmed.get("retmax") or 30), 1),
        "query_limit": max(int(pubmed.get("query_limit") or 12), 1),
        "base_url": _norm(pubmed.get("base_url") or "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"),
    }


def build_pubmed_queries(config: Dict[str, Any]) -> List[Dict[str, str]]:
    plan = build_pipeline_inputs(config or {})
    queries: List[Dict[str, str]] = []
    seen: set[str] = set()
    for item in plan.get("embedding_queries") or []:
        if not isinstance(item, dict):
            continue
        query_text = _norm(item.get("query_text") or item.get("query") or "")
        if not query_text:
            continue
        lowered = query_text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        queries.append(
            {
                "tag": _norm(item.get("paper_tag") or item.get("tag") or "pubmed"),
                "query_text": query_text,
            }
        )
    if queries:
        return queries

    root = config or {}
    intent_profiles = root.get("intent_profiles") or {}
    if isinstance(intent_profiles, dict):
        for profile_key, profile in intent_profiles.items():
            if not isinstance(profile, dict):
                continue
            tag = _norm(profile.get("label") or profile.get("tag") or profile_key or "pubmed")
            for field in ("queries", "rewrite_queries", "keywords", "tags"):
                values = profile.get(field) or []
                if isinstance(values, str):
                    values = [values]
                if not isinstance(values, list):
                    continue
                for value in values:
                    query_text = _norm(value)
                    lowered = query_text.lower()
                    if not query_text or lowered in seen:
                        continue
                    seen.add(lowered)
                    queries.append({"tag": tag, "query_text": query_text})

    llm_queries = root.get("llm_queries") or []
    if isinstance(llm_queries, list):
        for idx, item in enumerate(llm_queries, start=1):
            if isinstance(item, str):
                query_text = _norm(item)
                tag = f"llm-query-{idx}"
            elif isinstance(item, dict):
                query_text = _norm(item.get("query") or item.get("query_text") or item.get("rewrite") or "")
                tag = _norm(item.get("tag") or item.get("label") or f"llm-query-{idx}")
            else:
                continue
            lowered = query_text.lower()
            if not query_text or lowered in seen:
                continue
            seen.add(lowered)
            queries.append({"tag": tag, "query_text": query_text})
    return queries


def _build_params(pubmed_conf: Dict[str, Any]) -> Dict[str, str]:
    params = {
        "tool": _norm(pubmed_conf.get("tool") or DEFAULT_TOOL_NAME) or DEFAULT_TOOL_NAME,
        "email": _norm(pubmed_conf.get("email") or ""),
    }
    api_key = _norm(pubmed_conf.get("api_key") or "")
    if api_key:
        params["api_key"] = api_key
    return params


def _safe_date_text(pub_date_el: ET.Element | None) -> str:
    if pub_date_el is None:
        return ""
    year = _norm(pub_date_el.findtext("Year"))
    month = _norm(pub_date_el.findtext("Month"))
    day = _norm(pub_date_el.findtext("Day"))
    medline = _norm(pub_date_el.findtext("MedlineDate"))
    if year:
        month_num = _normalize_month(month)
        if month_num and day.isdigit():
            return f"{year}-{month_num:02d}-{int(day):02d}"
        if month_num:
            return f"{year}-{month_num:02d}-01"
        return f"{year}-01-01"
    if medline:
        match = re.search(r"(19|20)\d{2}", medline)
        if match:
            return f"{match.group(0)}-01-01"
    return ""


def _normalize_month(value: str) -> int | None:
    text = _norm(value)
    if not text:
        return None
    if text.isdigit():
        n = int(text)
        if 1 <= n <= 12:
            return n
    text = text[:3].lower()
    months = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }
    return months.get(text)


def _iter_author_names(author_list_el: ET.Element | None) -> Iterable[str]:
    if author_list_el is None:
        return []
    output: List[str] = []
    for author_el in author_list_el.findall("Author"):
        collective = _norm(author_el.findtext("CollectiveName"))
        if collective:
            output.append(collective)
            continue
        last = _norm(author_el.findtext("LastName"))
        fore = _norm(author_el.findtext("ForeName"))
        name = " ".join(part for part in [fore, last] if part)
        if name:
            output.append(name)
    return output


def _join_abstract(abstract_el: ET.Element | None) -> str:
    if abstract_el is None:
        return ""
    parts: List[str] = []
    for node in abstract_el.findall("AbstractText"):
        text = "".join(node.itertext()).strip()
        label = _norm(node.get("Label") or "")
        if label and text:
            parts.append(f"{label}: {text}")
        elif text:
            parts.append(text)
    return "\n\n".join(parts).strip()


def _extract_identifiers(pubmed_data_el: ET.Element | None) -> Tuple[str, str]:
    doi = ""
    pmc = ""
    if pubmed_data_el is None:
        return doi, pmc
    id_list_el = pubmed_data_el.find("ArticleIdList")
    if id_list_el is None:
        return doi, pmc
    for node in id_list_el.findall("ArticleId"):
        id_type = _norm(node.get("IdType") or "").lower()
        value = _norm("".join(node.itertext()))
        if not value:
            continue
        if id_type == "doi" and not doi:
            doi = value
        elif id_type == "pmc" and not pmc:
            pmc = value
    return doi, pmc


def search_pubmed_pmids(
    *,
    base_url: str,
    query_text: str,
    start_date: datetime,
    end_date: datetime,
    retmax: int,
    pubmed_conf: Dict[str, Any],
    timeout: int = DEFAULT_TIMEOUT,
) -> List[str]:
    params = {
        "db": "pubmed",
        "retmode": "json",
        "sort": "pub date",
        "retmax": str(max(int(retmax or 1), 1)),
        "term": query_text,
        "datetype": "pdat",
        "mindate": start_date.strftime("%Y/%m/%d"),
        "maxdate": end_date.strftime("%Y/%m/%d"),
    }
    params.update(_build_params(pubmed_conf))
    resp = requests.get(f"{base_url.rstrip('/')}/esearch.fcgi", params=params, timeout=timeout)
    resp.raise_for_status()
    data = resp.json() or {}
    id_list = (((data or {}).get("esearchresult") or {}).get("idlist") or [])
    return [pid for pid in id_list if _norm(pid)]


def fetch_pubmed_records(
    *,
    base_url: str,
    pmids: List[str],
    pubmed_conf: Dict[str, Any],
    timeout: int = DEFAULT_TIMEOUT,
) -> List[Dict[str, Any]]:
    safe_pmids = [_norm(pid) for pid in pmids if _norm(pid)]
    if not safe_pmids:
        return []
    params = {
        "db": "pubmed",
        "retmode": "xml",
        "id": ",".join(safe_pmids),
    }
    params.update(_build_params(pubmed_conf))
    resp = requests.get(f"{base_url.rstrip('/')}/efetch.fcgi", params=params, timeout=timeout)
    resp.raise_for_status()
    root = ET.fromstring(resp.text or "")
    rows: List[Dict[str, Any]] = []
    for article in root.findall(".//PubmedArticle"):
        medline = article.find("MedlineCitation")
        pubmed_data = article.find("PubmedData")
        if medline is None:
            continue
        pmid = _norm(medline.findtext("PMID"))
        article_el = medline.find("Article")
        if not pmid or article_el is None:
            continue
        journal_title = _norm(article_el.findtext("Journal/Title"))
        abstract = _join_abstract(article_el.find("Abstract"))
        title = "".join(article_el.findtext("ArticleTitle") or "").strip()
        authors = list(_iter_author_names(article_el.find("AuthorList")))
        pub_date = _safe_date_text(article_el.find("Journal/JournalIssue/PubDate"))
        doi, pmc = _extract_identifiers(pubmed_data)
        categories: List[str] = []
        keyword_list = medline.findall("KeywordList/Keyword")
        for node in keyword_list[:8]:
            text = _norm("".join(node.itertext()))
            if text:
                categories.append(text)
        link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        pdf_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmc}/pdf/" if pmc else ""
        rows.append(
            {
                "id": f"pubmed-{pmid}",
                "source": "pubmed",
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "primary_category": journal_title or "pubmed",
                "categories": categories,
                "published": pub_date,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "link": pdf_url or link,
                "source_link": link,
                "journal": journal_title,
                "doi": doi,
            }
        )
    return rows


def fetch_pubmed_for_topics(
    *,
    config: Dict[str, Any],
    start_date: datetime,
    end_date: datetime,
    timeout: int = DEFAULT_TIMEOUT,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    pubmed_conf = get_pubmed_config(config)
    if not pubmed_conf.get("enabled"):
        return [], []
    queries = build_pubmed_queries(config)[: int(pubmed_conf.get("query_limit") or 12)]
    if not queries:
        return [], []

    base_url = _norm(pubmed_conf.get("base_url") or "")
    retmax = int(pubmed_conf.get("retmax") or 30)
    collected: Dict[str, Dict[str, Any]] = {}
    logs: List[str] = []
    for item in queries:
        query_text = _norm(item.get("query_text") or "")
        tag = _norm(item.get("tag") or "pubmed")
        if not query_text:
            continue
        try:
            pmids = search_pubmed_pmids(
                base_url=base_url,
                query_text=query_text,
                start_date=start_date,
                end_date=end_date,
                retmax=retmax,
                pubmed_conf=pubmed_conf,
                timeout=timeout,
            )
            logs.append(f"[PubMed] query={query_text[:80]} | pmids={len(pmids)}")
            records = fetch_pubmed_records(
                base_url=base_url,
                pmids=pmids,
                pubmed_conf=pubmed_conf,
                timeout=timeout,
            )
            for record in records:
                pid = _norm(record.get("id") or "")
                if not pid:
                    continue
                row = collected.get(pid) or dict(record)
                tags = row.get("fetched_from_tags") or []
                if not isinstance(tags, list):
                    tags = []
                if tag and tag not in tags:
                    tags.append(tag)
                row["fetched_from_tags"] = tags
                collected[pid] = row
        except Exception as exc:
            logs.append(f"[PubMed][WARN] query={query_text[:80]} failed: {exc}")
    return list(collected.values()), logs

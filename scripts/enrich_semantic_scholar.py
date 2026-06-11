"""
Semantic Scholar 信息补充模块

功能:
- 根据 DOI 或标题查询 Semantic Scholar
- 补充 citationCount, influentialCitationCount, tldr, fieldsOfStudy
- 限流处理 (自动等待 + 重试)
"""

import time
import logging
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from config_loader import get_config

logger = logging.getLogger(__name__)

BASE_URL = "https://api.semanticscholar.org/graph/v1"

# 请求字段
PAPER_FIELDS = [
    "title",
    "year",
    "citationCount",
    "influentialCitationCount",
    "fieldsOfStudy",
    "journal",
    "authors",
    "externalIds",
    "openAccessPdf",
    "tldr",
    "abstract",
]


def _build_headers() -> dict:
    """构建请求头."""
    config = get_config()
    api_key = config.get("semantic_scholar_api_key", "")
    headers = {}
    if api_key:
        headers["x-api-key"] = api_key
    return headers


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
)
def _make_request(url: str, params: dict) -> Optional[dict]:
    """发送请求 (带重试)."""
    config = get_config()
    rate_limit_sleep = config.get("semantic_scholar_rate_limit_sleep", 1.0)

    try:
        resp = requests.get(
            url, params=params, headers=_build_headers(), timeout=20
        )

        if resp.status_code == 429:
            logger.warning("Semantic Scholar rate limit (429), waiting 5s...")
            time.sleep(5)
            resp = requests.get(
                url, params=params, headers=_build_headers(), timeout=20
            )

        if resp.status_code == 200:
            time.sleep(rate_limit_sleep)
            return resp.json()
        elif resp.status_code == 404:
            return None
        else:
            logger.warning(f"Semantic Scholar returned {resp.status_code}: {url}")
            resp.raise_for_status()

    except requests.exceptions.RequestException as e:
        logger.warning(f"Semantic Scholar request error: {e}")
        raise
    return None


def search_by_doi(doi: str) -> Optional[dict]:
    """通过 DOI 查询 Semantic Scholar."""
    if not doi:
        return None
    clean_doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
    url = f"{BASE_URL}/paper/DOI:{clean_doi}"
    params = {"fields": ",".join(PAPER_FIELDS)}
    return _make_request(url, params)


def search_by_title(title: str, limit: int = 3) -> list[dict]:
    """通过标题搜索 Semantic Scholar (使用 /paper/search 端点)."""
    if not title:
        return []

    url = f"{BASE_URL}/paper/search"
    params = {
        "query": title,
        "limit": limit,
        "fields": ",".join(PAPER_FIELDS),
    }

    try:
        resp = requests.get(
            url, params=params, headers=_build_headers(), timeout=20
        )

        if resp.status_code == 429:
            logger.warning("Semantic Scholar rate limit (429), waiting 5s...")
            time.sleep(5)
            resp = requests.get(
                url, params=params, headers=_build_headers(), timeout=20
            )

        if resp.status_code == 200:
            time.sleep(1)
            return resp.json().get("data", [])
        else:
            logger.warning(f"Semantic Scholar search returned {resp.status_code}")
            return []
    except Exception as e:
        logger.warning(f"Semantic Scholar search error: {e}")
        return []


def enrich_paper(paper: dict) -> dict:
    """
    用 Semantic Scholar 数据补充文献信息.

    Args:
        paper: 文献字典

    Returns:
        补充后的文献字典
    """
    doi = paper.get("doi", "")
    title = paper.get("title", "")

    s2_data = None

    # 优先通过 DOI 查询
    if doi:
        s2_data = search_by_doi(doi)

    # DOI 查询失败时通过标题搜索
    if not s2_data and title:
        results = search_by_title(title, limit=1)
        if results:
            s2_data = results[0]

    if s2_data:
        # 补充引用量
        if s2_data.get("citationCount"):
            # 取 OpenAlex 和 Semantic Scholar 中较高的引用量
            oa_citations = paper.get("cited_by_count", 0)
            s2_citations = s2_data["citationCount"]
            paper["cited_by_count"] = max(oa_citations, s2_citations)
            paper["influential_citation_count"] = s2_data.get("influentialCitationCount", 0)

        # 补充研究领域
        if s2_data.get("fieldsOfStudy"):
            paper["fields_of_study"] = s2_data["fieldsOfStudy"]

        # 补充 TLDR (AI 摘要)
        tldr = s2_data.get("tldr")
        if tldr and tldr.get("text"):
            paper["tldr"] = tldr["text"]

        # 补充 S2 ID
        if s2_data.get("paperId"):
            paper["semantic_scholar_id"] = s2_data["paperId"]

        # 补充 PDF 链接
        if s2_data.get("openAccessPdf") and s2_data["openAccessPdf"].get("url"):
            paper["open_access_pdf_url"] = s2_data["openAccessPdf"]["url"]

        # 补充 DOI (如果原文没有)
        external_ids = s2_data.get("externalIds", {}) or {}
        if not paper.get("doi") and external_ids.get("DOI"):
            paper["doi"] = external_ids["DOI"]

        paper["semantic_scholar_enriched"] = True
        logger.info(f"Enriched: {title[:60]}... (citations: {paper.get('cited_by_count', 0)})")
    else:
        paper["semantic_scholar_enriched"] = False

    return paper


def batch_enrich_papers(papers: list[dict], show_progress: bool = True) -> list[dict]:
    """
    批量补充文献信息.

    Args:
        papers: 文献列表
        show_progress: 是否显示进度

    Returns:
        补充后的文献列表
    """
    from tqdm import tqdm

    enriched = []
    iterator = tqdm(papers, desc="Enriching with S2") if show_progress else papers

    for paper in iterator:
        try:
            enriched.append(enrich_paper(paper))
        except Exception as e:
            logger.warning(f"Failed to enrich paper '{(paper.get('title') or '?')[:50]}': {e}")
            paper["semantic_scholar_enriched"] = False
            enriched.append(paper)

    enriched_count = sum(1 for p in enriched if p.get("semantic_scholar_enriched"))
    logger.info(f"Semantic Scholar enrichment complete: {enriched_count}/{len(enriched)} enriched")
    return enriched


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # 测试
    paper = {"doi": "10.1016/j.enbuild.2021.110877", "title": "Test paper"}
    enriched = enrich_paper(paper)
    print(f"Citations: {enriched.get('cited_by_count')}")
    print(f"TLDR: {enriched.get('tldr', 'N/A')}")

"""
文献去重模块

去重规则:
1. DOI 相同 → 同一文献
2. DOI 为空时，标题高度相似 → 同一文献
3. 优先保留信息更完整的版本
4. 合并 citation 信息和来源信息
"""

import logging
from typing import Optional

from rapidfuzz import fuzz

from config_loader import get_config

logger = logging.getLogger(__name__)


def _normalize_title(title: str) -> str:
    """规范化标题用于比较."""
    if not title:
        return ""
    # 转小写，去除多余空格，去除标点
    import re
    title = title.lower().strip()
    title = re.sub(r'[^\w\s]', '', title)
    title = re.sub(r'\s+', ' ', title)
    return title


def _title_similarity(t1: str, t2: str) -> float:
    """计算两个标题的相似度 (0-1)."""
    n1 = _normalize_title(t1)
    n2 = _normalize_title(t2)
    if not n1 or not n2:
        return 0.0
    return fuzz.ratio(n1, n2) / 100.0


def _merge_papers(primary: dict, secondary: dict) -> dict:
    """合并两篇文献，优先保留信息更完整的版本."""
    merged = dict(primary)

    # 合并来源
    sources = set()
    if primary.get("source"):
        sources.add(primary["source"])
    if secondary.get("source"):
        sources.add(secondary["source"])
    merged["source"] = ", ".join(sources)

    # 取较高的引用量
    c1 = primary.get("cited_by_count", 0) or 0
    c2 = secondary.get("cited_by_count", 0) or 0
    merged["cited_by_count"] = max(c1, c2)

    # 优先保留非空字段
    for field in ["abstract", "journal", "doi", "title", "year"]:
        if not merged.get(field) and secondary.get(field):
            merged[field] = secondary[field]

    # 合并作者
    authors_primary = set(primary.get("authors", []))
    authors_secondary = set(secondary.get("authors", []))
    merged["authors"] = list(authors_primary | authors_secondary)

    # 标记合并
    merged["dedup_merged_from"] = merged.get("dedup_merged_from", [])
    merged["dedup_merged_from"].append({
        "openalex_id": secondary.get("openalex_id", ""),
        "title": secondary.get("title", ""),
    })

    return merged


def deduplicate_papers(papers: list[dict]) -> list[dict]:
    """
    文献去重.

    Args:
        papers: 文献列表

    Returns:
        去重后的文献列表
    """
    config = get_config()
    threshold = config.get("title_similarity_threshold", 0.85)

    if not papers:
        return []

    # 第一轮: DOI 去重
    doi_map: dict[str, dict] = {}
    for paper in papers:
        doi = (paper.get("doi") or "").strip().lower()
        if doi:
            if doi in doi_map:
                # 合并到已有文献
                doi_map[doi] = _merge_papers(doi_map[doi], paper)
            else:
                doi_map[doi] = dict(paper)

    # 无 DOI 的文献
    no_doi_papers = [p for p in papers if not (p.get("doi") or "").strip()]

    # 合并 DOI 已匹配和未匹配的文献
    unique_papers = list(doi_map.values())

    # 第二轮: 标题相似度去重 (针对无 DOI 文献)
    for paper in no_doi_papers:
        paper_title = paper.get("title", "")
        if not paper_title:
            continue

        is_duplicate = False
        for existing in unique_papers:
            existing_title = existing.get("title", "")
            if _title_similarity(paper_title, existing_title) >= threshold:
                # 合并
                idx = unique_papers.index(existing)
                unique_papers[idx] = _merge_papers(existing, paper)
                is_duplicate = True
                logger.info(
                    f"Title dedup: '{paper_title[:60]}...' ≈ "
                    f"'{existing_title[:60]}...' "
                    f"(sim={_title_similarity(paper_title, existing_title):.2f})"
                )
                break

        if not is_duplicate:
            unique_papers.append(paper)

    removed = len(papers) - len(unique_papers)
    logger.info(f"Deduplication: {len(papers)} → {len(unique_papers)} (removed {removed})")

    return unique_papers


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # 测试
    test_papers = [
        {"title": "A Study on Solar Greenhouse", "doi": "10.1234/test1", "year": 2020, "source": "OpenAlex"},
        {"title": "A Study on Solar Greenhouse", "doi": "10.1234/test1", "year": 2020, "source": "Semantic Scholar"},
        {"title": "Different Paper", "doi": "", "year": 2021, "source": "OpenAlex"},
    ]
    result = deduplicate_papers(test_papers)
    print(f"Result: {len(result)} papers")
    for p in result:
        print(f"  - {p['title']} (source: {p['source']})")

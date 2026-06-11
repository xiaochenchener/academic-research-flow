"""
文献排序评分模块

评分公式:
综合分数 = 相关性分数 × 0.45 + 引用分数 × 0.25 + 新近性分数 × 0.20 + DOI可靠性分数 × 0.10

相关性分数: 基于关键词命中 (按类型加权、按位置加权) 或 DeepSeek 分类结果
引用分数: 基于 Ln 归一化的被引次数
新近性分数: 基于发表年份的新近程度
DOI可靠性分数: 基于 DOI 是否通过 CrossRef 验证
"""

import logging
import math
from datetime import datetime
from typing import Optional

from config_loader import get_config

logger = logging.getLogger(__name__)


def _compute_relevance_score(
    paper: dict,
    keywords: Optional[list[str]] = None,
    keyword_type_weights: Optional[dict[str, float]] = None,
) -> float:
    """
    计算相关性分数。

    优先级:
    1. DeepSeek 分类的 relevance_level (最可靠)
    2. 关键词命中 (按类型加权 + 按位置加权)

    Args:
        paper: 文献字典
        keywords: 用于命中的关键词列表
        keyword_type_weights: 关键词类型权重 (如 {'research_object': 3.0, ...})

    Returns:
        相关性分数 (0-1)
    """
    # 如果有 DeepSeek 分类结果，优先使用
    relevance_level = paper.get("relevance_level", "")
    if relevance_level == "high":
        return 1.0
    elif relevance_level == "medium":
        return 0.6
    elif relevance_level == "low":
        return 0.2

    # 基于关键词命中 (加权)
    if keywords:
        title = (paper.get("title") or "").lower()
        abstract = (paper.get("abstract") or "").lower()

        # 默认权重
        weights = keyword_type_weights or {
            "research_object": 3.0,
            "research_method": 2.0,
            "application_scenario": 1.5,
            "innovation_point": 1.0,
        }

        total_weight = sum(weights.values()) if weights else len(keywords)
        if total_weight == 0:
            total_weight = 1

        weighted_hits = 0.0
        for kw in keywords:
            kw_lower = kw.lower()

            # 确定关键词的权重 (基于类型)
            kw_weight = _get_kw_weight(kw, paper, weights)

            # 标题命中 (2倍) vs 摘要命中 (1倍)
            title_hit = 2.0 if kw_lower in title else 0.0
            abstract_hit = 1.0 if kw_lower in abstract else 0.0

            if title_hit > 0 or abstract_hit > 0:
                position_weight = title_hit + abstract_hit
                weighted_hits += kw_weight * position_weight

        # 归一化: 最大可能分数 = total_weight * 3 (全部关键词都在标题中命中)
        max_possible = total_weight * 3.0
        score = min(weighted_hits / max_possible, 1.0) if max_possible > 0 else 0.0

        return score

    # 兜底: 有信息就给基础分
    has_title = bool(paper.get("title"))
    has_abstract = bool(paper.get("abstract"))
    score = 0.0
    if has_title:
        score += 0.3
    if has_abstract:
        score += 0.3
    return min(score, 0.5)


def _get_kw_weight(kw: str, paper: dict, type_weights: dict[str, float]) -> float:
    """
    根据论文中该关键词的上下文确定其最可能的类型权重。

    返回该类型对应的权重值。
    """
    # 默认使用中位权重
    default_weight = 1.5

    # 如果有关键词类型信息，直接使用
    # 这里从 paper 的 keyword matrix 信息中获取 (如果存在)
    kw_info = paper.get("_keyword_type_map", {})
    if kw in kw_info:
        kw_type = kw_info[kw]
        return type_weights.get(kw_type, default_weight)

    # 否则返回默认权重
    return default_weight


def _compute_citation_score(cited_by_count: int) -> float:
    """
    计算引用分数。

    使用 Ln 归一化: score = min(ln(citations + 1) / ln(1000), 1.0)
    """
    if not cited_by_count or cited_by_count <= 0:
        return 0.0
    return min(math.log(cited_by_count + 1) / math.log(1000), 1.0)


def _compute_recency_score(year: int, current_year: int = None) -> float:
    """
    计算新近性分数。

    当年文献 = 1.0, 5年前 = 0.5, 10年前 = 0.0
    """
    if not year:
        return 0.3  # 无年份给中间分

    if current_year is None:
        current_year = datetime.now().year

    age = current_year - year
    if age <= 0:
        return 1.0
    elif age <= 5:
        return 1.0 - (age / 5) * 0.5  # 0.5~1.0
    elif age <= 20:
        return 0.5 - ((age - 5) / 15) * 0.5  # 0.0~0.5
    else:
        return 0.0


def _compute_validity_score(paper: dict) -> float:
    """
    计算 DOI 可靠性分数.

    有 DOI 且通过 CrossRef 验证 = 1.0
    有 DOI 未验证 = 0.5
    无 DOI = 0.1
    """
    has_doi = bool(paper.get("doi"))
    is_verified = paper.get("crossref_verified", False)

    if has_doi and is_verified:
        return 1.0
    elif has_doi and not is_verified:
        return 0.5
    else:
        return 0.1


def rank_papers(
    papers: list[dict],
    keywords: list[str] = None,
    keyword_type_weights: dict[str, float] = None,
) -> list[dict]:
    """
    对文献进行综合排序评分.

    Args:
        papers: 文献列表
        keywords: 用于计算相关性分数的关键词 (可选)
        keyword_type_weights: 关键词类型权重

    Returns:
        添加了评分字段的文献列表 (按总分降序)
    """
    config = get_config()
    w_rel = config.get("relevance_weight", 0.45)
    w_cit = config.get("citation_weight", 0.25)
    w_rec = config.get("recency_weight", 0.20)
    w_val = config.get("validity_weight", 0.10)

    # 关键词类型权重 (从配置读取)
    kt_weights = keyword_type_weights or config.get("keyword_type_weights", {})

    current_year = datetime.now().year

    for paper in papers:
        rel = _compute_relevance_score(paper, keywords, kt_weights)
        cit = _compute_citation_score(paper.get("cited_by_count", 0))
        rec = _compute_recency_score(paper.get("year"), current_year)
        val = _compute_validity_score(paper)

        total = (
            rel * w_rel +
            cit * w_cit +
            rec * w_rec +
            val * w_val
        )

        paper["relevance_score"] = round(rel, 3)
        paper["citation_score"] = round(cit, 3)
        paper["recency_score"] = round(rec, 3)
        paper["validity_score"] = round(val, 3)
        paper["total_score"] = round(total, 3)

    # 按总分降序排列
    sorted_papers = sorted(papers, key=lambda p: p["total_score"], reverse=True)

    # 添加排名
    for rank, paper in enumerate(sorted_papers, 1):
        paper["rank"] = rank

    top_score = sorted_papers[0]["total_score"] if sorted_papers else 0
    logger.info(f"Ranking complete: {len(sorted_papers)} papers, top score={top_score:.3f}")

    return sorted_papers


def get_top_papers(papers: list[dict], n: int = 10, category: str = None) -> list[dict]:
    """
    获取 Top-N 文献.

    Args:
        papers: 已排序的文献列表
        n: 返回数量
        category: 按类别筛选 (可选)

    Returns:
        Top-N 文献列表
    """
    if category:
        papers = [p for p in papers if p.get("category") == category]
    return papers[:n]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # 测试
    test_papers = [
        {
            "title": "Dynamic thermal model for solar greenhouse",
            "year": 2024,
            "cited_by_count": 100,
            "doi": "10.1234/test1",
            "crossref_verified": True,
            "abstract": "solar greenhouse thermal model CFD simulation",
        },
        {
            "title": "Greenhouse gas emissions from agriculture",
            "year": 2020,
            "cited_by_count": 5,
            "doi": "",
            "crossref_verified": False,
            "abstract": "greenhouse gas emissions climate change",
        },
    ]
    ranked = rank_papers(test_papers, keywords=["solar greenhouse", "thermal model", "CFD"])
    for p in ranked:
        print(f"[{p['rank']}] {p['title']}: total={p['total_score']:.3f}, "
              f"rel={p['relevance_score']:.3f}")

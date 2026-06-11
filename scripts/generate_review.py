"""
文献综述生成模块

功能:
- 基于已分类的文献生成结构化文献综述
- 调用 DeepSeek 生成中文综述段落
- 生成推荐阅读清单
- 生成研究空白分析
"""

import json
import logging
from pathlib import Path

from config_loader import get_config
from deepseek_client import generate_literature_review, extract_research_gap

logger = logging.getLogger(__name__)


def prepare_papers_for_review(papers: list[dict], max_papers: int = 50) -> list[dict]:
    """
    准备用于综述生成的文献子集.

    优先选取:
    1. 直接竞争文献 (全部)
    2. 经典基础文献 (top 10)
    3. 近年前沿文献 (top 15)
    4. 可引用支撑文献 (top 15)
    5. 方法模型文献 (top 10)

    Args:
        papers: 已排序分类的文献列表
        max_papers: 最大文献数

    Returns:
        筛选后的文献列表
    """
    selected = []

    # 按类别优先级选取
    priority = [
        "直接竞争文献",
        "经典基础文献",
        "近年前沿文献",
        "可引用支撑文献",
        "方法模型文献",
        "工程应用文献",
        "背景政策文献",
    ]

    for cat in priority:
        cat_papers = [p for p in papers if p.get("category") == cat]
        selected.extend(cat_papers)
        if len(selected) >= max_papers:
            break

    # 排除噪音文献
    selected = [p for p in selected if p.get("category") != "噪音文献"]

    return selected[:max_papers]


def generate_review_markdown(
    papers: list[dict],
    topic: str,
    innovation: str = "",
    use_deepseek: bool = True,
) -> str:
    """
    生成文献综述 Markdown 文件.

    Args:
        papers: 已分类排序的文献列表
        topic: 研究方向
        innovation: 创新点
        use_deepseek: 是否使用 DeepSeek 生成综述

    Returns:
        Markdown 格式的综述文本
    """
    review_papers = prepare_papers_for_review(papers)

    # 统计信息
    from collections import Counter
    cat_counts = Counter(p.get("category", "未分类") for p in review_papers)

    sections = []

    # 标题
    sections.append(f"# 文献综述初稿：{topic}")
    sections.append("")
    sections.append(f"> 生成时间: 自动生成 | 文献来源: OpenAlex, CrossRef, Semantic Scholar")
    sections.append(f"> 检索文献: {len(papers)} 篇 | 纳入综述: {len(review_papers)} 篇")
    sections.append(f"> 分类统计: {dict(cat_counts)}")
    sections.append("")

    # 使用 DeepSeek 生成核心综述
    if use_deepseek and review_papers:
        try:
            ds_review = generate_literature_review(review_papers, topic)
            sections.append(ds_review)
        except Exception as e:
            logger.error(f"DeepSeek review generation failed: {e}")
            sections.append("> ⚠️ DeepSeek 综述生成失败，以下为基于规则的结构化整理。")
            sections.append("")
            sections.append(_generate_rule_based_review(review_papers, topic))
    else:
        sections.append(_generate_rule_based_review(review_papers, topic))

    # 添加研究空白分析
    if use_deepseek and review_papers:
        try:
            sections.append("")
            sections.append("## 研究空白补充分析")
            sections.append("")
            gap_analysis = extract_research_gap(review_papers[:20], topic)
            sections.append(gap_analysis)
        except Exception as e:
            logger.error(f"DeepSeek gap analysis failed: {e}")
            sections.append("")
            sections.append("> ⚠️ 研究空白分析未能自动生成，请手动分析。")

    # 创新点论证
    if innovation and review_papers:
        sections.append("")
        sections.append("## 创新点合理性论证")
        sections.append("")
        sections.append(f"**用户创新点**：{innovation}")
        sections.append("")

        # 找出竞争文献
        competitors = [p for p in review_papers if p.get("category") == "直接竞争文献"]
        if competitors:
            sections.append(f"### 直接竞争文献 ({len(competitors)} 篇)")
            sections.append("")
            sections.append("以下文献的研究内容与您的创新点存在重叠，请仔细分析差异：")
            sections.append("")
            for i, p in enumerate(competitors[:10], 1):
                authors = ", ".join(p.get("authors", [])[:3])
                sections.append(
                    f"{i}. **{p.get('title', 'N/A')}** "
                    f"({p.get('year', '?')}) - {authors} "
                    f"[DOI: {p.get('doi', '无')}]"
                )
                if p.get("classification_reason"):
                    sections.append(f"   - 分类理由: {p['classification_reason']}")
                sections.append("")
        else:
            sections.append("✅ 未发现直接竞争文献，创新点初步判断为新颖。")
            sections.append("")
            sections.append("> 注意: 此结论基于检索到的文献范围，可能存在未覆盖的研究。建议进一步人工确认。")

    # 推荐阅读
    sections.append("")
    sections.append("## 推荐重点阅读文献 (Top 10)")
    sections.append("")
    sections.append("| # | 标题 | 年份 | 被引 | 推荐理由 |")
    sections.append("|---|------|------|------|---------|")
    for i, p in enumerate(review_papers[:10], 1):
        citations = p.get("cited_by_count", 0)
        reason = (p.get("classification_reason") or p.get("category") or "")[:40]
        sections.append(
            f"| {i} | {(p.get('title') or 'N/A')[:50]}... | {p.get('year', '?')} | {citations} | {reason} |"
        )

    # 需精读文献
    sections.append("")
    sections.append("## 需要全文精读的文献")
    sections.append("")
    competitors = [p for p in review_papers if p.get("category") == "直接竞争文献"]
    classics = [p for p in review_papers if p.get("category") == "经典基础文献"][:5]
    must_read = competitors + classics

    for i, p in enumerate(must_read[:10], 1):
        authors = ", ".join(p.get("authors", [])[:3])
        doi = p.get("doi", "无 DOI")
        sections.append(f"{i}. **{p.get('title', 'N/A')}**")
        sections.append(f"   - 作者: {authors} ({p.get('year', '?')})")
        sections.append(f"   - DOI: {doi}")
        sections.append(f"   - 类别: {p.get('category', '未分类')}")
        sections.append("")


    return "\n".join(sections)


def _generate_rule_based_review(papers: list[dict], topic: str) -> str:
    """基于规则生成结构化文献整理 (不调用 DeepSeek)."""
    sections = []

    # 按类别分组
    from collections import defaultdict
    by_category = defaultdict(list)
    for p in papers:
        cat = p.get("category", "未分类")
        by_category[cat].append(p)

    category_titles = {
        "直接竞争文献": "直接竞争研究",
        "经典基础文献": "经典基础研究",
        "近年前沿文献": "近年最新进展",
        "可引用支撑文献": "可引用支撑研究",
        "方法模型文献": "方法论相关研究",
        "工程应用文献": "工程应用研究",
        "背景政策文献": "背景与综述文献",
    }

    for cat, title in category_titles.items():
        cat_papers = by_category.get(cat, [])
        if not cat_papers:
            continue

        sections.append(f"### {title} ({len(cat_papers)}篇)")
        sections.append("")

        for i, p in enumerate(cat_papers[:10], 1):
            authors = ", ".join(p.get("authors", [])[:3])
            year = p.get("year", "?")
            journal = p.get("journal", "")
            citations = p.get("cited_by_count", 0)

            sections.append(
                f"**[{i}] {p.get('title', 'N/A')}**"
            )
            sections.append(f"- 作者: {authors} ({year})")
            if journal:
                sections.append(f"- 期刊: {journal}")
            sections.append(f"- 被引: {citations}次 | DOI: {p.get('doi', '无')}")

            abstract = p.get("abstract", p.get("tldr", ""))
            if abstract:
                sections.append(f"- 摘要: {abstract[:300]}...")
            sections.append("")

    return "\n".join(sections) if sections else "> 无文献可供整理，请检查检索结果。"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # 测试
    test_papers = [
        {
            "title": "Test Paper on Solar Greenhouse",
            "year": 2023,
            "cited_by_count": 15,
            "category": "直接竞争文献",
            "doi": "10.1234/test",
            "authors": ["Zhang, S.", "Li, W."],
            "journal": "Energy and Buildings",
            "abstract": "This paper presents a dynamic thermal model for solar greenhouses...",
        }
    ]
    md = generate_review_markdown(test_papers, "双层日光温室", use_deepseek=False)
    print(md[:1000])

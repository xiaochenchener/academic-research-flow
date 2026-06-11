"""
引文嵌入模块

根据不同的论文写作场景生成引用句。

引用句类型:
- 背景引入型
- 研究现状型
- 方法借鉴型
- 不足分析型
- 创新点引出型
- 对比竞争型
"""

import json
import logging
from typing import Optional

from deepseek_client import generate_citation_sentence

logger = logging.getLogger(__name__)

CITATION_TYPES = {
    "background": "背景引入型",
    "status": "研究现状型",
    "method": "方法借鉴型",
    "gap": "不足分析型",
    "innovation": "创新点引出型",
    "comparison": "对比竞争型",
}

USAGE_TEMPLATES = {
    "background": "用于引入{field}领域的研究背景和意义，说明该研究的现实需求和学术价值",
    "status": "用于总结{field}领域的当前研究进展，概括已有研究的主要方向和代表性成果",
    "method": "用于说明本文借鉴了该方法/模型的技术路线，作为方法论支撑",
    "gap": "用于指出现有研究在{aspect}方面存在的不足和局限性",
    "innovation": "用于从现有不足引出本研究的创新点，论证创新点的合理性",
    "comparison": "用于与直接竞争文献进行对比，突出本研究的差异和优势",
}


def generate_citation_sentences_for_paper(
    paper: dict,
    topic: str = "",
    auto_detect: bool = True,
) -> list[dict]:
    """
    为一篇文献生成多种引用句.

    Args:
        paper: 文献信息
        topic: 研究方向
        auto_detect: 是否自动判断适合的引用句类型

    Returns:
        引用句列表
    """
    sentences = []

    # 自动判断需要生成哪些类型的引用句
    if auto_detect:
        cat = paper.get("category", "")
        types_to_generate = []

        if cat in ["经典基础文献", "背景政策文献"]:
            types_to_generate = ["background", "status", "method"]
        elif cat == "直接竞争文献":
            types_to_generate = ["comparison", "gap", "innovation"]
        elif cat in ["近年前沿文献", "可引用支撑文献"]:
            types_to_generate = ["status", "method", "background"]
        elif cat == "方法模型文献":
            types_to_generate = ["method", "status"]
        else:
            types_to_generate = ["status", "method"]
    else:
        types_to_generate = list(CITATION_TYPES.keys())

    for cit_type in types_to_generate:
        template = USAGE_TEMPLATES.get(cit_type, USAGE_TEMPLATES["status"])
        usage = template.format(
            field=topic,
            aspect=paper.get("category", "研究方法"),
        )

        try:
            sentence = generate_citation_sentence(paper, usage)
            sentences.append({
                "type": CITATION_TYPES.get(cit_type, cit_type),
                "usage_context": usage,
                "sentence": sentence,
                "paper_title": paper.get("title", ""),
                "paper_doi": paper.get("doi", ""),
            })
        except Exception as e:
            logger.warning(f"Citation generation failed for {(paper.get('title') or '?')[:50]}: {e}")
            sentences.append({
                "type": CITATION_TYPES.get(cit_type, cit_type),
                "sentence": f"[需重新生成] {paper.get('title', 'N/A')}",
                "paper_title": paper.get("title", ""),
                "paper_doi": paper.get("doi", ""),
            })

    return sentences


def generate_all_citation_sentences(
    papers: list[dict],
    topic: str = "",
    max_papers: int = 20,
    show_progress: bool = True,
) -> list[dict]:
    """
    为所有高优先级文献生成引用句.

    Args:
        papers: 文献列表
        topic: 研究方向
        max_papers: 最多处理多少篇文献
        show_progress: 是否显示进度

    Returns:
        引用句列表
    """
    from tqdm import tqdm

    # 优先为高相关性文献生成引用句
    priority_papers = [
        p for p in papers
        if p.get("category") not in ["噪音文献", "未分类"]
        and p.get("relevance_level") in ["high", "medium", None]
    ][:max_papers]

    all_sentences = []
    iterator = tqdm(priority_papers, desc="Generating citations") if show_progress else priority_papers

    for paper in iterator:
        try:
            sentences = generate_citation_sentences_for_paper(paper, topic)
            all_sentences.extend(sentences)
        except Exception as e:
            logger.warning(f"Failed to generate citations for '{(paper.get('title') or '?')[:50]}': {e}")

    logger.info(f"Generated {len(all_sentences)} citation sentences for {len(priority_papers)} papers")
    return all_sentences


def format_citation_sentences_markdown(sentences: list[dict]) -> str:
    """
    将引用句格式化为 Markdown.

    Args:
        sentences: 引用句列表

    Returns:
        Markdown 文本
    """
    from collections import defaultdict

    by_type = defaultdict(list)
    for s in sentences:
        by_type[s["type"]].append(s)

    lines = ["# 可嵌入论文的引用句", ""]
    lines.append(f"> 共 {len(sentences)} 条引用句，按类型组织")
    lines.append("")

    for cit_type, items in by_type.items():
        lines.append(f"## {cit_type}")
        lines.append("")

        for i, item in enumerate(items, 1):
            lines.append(f"### [{i}] {item['paper_title'][:80]}")
            if item.get("paper_doi"):
                lines.append(f"DOI: {item['paper_doi']}")
            lines.append("")
            lines.append("**引用句**：")
            lines.append("")
            lines.append(item["sentence"])
            lines.append("")
            lines.append("---")
            lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # 测试
    paper = {
        "title": "Dynamic thermal model for a solar greenhouse with an earth-to-air heat exchanger",
        "year": 2022,
        "authors": ["Zhang, S.", "Li, W.", "Wang, X."],
        "abstract": "A dynamic thermal model was developed to predict the thermal environment "
                    "of a solar greenhouse with an earth-to-air heat exchanger...",
        "category": "可引用支撑文献",
        "doi": "10.1016/j.enbuild.2022.111234",
    }
    sentences = generate_citation_sentences_for_paper(paper, "日光温室热环境")
    print(format_citation_sentences_markdown(sentences)[:500])

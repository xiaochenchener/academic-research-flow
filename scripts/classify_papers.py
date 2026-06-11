"""
文献分类模块 (本地规则 + DeepSeek 辅助)

将文献分为:
1. 直接竞争文献 — 与创新点高度重叠
2. 可引用支撑文献 — 可用于支撑论述
3. 经典基础文献 — 领域奠基性工作
4. 近年前沿文献 — 近3年发表
5. 方法模型文献 — 提供方法论参考
6. 工程应用文献 — 工程实践和案例
7. 背景政策文献 — 政策标准综述类
8. 噪音文献 — 不相关
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

CATEGORIES = [
    "直接竞争文献",
    "可引用支撑文献",
    "经典基础文献",
    "近年前沿文献",
    "方法模型文献",
    "工程应用文献",
    "背景政策文献",
    "噪音文献",
]


def classify_by_rules(paper: dict) -> dict:
    """
    基于规则的文献初步分类.

    Args:
        paper: 文献字典

    Returns:
        分类结果字典
    """
    title = (paper.get("title") or "").lower()
    abstract = (paper.get("abstract") or paper.get("tldr") or "").lower()
    text = title + " " + abstract

    year = paper.get("year")
    citations = paper.get("cited_by_count", 0) or 0
    current_year = datetime.now().year

    # 规则分类
    category = "可引用支撑文献"  # 默认
    reasons = []

    # 噪音检测关键词
    noise_keywords = [
        "greenhouse gas", "climate change", "carbon footprint",
        "global warming", "co2 emission", "carbon dioxide",
        "politics", "policy framework", "economic analysis",
    ]

    is_noise = False
    for nk in noise_keywords:
        if nk in text:
            is_noise = True
            reasons.append(f"含噪音关键词: {nk}")
            break

    if is_noise:
        category = "噪音文献"

    # 经典文献判断 (高被引 + 较早年)
    if citations >= 50 and year and (current_year - year) >= 5:
        if category != "噪音文献":
            category = "经典基础文献"
            reasons.append(f"高被引({citations}次) + 较早({year}年)")

    # 近年文献判断
    if year and (current_year - year) <= 3:
        if category not in ["经典基础文献", "噪音文献"]:
            category = "近年前沿文献"
            reasons.append(f"近3年发表({year}年)")

    # 综述/政策文献检测
    review_keywords = ["review", "survey", "state of the art", "overview",
                       "综述", "进展", "回顾", "policy", "standard",
                       "regulation", "guideline"]
    for rk in review_keywords:
        if rk in text:
            if category not in ["经典基础文献", "噪音文献"]:
                category = "背景政策文献"
                reasons.append(f"综述/政策类: {rk}")
            break

    # 工程应用检测
    application_keywords = ["case study", "application", "demonstration",
                            "pilot", "field test", "measured data",
                            "experimental study", "on-site"]
    for ak in application_keywords:
        if ak in text:
            if category not in ["经典基础文献", "背景政策文献", "噪音文献"]:
                category = "工程应用文献"
                reasons.append(f"应用类: {ak}")
            break

    # 方法关键词
    method_keywords = ["model", "simulation", "algorithm", "numerical",
                       "cfd", "finite element", "optimization",
                       "mathematical model", "analytical"]
    method_hits = sum(1 for mk in method_keywords if mk in text)
    if method_hits >= 2:
        if category not in ["经典基础文献", "背景政策文献", "噪音文献"]:
            category = "方法模型文献"
            reasons.append(f"方法类: {method_hits}个方法关键词")

    return {
        "rule_category": category,
        "rule_reasons": reasons,
        "rule_confidence": "medium" if len(reasons) >= 2 else "low",
    }


def classify_all_papers(papers: list[dict]) -> list[dict]:
    """
    对所有文献进行规则分类.

    Args:
        papers: 文献列表

    Returns:
        添加了规则分类的文献列表
    """
    for paper in papers:
        rule_result = classify_by_rules(paper)
        paper["rule_category"] = rule_result["rule_category"]
        paper["rule_reasons"] = rule_result["rule_reasons"]

        # 如果还没有 DeepSeek 分类，使用规则分类
        if not paper.get("category"):
            paper["category"] = rule_result["rule_category"]

    # 统计
    from collections import Counter
    cat_counts = Counter(p.get("rule_category", "未分类") for p in papers)
    logger.info(f"Rule-based classification: {dict(cat_counts)}")
    return papers


def get_classification_summary(papers: list[dict]) -> dict:
    """
    生成分类汇总.

    Args:
        papers: 已分类的文献列表

    Returns:
        分类汇总字典
    """
    from collections import Counter

    summary = {
        "total": len(papers),
        "by_category": {},
        "competitors": [],
        "classics": [],
        "support": [],
    }

    for p in papers:
        cat = p.get("category", "未分类")
        if cat not in summary["by_category"]:
            summary["by_category"][cat] = {"count": 0, "papers": []}
        summary["by_category"][cat]["count"] += 1
        summary["by_category"][cat]["papers"].append({
            "title": p.get("title", ""),
            "year": p.get("year"),
            "doi": p.get("doi", ""),
            "cited_by_count": p.get("cited_by_count", 0),
        })

    # 分类汇总
    for cat_name in CATEGORIES:
        if cat_name not in summary["by_category"]:
            summary["by_category"][cat_name] = {"count": 0, "papers": []}

    # 提取竞争者
    for cat_name in ["直接竞争文献"]:
        if cat_name in summary["by_category"]:
            summary["competitors"].extend(summary["by_category"][cat_name]["papers"])

    # 提取经典文献
    for cat_name in ["经典基础文献"]:
        if cat_name in summary["by_category"]:
            summary["classics"].extend(summary["by_category"][cat_name]["papers"])

    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # 测试
    test = [
        {"title": "A review of solar greenhouse technology", "year": 2020, "cited_by_count": 80,
         "abstract": "This review summarizes solar greenhouse research..."},
        {"title": "Greenhouse gas emissions from agriculture", "year": 2021, "cited_by_count": 200,
         "abstract": "We analyze greenhouse gas emissions and climate change impacts..."},
    ]
    result = classify_all_papers(test)
    for p in result:
        print(f"{p['title'][:60]}: {p['rule_category']}")

"""
结果导出模块

功能:
- 导出 JSON (完整数据 + 精简版)
- 导出 Markdown (综述 + 分类 + 引用句)
- 导出 Excel (排序文献表)
- 导出增强版最终报告 (含期刊影响因子)
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from config_loader import get_output_dir
from enrich_journal_info import format_journal_info

logger = logging.getLogger(__name__)


def save_json(data: dict | list, filepath: Path, indent: int = 2) -> None:
    """保存 JSON 文件."""
    filepath.parent.mkdir(parents=True, exist_ok=True)

    class CustomEncoder(json.JSONEncoder):
        def default(self, obj):
            if hasattr(obj, '__dict__'):
                return obj.__dict__
            return str(obj)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent, cls=CustomEncoder)
    logger.info(f"Saved JSON: {filepath}")


def save_markdown(content: str, filepath: Path) -> None:
    """保存 Markdown 文件."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"Saved Markdown: {filepath}")


def save_excel(papers: list[dict], filepath: Path) -> None:
    """
    保存 Excel 文件.

    Args:
        papers: 文献列表
        filepath: 保存路径
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for p in papers:
        jinfo = p.get("journal_info", {})
        rows.append({
            "排名": p.get("rank", ""),
            "标题": p.get("title", ""),
            "作者": "; ".join(p.get("authors", [])[:5]),
            "年份": p.get("year", ""),
            "期刊": p.get("journal", ""),
            "影响因子": jinfo.get("impact_factor", "") if jinfo.get("success") else "",
            "SCI分区": jinfo.get("sci_zone", "") if jinfo.get("success") else "",
            "中科院分区": jinfo.get("cas_zone_name", "") if jinfo.get("success") else "",
            "DOI": p.get("doi", ""),
            "被引次数": p.get("cited_by_count", 0),
            "分类": p.get("category", ""),
            "相关性": p.get("relevance_level", ""),
            "风险等级": p.get("risk_level", ""),
            "综合分数": p.get("total_score", ""),
            "相关性分": p.get("relevance_score", ""),
            "引用分": p.get("citation_score", ""),
            "新近性分": p.get("recency_score", ""),
            "DOI验证": "是" if p.get("crossref_verified") else "否",
            "TLDR": p.get("tldr", ""),
            "摘要": (p.get("abstract") or "")[:300],
            "可引用场景": p.get("can_be_cited_for", ""),
        })

    df = pd.DataFrame(rows)

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="全部文献", index=False)

        categories = df["分类"].dropna().unique()
        for cat in categories:
            cat_df = df[df["分类"] == cat]
            sheet_name = cat[:31]
            cat_df.to_excel(writer, sheet_name=sheet_name, index=False)

        summary_data = []
        for cat in categories:
            cat_df = df[df["分类"] == cat]
            summary_data.append({
                "分类": cat,
                "文献数": len(cat_df),
                "平均综合分": round(cat_df["综合分数"].mean(), 3) if not cat_df["综合分数"].empty else 0,
                "高相关数": len(cat_df[cat_df["相关性"] == "high"]),
                "平均被引": round(cat_df["被引次数"].mean(), 1),
            })

        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name="分类汇总", index=False)

    logger.info(f"Saved Excel: {filepath} ({len(rows)} rows)")


def export_all_results(
    papers: list[dict],
    output_dir: Path,
    topic: str,
    topic_analysis: Optional[dict] = None,
    keyword_matrix: Optional[dict] = None,
    search_queries: Optional[dict] = None,
    literature_review: str = "",
    citation_sentences: str = "",
    final_report: str = "",
) -> dict[str, Path]:
    """
    导出所有结果文件.

    Args:
        papers: 文献列表
        output_dir: 输出目录
        topic: 研究方向
        topic_analysis: 选题分析
        keyword_matrix: 关键词矩阵
        search_queries: 检索式
        literature_review: 文献综述
        citation_sentences: 引用句
        final_report: 最终报告

    Returns:
        输出文件路径字典
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = {}

    # 01 - 选题分析
    if topic_analysis:
        files["01_topic_analysis"] = output_dir / "01_topic_analysis.json"
        save_json(topic_analysis, files["01_topic_analysis"])

    # 02 - 关键词矩阵
    if keyword_matrix:
        files["02_keyword_matrix"] = output_dir / "02_keyword_matrix.md"
        kw_md = _format_keyword_matrix_markdown(keyword_matrix)
        save_markdown(kw_md, files["02_keyword_matrix"])

    # 03 - 检索式
    if search_queries:
        files["03_search_queries"] = output_dir / "03_search_queries.json"
        save_json(search_queries, files["03_search_queries"])

    # 04 - 原始文献
    files["04_raw_papers"] = output_dir / "04_raw_papers.json"
    save_json(papers, files["04_raw_papers"])

    # 05 - 验证后文献
    files["05_verified_papers"] = output_dir / "05_verified_papers.json"
    save_json(papers, files["05_verified_papers"])

    # 06 - 排序文献 Excel
    files["06_ranked_papers"] = output_dir / "06_ranked_papers.xlsx"
    save_excel(papers, files["06_ranked_papers"])

    # 07 - 分类文献
    files["07_classified_papers"] = output_dir / "07_classified_papers.md"
    classified_md = _format_classified_papers_markdown(papers)
    save_markdown(classified_md, files["07_classified_papers"])

    # 08 - 竞争文献
    competitors = [p for p in papers if p.get("category") == "直接竞争文献"]
    files["08_competitor_papers"] = output_dir / "08_competitor_papers.md"
    comp_md = _format_competitor_markdown(competitors)
    save_markdown(comp_md, files["08_competitor_papers"])

    # 09 - 支撑文献
    support = [p for p in papers if p.get("category") in ["可引用支撑文献", "方法模型文献"]]
    files["09_support_papers"] = output_dir / "09_support_papers.md"
    supp_md = _format_support_markdown(support)
    save_markdown(supp_md, files["09_support_papers"])

    # 10 - 文献综述
    if literature_review:
        files["10_literature_review"] = output_dir / "10_literature_review.md"
        save_markdown(literature_review, files["10_literature_review"])

    # 11 - 引用句
    if citation_sentences:
        files["11_citation_sentences"] = output_dir / "11_citation_sentences.md"
        save_markdown(citation_sentences, files["11_citation_sentences"])

    # 最终报告
    if final_report:
        files["final_report"] = output_dir / "final_report.md"
        save_markdown(final_report, files["final_report"])

    logger.info(f"All results exported to {output_dir}")
    return files


def generate_enhanced_final_report(
    papers: list[dict],
    topic: str,
    innovation: str = "",
    from_year: int = 2020,
    to_year: int = 2026,
    topic_analysis: Optional[dict] = None,
    snowball_count: int = 0,
) -> str:
    """
    生成增强版最终报告 (含期刊影响因子等详细信息).

    Args:
        papers: 已排序的文献列表
        topic: 研究方向
        innovation: 创新点描述
        from_year: 检索起始年
        to_year: 检索结束年
        topic_analysis: 选题分析结果
        snowball_count: 通过引用追溯发现的文献数

    Returns:
        Markdown 格式的完整报告
    """
    from collections import Counter

    lines = []
    lines.append(f"# 文献调研报告: {topic}")
    lines.append("")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**检索范围**: {from_year}-{to_year}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ====== 一、调研概览 ======
    lines.append("## 一、文献调研概览")
    lines.append("")

    total = len(papers)
    with_doi = sum(1 for p in papers if p.get("doi"))
    verified_doi = sum(1 for p in papers if p.get("crossref_verified"))
    has_abstract = sum(1 for p in papers if p.get("abstract") or p.get("tldr"))

    lines.append(f"- **检索到文献**: {total} 篇")
    lines.append(f"- **有效 DOI**: {with_doi} 篇 ({with_doi * 100 // max(total, 1)}%)")
    lines.append(f"- **DOI 已验证**: {verified_doi} 篇 ({verified_doi * 100 // max(total, 1)}%)")
    lines.append(f"- **有摘要**: {has_abstract} 篇")
    if snowball_count:
        lines.append(f"- **通过引用追溯发现**: {snowball_count} 篇")

    lines.append("")

    # 年份分布
    years = [p.get("year") for p in papers if p.get("year")]
    if years:
        lines.append("### 年份分布")
        lines.append("")
        year_counts = Counter(years)
        for yr in sorted(year_counts.keys(), reverse=True):
            count = year_counts[yr]
            bar = "█" * max(count, 1)
            lines.append(f"- {yr}: {bar} ({count}篇)")
        lines.append("")

    # 期刊分布
    journals = [p.get("journal", "") for p in papers if p.get("journal")]
    if journals:
        j_counts = Counter(journals)
        lines.append("### 期刊分布 (Top 15)")
        lines.append("")
        lines.append("| 期刊 | 文献数 | 影响因子 |")
        lines.append("|------|--------|---------|")
        for j, count in j_counts.most_common(15):
            # 查找该期刊的影响因子
            if_val = ""
            for p in papers:
                if p.get("journal") == j:
                    jinfo = p.get("journal_info", {})
                    if jinfo.get("success") and jinfo.get("impact_factor"):
                        if_val = str(jinfo["impact_factor"])
                    break
            lines.append(f"| {j} | {count} | {if_val} |")
        lines.append("")

    # 影响因子区间分布
    impact_factors = []
    for p in papers:
        jinfo = p.get("journal_info", {})
        if jinfo.get("success") and jinfo.get("impact_factor"):
            try:
                impact_factors.append(float(jinfo["impact_factor"]))
            except (ValueError, TypeError):
                pass
    if impact_factors:
        lines.append("### 影响因子分布")
        lines.append("")
        lines.append(f"- 最高 IF: {max(impact_factors):.1f}")
        lines.append(f"- 最低 IF: {min(impact_factors):.1f}")
        lines.append(f"- 平均 IF: {sum(impact_factors) / len(impact_factors):.1f}")
        lines.append(f"- IF > 10: {sum(1 for x in impact_factors if x > 10)} 篇")
        lines.append(f"- IF 5-10: {sum(1 for x in impact_factors if 5 < x <= 10)} 篇")
        lines.append(f"- IF < 5: {sum(1 for x in impact_factors if x <= 5)} 篇")
        lines.append("")

    # 选题分析
    if topic_analysis:
        lines.append("---")
        lines.append("")
        lines.append("## 二、选题分析")
        lines.append("")
        lines.append(f"- **研究对象**: {topic_analysis.get('research_object', 'N/A')}")
        lines.append(f"- **研究方法**: {topic_analysis.get('research_method', 'N/A')}")
        lines.append(f"- **应用场景**: {topic_analysis.get('application_scenario', 'N/A')}")
        if topic_analysis.get("possible_innovation_points"):
            lines.append(f"- **创新点**: {', '.join(topic_analysis['possible_innovation_points'])}")
        lines.append("")
        if innovation:
            lines.append(f"**用户创新点**: {innovation}")
            lines.append("")

    # 分类统计
    lines.append("---")
    lines.append("")
    lines.append("## 三、文献分类统计")
    lines.append("")
    cat_counts = Counter(p.get("category", "未分类") for p in papers)
    lines.append("| 分类 | 数量 | 占比 |")
    lines.append("|------|------|------|")
    for cat, count in cat_counts.most_common():
        pct = count * 100 / max(total, 1)
        lines.append(f"| {cat} | {count} | {pct:.1f}% |")
    lines.append("")

    # 竞争文献警告
    competitors = [p for p in papers if p.get("category") == "直接竞争文献"]
    if competitors:
        lines.append(f"### ⚠️ 直接竞争文献 ({len(competitors)} 篇)")
        lines.append("")
        lines.append("以下文献与您的研究高度相关，建议优先精读：")
        lines.append("")
        for i, p in enumerate(competitors[:10], 1):
            doi = p.get("doi", "")
            doi_link = f"[{doi}](https://doi.org/{doi})" if doi else "无"
            lines.append(f"{i}. **{p.get('title', 'N/A')}** ({p.get('year', '?')})")
            lines.append(f"   - 期刊: {p.get('journal', '')} {format_journal_info(p)}")
            lines.append(f"   - DOI: {doi_link}")
            lines.append("")

    # ====== 四、文献详细信息 ======
    lines.append("---")
    lines.append("")
    lines.append("## 四、文献详细信息")
    lines.append("")

    for p in papers:
        rank = p.get("rank", "?")
        title = p.get("title", "N/A")
        authors = ", ".join(p.get("authors", [])[:5])
        year = p.get("year", "?")
        journal = p.get("journal", "")
        doi = p.get("doi", "")
        citations = p.get("cited_by_count", 0)
        category = p.get("category", "未分类")
        total_score = p.get("total_score", 0)
        abstract = p.get("abstract", p.get("tldr", ""))
        source = p.get("source", "")

        lines.append(f"### [{rank}] {title}")
        lines.append("")

        # 基本信息表
        lines.append("| 字段 | 值 |")
        lines.append("|------|-----|")
        lines.append(f"| **期刊** | {journal} |")
        lines.append(f"| **年份** | {year} |")
        lines.append(f"| **作者** | {authors} |")

        # 影响因子信息
        jinfo = p.get("journal_info", {})
        if jinfo.get("success"):
            if jinfo.get("impact_factor"):
                lines.append(f"| **影响因子** | {jinfo['impact_factor']} ({jinfo.get('impact_factor_year', '')}) |")
            if jinfo.get("sci_zone"):
                lines.append(f"| **SCI分区** | {jinfo['sci_zone']} |")
            if jinfo.get("cas_zone_name"):
                lines.append(f"| **中科院分区** | {jinfo['cas_zone_name']} ({jinfo.get('cas_zone', '')}) |")

        doi_link = f"[{doi}](https://doi.org/{doi})" if doi else "无"
        lines.append(f"| **DOI** | {doi_link} |")
        lines.append(f"| **被引次数** | {citations} |")
        lines.append(f"| **分类** | {category} |")
        lines.append(f"| **综合评分** | {total_score} |")
        lines.append(f"| **来源** | {source} |")

        # 风险等级
        risk = p.get("risk_level", "")
        if risk:
            risk_emoji = {"safe": "🟢", "caution": "🟡", "exclude": "🔴"}.get(risk, "")
            lines.append(f"| **风险等级** | {risk_emoji} {risk} |")

        lines.append("")

        # 摘要
        if abstract:
            lines.append(f"**摘要**: {abstract[:600]}")
            if len(abstract) > 600:
                lines.append("...")
            lines.append("")

        # 分类理由
        reason = p.get("classification_reason", "")
        if reason:
            lines.append(f"> 分类理由: {reason}")
            lines.append("")

        # 可引用场景
        cited_for = p.get("can_be_cited_for", "")
        if cited_for:
            lines.append(f"> 可引用场景: {cited_for}")
            lines.append("")

        # Snowball 标记
        if "Snowball" in source:
            seed = p.get("snowball_seed", "")
            if seed:
                lines.append(f"> 🔗 通过引用追溯发现 (种子文献: {seed})")
                lines.append("")

        lines.append("---")
        lines.append("")

    # ====== 五、推荐阅读建议 ======
    lines.append("## 五、推荐阅读建议")
    lines.append("")

    # 按优先级分三档
    high_priority = [p for p in papers if p.get("relevance_level") == "high" or p.get("total_score", 0) > 0.7]
    medium_priority = [p for p in papers if 0.4 < p.get("total_score", 0) <= 0.7]
    low_priority = [p for p in papers if p.get("total_score", 0) <= 0.4]

    lines.append(f"### 🔴 优先精读 ({len(high_priority)} 篇)")
    lines.append("")
    for p in high_priority[:10]:
        lines.append(f"- [{p.get('rank', '?')}] **{p.get('title', '')}** "
                    f"({p.get('year', '?')}, IF: {_get_if_str(p)}, 被引: {p.get('cited_by_count', 0)})")

    lines.append("")
    lines.append(f"### 🟡 建议浏览 ({len(medium_priority)} 篇)")
    lines.append("")
    for p in medium_priority[:5]:
        lines.append(f"- [{p.get('rank', '?')}] {p.get('title', '')} ({p.get('year', '?')})")

    lines.append("")
    lines.append(f"### 🟢 可选择性阅读 ({len(low_priority)} 篇)")
    lines.append("")

    # ====== 六、下一步建议 ======
    lines.append("## 六、下一步建议")
    lines.append("")
    lines.append("1. 按优先级标记阅读上述文献，重点精读「优先精读」中的竞争文献")
    lines.append("2. 在 Excel 文件中筛选、标注阅读笔记")
    lines.append("3. 根据阅读结果调整创新点表述")
    lines.append(f"4. 如需补充文献，可针对具体子方向重新检索")
    lines.append("")

    return "\n".join(lines)


def _get_if_str(paper: dict) -> str:
    """从 paper 中获取影响因子字符串."""
    jinfo = paper.get("journal_info", {})
    if jinfo.get("success") and jinfo.get("impact_factor"):
        return str(jinfo["impact_factor"])
    return "?"


# ====== 格式化辅助函数 ======

def _format_keyword_matrix_markdown(matrix: dict) -> str:
    """格式化关键词矩阵为 Markdown."""
    lines = ["# 关键词矩阵", ""]
    kw_list = matrix.get("keyword_matrix", [])
    if kw_list:
        lines.append("| 类型 | 中文 | 英文 | 用途 | 优先级 |")
        lines.append("|------|------|------|------|--------|")
        for kw in kw_list:
            lines.append(
                f"| {kw.get('type', '')} | {kw.get('chinese', '')} | "
                f"{kw.get('english', '')} | {kw.get('purpose', '')} | "
                f"{kw.get('priority', '')} |"
            )
    return "\n".join(lines)


def _format_classified_papers_markdown(papers: list[dict]) -> str:
    """格式化分类文献为 Markdown."""
    from collections import defaultdict

    by_category = defaultdict(list)
    for p in papers:
        by_category[p.get("category", "未分类")].append(p)

    lines = ["# 文献分类结果", ""]
    lines.append(f"共 {len(papers)} 篇文献")
    lines.append("")

    for cat, cat_papers in by_category.items():
        lines.append(f"## {cat} ({len(cat_papers)}篇)")
        lines.append("")
        for i, p in enumerate(cat_papers[:20], 1):
            authors = ", ".join(p.get("authors", [])[:3])
            ji = format_journal_info(p)
            lines.append(
                f"{i}. **{p.get('title', 'N/A')}** "
                f"({p.get('year', '?')}) - {authors}"
            )
            if p.get("journal"):
                jline = f"   {p['journal']}"
                if ji:
                    jline += f" | {ji}"
                lines.append(jline)
            if p.get("doi"):
                lines.append(f"   DOI: {p['doi']}")
            if p.get("classification_reason"):
                lines.append(f"   理由: {p['classification_reason']}")
            lines.append("")

    return "\n".join(lines)


def _format_competitor_markdown(competitors: list[dict]) -> str:
    """格式化竞争文献为 Markdown."""
    lines = ["# 直接竞争文献", ""]
    if not competitors:
        lines.append("✅ 未发现直接竞争文献")
        return "\n".join(lines)

    lines.append(f"共 {len(competitors)} 篇可能构成直接竞争的文献")
    lines.append("")
    for i, p in enumerate(competitors, 1):
        lines.append(f"## [{i}] {p.get('title', 'N/A')}")
        lines.append("")
        lines.append(f"- **作者**: {', '.join(p.get('authors', [])[:5])}")
        lines.append(f"- **年份**: {p.get('year', '?')}")
        lines.append(f"- **期刊**: {p.get('journal', '')}")
        lines.append(f"- **DOI**: {p.get('doi', '无')}")
        ji = format_journal_info(p)
        if ji:
            lines.append(f"- **期刊信息**: {ji}")
        lines.append(f"- **被引**: {p.get('cited_by_count', 0)}次")
        lines.append("")
        abstract = p.get("abstract", p.get("tldr", ""))
        if abstract:
            lines.append(f"**摘要**: {abstract[:500]}")
            lines.append("")
        if p.get("classification_reason"):
            lines.append(f"**竞争分析**: {p['classification_reason']}")
            lines.append("")

    return "\n".join(lines)


def _format_support_markdown(support: list[dict]) -> str:
    """格式化支撑文献为 Markdown."""
    lines = ["# 可引用支撑文献", ""]
    if not support:
        lines.append("无支撑文献")
        return "\n".join(lines)

    lines.append(f"共 {len(support)} 篇可引用支撑文献")
    lines.append("")
    for i, p in enumerate(support, 1):
        ji = format_journal_info(p)
        lines.append(
            f"{i}. **{p.get('title', 'N/A')}** "
            f"({p.get('year', '?')}) - {p.get('journal', '')} "
            f"- 被引 {p.get('cited_by_count', 0)}次"
        )
        if ji:
            lines.append(f"   {ji}")
        if p.get("can_be_cited_for"):
            lines.append(f"   场景: {p['can_be_cited_for']}")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_papers = [
        {
            "title": "Dynamic thermal model for solar greenhouse",
            "year": 2023,
            "doi": "10.1234/test",
            "authors": ["Zhang, S.", "Li, W."],
            "journal": "Energy and Buildings",
            "cited_by_count": 10,
            "category": "可引用支撑文献",
            "total_score": 0.85,
            "crossref_verified": True,
            "abstract": "This paper presents a comprehensive dynamic thermal model...",
        }
    ]
    out = Path("/tmp/test_output")
    export_all_results(test_papers, out, "测试课题")
    print("Export done")

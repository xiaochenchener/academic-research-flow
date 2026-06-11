#!/usr/bin/env python3
"""
Academic Research Flow - 主程序

从选题分析到文献综述的本地科研自动化文献检索与总结工作流。

Usage:
    python scripts/main.py --topic "研究方向" [选项]

Examples:
    # 基本用法
    python scripts/main.py --topic "模块化相变电热地板低碳供暖"

    # 完整用法
    python scripts/main.py \
        --topic "寒冷地区双层日光温室热湿环境动态模型" \
        --innovation "考虑太阳辐射传输、双层膜围护结构传热、保温被动态控制..." \
        --from-year 2020 \
        --to-year 2026 \
        --classic-count 30 \
        --recent-count 30 \
        --competition-count 20
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# 将 scripts 目录加入 Python path
sys.path.insert(0, str(Path(__file__).parent))

from config_loader import get_config, get_output_dir
from search_openalex import search_openalex_by_topic, snowball_search
from verify_crossref import batch_verify_dois
from enrich_semantic_scholar import batch_enrich_papers
from deduplicate_papers import deduplicate_papers
from rank_papers import rank_papers
from classify_papers import classify_all_papers
from deepseek_client import (
    analyze_topic,
    generate_keyword_matrix,
    batch_classify_papers,
)
from generate_review import generate_review_markdown
from generate_citation_sentences import (
    generate_all_citation_sentences,
    format_citation_sentences_markdown,
)
from export_results import (
    export_all_results,
    save_json,
    save_markdown,
    generate_enhanced_final_report,
)
from enrich_journal_info import batch_enrich_journals


def setup_logging(output_dir: Path) -> None:
    """配置日志."""
    config = get_config()
    log_level = getattr(logging, config.get("log_level", "INFO"), logging.INFO)

    output_dir.mkdir(parents=True, exist_ok=True)
    log_file = output_dir / "pipeline.log"

    logging.basicConfig(
        level=log_level,
        format=config.get("log_format", "%(asctime)s [%(levelname)s] %(name)s: %(message)s"),
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )


def slugify(text: str) -> str:
    """生成 URL 友好的 slug."""
    import re
    text = text.strip()
    text = text[:30]
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '_', text)
    return text.strip('_').lower() or "research"


def _extract_search_terms(keyword_matrix: dict, topic: str, config: dict) -> list[str]:
    """
    从关键词矩阵中提取检索词，按优先级排序。

    返回去重后的检索词列表 (最多 max_search_terms 个).
    """
    search_terms = []

    if keyword_matrix:
        # 按优先级提取: 研究对象 > 研究方法 > 应用场景 > 创新点
        kw_list = keyword_matrix.get("keyword_matrix", [])
        # 按 priority 排序
        priority_order = {"high": 0, "medium": 1, "low": 2}
        sorted_kw = sorted(kw_list, key=lambda k: priority_order.get(k.get("priority", "medium"), 1))

        for kw in sorted_kw:
            english = kw.get("english", "")
            if english:
                search_terms.append(english)

        # 也添加预组合的检索式
        for query_group in ["classic_search_queries", "recent_search_queries",
                             "competition_search_queries", "support_search_queries"]:
            queries = keyword_matrix.get(query_group, [])
            for q in queries:
                term = q.get("query", "")
                if term and term not in search_terms:
                    search_terms.append(term)

    # 如果 DeepSeek 没生成关键词，使用 topic 本身
    if not search_terms:
        search_terms = [topic]

    # 去重并限制数量
    seen = set()
    unique_terms = []
    for t in search_terms:
        if t.lower() not in seen:
            seen.add(t.lower())
            unique_terms.append(t)

    max_terms = config.get("max_search_terms", 15)
    search_terms = unique_terms[:max_terms]

    return search_terms


def main():
    parser = argparse.ArgumentParser(
        description="☕ Academic Research Flow — 一杯咖啡的功夫，完成一篇文献综述",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # 必选参数
    parser.add_argument(
        "--topic", "-t",
        type=str,
        required=True,
        help="研究方向 (例如: '寒冷地区双层日光温室热湿环境动态模型')",
    )

    # 可选参数
    parser.add_argument(
        "--innovation", "-i",
        type=str,
        default="",
        help="初步创新点描述 (用于竞争文献检索和创新性判断)",
    )
    parser.add_argument(
        "--from-year",
        type=int,
        default=2020,
        help="文献检索起始年份 (默认: 2020)",
    )
    parser.add_argument(
        "--to-year",
        type=int,
        default=2026,
        help="文献检索结束年份 (默认: 2026)",
    )
    parser.add_argument(
        "--classic-count",
        type=int,
        default=30,
        help="经典文献检索数量 (默认: 30)",
    )
    parser.add_argument(
        "--recent-count",
        type=int,
        default=30,
        help="近年文献检索数量 (默认: 30)",
    )
    parser.add_argument(
        "--competition-count",
        type=int,
        default=20,
        help="竞争文献检索数量 (默认: 20)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="",
        help="输出目录 (默认: outputs/<topic_slug>)",
    )
    parser.add_argument(
        "--skip-deepseek",
        action="store_true",
        help="跳过 DeepSeek API 调用 (仅做检索和规则分类)",
    )
    parser.add_argument(
        "--skip-enrichment",
        action="store_true",
        help="跳过 Semantic Scholar 信息补充",
    )
    parser.add_argument(
        "--skip-verification",
        action="store_true",
        help="跳过 CrossRef DOI 验证",
    )
    parser.add_argument(
        "--skip-citations",
        action="store_true",
        help="跳过引用句生成",
    )
    parser.add_argument(
        "--skip-journal-info",
        action="store_true",
        help="跳过 easyScholar 期刊信息查询",
    )
    parser.add_argument(
        "--skip-snowballing",
        action="store_true",
        help="跳过引用追溯",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="详细输出",
    )

    args = parser.parse_args()

    # 确定输出目录
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        topic_slug = slugify(args.topic)
        output_dir = get_output_dir(topic_slug)

    # 设置日志
    setup_logging(output_dir)
    logger = logging.getLogger("main")

    config = get_config()

    logger.info("=" * 60)
    logger.info("Academic Research Flow - Starting")
    logger.info(f"Topic: {args.topic}")
    logger.info(f"Innovation: {args.innovation or '(not specified)'}")
    logger.info(f"Year range: {args.from_year}-{args.to_year}")
    logger.info(f"Output: {output_dir}")
    logger.info(f"Concept filter: {'on' if config.get('enable_concept_filter') else 'off'}")
    logger.info(f"Snowballing: {'on' if config.get('enable_snowballing') and not args.skip_snowballing else 'off'}")
    logger.info("=" * 60)

    # 存储所有中间结果
    topic_analysis = None
    keyword_matrix = None
    all_papers = []
    literature_review = ""
    citation_sentences_text = ""
    snowball_papers_count = 0

    # ================================================================
    # Step 1: 选题分析
    # ================================================================
    logger.info("--- Step 1: Topic Analysis ---")
    if not args.skip_deepseek:
        try:
            topic_analysis = analyze_topic(args.topic, args.innovation)
            logger.info(f"Research object: {topic_analysis.get('research_object', 'N/A')}")
            logger.info(f"Research method: {topic_analysis.get('research_method', 'N/A')}")
            logger.info(f"Innovation points: {topic_analysis.get('possible_innovation_points', [])}")

            save_json(topic_analysis, output_dir / "01_topic_analysis.json")
        except Exception as e:
            logger.error(f"Topic analysis failed: {e}")
            logger.info("Continuing with manual keywords...")
            topic_analysis = {"research_topic": args.topic, "error": str(e)}
    else:
        logger.info("DeepSeek skipped (--skip-deepseek), using basic analysis")
        topic_analysis = {
            "research_topic": args.topic,
            "research_object": args.topic,
            "research_method": "",
            "note": "DeepSeek analysis skipped. Run without --skip-deepseek for AI analysis.",
        }

    # ================================================================
    # Step 2: 生成关键词矩阵和检索式
    # ================================================================
    logger.info("--- Step 2: Keyword Matrix ---")
    if not args.skip_deepseek:
        try:
            keyword_matrix = generate_keyword_matrix(args.topic, topic_analysis)
            logger.info(f"Keywords generated: {json.dumps(keyword_matrix.get('keyword_matrix', []), ensure_ascii=False)[:200]}")

            kw_md_lines = ["# 关键词矩阵", ""]
            kw_list = keyword_matrix.get("keyword_matrix", [])
            if kw_list:
                kw_md_lines.append("| 类型 | 中文 | 英文 | 用途 | 优先级 |")
                kw_md_lines.append("|------|------|------|------|--------|")
                for kw in kw_list:
                    kw_md_lines.append(
                        f"| {kw.get('type', '')} | {kw.get('chinese', '')} | "
                        f"{kw.get('english', '')} | {kw.get('purpose', '')} | "
                        f"{kw.get('priority', '')} |"
                    )
            save_markdown("\n".join(kw_md_lines), output_dir / "02_keyword_matrix.md")
            save_json(keyword_matrix, output_dir / "03_search_queries.json")
        except Exception as e:
            logger.warning(f"Keyword generation failed: {e}")
            keyword_matrix = {}
    else:
        keyword_matrix = {}

    # ================================================================
    # Step 3-4: OpenAlex 多轮检索 (使用全部关键词, 最多 max_search_terms)
    # ================================================================
    logger.info("--- Step 3: Literature Search ---")

    # 提取检索词 (按优先级, 全部使用, 限制在 max_search_terms)
    search_terms = _extract_search_terms(keyword_matrix, args.topic, config)
    logger.info(f"Search terms ({len(search_terms)}): {search_terms[:10]}...")

    raw_papers = []

    # 经典文献回溯年数
    classic_lookback = config.get("classic_lookback_years", 20)

    # 执行经典文献检索
    logger.info("Searching classic literature...")
    try:
        classic_papers = search_openalex_by_topic(
            search_terms,
            from_year=max(args.from_year - classic_lookback, 1970),
            to_year=args.to_year - 3,
            max_results=args.classic_count,
            sort="cited_by_count:desc",
        )
        raw_papers.extend(classic_papers)
        logger.info(f"Classic search ({max(args.from_year - classic_lookback, 1970)}-{args.to_year - 3}): {len(classic_papers)} results")
    except Exception as e:
        logger.error(f"Classic search failed: {e}")

    # 执行近年文献检索
    logger.info("Searching recent literature...")
    try:
        recent_papers = search_openalex_by_topic(
            search_terms,
            from_year=max(args.from_year, args.to_year - 3),
            to_year=args.to_year,
            max_results=args.recent_count,
            sort="publication_date:desc",
        )
        raw_papers.extend(recent_papers)
        logger.info(f"Recent search ({max(args.from_year, args.to_year - 3)}-{args.to_year}): {len(recent_papers)} results")
    except Exception as e:
        logger.error(f"Recent search failed: {e}")

    # 执行竞争文献检索 (如果有创新点)
    if args.innovation and keyword_matrix:
        logger.info("Searching competition literature...")
        try:
            comp_queries = keyword_matrix.get("competition_search_queries", [])
            comp_terms = [q.get("query", "") for q in comp_queries if q.get("query")]
            if comp_terms:
                competition_papers = search_openalex_by_topic(
                    comp_terms,
                    from_year=args.from_year,
                    to_year=args.to_year,
                    max_results=args.competition_count,
                    sort="publication_date:desc",
                )
                raw_papers.extend(competition_papers)
                logger.info(f"Competition search: {len(competition_papers)} results")
        except Exception as e:
            logger.error(f"Competition search failed: {e}")

    # 保存原始结果
    save_json(raw_papers, output_dir / "04_raw_papers.json")
    logger.info(f"Total raw papers: {len(raw_papers)}")

    if not raw_papers:
        logger.warning("No papers found! Check search terms or network connection.")
        _generate_empty_report(output_dir, args)
        return

    # ================================================================
    # Step 5: 去重
    # ================================================================
    logger.info("--- Step 5: Deduplication ---")
    all_papers = deduplicate_papers(raw_papers)

    # ================================================================
    # Step 6: CrossRef DOI 验证
    # ================================================================
    if not args.skip_verification:
        logger.info("--- Step 6: CrossRef DOI Verification ---")
        try:
            all_papers = batch_verify_dois(all_papers, show_progress=not args.verbose)
        except Exception as e:
            logger.warning(f"CrossRef verification failed (non-fatal): {e}")
    else:
        logger.info("CrossRef verification skipped (--skip-verification)")

    # ================================================================
    # Step 7: Semantic Scholar 补充
    # ================================================================
    if not args.skip_enrichment:
        logger.info("--- Step 7: Semantic Scholar Enrichment ---")
        try:
            all_papers = batch_enrich_papers(all_papers, show_progress=not args.verbose)
        except Exception as e:
            logger.warning(f"Semantic Scholar enrichment failed (non-fatal): {e}")
    else:
        logger.info("Semantic Scholar enrichment skipped (--skip-enrichment)")

    # ================================================================
    # Step 8: 规则分类
    # ================================================================
    logger.info("--- Step 8: Rule-based Classification ---")
    all_papers = classify_all_papers(all_papers)

    # ================================================================
    # Step 9: DeepSeek 分类
    # ================================================================
    if not args.skip_deepseek and all_papers:
        logger.info("--- Step 9: DeepSeek Classification ---")
        try:
            all_papers = batch_classify_papers(
                all_papers[:50],
                args.topic,
                show_progress=not args.verbose,
            )
        except Exception as e:
            logger.warning(f"DeepSeek classification failed (non-fatal, using rule-based): {e}")

    # ================================================================
    # Step 10: 排序 (使用类型加权关键词)
    # ================================================================
    logger.info("--- Step 10: Ranking ---")
    kw_type_weights = config.get("keyword_type_weights", {})
    all_papers = rank_papers(
        all_papers,
        keywords=search_terms,
        keyword_type_weights=kw_type_weights,
    )

    # ================================================================
    # Step 11: 引用追溯 (snowballing)
    # ================================================================
    if config.get("enable_snowballing") and not args.skip_snowballing and all_papers:
        logger.info("--- Step 11: Snowballing (Citation Tracing) ---")
        try:
            top_n = config.get("snowball_top_n_seeds", 10)
            seed_papers = all_papers[:top_n]

            snowball_new = snowball_search(
                seed_papers,
                direction="both",
                max_forward=config.get("snowball_max_forward", 20),
                max_backward=config.get("snowball_max_backward", 30),
            )

            if snowball_new:
                # 与新文献合并去重
                combined = all_papers + snowball_new
                all_papers = deduplicate_papers(combined)
                logger.info(f"Snowballing added {len(snowball_new)} new papers, "
                           f"total now {len(all_papers)}")

                # 重新分类和排序
                all_papers = classify_all_papers(all_papers)
                all_papers = rank_papers(
                    all_papers,
                    keywords=search_terms,
                    keyword_type_weights=kw_type_weights,
                )

                snowball_papers_count = len(snowball_new)
        except Exception as e:
            logger.warning(f"Snowballing failed (non-fatal): {e}")

    # 保存验证后结果
    save_json(all_papers, output_dir / "05_verified_papers.json")

    # ================================================================
    # Step 12: easyScholar 期刊信息查询
    # ================================================================
    if not args.skip_journal_info:
        logger.info("--- Step 12: Journal Info Enrichment (easyScholar) ---")
        try:
            all_papers = batch_enrich_journals(
                all_papers,
                show_progress=not args.verbose,
            )
        except Exception as e:
            logger.warning(f"Journal info enrichment failed (non-fatal): {e}")
    else:
        logger.info("Journal info enrichment skipped (--skip-journal-info)")

    # ================================================================
    # Step 13: 生成文献综述
    # ================================================================
    logger.info("--- Step 13: Literature Review ---")
    try:
        literature_review = generate_review_markdown(
            all_papers,
            args.topic,
            args.innovation,
            use_deepseek=not args.skip_deepseek,
        )
        save_markdown(literature_review, output_dir / "10_literature_review.md")
    except Exception as e:
        logger.error(f"Review generation failed: {e}")
        literature_review = f"# 文献综述生成失败\n\nError: {e}"

    # ================================================================
    # Step 14: 生成引用句
    # ================================================================
    if not args.skip_citations:
        logger.info("--- Step 14: Citation Sentences ---")
        try:
            all_sentences = generate_all_citation_sentences(
                all_papers,
                topic=args.topic,
                max_papers=15,
                show_progress=not args.verbose,
            )
            citation_sentences_text = format_citation_sentences_markdown(all_sentences)
            save_markdown(citation_sentences_text, output_dir / "11_citation_sentences.md")
        except Exception as e:
            logger.warning(f"Citation generation failed (non-fatal): {e}")
            citation_sentences_text = f"# 引用句生成失败\n\nError: {e}"

    # ================================================================
    # Step 15: 导出所有结果
    # ================================================================
    logger.info("--- Step 15: Export All Results ---")
    try:
        export_all_results(
            all_papers,
            output_dir,
            args.topic,
            topic_analysis=topic_analysis,
            keyword_matrix=keyword_matrix,
            literature_review=literature_review,
            citation_sentences=citation_sentences_text,
        )
    except Exception as e:
        logger.error(f"Export failed: {e}")

    # ================================================================
    # Step 16: 生成增强版最终报告
    # ================================================================
    logger.info("--- Step 16: Enhanced Final Report ---")
    final_report = generate_enhanced_final_report(
        all_papers,
        args.topic,
        innovation=args.innovation,
        from_year=args.from_year,
        to_year=args.to_year,
        topic_analysis=topic_analysis,
        snowball_count=snowball_papers_count,
    )
    save_markdown(final_report, output_dir / "final_report.md")

    # ================================================================
    # 完成
    # ================================================================
    logger.info("=" * 60)
    logger.info("Pipeline Complete!")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Total papers: {len(all_papers)}")

    from collections import Counter
    cat_counts = Counter(p.get("category", "未分类") for p in all_papers)
    logger.info("Classification summary:")
    for cat, count in cat_counts.most_common():
        logger.info(f"  {cat}: {count}")

    # 打印摘要
    print("\n" + "=" * 60)
    print("✅ Academic Research Flow - Pipeline Complete!")
    print("=" * 60)
    print(f"\n📁 Output: {output_dir}")
    print(f"\n📊 Results:")
    print(f"   - Total papers found: {len(raw_papers) + snowball_papers_count}")
    print(f"   - After dedup: {len(all_papers)}")
    print(f"   - Verified DOIs: {sum(1 for p in all_papers if p.get('crossref_verified'))}")
    if snowball_papers_count:
        print(f"   - Snowballing discovered: {snowball_papers_count}")

    competitors = [p for p in all_papers if p.get("category") == "直接竞争文献"]
    if competitors:
        print(f"   - ⚠️  Direct competitors: {len(competitors)}")
    else:
        print(f"   - ✅ No direct competitors found")

    print(f"\n📄 Key files:")
    key_files = [
        "final_report.md",
        "06_ranked_papers.xlsx",
        "10_literature_review.md",
        "11_citation_sentences.md",
    ]
    for f in key_files:
        fp = output_dir / f
        if fp.exists():
            print(f"   ✅ {f}")
        else:
            print(f"   ❌ {f} (not generated)")

    print(f"\n🔜 Next steps:")
    print(f"   1. Review the enhanced final report: {output_dir}/final_report.md")
    print(f"   2. Open and filter ranked papers in: {output_dir}/06_ranked_papers.xlsx")
    print(f"   3. Refine your literature review: {output_dir}/10_literature_review.md")
    print(f"   4. Use citation sentences in your paper: {output_dir}/11_citation_sentences.md")
    print()


def _generate_empty_report(output_dir: Path, args) -> None:
    """生成空检索报告."""
    lines = ["# 检索结果为空", ""]
    lines.append(f"研究方向: {args.topic}")
    lines.append(f"检索范围: {args.from_year}-{args.to_year}")
    lines.append("")
    lines.append("## 未找到相关文献")
    lines.append("")
    lines.append("可能的原因：")
    lines.append("1. 检索词过于精确，尝试放宽检索条件")
    lines.append("2. 研究方向较新，还没有被 OpenAlex 收录")
    lines.append("3. 网络问题导致 API 请求失败")
    lines.append("4. OpenAlex 礼貌池限流")
    lines.append("")
    lines.append("## 建议")
    lines.append("1. 简化检索词，使用更宽泛的关键词")
    lines.append("2. 手动在 Google Scholar 或知网检索")
    lines.append("3. 检查网络连接和 API 可用性")
    lines.append("4. 减少经典文献数量，增加近年文献检索")
    lines.append("")
    lines.append("> ⚠️ 为避免编造文献，本系统在无法检索到文献时不会生成任何虚假结果。")

    report = "\n".join(lines)
    save_markdown(report, output_dir / "final_report.md")
    print(f"\n⚠️  No papers found. Empty report generated at {output_dir}/final_report.md")
    print("Please check search terms and try again.")


if __name__ == "__main__":
    main()

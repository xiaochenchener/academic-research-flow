"""
测试: 完整 Pipeline 单元测试

测试各个模块的串联运行。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from search_openalex import _normalize_paper, _decode_inverted_index, search_openalex
from deduplicate_papers import deduplicate_papers, _title_similarity, _normalize_title
from rank_papers import rank_papers, _compute_relevance_score, _compute_citation_score, _compute_recency_score
from classify_papers import classify_by_rules, classify_all_papers


def test_normalize_paper():
    """测试 OpenAlex 数据标准化."""
    raw = {
        "title": "Test Paper",
        "publication_year": 2023,
        "doi": "https://doi.org/10.1234/test",
        "authorships": [
            {"author": {"display_name": "Zhang, San"}},
            {"author": {"display_name": "Li, Si"}},
        ],
        "primary_location": {
            "source": {"display_name": "Energy and Buildings"}
        },
        "cited_by_count": 42,
        "id": "https://openalex.org/W12345",
        "abstract_inverted_index": {"this": [0], "is": [1], "test": [2]},
        "concepts": [],
        "referenced_works": [],
    }
    paper = _normalize_paper(raw)
    assert paper["title"] == "Test Paper"
    assert paper["year"] == 2023
    assert paper["doi"] == "10.1234/test"
    assert paper["authors"] == ["Zhang, San", "Li, Si"]
    assert paper["journal"] == "Energy and Buildings"
    assert paper["cited_by_count"] == 42
    assert paper["abstract"] == "this is test"
    print("✅ test_normalize_paper passed")


def test_deduplicate():
    """测试去重."""
    papers = [
        {"title": "Solar greenhouse thermal model", "doi": "10.1234/A", "year": 2023, "source": "OpenAlex",
         "cited_by_count": 10},
        {"title": "Solar greenhouse thermal model", "doi": "10.1234/A", "year": 2023, "source": "Semantic Scholar",
         "cited_by_count": 15},
        {"title": "A different study on greenhouses", "doi": "10.1234/B", "year": 2022, "source": "OpenAlex",
         "cited_by_count": 5},
    ]
    result = deduplicate_papers(papers)
    assert len(result) == 2, f"Expected 2 after dedup, got {len(result)}"
    assert result[0]["cited_by_count"] == 15, "Should keep higher citation count"
    assert "OpenAlex" in result[0]["source"] and "Semantic Scholar" in result[0]["source"]
    print("✅ test_deduplicate passed")


def test_title_similarity():
    """测试标题相似度."""
    sim = _title_similarity(
        "A study on solar greenhouse thermal environment",
        "a study on solar greenhouse thermal environment",
    )
    assert sim > 0.9, f"Expected >0.9, got {sim}"

    sim2 = _title_similarity(
        "Solar greenhouse thermal model",
        "Greenhouse gas emission analysis",
    )
    assert sim2 < 0.6, f"Expected <0.6, got {sim2}"
    print("✅ test_title_similarity passed")


def test_ranking():
    """测试排序评分."""
    papers = [
        {
            "title": "Paper 1",
            "year": 2024,
            "cited_by_count": 200,
            "doi": "10.1234/A",
            "crossref_verified": True,
            "abstract": "solar greenhouse thermal model",
        },
        {
            "title": "Paper 2",
            "year": 2015,
            "cited_by_count": 2,
            "doi": "",
            "crossref_verified": False,
            "abstract": "greenhouse gas climate change",
        },
    ]
    ranked = rank_papers(papers, keywords=["solar greenhouse", "thermal model"])
    assert len(ranked) == 2
    assert ranked[0]["total_score"] > ranked[1]["total_score"], "Paper 1 should rank higher"
    print(f"Paper 1 score: {ranked[0]['total_score']:.3f}")
    print(f"Paper 2 score: {ranked[1]['total_score']:.3f}")
    print("✅ test_ranking passed")


def test_classification_rules():
    """测试规则分类."""
    paper = {
        "title": "A review of solar greenhouse thermal modeling",
        "year": 2020,
        "cited_by_count": 80,
        "abstract": "This review summarizes recent progress in solar greenhouse "
                    "thermal modeling...",
    }
    result = classify_by_rules(paper)
    print(f"Category: {result['rule_category']}")
    print(f"Reasons: {result['rule_reasons']}")

    # 噪音测试
    noise_paper = {
        "title": "Greenhouse gas emissions from agriculture",
        "year": 2021,
        "cited_by_count": 200,
        "abstract": "We analyze greenhouse gas emissions and their impact on climate change...",
    }
    noise_result = classify_by_rules(noise_paper)
    assert noise_result["rule_category"] == "噪音文献", f"Expected 噪音文献, got {noise_result['rule_category']}"
    print("✅ test_classification_rules passed")


def test_search_with_concept_filter():
    """测试带 concept filter 的搜索 (仅检查参数构建)."""
    # 验证 concept filter 函数存在且返回正确的 filter 格式
    from search_openalex import _build_noise_concept_filters
    filters = _build_noise_concept_filters()
    assert len(filters) > 0, "Should have noise concept filters configured"
    for f in filters:
        assert f.startswith("concepts.id:!"), f"Expected concepts.id:! prefix, got: {f}"
    print(f"✅ test_search_with_concept_filter passed ({len(filters)} noise concepts)")


def test_weighted_relevance():
    """测试加权关键词相关性评分."""
    # 高相关论文 (标题和摘要都命中核心关键词)
    high_rel = {
        "title": "Dynamic thermal model for Chinese solar greenhouse",
        "abstract": "This study develops a CFD-based dynamic thermal model for "
                    "Chinese solar greenhouse in cold regions.",
    }
    # 低相关论文 (只有场景词命中)
    low_rel = {
        "title": "Energy consumption in cold region buildings",
        "abstract": "We analyze heating energy consumption patterns in cold region "
                    "residential buildings.",
    }
    keywords = ["solar greenhouse", "thermal model", "CFD", "cold region"]
    kw_weights = {
        "research_object": 3.0,
        "research_method": 2.0,
        "application_scenario": 1.5,
        "innovation_point": 1.0,
    }

    score_high = _compute_relevance_score(high_rel, keywords, kw_weights)
    score_low = _compute_relevance_score(low_rel, keywords, kw_weights)
    print(f"High relevance score: {score_high:.3f}")
    print(f"Low relevance score: {score_low:.3f}")
    assert score_high > score_low, "High relevance paper should score higher"
    print("✅ test_weighted_relevance passed")


if __name__ == "__main__":
    test_normalize_paper()
    test_deduplicate()
    test_title_similarity()
    test_ranking()
    test_classification_rules()
    test_search_with_concept_filter()
    test_weighted_relevance()
    print("\n🎉 All pipeline tests passed!")

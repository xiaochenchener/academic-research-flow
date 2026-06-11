"""
测试: DeepSeek API 模块

注意: 需要在 .env 中配置 DEEPSEEK_API_KEY 才能运行这些测试。
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from deepseek_client import (
    deepseek_chat,
    analyze_topic,
    classify_paper_with_deepseek,
    extract_research_gap,
)


def check_api_key():
    """检查 API Key 是否配置."""
    from config_loader import get_config
    config = get_config()
    key = config.get("deepseek_api_key", "")
    if not key or key == "your_api_key_here":
        print("⚠️  DEEPSEEK_API_KEY not configured. Skipping DeepSeek tests.")
        print("   Set DEEPSEEK_API_KEY in .env file to run these tests.")
        return False
    return True


def test_chat():
    """测试基本对话."""
    response = deepseek_chat(
        "Say 'hello' in exactly one word.",
        max_tokens=10,
        temperature=0.0,
    )
    print(f"Chat response: {response.strip()}")
    assert len(response) > 0
    print("✅ test_chat passed")


def test_analyze_topic():
    """测试选题分析."""
    result = analyze_topic("寒冷地区双层日光温室热湿环境动态模型")
    print(f"Research object: {result.get('research_object', 'N/A')}")
    print(f"Research method: {result.get('research_method', 'N/A')}")
    print(f"Innovation points: {result.get('possible_innovation_points', [])}")
    print(f"Search terms: {result.get('recommended_search_terms', {})}")

    assert "research_object" in result
    assert "research_method" in result
    print("✅ test_analyze_topic passed")


def test_classify_paper():
    """测试文献分类."""
    paper = {
        "title": "Dynamic thermal model for a solar greenhouse with phase change material",
        "year": 2023,
        "abstract": "This study develops a dynamic thermal model for predicting "
                    "the internal temperature of a solar greenhouse equipped with "
                    "phase change material walls. The model considers solar radiation, "
                    "convection, and thermal storage...",
        "cited_by_count": 15,
    }
    result = classify_paper_with_deepseek(paper, "双层日光温室热湿环境")
    print(f"Category: {result.get('category', 'N/A')}")
    print(f"Reason: {result.get('reason', 'N/A')}")
    print(f"Relevance: {result.get('relevance_level', 'N/A')}")

    assert "category" in result
    print("✅ test_classify_paper passed")


def test_extract_gap():
    """测试研究空白提取."""
    papers = [
        {
            "title": "Review of greenhouse thermal modeling",
            "year": 2022,
            "abstract": "This review summarizes the current state of greenhouse "
                        "thermal modeling. Most models focus on single-layer structures "
                        "and steady-state conditions. Dynamic models with moisture "
                        "transport are rare.",
        },
        {
            "title": "CFD simulation of greenhouse climate",
            "year": 2023,
            "abstract": "A CFD model was developed for greenhouse climate simulation. "
                        "The model includes temperature, humidity, and CO2 distribution. "
                        "Limitations include simplified boundary conditions for cold regions.",
        },
    ]
    result = extract_research_gap(papers, "日光温室热湿环境")
    print(f"Research gap analysis:\n{result[:500]}...")
    assert len(result) > 0
    print("✅ test_extract_gap passed")


if __name__ == "__main__":
    if not check_api_key():
        sys.exit(0)

    test_chat()
    test_analyze_topic()
    test_classify_paper()
    test_extract_gap()
    print("\n🎉 All DeepSeek tests passed!")

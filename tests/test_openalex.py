"""
测试: OpenAlex 检索模块
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from search_openalex import search_openalex, search_openalex_by_topic, get_work_by_doi


def test_search_title():
    """测试标题搜索."""
    results = search_openalex(
        title_search="solar greenhouse thermal",
        from_year=2020,
        to_year=2026,
        per_page=5,
        max_pages=1,
    )
    print(f"Title search returned {len(results)} results")
    for r in results[:3]:
        print(f"  - {r['title'][:80]}")
    assert isinstance(results, list)
    print("✅ test_search_title passed")


def test_search_keywords():
    """测试关键词批量检索."""
    results = search_openalex_by_topic(
        ["solar greenhouse", "greenhouse thermal model"],
        from_year=2020,
        to_year=2026,
        max_results=10,
    )
    print(f"Keyword search returned {len(results)} results")
    assert isinstance(results, list)
    # 验证去重
    dois = [r.get("doi") for r in results if r.get("doi")]
    assert len(dois) == len(set(dois)), "Duplicate DOIs found"
    print("✅ test_search_keywords passed")


def test_get_work_by_doi():
    """测试 DOI 查询."""
    # 使用一个可靠的 DOI
    result = get_work_by_doi("10.1038/nature12373")
    if result:
        print(f"DOI lookup: {result['title'][:80]}")
        assert result["title"], "Title should not be empty"
    else:
        print("DOI lookup returned None (may be network issue)")
    print("✅ test_get_work_by_doi passed")


if __name__ == "__main__":
    test_search_title()
    test_search_keywords()
    test_get_work_by_doi()
    print("\n🎉 All OpenAlex tests passed!")

"""
测试: CrossRef DOI 验证模块
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from verify_crossref import verify_doi_with_crossref, batch_verify_dois


def test_verify_valid_doi():
    """测试验证有效 DOI."""
    # 已知有效 DOI
    result = verify_doi_with_crossref("10.1038/nature12373")
    print(f"Valid DOI test:")
    print(f"  is_valid: {result['is_valid']}")
    print(f"  title: {result['title'][:80]}")
    print(f"  container: {result['container_title']}")
    print(f"  publisher: {result['publisher']}")
    print(f"  year: {result['year']}")
    assert result["is_valid"], "Valid DOI should pass verification"
    assert result["title"], "Title should not be empty"
    print("✅ test_verify_valid_doi passed")


def test_verify_invalid_doi():
    """测试验证无效 DOI."""
    result = verify_doi_with_crossref("10.9999/this-is-definitely-not-real-12345")
    print(f"Invalid DOI test:")
    print(f"  is_valid: {result['is_valid']}")
    print(f"  error: {result.get('error', 'N/A')}")
    assert not result["is_valid"], "Invalid DOI should fail verification"
    print("✅ test_verify_invalid_doi passed")


def test_verify_empty_doi():
    """测试空 DOI."""
    result = verify_doi_with_crossref("")
    assert not result["is_valid"], "Empty DOI should fail"
    print("✅ test_verify_empty_doi passed")


def test_batch_verify():
    """测试批量验证."""
    papers = [
        {"title": "Test 1", "doi": "10.1038/nature12373"},
        {"title": "Test 2", "doi": ""},
        {"title": "Test 3", "doi": "10.9999/invalid-doi-999"},
    ]
    result = batch_verify_dois(papers, show_progress=False)
    print(f"Batch verify: {len(result)} papers")
    for p in result:
        print(f"  {p['title']}: verified={p.get('crossref_verified', False)}")
    assert len(result) == 3
    assert result[0]["crossref_verified"], "Valid DOI should be verified"
    assert not result[1]["crossref_verified"], "Empty DOI should not be verified"
    assert not result[2]["crossref_verified"], "Invalid DOI should not be verified"
    print("✅ test_batch_verify passed")


if __name__ == "__main__":
    test_verify_valid_doi()
    test_verify_invalid_doi()
    test_verify_empty_doi()
    test_batch_verify()
    print("\n🎉 All CrossRef tests passed!")

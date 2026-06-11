"""
CrossRef DOI 验证模块

功能:
- 根据 DOI 验证论文是否真实存在
- 补充期刊、年份、作者、出版社信息
- 标记 DOI 无效或无法访问的文献
- 避免幻觉引用
"""

import time
import logging
from typing import Optional

import requests

from config_loader import get_config

logger = logging.getLogger(__name__)

BASE_URL = "https://api.crossref.org"


def _normalize_doi(doi: str) -> str:
    """规范化 DOI 格式."""
    if not doi:
        return ""
    doi = doi.strip()
    # 去除 URL 前缀
    for prefix in ["https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/"]:
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
            break
    return doi


def verify_doi_with_crossref(doi: str) -> dict:
    """
    通过 CrossRef API 验证 DOI.

    Args:
        doi: DOI 字符串

    Returns:
        验证结果字典
    """
    clean_doi = _normalize_doi(doi)

    if not clean_doi:
        return {
            "doi": doi,
            "is_valid": False,
            "error": "Empty or invalid DOI format",
            "title": "",
            "container_title": "",
            "publisher": "",
            "year": None,
            "authors": [],
            "crossref_url": "",
        }

    url = f"{BASE_URL}/works/{clean_doi}"

    config = get_config()
    rate_limit_sleep = config.get("crossref_rate_limit_sleep", 0.2)

    try:
        resp = requests.get(url, timeout=15)
        time.sleep(rate_limit_sleep)
    except requests.exceptions.RequestException as e:
        logger.warning(f"CrossRef request failed for DOI {clean_doi}: {e}")
        return {
            "doi": clean_doi,
            "is_valid": False,
            "error": str(e),
            "title": "",
            "container_title": "",
            "publisher": "",
            "year": None,
            "authors": [],
            "crossref_url": "",
        }

    if resp.status_code == 404:
        return {
            "doi": clean_doi,
            "is_valid": False,
            "error": "DOI not found in CrossRef",
            "title": "",
            "container_title": "",
            "publisher": "",
            "year": None,
            "authors": [],
            "crossref_url": "",
        }

    if resp.status_code != 200:
        return {
            "doi": clean_doi,
            "is_valid": False,
            "error": f"CrossRef returned status {resp.status_code}",
            "title": "",
            "container_title": "",
            "publisher": "",
            "year": None,
            "authors": [],
            "crossref_url": "",
        }

    data = resp.json().get("message", {})

    # 提取作者
    authors = []
    for a in data.get("author", []):
        given = a.get("given", "")
        family = a.get("family", "")
        if family:
            authors.append(f"{family}, {given}" if given else family)

    # 提取期刊
    container = data.get("container-title", [])
    container_title = container[0] if container else ""

    # 提取年份
    year = None
    pub_date = data.get("published-print", {}) or data.get("published-online", {})
    date_parts = pub_date.get("date-parts", [[]])
    if date_parts and date_parts[0]:
        year = date_parts[0][0]

    return {
        "doi": clean_doi,
        "is_valid": True,
        "title": data.get("title", [""])[0] if data.get("title") else "",
        "container_title": container_title,
        "publisher": data.get("publisher", ""),
        "year": year,
        "authors": authors,
        "crossref_url": f"https://doi.org/{clean_doi}",
        "type": data.get("type", ""),
        "is_referenced_by_count": data.get("is-referenced-by-count", 0),
    }


def batch_verify_dois(papers: list[dict], show_progress: bool = True) -> list[dict]:
    """
    批量验证文献 DOI.

    Args:
        papers: 文献列表
        show_progress: 是否显示进度

    Returns:
        添加了验证信息的文献列表
    """
    from tqdm import tqdm

    iterator = tqdm(papers, desc="Verifying DOIs") if show_progress else papers

    for paper in iterator:
        doi = paper.get("doi", "")
        if doi:
            verification = verify_doi_with_crossref(doi)
            paper["crossref_verified"] = verification["is_valid"]
            paper["crossref_data"] = verification
            # 补充元数据
            if verification["is_valid"]:
                if verification["title"] and not paper.get("title"):
                    paper["title"] = verification["title"]
                if verification["year"] and not paper.get("year"):
                    paper["year"] = verification["year"]
                if verification["authors"] and not paper.get("authors"):
                    paper["authors"] = verification["authors"]
                if verification["container_title"] and not paper.get("journal"):
                    paper["journal"] = verification["container_title"]
                paper["publisher"] = verification.get("publisher", "")
        else:
            paper["crossref_verified"] = False
            paper["crossref_data"] = {
                "doi": "",
                "is_valid": False,
                "error": "No DOI provided",
            }

    verified_count = sum(1 for p in papers if p.get("crossref_verified"))
    logger.info(f"DOI verification complete: {verified_count}/{len(papers)} valid")
    return papers


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # 测试
    result = verify_doi_with_crossref("10.1016/j.enbuild.2020.109876")
    print(result)

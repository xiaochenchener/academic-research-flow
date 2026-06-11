"""
期刊信息补充模块 (easyScholar API)

功能:
- 通过 easyScholar 开放 API 查询期刊影响因子、中科院分区、SCI分区
- 本地缓存避免重复查询
- 限流控制
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests

from config_loader import get_config

logger = logging.getLogger(__name__)


class JournalInfoCache:
    """期刊信息本地缓存."""

    def __init__(self, cache_file: Path):
        self.cache_file = cache_file
        self._cache: dict[str, dict] = {}
        self._load()

    def _load(self):
        """加载缓存文件."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
                logger.info(f"Loaded {len(self._cache)} journal cache entries")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load journal cache: {e}")
                self._cache = {}

    def _save(self):
        """保存缓存到文件."""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.warning(f"Failed to save journal cache: {e}")

    def get(self, journal_name: str) -> Optional[dict]:
        """从缓存中获取期刊信息."""
        key = journal_name.strip().lower()
        return self._cache.get(key)

    def set(self, journal_name: str, info: dict):
        """写入缓存."""
        key = journal_name.strip().lower()
        self._cache[key] = info
        self._save()

    def has(self, journal_name: str) -> bool:
        """检查缓存是否存在."""
        key = journal_name.strip().lower()
        return key in self._cache


def query_journal_info(journal_name: str, secret_key: str, cache: JournalInfoCache = None) -> dict:
    """
    查询单个期刊的影响因子等信息.

    Args:
        journal_name: 期刊名称
        secret_key: easyScholar API secretKey
        cache: 缓存实例 (可选)

    Returns:
        期刊信息字典, 包含:
        - impact_factor: 影响因子
        - sci_zone: SCI 分区 (Q1-Q4)
        - cas_zone: 中科院分区
        - journal_name: 期刊名称
        - success: 是否成功
    """
    if not journal_name or not secret_key:
        return {"success": False, "journal_name": journal_name, "error": "Missing journal name or secret key"}

    # 检查缓存
    if cache and cache.has(journal_name):
        cached = cache.get(journal_name)
        if cached:
            return cached

    config = get_config()
    base_url = config.get("easyscholar_base_url", "https://www.easyscholar.cc/open/getPublicationInfo")
    rate_limit_sleep = config.get("easyscholar_rate_limit_sleep", 1.0)

    try:
        url = f"{base_url}?secretKey={secret_key}&publicationName={quote(journal_name)}"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        # 构建标准化结果
        result = {
            "success": True,
            "journal_name": journal_name,
            "impact_factor": data.get("impactFactor", ""),
            "impact_factor_year": data.get("impactFactorYear", ""),
            "sci_zone": data.get("sciZone", ""),
            "cas_zone": data.get("casZone", ""),
            "cas_zone_name": data.get("casZoneName", ""),
            "jcr_zone": data.get("jcrZone", ""),
            "esi_hot": data.get("esiHot", False),
            "esi_highly_cited": data.get("esiHighlyCited", False),
            "raw": data,
        }

        # 写入缓存
        if cache:
            cache.set(journal_name, result)

        return result

    except requests.exceptions.RequestException as e:
        logger.warning(f"Failed to query journal '{journal_name}': {e}")
        result = {"success": False, "journal_name": journal_name, "error": str(e)}
        # 失败也缓存 (避免重复请求)
        if cache:
            cache.set(journal_name, result)
        return result


def batch_enrich_journals(
    papers: list[dict],
    secret_key: str = "",
    show_progress: bool = True,
) -> list[dict]:
    """
    批量为文献补充期刊影响因子信息.

    Args:
        papers: 文献列表
        secret_key: easyScholar API secretKey
        show_progress: 是否显示进度

    Returns:
        补充了期刊信息的文献列表
    """
    if not secret_key:
        secret_key = get_config().get("easyscholar_secret_key", "")
    if not secret_key:
        logger.warning("No easyScholar secret key configured. Skipping journal enrichment.")
        for p in papers:
            p["journal_info"] = {"success": False, "error": "No secret key"}
        return papers

    config = get_config()
    cache_file = config.get("easyscholar_cache_file", Path("easyscholar_cache.json"))
    rate_limit_sleep = config.get("easyscholar_rate_limit_sleep", 1.0)

    cache = JournalInfoCache(cache_file)

    # 收集所有唯一期刊名称
    unique_journals = set()
    for p in papers:
        j = p.get("journal", "")
        if j:
            unique_journals.add(j)

    logger.info(f"Querying {len(unique_journals)} unique journals via easyScholar...")

    # 查询所有期刊
    journal_info_map = {}
    journals_list = sorted(unique_journals)

    for i, jname in enumerate(journals_list):
        info = query_journal_info(jname, secret_key, cache)
        journal_info_map[jname] = info

        if show_progress and (i + 1) % 10 == 0:
            logger.info(f"  Journal query progress: {i + 1}/{len(journals_list)}")

        time.sleep(rate_limit_sleep)

    # 为每篇文献附上期刊信息
    enriched_count = 0
    for p in papers:
        jname = p.get("journal", "")
        info = journal_info_map.get(jname, {"success": False, "journal_name": jname})
        p["journal_info"] = info
        if info.get("success"):
            enriched_count += 1

    logger.info(f"Journal enrichment complete: {enriched_count}/{len(papers)} papers enriched")
    return papers


def format_journal_info(paper: dict) -> str:
    """
    格式化单篇文献的期刊信息为 Markdown 表格行.

    Args:
        paper: 包含 journal_info 的文献字典

    Returns:
        Markdown 格式的期刊信息字符串
    """
    jinfo = paper.get("journal_info", {})
    if not jinfo or not jinfo.get("success"):
        return ""

    parts = []
    if jinfo.get("impact_factor"):
        parts.append(f"**IF**: {jinfo['impact_factor']} ({jinfo.get('impact_factor_year', '')})".strip())
    if jinfo.get("sci_zone"):
        parts.append(f"**SCI**: {jinfo['sci_zone']}")
    if jinfo.get("cas_zone_name"):
        parts.append(f"**CAS**: {jinfo['cas_zone_name']}")
    if jinfo.get("cas_zone"):
        parts.append(f"({jinfo['cas_zone']})")

    return " | ".join(parts) if parts else ""

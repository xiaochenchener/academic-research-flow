"""
配置加载模块

从 config.yaml 和 .env 加载配置，提供统一接口。
"""

import os
import logging
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 加载 .env
_env_file = PROJECT_ROOT / ".env"
if _env_file.exists():
    load_dotenv(_env_file)
else:
    logger.warning(f".env file not found at {_env_file}, using environment variables only")

# 加载 config.yaml
_config = {}
_config_file = PROJECT_ROOT / "config.yaml"
if _config_file.exists():
    with open(_config_file, "r", encoding="utf-8") as f:
        _config = yaml.safe_load(f) or {}
else:
    logger.warning(f"config.yaml not found at {_config_file}")


def get_config() -> dict[str, Any]:
    """获取合并后的配置 (config.yaml + .env)."""
    merged = {}

    # --- API 配置 ---
    apis = _config.get("apis", {})

    # OpenAlex
    oa = apis.get("openalex", {})
    merged["openalex_base_url"] = oa.get("base_url", "https://api.openalex.org")
    merged["openalex_mailto"] = os.getenv("OPENALEX_MAILTO", "")
    merged["openalex_per_page"] = oa.get("per_page", 200)
    merged["openalex_max_pages"] = oa.get("max_pages", 5)
    merged["openalex_rate_limit_sleep"] = oa.get("rate_limit_sleep", 0.1)

    # CrossRef
    cr = apis.get("crossref", {})
    merged["crossref_base_url"] = cr.get("base_url", "https://api.crossref.org")
    merged["crossref_rate_limit_sleep"] = cr.get("rate_limit_sleep", 0.2)

    # Semantic Scholar
    ss = apis.get("semantic_scholar", {})
    merged["semantic_scholar_base_url"] = ss.get("base_url", "https://api.semanticscholar.org/graph/v1")
    merged["semantic_scholar_rate_limit_sleep"] = ss.get("rate_limit_sleep", 1.0)
    merged["semantic_scholar_max_retries"] = ss.get("max_retries", 3)
    merged["semantic_scholar_api_key"] = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")

    # DeepSeek
    merged["deepseek_api_key"] = os.getenv("DEEPSEEK_API_KEY", "")
    merged["deepseek_base_url"] = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    merged["deepseek_model"] = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    merged["deepseek_max_tokens"] = apis.get("deepseek", {}).get("max_tokens", 4096)
    merged["deepseek_temperature"] = apis.get("deepseek", {}).get("temperature", 0.3)

    # easyScholar
    es = apis.get("easyscholar", {})
    merged["easyscholar_base_url"] = es.get("base_url", "https://www.easyscholar.cc/open/getPublicationInfo")
    merged["easyscholar_secret_key"] = os.getenv("EASYSCHOLAR_SECRET_KEY", "")
    merged["easyscholar_rate_limit_sleep"] = es.get("rate_limit_sleep", 1.0)
    merged["easyscholar_cache_file"] = PROJECT_ROOT / es.get("cache_file", "easyscholar_cache.json")

    # --- 检索配置 ---
    search = _config.get("search", {})
    merged["classic_year_range"] = search.get("classic_year_range", [2000, 2022])
    merged["recent_year_range"] = search.get("recent_year_range", [2023, 2026])
    merged["classic_count"] = search.get("classic_count", 30)
    merged["recent_count"] = search.get("recent_count", 30)
    merged["competition_count"] = search.get("competition_count", 20)
    merged["classic_lookback_years"] = search.get("classic_lookback_years", 20)
    merged["max_search_terms"] = search.get("max_search_terms", 15)
    merged["enable_concept_filter"] = search.get("enable_concept_filter", True)
    merged["enable_snowballing"] = search.get("enable_snowballing", True)
    merged["noise_concept_ids"] = search.get("noise_concept_ids", [])
    merged["tiers"] = search.get("tiers", {})

    # --- 排序权重 ---
    ranking = _config.get("ranking", {})
    merged["relevance_weight"] = ranking.get("relevance_weight", 0.45)
    merged["citation_weight"] = ranking.get("citation_weight", 0.25)
    merged["recency_weight"] = ranking.get("recency_weight", 0.20)
    merged["validity_weight"] = ranking.get("validity_weight", 0.10)
    merged["keyword_type_weights"] = ranking.get("keyword_type_weights", {})

    # --- 输出配置 ---
    output = _config.get("output", {})
    merged["output_base_dir"] = output.get("base_dir", "outputs")

    # --- 去重配置 ---
    dedup = _config.get("dedup", {})
    merged["title_similarity_threshold"] = dedup.get("title_similarity_threshold", 0.85)

    # --- Snowballing 配置 ---
    sb = _config.get("snowballing", {})
    merged["snowball_max_forward"] = sb.get("max_forward_citations", 20)
    merged["snowball_max_backward"] = sb.get("max_backward_citations", 30)
    merged["snowball_top_n_seeds"] = sb.get("top_n_seeds", 10)

    # --- 日志配置 ---
    logging_cfg = _config.get("logging", {})
    merged["log_level"] = logging_cfg.get("level", "INFO")
    merged["log_format"] = logging_cfg.get("format", "%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    return merged


def get_output_dir(topic_slug: str) -> Path:
    """获取某次运行的输出目录."""
    config = get_config()
    base = PROJECT_ROOT / config["output_base_dir"]
    return base / topic_slug

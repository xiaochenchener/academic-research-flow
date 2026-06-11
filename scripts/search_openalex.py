"""
OpenAlex 文献检索模块

功能:
- 支持普通 search (全文检索)
- 支持 display_name.search (标题匹配)
- 支持 concept filter 排除噪音 (避免同名词淹没)
- 支持组合 AND 查询 (多关键词联合检索)
- 支持年份筛选、引用量排序、时间排序
- 支持引用追溯 (snowballing)
- 自动处理空 DOI、限流、分页
- 标准化输出格式
"""

import time
import logging
from typing import Optional
import requests

from config_loader import get_config

logger = logging.getLogger(__name__)

BASE_URL = "https://api.openalex.org"


def _get_mailto() -> Optional[str]:
    """从配置中获取礼貌池邮箱."""
    config = get_config()
    return config.get("openalex_mailto") or None


def _build_headers() -> dict:
    """构建请求头."""
    headers = {}
    mailto = _get_mailto()
    if mailto:
        headers["User-Agent"] = f"AcademicResearchFlow/0.2 (mailto:{mailto})"
    else:
        headers["User-Agent"] = "AcademicResearchFlow/0.2"
    return headers


def _normalize_paper(work: dict) -> dict:
    """将 OpenAlex work 对象标准化为内部格式."""
    # 提取作者
    authors = []
    for a in work.get("authorships", []):
        author = a.get("author", {})
        name = author.get("display_name", "")
        if name:
            authors.append(name)

    # 提取期刊/会议名
    primary_location = work.get("primary_location", {}) or {}
    source = primary_location.get("source", {}) or {}
    journal = source.get("display_name", "")

    # 提取 DOI
    doi = work.get("doi", "")
    if doi:
        doi = doi.replace("https://doi.org/", "")

    # 提取摘要 (OpenAlex 使用 inverted index)
    abstract_inverted = work.get("abstract_inverted_index", {})
    abstract = _decode_inverted_index(abstract_inverted) if abstract_inverted else ""

    # 提取 ISSN
    issn_list = source.get("issn_l", "") or (source.get("issn", []) if source else [])

    # 提取 OpenAlex concepts
    concepts = []
    for c in work.get("concepts", []):
        concepts.append({
            "id": c.get("id", ""),
            "display_name": c.get("display_name", ""),
            "level": c.get("level", 0),
            "score": c.get("score", 0),
        })

    # 提取引用文献列表 (用于 snowballing)
    referenced_works = work.get("referenced_works", [])

    return {
        "title": work.get("title", ""),
        "year": work.get("publication_year"),
        "doi": doi,
        "authors": authors,
        "journal": journal,
        "issn": issn_list,
        "abstract": abstract,
        "cited_by_count": work.get("cited_by_count", 0),
        "openalex_id": work.get("id", ""),
        "url": f"https://doi.org/{doi}" if doi else work.get("id", ""),
        "source": "OpenAlex",
        "publication_date": work.get("publication_date", ""),
        "type": work.get("type", ""),
        "keywords": [k.get("display_name", "") for k in work.get("keywords", [])],
        "concepts": concepts,
        "referenced_works": referenced_works,
        # 保留原始 OpenAlex 数据以备后用
        "_raw_openalex": work,
    }


def _decode_inverted_index(inverted: dict) -> str:
    """解码 OpenAlex 的倒排索引摘要."""
    if not inverted:
        return ""
    positions = {}
    for word, indices in inverted.items():
        for idx in indices:
            positions[idx] = word
    words = [positions[i] for i in sorted(positions.keys())]
    return " ".join(words)


def _build_noise_concept_filters() -> list[str]:
    """构建噪音 concept 排除过滤器列表."""
    config = get_config()
    noise_ids = config.get("noise_concept_ids", [])
    return [f"concepts.id:!{cid}" for cid in noise_ids]


def search_openalex(
    query: str = "",
    title_search: Optional[str] = None,
    from_year: Optional[int] = None,
    to_year: Optional[int] = None,
    per_page: int = 200,
    max_pages: int = 5,
    sort: str = "cited_by_count:desc",
    exclude_noise_concepts: bool = True,
) -> list[dict]:
    """
    搜索 OpenAlex 文献.

    Args:
        query: 全文搜索词 (搜索标题+摘要)。支持 `+` 表示 AND，`|` 表示 OR。
        title_search: 精确标题搜索词 (使用 filter=display_name.search)
        from_year: 起始年份
        to_year: 结束年份
        per_page: 每页条数 (最大 200, 默认 200)
        max_pages: 最大页数
        sort: 排序方式 ('cited_by_count:desc' | 'publication_date:desc' | 'relevance_score:desc')
        exclude_noise_concepts: 是否启用 concept filter 排除噪音

    Returns:
        标准化的文献列表
    """
    config = get_config()
    rate_limit_sleep = config.get("openalex_rate_limit_sleep", 0.1)

    all_papers = []
    cursor = "*"

    for page in range(1, max_pages + 1):
        url = f"{BASE_URL}/works"

        params = {
            "per_page": per_page,
            "sort": sort,
            "cursor": cursor,
        }

        # 构建 filter 字符串
        filters = []

        if title_search:
            filters.append(f"display_name.search:{title_search}")

        if from_year:
            filters.append(f"from_publication_date:{from_year}-01-01")

        if to_year:
            filters.append(f"to_publication_date:{to_year}-12-31")

        # 噪音 concept 过滤
        if exclude_noise_concepts:
            noise_filters = _build_noise_concept_filters()
            filters.extend(noise_filters)

        if filters:
            params["filter"] = ",".join(filters)

        # 全文搜索
        if query and not title_search:
            params["search"] = query

        logger.info(
            f"OpenAlex search page {page}/{max_pages}: "
            f"query='{query}', title_search='{title_search}', "
            f"years={from_year}-{to_year}, "
            f"noise_filter={'on' if exclude_noise_concepts else 'off'}"
        )

        try:
            resp = requests.get(url, params=params, headers=_build_headers(), timeout=30)
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenAlex request failed (page {page}): {e}")
            break

        data = resp.json()

        results = data.get("results", [])
        if not results:
            logger.info(f"No more results on page {page}")
            break

        for work in results:
            paper = _normalize_paper(work)
            all_papers.append(paper)

        # 获取下一页 cursor
        meta = data.get("meta", {})
        cursor = meta.get("next_cursor")
        if not cursor:
            logger.info("No more cursors, search complete")
            break

        time.sleep(rate_limit_sleep)

    logger.info(f"OpenAlex search returned {len(all_papers)} papers")
    return all_papers


def search_with_and_combination(
    object_terms: list[str],
    method_terms: list[str],
    scene_terms: list[str] = None,
    from_year: Optional[int] = None,
    to_year: Optional[int] = None,
    per_page: int = 200,
    max_results: int = 100,
    sort: str = "cited_by_count:desc",
) -> list[dict]:
    """
    使用 AND 组合查询: 研究对象词 + 方法词用 `+` 连接，减少噪音。

    对每组 (研究对象 × 方法) 组合构建 AND 查询，同时保留独立 OR 查询兜底。

    Args:
        object_terms: 研究对象关键词
        method_terms: 研究方法关键词
        scene_terms: 应用场景关键词 (可选)
        from_year: 起始年份
        to_year: 结束年份
        per_page: 每页条数
        max_results: 每组最大结果数
        sort: 排序方式

    Returns:
        标准化的文献列表
    """
    all_papers = []
    per_query = max(max_results // max(len(object_terms), 1), 20)

    # 组合 AND 查询: object_term + method_term
    for obj_term in object_terms[:5]:  # 限制组合数
        for method_term in method_terms[:3]:
            and_query = f"{obj_term} + {method_term}"
            papers = search_openalex(
                query=and_query,
                title_search=None,
                from_year=from_year,
                to_year=to_year,
                per_page=per_page,
                max_pages=max(per_query // per_page, 1),
                sort=sort,
            )
            all_papers.extend(papers)
            logger.info(f"AND query '{and_query}': {len(papers)} results")

    # 兜底: 单独 title_search 每个对象词
    for obj_term in object_terms[:5]:
        papers = search_openalex(
            query="",
            title_search=obj_term.lower(),
            from_year=from_year,
            to_year=to_year,
            per_page=per_page,
            max_pages=1,
            sort=sort,
        )
        all_papers.extend(papers)

    # 简单去重 (基于 openalex_id)
    seen = set()
    unique = []
    for p in all_papers:
        oid = p.get("openalex_id", "")
        doi = p.get("doi", "")
        key = oid or doi or p.get("title", "")
        if key and key not in seen:
            seen.add(key)
            unique.append(p)

    logger.info(f"AND combination search: {len(unique)} unique papers (from {len(all_papers)} raw)")
    return unique


def search_openalex_by_topic(
    topic_keywords: list[str],
    from_year: int,
    to_year: int,
    max_results: int = 100,
    sort: str = "cited_by_count:desc",
    keyword_weights: dict[str, float] = None,
) -> list[dict]:
    """
    按主题关键词批量检索。

    优先使用 AND 组合查询减少噪音，独立关键词查询作为补充。

    Args:
        topic_keywords: 关键词列表 (English)，按优先级排序
        from_year: 起始年份
        to_year: 结束年份
        max_results: 最大结果数
        sort: 排序方式
        keyword_weights: 关键词权重字典 (可选，用于后续排序)

    Returns:
        去重后的文献列表
    """
    config = get_config()
    per_page = config.get("openalex_per_page", 200)

    all_papers = []
    per_query = min(max_results // max(len(topic_keywords), 1), 100)
    max_pages = max(per_query // per_page, 1)

    for kw in topic_keywords:
        # 先尝试 title_search (精确标题匹配)
        papers = search_openalex(
            query="",
            title_search=kw.lower(),
            from_year=from_year,
            to_year=to_year,
            per_page=per_page,
            max_pages=max_pages,
            sort=sort,
        )

        # 如果 title_search 结果太少，用全文 AND search 补充
        if len(papers) < 10:
            extra = search_openalex(
                query=kw,
                title_search=None,
                from_year=from_year,
                to_year=to_year,
                per_page=per_page,
                max_pages=1,
                sort=sort,
            )
            papers.extend(extra)

        all_papers.extend(papers)
        logger.info(f"Keyword '{kw}': {len(papers)} results")

    # 简单去重 (基于 openalex_id)
    seen = set()
    unique = []
    for p in all_papers:
        oid = p.get("openalex_id", "")
        doi = p.get("doi", "")
        key = oid or doi or p.get("title", "")
        if key and key not in seen:
            seen.add(key)
            unique.append(p)

    logger.info(f"Total unique papers: {len(unique)} (from {len(all_papers)} raw)")
    return unique


def get_work_by_doi(doi: str) -> Optional[dict]:
    """根据 DOI 获取单篇文献信息."""
    clean_doi = doi.replace("https://doi.org/", "")
    url = f"{BASE_URL}/works/https://doi.org/{clean_doi}"

    try:
        resp = requests.get(url, headers=_build_headers(), timeout=15)
        resp.raise_for_status()
        return _normalize_paper(resp.json())
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get work by DOI {doi}: {e}")
        return None


def snowball_search(
    seed_papers: list[dict],
    direction: str = "both",
    max_forward: int = 20,
    max_backward: int = 30,
) -> list[dict]:
    """
    引用追溯 (snowballing): 基于种子文献查找引用和被引文献。

    Args:
        seed_papers: 种子文献列表 (通常为 Top N 排序结果)
        direction: 追溯方向 ('forward' | 'backward' | 'both')
        max_forward: 前向引用最大检索数 (引用种子文献的文献)
        max_backward: 后向引用最大检索数 (种子文献引用的文献)

    Returns:
        新发现的文献列表
    """
    config = get_config()
    rate_limit_sleep = config.get("openalex_rate_limit_sleep", 0.1)

    discovered = []
    seen_dois = set()
    seen_ids = set()

    # 记录种子文献以避免重复
    for p in seed_papers:
        if p.get("doi"):
            seen_dois.add(p["doi"].lower())
        if p.get("openalex_id"):
            seen_ids.add(p["openalex_id"])

    for seed in seed_papers:
        seed_doi = seed.get("doi", "")
        seed_id = seed.get("openalex_id", "")

        # ---- Backward: 种子文献引用的文献 ----
        if direction in ("backward", "both"):
            referenced = seed.get("referenced_works", [])
            if referenced:
                logger.info(f"  Snowball backward: seed '{seed.get('title', '')[:50]}' "
                           f"has {len(referenced)} references")

            for ref_id in referenced[:max_backward]:
                if ref_id in seen_ids:
                    continue
                seen_ids.add(ref_id)

                try:
                    resp = requests.get(ref_id, headers=_build_headers(), timeout=15)
                    resp.raise_for_status()
                    paper = _normalize_paper(resp.json())

                    doi = paper.get("doi", "").lower()
                    if doi and doi in seen_dois:
                        continue
                    if doi:
                        seen_dois.add(doi)

                    paper["source"] = "Snowball (backward)"
                    paper["snowball_seed"] = seed.get("title", "")[:60]
                    discovered.append(paper)
                except requests.exceptions.RequestException as e:
                    logger.warning(f"  Failed to fetch reference {ref_id}: {e}")

                time.sleep(rate_limit_sleep)

        # ---- Forward: 引用种子文献的文献 ----
        if direction in ("forward", "both") and seed_doi:
            try:
                cited_by_url = f"{BASE_URL}/works"
                params = {
                    "filter": f"cites:https://doi.org/{seed_doi}",
                    "per_page": min(max_forward, 200),
                    "sort": "cited_by_count:desc",
                }
                resp = requests.get(cited_by_url, params=params, headers=_build_headers(), timeout=30)
                resp.raise_for_status()
                data = resp.json()

                forward_count = 0
                for work in data.get("results", []):
                    paper = _normalize_paper(work)
                    doi = paper.get("doi", "").lower()
                    if doi and doi in seen_dois:
                        continue
                    oid = paper.get("openalex_id", "")
                    if oid in seen_ids:
                        continue

                    if doi:
                        seen_dois.add(doi)
                    seen_ids.add(oid)
                    paper["source"] = "Snowball (forward)"
                    paper["snowball_seed"] = seed.get("title", "")[:60]
                    discovered.append(paper)
                    forward_count += 1

                logger.info(f"  Snowball forward: seed '{seed.get('title', '')[:50]}' "
                           f"→ {forward_count} citing papers")
            except requests.exceptions.RequestException as e:
                logger.warning(f"  Failed forward snowball for {seed_doi}: {e}")

            time.sleep(rate_limit_sleep)

    logger.info(f"Snowballing complete: {len(discovered)} new papers discovered")
    return discovered


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # 测试基本检索
    results = search_openalex(
        title_search="solar greenhouse thermal",
        from_year=2020,
        to_year=2026,
    )
    for r in results[:3]:
        print(f"\n{r['title']}")
        print(f"  DOI: {r['doi']}")
        print(f"  Year: {r['year']}")
        print(f"  Citations: {r['cited_by_count']}")

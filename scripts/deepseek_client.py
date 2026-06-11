"""
DeepSeek API 客户端模块

功能:
- 通用 chat completion 调用
- 文献分类
- 研究贡献提取
- 研究空白分析
- 文献综述生成
- 引用句生成
"""

import json
import logging
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from config_loader import get_config

logger = logging.getLogger(__name__)


def _get_api_config() -> dict:
    """获取 DeepSeek API 配置."""
    cfg = get_config()
    return {
        "api_key": cfg.get("deepseek_api_key", ""),
        "base_url": cfg.get("deepseek_base_url", "https://api.deepseek.com"),
        "model": cfg.get("deepseek_model", "deepseek-chat"),
        "max_tokens": cfg.get("deepseek_max_tokens", 4096),
        "temperature": cfg.get("deepseek_temperature", 0.3),
    }


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
)
def deepseek_chat(
    prompt: str,
    system_prompt: str = "",
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> str:
    """
    调用 DeepSeek Chat API.

    Args:
        prompt: 用户提示词
        system_prompt: 系统提示词
        temperature: 温度参数 (默认使用配置值)
        max_tokens: 最大 token 数 (默认使用配置值)

    Returns:
        DeepSeek 的回复文本
    """
    config = _get_api_config()

    if not config["api_key"]:
        raise ValueError("DEEPSEEK_API_KEY not set. Please configure in .env file.")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": config["model"],
        "messages": messages,
        "max_tokens": max_tokens or config["max_tokens"],
        "temperature": temperature if temperature is not None else config["temperature"],
    }

    url = f"{config['base_url']}/v1/chat/completions"

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"DeepSeek API request failed: {e}")
        if resp is not None and hasattr(resp, "text"):
            logger.error(f"Response body: {resp.text[:500]}")
        raise

    data = resp.json()
    message = data["choices"][0]["message"]
    content = message.get("content") or ""
    reasoning = message.get("reasoning_content") or ""

    # deepseek-reasoner 模型会把 token 花在推理过程上，导致 content 为空
    # 此时退而求其次返回 reasoning_content
    if not content.strip() and reasoning:
        logger.warning("content is empty, falling back to reasoning_content")
        return reasoning

    return content


def _extract_json_from_response(text: str) -> Optional[dict]:
    """从 DeepSeek 回复中提取 JSON."""
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 代码块
    import re
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试提取 { ... } 块
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    logger.warning("Could not extract JSON from DeepSeek response")
    return None


def analyze_topic(topic: str, innovation: str = "") -> dict:
    """
    选题分析: 分析研究对象、方法、创新点、关键词歧义风险.

    Args:
        topic: 研究方向
        innovation: 初步创新点 (可选)

    Returns:
        选题分析结果字典
    """
    system_prompt = (
        "你是一位资深学术研究顾问，专长于理工科论文选题分析。"
        "请用 JSON 格式输出分析结果。不编造任何文献信息。"
    )

    prompt = f"""请分析以下研究方向：

研究方向：{topic}
{('初步创新点：' + innovation) if innovation else ''}

请输出 JSON 格式，包含以下字段：
{{
    "research_topic": "完整的研究课题名称",
    "research_object": "研究对象（具体的物理系统、结构、材料等）",
    "research_method": "研究方法（模型、实验、模拟等）",
    "application_scenario": "应用场景和边界条件",
    "possible_innovation_points": ["创新点1", "创新点2"],
    "main_disciplines": ["主学科1", "主学科2"],
    "related_subfields": ["子领域1", "子领域2"],
    "risk_of_keyword_ambiguity": [
        {{
            "keyword": "关键词",
            "ambiguity": "可能与哪些其他领域混淆",
            "disambiguation_strategy": "如何消除歧义"
        }}
    ],
    "recommended_search_terms": {{
        "english": ["term1", "term2"],
        "chinese": ["术语1", "术语2"]
    }},
    "classic_literature_leads": ["经典文献方向1"],
    "novelty_assessment_notes": "对创新性的初步评估"
}}

只输出 JSON，不要有其他文字。"""

    response = deepseek_chat(prompt, system_prompt=system_prompt)
    result = _extract_json_from_response(response)

    if not result:
        logger.warning("Failed to parse topic analysis, returning raw text")
        return {"error": "JSON parse failed", "raw_response": response}

    return result


def generate_keyword_matrix(topic: str, topic_analysis: dict = None) -> dict:
    """
    生成关键词矩阵和检索式.

    Args:
        topic: 研究方向
        topic_analysis: 选题分析结果 (可选)

    Returns:
        关键词矩阵字典
    """
    system_prompt = (
        "你是学术文献检索专家，擅长从研究方向中提取和扩展检索关键词。"
        "请用 JSON 格式输出。不编造任何文献。"
    )

    context = f"研究方向：{topic}\n"
    if topic_analysis:
        context += f"选题分析：{json.dumps(topic_analysis, ensure_ascii=False)}"

    prompt = f"""{context}

请生成关键词矩阵和检索式。输出 JSON：

{{
    "keyword_matrix": [
        {{"type": "研究对象", "chinese": "", "english": "", "purpose": "", "priority": "高"}},
        ...
    ],
    "classic_search_queries": [
        {{"query": "title search term", "search_type": "title", "purpose": "检索经典高被引文献"}}
    ],
    "recent_search_queries": [
        {{"query": "title search term", "search_type": "title", "purpose": "检索近年最新文献"}}
    ],
    "competition_search_queries": [
        {{"query": "title search term", "search_type": "title", "purpose": "检索直接竞争文献"}}
    ],
    "support_search_queries": [
        {{"query": "title search term", "search_type": "title", "purpose": "检索可引用支撑文献"}}
    ],
    "exclusion_terms": ["需要排除的歧义词"]
}}

注意：
1. 英文关键词优先使用领域标准术语
2. greenhouse 类词要特别标注排除 greenhouse gas/effect
3. 检索式中的空格用 + 连接
4. 只输出 JSON"""

    response = deepseek_chat(prompt, system_prompt=system_prompt)
    result = _extract_json_from_response(response)

    if not result:
        return {"error": "JSON parse failed", "raw_response": response}

    return result


def classify_paper_with_deepseek(paper: dict, topic: str) -> dict:
    """
    用 DeepSeek 对单篇文献进行分类.

    Args:
        paper: 文献信息
        topic: 用户研究方向

    Returns:
        分类结果
    """
    system_prompt = (
        "你是学术文献分类专家。请根据文献的标题、摘要和研究内容，"
        "将其准确分类。只输出 JSON，不编造任何信息。"
    )

    prompt = f"""用户研究方向：{topic}

文献信息：
- 标题：{paper.get('title', 'N/A')}
- 年份：{paper.get('year', 'N/A')}
- 期刊：{paper.get('journal', 'N/A')}
- 摘要：{(paper.get('abstract') or 'N/A')[:1500]}
- TLDR：{paper.get('tldr', 'N/A')}
- 被引次数：{paper.get('cited_by_count', 0)}

请将该文献分入以下类别之一：
1. 直接竞争文献 — 研究问题、方法、场景与用户高度重合
2. 可引用支撑文献 — 可用于支撑用户论文的论点或方法
3. 经典基础文献 — 领域奠基性工作，高被引
4. 近年前沿文献 — 近3年发表的最新进展
5. 方法模型文献 — 提供方法论参考
6. 工程应用文献 — 侧重工程应用和案例
7. 背景政策文献 — 政策、标准、综述类
8. 噪音文献 — 不相关，应排除

输出 JSON：
{{
    "category": "分类名称",
    "reason": "分类理由（2-3句话）",
    "can_be_cited_for": "可用于支撑什么论点",
    "relevance_level": "high/medium/low",
    "risk_level": "safe/caution/exclude"
}}"""

    response = deepseek_chat(prompt, system_prompt=system_prompt, max_tokens=1024)
    result = _extract_json_from_response(response)

    if not result:
        return {
            "category": "需人工判断",
            "reason": "DeepSeek 分类失败",
            "relevance_level": "unknown",
            "risk_level": "caution",
        }

    return result


def extract_research_contribution(paper: dict) -> dict:
    """
    提取文献的研究贡献.

    Args:
        paper: 文献信息

    Returns:
        贡献提取结果
    """
    system_prompt = "你是学术文献分析专家，擅长从论文中提取核心贡献。只输出 JSON。"

    prompt = f"""请从以下文献中提取研究贡献：

标题：{paper.get('title', 'N/A')}
摘要：{paper.get('abstract', paper.get('tldr', 'N/A'))[:2000]}

输出 JSON：
{{
    "research_object": "研究对象",
    "research_method": "研究方法",
    "key_findings": "主要结论（1-2句话）",
    "limitations": "研究不足或局限性",
    "contribution_type": "理论创新/方法改进/实验验证/综述回顾/工程应用",
    "is_competitor": true/false,
    "competitor_reason": "如果是竞争文献，说明原因"
}}"""

    response = deepseek_chat(prompt, system_prompt=system_prompt, max_tokens=1024)
    result = _extract_json_from_response(response)

    if not result:
        return {
            "research_object": paper.get("title", ""),
            "research_method": "",
            "key_findings": "",
            "limitations": "",
        }

    return result


def extract_research_gap(papers: list[dict], topic: str) -> str:
    """
    基于文献列表提取研究空白.

    Args:
        papers: 文献列表 (建议 10-30 篇)
        topic: 研究方向

    Returns:
        研究空白分析文本
    """
    system_prompt = (
        "你是学术研究空白分析专家。请基于提供的文献列表，"
        "识别当前研究中的空白和不足。只使用提供的文献，不编造文献。"
    )

    # 构建文献摘要
    papers_summary = []
    for i, p in enumerate(papers[:30], 1):
        papers_summary.append(
            f"[{i}] {p.get('title', '?')} ({p.get('year', '?')}): "
            f"{p.get('abstract', p.get('tldr', ''))[:300]}"
        )

    prompt = f"""研究方向：{topic}

已有文献：
{chr(10).join(papers_summary)}

请分析：
1. 现有研究已经解决了哪些问题
2. 现有研究在方法、数据、应用层⾯存在哪些不足
3. 哪些研究方向尚未被充分探索
4. 建议的研究切入点

请用中文段落输出，风格类似硕士论文的"现有研究不足"部分。
不需要引用格式，直接陈述即可。"""

    return deepseek_chat(prompt, system_prompt=system_prompt, max_tokens=2048)


def generate_literature_review(papers: list[dict], topic: str) -> str:
    """
    生成结构化文献综述.

    Args:
        papers: 已分类的文献列表
        topic: 研究方向

    Returns:
        Markdown 格式的文献综述
    """
    system_prompt = (
        "你是一位经验丰富的学术论文写作者，擅长撰写硕士论文级别的文献综述。"
        "请严格遵守以下规则：\n"
        "1. 只基于提供的文献进行写作，不编造任何文献\n"
        "2. 中文表达自然，避免翻译腔和 AI 套话\n"
        "3. 每段有明确的论点+论据+小结\n"
        "4. 无法确认的信息标注'需进一步查证'\n"
        "5. 引用的文献标注 [序号]"
    )

    # 分类整理文献
    categories = {}
    for p in papers:
        cat = p.get("category", "未分类")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(p)

    # 构建输入
    papers_text = []
    for i, p in enumerate(papers[:50], 1):
        papers_text.append(
            f"[{i}] {p.get('title', '?')}"
            f" | {', '.join(p.get('authors', [])[:3])}"
            f" | {p.get('year', '?')}"
            f" | {p.get('journal', '?')}"
            f" | 被引{p.get('cited_by_count', 0)}次"
            f"\n   {p.get('abstract', p.get('tldr', ''))[:400]}"
        )

    prompt = f"""研究方向：{topic}

检索到的文献（共 {len(papers)} 篇）：
{chr(10).join(papers_text)}

请生成以下结构的文献综述初稿：

# 文献综述

## 1. 研究背景与意义
（2-3段，说明该领域的研究价值和现实需求）

## 2. 国内外研究现状
### 2.1 主要研究进展
（按主题组织，引用具体文献的 [序号]）

### 2.2 研究方法综述
（总结该领域常用的研究方法及其优缺点）

### 2.3 现有研究的主要不足
（客观分析现有研究在哪些方面仍存在不足）

## 3. 研究空白与切入点
（基于现有不足，指出可进一步研究的方向）

## 4. 推荐重点阅读文献
（列出 5-10 篇最重要的文献及其推荐理由）

要求：
- 每个论述都要有文献序号支撑
- 中文表达自然，不要有翻译腔
- 客观评价，不贬低前人工作
- 格式为 Markdown"""

    return deepseek_chat(prompt, system_prompt=system_prompt, max_tokens=4096)


def generate_citation_sentence(paper: dict, usage_context: str) -> str:
    """
    为单篇文献生成引文句.

    Args:
        paper: 文献信息
        usage_context: 使用场景描述

    Returns:
        中文引用句
    """
    system_prompt = (
        "你是学术论文写作助手，擅长将文献引用自然地嵌入论文段落。"
        "生成的引用句要符合中文硕士论文的写作规范。只基于提供的文献信息。"
    )

    prompt = f"""文献信息：
- 标题：{paper.get('title', 'N/A')}
- 作者：{', '.join(paper.get('authors', [])[:5])}
- 年份：{paper.get('year', 'N/A')}
- 期刊：{paper.get('journal', 'N/A')}
- 关键发现：{paper.get('abstract', paper.get('tldr', ''))[:500]}

使用场景：{usage_context}

请生成 1-2 句中文引用句，可以直接嵌入硕士论文。
要求：
- 中文自然流畅，不要翻译腔
- 准确概括文献贡献
- 与使用场景紧密关联
- 使用恰当的学术评价词
- 标注建议的引用方式（标注式/叙述式）"""

    return deepseek_chat(prompt, system_prompt=system_prompt, max_tokens=1024)


def batch_classify_papers(papers: list[dict], topic: str, show_progress: bool = True) -> list[dict]:
    """
    批量分类文献.

    Args:
        papers: 文献列表
        topic: 研究方向
        show_progress: 是否显示进度

    Returns:
        添加了分类信息的文献列表
    """
    from tqdm import tqdm

    iterator = tqdm(papers, desc="Classifying with DeepSeek") if show_progress else papers

    for paper in iterator:
        try:
            classification = classify_paper_with_deepseek(paper, topic)
            paper["category"] = classification.get("category", "未分类")
            paper["classification_reason"] = classification.get("reason", "")
            paper["can_be_cited_for"] = classification.get("can_be_cited_for", "")
            paper["relevance_level"] = classification.get("relevance_level", "unknown")
            paper["risk_level"] = classification.get("risk_level", "caution")
        except Exception as e:
            logger.warning(f"Classification failed for '{(paper.get('title') or '?')[:50]}': {e}")
            paper["category"] = "未分类"
            paper["relevance_level"] = "unknown"
            paper["risk_level"] = "caution"

    # 统计
    from collections import Counter
    cat_counts = Counter(p.get("category", "未分类") for p in papers)
    logger.info(f"Classification complete: {dict(cat_counts)}")
    return papers


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # 测试选题分析
    result = analyze_topic("寒冷地区双层日光温室热湿环境动态模型")
    print(json.dumps(result, ensure_ascii=False, indent=2))

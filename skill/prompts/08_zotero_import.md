# Prompt: Zotero 导入方案

## System

你是文献管理专家，擅长为 Zotero 设计合理的文献分类、标签和集合（Collection）方案。

## Task

基于已分类的文献，设计 Zotero 导入方案，包括集合结构、标签体系和导入优先级。

## Zotero 集合结构设计

```markdown
ARF/{研究方向}/
├── 01_经典基础文献/
├── 02_近年前沿文献/
├── 03_直接竞争文献/
├── 04_可引用支撑文献/
├── 05_方法模型文献/
├── 06_工程应用文献/
├── 07_背景政策文献/
└── 08_需人工判断/
```

## 标签体系

每篇文献添加以下标签：

```text
主要分类标签：ARF/{category_name}
检索来源标签：ARF/source-{openalex|crossref|semantic_scholar}
优先级标签：ARF/priority-{high|medium|low}
相关性标签：ARF/relevance-{high|medium|low}
年份标签：ARF/year-{YYYY}
方法标签：ARF/method-{method_type}
创新点标签：ARF/innovation-{aspect}
```

## 输出格式

```json
{
  "collection_name": "ARF/{研究方向}",
  "subcollections": [
    "01_经典基础文献",
    "02_近年前沿文献",
    "03_直接竞争文献",
    "04_可引用支撑文献",
    "05_方法模型文献",
    "06_工程应用文献",
    "07_背景政策文献"
  ],
  "papers_to_import": [
    {
      "title": "...",
      "doi": "...",
      "tags": ["ARF/direct_competition", "ARF/priority-high"],
      "category": "直接竞争文献",
      "priority": "high",
      "collection_path": "ARF/{研究方向}/03_直接竞争文献"
    }
  ],
  "papers_need_manual_check": [
    {
      "title": "...",
      "reason": "DOI 缺失/无效"
    }
  ],
  "papers_need_vpn_pdf_download": [
    {
      "title": "...",
      "doi": "...",
      "journal": "...",
      "year": "...",
      "note": "需要通过学校 VPN 下载全文"
    }
  ],
  "import_statistics": {
    "total_papers": 0,
    "with_doi": 0,
    "without_doi": 0,
    "verified_doi": 0,
    "unverified_doi": 0
  }
}
```

## Rules

1. 标签命名使用英文，便于搜索和过滤
2. 集合名称使用中文+数字序号，便于排序
3. 优先级标签根据文献与用户研究的相关程度确定
4. 一个文献可以属于多个标签，但只能放在一个集合中
5. DOI 无效或无 DOI 的文献单独列出，供人工处理

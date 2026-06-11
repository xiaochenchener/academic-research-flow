# ☕ Academic Research Flow

> **一杯咖啡的功夫，完成一篇文献综述。**

面向硕士/博士的本地科研自动化工作流：选题分析 → 文献检索 → 分类排序 → 综述生成，全程自动。

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 目录

- [功能特性](#功能特性)
- [安装](#安装)
- [配置 API](#配置-api)
- [使用方式](#使用方式)
- [输出文件](#输出文件)
- [命令行参数](#命令行参数)
- [配置调优](#配置调优)
- [结果解读与最佳实践](#结果解读与最佳实践)
- [故障排查](#故障排查)
- [项目结构](#项目结构)
- [License](#license)

---

## 功能特性

**检索与验证**
1. **智能检索** — OpenAlex 多轮检索，concept filter 自动排除噪音（如 greenhouse gas），AND 组合查询提高精度
2. **DOI 验证** — CrossRef 逐条验证，杜绝幻觉引用
3. **信息补充** — Semantic Scholar 补充引用量、AI 摘要
4. **引用追溯** — 对 Top 文献做前后向 snowballing，发现遗漏的相关研究
5. **期刊信息** — easyScholar 查询影响因子、SCI 分区、中科院分区

**AI 分析**（需 DeepSeek API）
6. **选题分析** — 识别研究对象、方法、场景，判断关键词歧义
7. **关键词拆解** — 生成研究对象/方法/场景/创新点四类矩阵
8. **文献分类** — 规则 + AI 双重分类，分入直接竞争、经典基础等 8 类
9. **综述生成** — 硕士论文级别的文献综述初稿
10. **引用句生成** — 6 种句式的中文引用句，可直接嵌入论文

**输出**
11. **增强报告** — 每篇文献含期刊、IF、分区、摘要、分类理由
12. **多格式导出** — Markdown + JSON + Excel（含 IF、分区列）

---

## 安装

**前置要求**：Python 3.10+、pip 23.0+。macOS 只有 `python3` 命令，下同。

```bash
git clone https://github.com/xiaochenchener/academic-research-flow.git
cd academic-research-flow
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate.ps1
python3 -m pip install -r requirements.txt
cp .env.example .env
python3 tests/test_pipeline.py     # 看到 🎉 即成功
```

---

## 配置 API

> 不配也能用——检索和导出完全免费。API 只解锁 AI 功能和影响因子。

| 服务 | 用途 | 配置方式 | 费用 |
|------|------|---------|------|
| DeepSeek | AI 选题/分类/综述/引用句 | `.env` 设 `DEEPSEEK_API_KEY=sk-xxx` | ~¥0.1/次 |
| easyScholar | 影响因子/SCI分区/中科院分区 | `.env` 设 `EASYSCHOLAR_SECRET_KEY=xxx` | 免费 |
| OpenAlex 礼貌池 | 提高 API 限流 | `.env` 设 `OPENALEX_MAILTO=you@email` | 免费 |
| Semantic Scholar | 提高补充速度 | `.env` 设 `SEMANTIC_SCHOLAR_API_KEY=xxx` | 免费 |

注册地址：DeepSeek ([platform.deepseek.com](https://platform.deepseek.com))、easyScholar ([easyscholar.cc](https://www.easyscholar.cc))、Semantic Scholar ([api.semanticscholar.org](https://api.semanticscholar.org))、OpenAlex ([openalex.org](https://openalex.org))

---

## 使用方式

### 方式 1：交互式（推荐）

```bash
./run.sh
```

按提示回答即可，大部分直接回车用默认值。支持 4 种预设：快速检索 / 完整 AI / 极简预览 / 自定义。

### 方式 2：一行命令

```bash
./run.sh "研究方向"
./run.sh "研究方向" "创新点描述"
./run.sh -- -t "topic" --from-year 2015 --classic-count 50  # 透传原始参数
```

### 方式 3：Claude Code 对话

直接说即可，Claude Code 自动调用 pipeline：

> "帮我检索双层日光温室热湿环境动态模型的文献"
> "分析相变储能地板方向，判断创新点是否新颖"

---

运行后自动执行 16 步流水线：

| 步骤 | 说明 | 步骤 | 说明 |
|------|------|------|------|
| 1. 选题分析 | DeepSeek 分析 | 9. AI 分类 | DeepSeek 精细分类 |
| 2. 关键词矩阵 | 四类关键词生成 | 10. 排序评分 | 加权多维排序 |
| 3. 文献检索 | OpenAlex 多轮 | 11. 引用追溯 | 前后向 snowballing |
| 5. 去重 | DOI+标题去重 | 12. 期刊信息 | easyScholar IF/分区 |
| 6. DOI 验证 | CrossRef 验证 | 13. 综述生成 | AI 文献综述 |
| 7. S2 补充 | Semantic Scholar | 14. 引用句 | 6 种句式生成 |
| 8. 规则分类 | 关键词规则分类 | 15-16. 导出 | 全部格式 + 增强报告 |

---

## 输出文件

| 文件 | 说明 |
|------|------|
| `final_report.md` | **先看这个**。文献概览、年份/期刊/IF 分布、每篇文献卡片（期刊/IF/分区/DOI/摘要/分类理由）、推荐阅读 |
| `06_ranked_papers.xlsx` | **最重要**。全部文献表，含影响因子、SCI分区、中科院分区列，按分类分 Sheet |
| `10_literature_review.md` | AI 综述初稿（研究背景、现状、空白、创新点论证）。需人工修改润色 |
| `11_citation_sentences.md` | 可直接嵌入论文的中文引用句，含 DOI 和适用位置标注 |
| `04_raw_papers.json` | 原始检索结果 |
| `07_classified_papers.md` | 按 8 类整理的文献列表 |
| `08_competitor_papers.md` | 直接竞争文献详情 |

---

## 命令行参数

> `run.sh` 已处理大部分参数。以下供高级用户参考。

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `-t, --topic` | 必填 | 研究方向 |
| `-i, --innovation` | `""` | 创新点描述 |
| `--from-year` | `2020` | 起始年份 |
| `--to-year` | `2026` | 结束年份 |
| `--classic-count` | `30` | 经典文献数 |
| `--recent-count` | `30` | 近年文献数 |
| `--competition-count` | `20` | 竞争文献数 |
| `--output-dir` | 自动 | 输出目录 |
| `--skip-deepseek` | — | 跳过 AI |
| `--skip-snowballing` | — | 跳过引用追溯 |
| `--skip-journal-info` | — | 跳过影响因子 |
| `--skip-citations` | — | 跳过引用句 |
| `--skip-enrichment` | — | 跳过 S2 补充 |
| `--skip-verification` | — | 跳过 DOI 验证 |
| `-v, --verbose` | — | 详细日志 |

---

## 配置调优

`config.yaml` 关键配置项：

```yaml
search:
  classic_lookback_years: 20        # 经典文献回溯年数
  max_search_terms: 15              # 最多使用的检索词数
  enable_concept_filter: true       # concept filter 排除噪音
  enable_snowballing: true          # 引用追溯
  noise_concept_ids:                # 排除的噪音概念
    - "C2777034668"   # greenhouse gas
    - "C132651083"    # climate change

ranking:
  relevance_weight: 0.45
  keyword_type_weights:             # 关键词按类型加权
    research_object: 3.0            # 研究对象 (最高)
    research_method: 2.0            # 研究方法
    application_scenario: 1.5        # 应用场景
    innovation_point: 1.0           # 创新点

snowballing:
  top_n_seeds: 10                   # 用于追溯的种子文献数
  max_forward_citations: 20         # 前向引用上限
  max_backward_citations: 30        # 后向引用上限

dedup:
  title_similarity_threshold: 0.85  # 标题相似度阈值
```

---

## 结果解读与最佳实践

### 判断文献优先级

1. 相关性 = high → 必读
2. 综合分数 > 0.6 → 优先读
3. 影响因子 > 5 → 高水平期刊，可信度高
4. 分类 = 直接竞争文献 → 必须精读

### 判断创新点新颖性

竞争文献 0-2 篇且确有差异 → 大概率新颖；> 5 篇 → 需调整创新点表述。

### 迭代策略

```
第一轮: 宽泛检索 → 读 Top 10，了解领域
    ↓
第二轮: 精确检索 → 聚焦竞争+近年文献
    ↓
第三轮: 引用句生成 → 基于精选文献
```

### 人工把关点

| 环节 | 你需要做的 |
|------|-----------|
| 关键词 | 检查 AI 生成的关键词是否准确 |
| 文献筛选 | Excel 中筛掉不相关文献 |
| 竞争判断 | 读竞争文献摘要，判断是否真构成竞争 |
| 综述修改 | 调整 AI 综述，融入自己的理解 |
| 引用核实 | 确认引用句对应的文献信息正确 |

---

## 故障排查

| 问题 | 解决 |
|------|------|
| `command not found: python` (macOS) | 用 `python3` 替代 `python` |
| `ModuleNotFoundError` | `source .venv/bin/activate && python3 -m pip install -r requirements.txt` |
| `DEEPSEEK_API_KEY not set` | `.env` 中等号前后不要有空格和引号 |
| OpenAlex 返回空 | 用更宽泛关键词：`./run.sh -- -t "greenhouse thermal model" --from-year 2010` |
| easyScholar 查询失败 | 验证 Key：`curl "https://www.easyscholar.cc/open/getPublicationInfo?secretKey=你的KEY&publicationName=Nature"` |
| DeepSeek 报错 | 检查余额 [platform.deepseek.com](https://platform.deepseek.com)，或用 `--skip-deepseek` 跳过 |

---

## 项目结构

```
academic-research-flow/
├── run.sh                 # 一键启动脚本
├── config.yaml            # 主配置文件
├── .env.example           # 环境变量模板
├── requirements.txt
├── scripts/
│   ├── main.py            # 主入口
│   ├── search_openalex.py # 检索 + snowballing
│   ├── rank_papers.py     # 加权排序
│   ├── classify_papers.py # 规则分类
│   ├── deduplicate_papers.py
│   ├── verify_crossref.py
│   ├── enrich_semantic_scholar.py
│   ├── enrich_journal_info.py  # easyScholar IF
│   ├── deepseek_client.py      # DeepSeek API
│   ├── generate_review.py
│   ├── generate_citation_sentences.py
│   ├── export_results.py       # 导出 + 增强报告
│   └── config_loader.py
├── skill/                 # Claude Code Skill 定义
│   ├── SKILL.md
│   ├── prompts/           # 8 个 Prompt 模板
│   └── examples/          # 3 个领域示例
└── tests/
```

---

## License

MIT — 详见 [LICENSE](LICENSE)。

---

## 致谢

[OpenAlex](https://openalex.org) · [CrossRef](https://www.crossref.org) · [Semantic Scholar](https://www.semanticscholar.org) · [DeepSeek](https://platform.deepseek.com) · [easyScholar](https://www.easyscholar.cc)

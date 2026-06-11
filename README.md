# Academic Research Flow

从选题分析到文献综述的**本地科研自动化文献检索与总结工作流**。

面向硕士/博士论文写作、开题报告、文献综述、创新点论证和论文引用整理。

---

## 目录

- [这个工具能做什么](#这个工具能做什么)
- [快速开始](#快速开始)
- [环境准备](#环境准备)
- [第一步：安装](#第一步安装)
- [第二步：配置 API（可选）](#第二步配置-api可选)
- [三种运行方式](#三种运行方式)
- [命令行参数速查](#命令行参数速查)
- [输出文件详解](#输出文件详解)
- [配置调优](#配置调优)
- [如何解读结果](#如何解读结果)
- [最佳实践](#最佳实践)
- [故障排查](#故障排查)

---

## 快速开始

安装完成后，最简单的使用方式：

```bash
# 方式 1: 交互式问答（最推荐，一个命令都不用记）
./run.sh

# 方式 2: 一行命令直接搜
./run.sh "双层日光温室热湿环境动态模型"

# 方式 3: 带创新点验证
./run.sh "相变电热地板" "新型微胶囊PCM封装"

# 方式 4: 在 Claude Code 中直接说
#   "帮我检索双层日光温室热湿环境动态模型的文献"
```

`run.sh` 自动处理所有复杂操作：激活虚拟环境、检查配置、引导参数。

> 💡 第一次运行如果提示 `.env` 不存在，不用管——没有 AI 功能也能搜索和导出文献。想要 AI 综述的话，花 2 分钟配置 DeepSeek API Key。参见 [第二步：配置 API](#第二步配置-api可选)。

1. **选题分析** — 识别研究对象、研究方法、应用场景，判断关键词是否有歧义
2. **关键词拆解** — 自动生成四类关键词矩阵（研究对象/方法/场景/创新点）
3. **智能检索** — 从 OpenAlex 数据库获取英文文献，支持 concept filter 排除噪音、AND 组合查询减少无效结果
4. **DOI 验证** — 通过 CrossRef 验证每篇文献的 DOI 是否真实有效，杜绝幻觉引用
5. **信息补充** — 从 Semantic Scholar 补充引用量、研究领域、AI 摘要
6. **文献去重** — 基于 DOI + 标题相似度自动去重
7. **文献分类** — 将文献分为直接竞争、经典基础、近年前沿等 8 类
8. **排序评分** — 综合相关性、引用量、新近性、DOI 可靠性四个维度打分（关键词按类型加权）
9. **引用追溯** — 对 Top 文献做前向/后向引用追溯，发现更多相关研究
10. **期刊信息** — 通过 easyScholar API 查询期刊影响因子、SCI分区、中科院分区
11. **综述生成** — 调用 DeepSeek 生成硕士论文级别的文献综述初稿
12. **引用句生成** — 生成可直接嵌入论文的中文引用句（6 种句式）
13. **增强报告** — 每篇文献包含完整信息：期刊、影响因子、分区、摘要、分类理由
14. **多格式导出** — 输出 Markdown、JSON、Excel 三种格式

---

## 环境准备

### 你的电脑需要安装

| 软件 | 最低版本 | 检查命令 | 用途 |
|------|---------|---------|------|
| Python | 3.10+ | `python3 --version` | 运行所有检索脚本 |
| pip | 23.0+ | `pip3 --version`（或 `python3 -m pip --version`） | 安装 Python 依赖 |
| git | 任意版本 | `git --version` | (可选) 版本管理 |

> 🍎 **macOS 用户特别注意**：macOS 系统**没有** `python` 命令，只有 `python3`。本文档所有命令均使用 `python3`。

### 可选但强烈推荐

| 服务 | 注册地址 | 用途 | 费用 |
|------|---------|------|------|
| DeepSeek API | https://platform.deepseek.com/ | AI 选题分析、文献分类、综述生成 | ¥2/百万 token（约几毛钱一次） |
| Semantic Scholar API | https://api.semanticscholar.org/ | 补充文献引用量和摘要 | 免费 |
| easyScholar | https://www.easyscholar.cc | 查询期刊影响因子、SCI/中科院分区 | 免费（需注册） |
| OpenAlex 礼貌池 | https://openalex.org/ | 提高 API 限流额度 | 免费（需注册邮箱） |

> 💡 **省钱提示**：DeepSeek 价格极低，完整运行一次（含选题分析、50篇文献分类、综述生成）大约消耗 50K-100K token，花费约 ¥0.1-0.2。

---

## 第一步：安装

### 1.1 克隆或进入项目目录

```bash
cd /Users/xiaochenchener/Documents/Studys/academic-workflow/academic-research-flow
```

### 1.2 创建 Python 虚拟环境

```bash
# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境（每次使用前都需要执行）
# 🍎 macOS / 🐧 Linux:
source .venv/bin/activate
# 🪟 Windows (PowerShell):
# .venv\Scripts\Activate.ps1
# 🪟 Windows (CMD):
# .venv\Scripts\activate.bat

# 验证：终端提示符前面应该出现 (.venv)
which python3
# 应该输出: .../academic-research-flow/.venv/bin/python3
```

### 1.3 安装依赖

```bash
# 🍎 macOS: 确保用虚拟环境里的 pip
python3 -m pip install -r requirements.txt
```

安装的包及其用途：

| 包名 | 用途 |
|------|------|
| `requests` | 所有 API 请求（OpenAlex, CrossRef, DeepSeek, Semantic Scholar, easyScholar） |
| `pandas` | 数据处理和 Excel 导出 |
| `openpyxl` | Excel 文件读写引擎 |
| `python-dotenv` | 从 `.env` 文件加载 API Key |
| `pyyaml` | 读取 `config.yaml` 配置 |
| `tqdm` | 进度条显示 |
| `rapidfuzz` | 标题相似度计算（去重用） |
| `tenacity` | API 请求失败自动重试 |
| `rich` | 终端彩色输出 |

### 1.4 创建配置文件

```bash
# 复制环境变量模板
cp .env.example .env

# 验证项目结构
ls -la
# 应该看到: README.md  .env  .env.example  config.yaml  requirements.txt  skill/  scripts/  outputs/  tests/
```

### 1.5 验证安装

```bash
# 运行单元测试，确保基础模块正常
python3 tests/test_pipeline.py
```

如果看到 `🎉 All pipeline tests passed!`，说明安装成功。

---

## 第二步：配置 API（可选）

> 💡 **即使不配置任何 API，也能用 `run.sh` 完成文献检索和导出。** API 配置只是解锁 AI 功能（选题分析、综述写作、引用句生成）+ 期刊影响因子。

### DeepSeek API（解锁 AI 功能）

1. 注册 https://platform.deepseek.com/ → 获取 API Key
2. 编辑 `.env`：`DEEPSEEK_API_KEY=sk-xxxxxxxx`
3. 验证：`python3 tests/test_deepseek.py`

花费约 ¥0.1-0.2/次。

### easyScholar（解锁影响因子和分区）

1. 注册 https://www.easyscholar.cc → 我的信息 → 开放接口 → 复制 secretKey
2. 编辑 `.env`：`EASYSCHOLAR_SECRET_KEY=你的key`

### 其他（可选）

```bash
OPENALEX_MAILTO=your_email@example.com    # 提高 API 限流
SEMANTIC_SCHOLAR_API_KEY=                # 提高文献补充速度
```

---

## 三种运行方式

### 方式 1: 交互式问答（一个命令都不用记）

```bash
./run.sh
```

运行后会逐步引导你：

```
╔══════════════════════════════════════════╗
║      Academic Research Flow              ║
║      学术文献检索与总结工具               ║
╚══════════════════════════════════════════╝

📋 交互式配置模式
（直接按回车使用默认值）

1. 研究方向: 双层日光温室热湿环境动态模型

2. 创新点描述 (可选): 保温被动态控制与湿量迁移耦合

3. 检索起始年份 [2020]:

4. 检索结束年份 [2026]:

5. 检索模式:
   [1] 快速检索 (无 AI，只做检索+分类+导出)
   [2] 完整 AI 分析 (选题分析+文献综述+引用句，推荐)
   [3] 极简模式 (最小检索量，快速预览)
   [4] 自定义参数
   选择 [2]:

6. 输出目录名 (可选，留空自动生成):

────────────────────────────────────────
🚀 执行命令:
────────────────────────────────────────

确认执行? [Y/n]:
```

### 方式 2: 一行命令

```bash
# 最简：只要研究方向
./run.sh "模块化相变电热地板低碳供暖"

# 带创新点
./run.sh "日光温室热湿模型" "保温被动态控制与湿量迁移耦合"

# 透传原始参数（高级用法）
./run.sh -- -t "solar greenhouse" --from-year 2015 --classic-count 50
```

### 方式 3: 在 Claude Code 中直接说

在 Claude Code 对话中直接说：

- `"帮我检索双层日光温室热湿环境动态模型的文献"`
- `"用 Academic Research Flow 分析相变储能地板这个方向"`
- `"帮我查一下 2020-2026 年关于 greenhouse thermal model 的文献，判断我的创新点是否新颖"`

Claude Code 会自动调用 pipeline。

---

### 运行过程

无论哪种方式，运行后你会看到 16 步自动化流程：

```
============================================================
Academic Research Flow - Starting
Topic: 寒冷地区双层日光温室热湿环境动态模型
Concept filter: on | Snowballing: on
============================================================

Step 1: Topic Analysis        → DeepSeek 分析研究方向
Step 2: Keyword Matrix        → 生成四类关键词矩阵
Step 3: Literature Search     → OpenAlex 多轮检索
Step 5: Deduplication         → 去重
Step 6: DOI Verification      → CrossRef 验证
Step 7: S2 Enrichment         → Semantic Scholar 补充
Step 8-9: Classification      → 规则 + AI 双重分类
Step 10: Ranking              → 加权评分排序
Step 11: Snowballing          → 引用追溯
Step 12: Journal Info         → easyScholar 影响因子
Step 13: Literature Review    → AI 生成综述初稿
Step 14: Citation Sentences   → AI 生成引用句
Step 15-16: Export + Report   → 导出全部结果

============================================================
✅ Pipeline Complete!
============================================================

📄 输出文件:
   ✅ final_report.md        ← 先看这个（含期刊、IF、摘要）
   ✅ 06_ranked_papers.xlsx   ← Excel 文献表（含 IF、分区）
   ✅ 10_literature_review.md ← 文献综述初稿
   ✅ 11_citation_sentences.md ← 可嵌入论文的引用句
```

---

## 命令行参数速查

> `run.sh` 帮你处理了大部分参数。以下供高级用户参考。

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--topic` / `-t` | **必填** | 研究方向 |
| `--innovation` / `-i` | `""` | 创新点描述 |
| `--from-year` | `2020` | 检索起始年份 |
| `--to-year` | `2026` | 检索结束年份 |
| `--classic-count` | `30` | 经典文献数量 |
| `--recent-count` | `30` | 近年文献数量 |
| `--competition-count` | `20` | 竞争文献数量 |
| `--output-dir` | 自动生成 | 输出目录路径 |
| `--skip-deepseek` | — | 跳过所有 AI 功能 |
| `--skip-enrichment` | — | 跳过 Semantic Scholar |
| `--skip-verification` | — | 跳过 DOI 验证 |
| `--skip-citations` | — | 跳过引用句生成 |
| `--skip-journal-info` | — | 跳过影响因子查询 |
| `--skip-snowballing` | — | 跳过引用追溯 |

### 📄 `final_report.md` — 增强版最终报告（先看这个）

包含完整的文献调研结果，每篇文献的详细信息：

- **文献调研概览**：总量统计、年份分布图、期刊分布表（含影响因子）、IF 区间分布
- **选题分析摘要**：研究对象、方法、应用场景、创新点
- **文献分类统计**：各类别数量和占比
- **直接竞争文献详情**：竞争分析和差异判断
- **每篇文献卡片**：期刊名、影响因子、SCI分区、中科院分区、DOI、被引次数、完整摘要、分类理由
- **推荐阅读建议**：按优先级三档（精读/浏览/选读）

### 📊 `06_ranked_papers.xlsx` — 排序后的文献表（最重要）

包含多个 Sheet：

| Sheet 名 | 内容 |
|----------|------|
| **全部文献** | 所有文献完整信息，含影响因子、SCI分区、摘要 |
| **直接竞争文献** | 仅竞争文献 |
| **经典基础文献** | 仅经典文献 |
| ...（其他分类） | 每个分类一个 Sheet |
| **分类汇总** | 各类别统计表 |

新增列：
- **影响因子** — 期刊影响因子
- **SCI分区** — SCI 分区（Q1-Q4）
- **中科院分区** — 中科院期刊分区

### 📝 `10_literature_review.md` — 文献综述初稿

AI 生成的结构化文献综述，包含研究背景、国内外研究现状、研究空白、创新点论证、推荐阅读清单。

> ⚠️ **不要直接复制粘贴到论文**！这是初稿，需要你人工修改润色。

### 💬 `11_citation_sentences.md` — 可嵌入论文的引用句

包含按 6 种类型组织的中文引用句，每条含 DOI、适用位置、引用方式标注。

---

## 如何在 Claude Code 中使用

在对话中直接说就行，Claude Code 会自动调用 pipeline：

```
"帮我检索太阳能温室热环境模型的文献"

"分析一下相变储能地板这个方向，看看有没有直接竞争"

"帮我查 2020-2026 年 greenhouse thermal model 的文献，生成综述"
```

Skill 文件位于 `~/.claude/skills/academic-research-flow.md`，你不需要手动操作。在 Claude Code 中直接说方向即可。

---

## 配置调优

### `config.yaml` 详解

```yaml
# 检索配置
search:
  classic_lookback_years: 20  # 经典文献回溯年数
  max_search_terms: 15        # 单次最多使用的检索词数量
  enable_concept_filter: true # 是否启用 concept filter 排除噪音
  enable_snowballing: true    # 是否启用引用追溯

  # 噪音 Concept IDs (OpenAlex) — 检索时自动排除
  noise_concept_ids:
    - "C2777034668"   # greenhouse gas
    - "C132651083"    # climate change
    ...
```

```yaml
# 排序权重
ranking:
  relevance_weight: 0.45

  # 关键词类型权重
  keyword_type_weights:
    research_object: 3.0      # 研究对象词 (最重要)
    research_method: 2.0      # 研究方法词
    application_scenario: 1.5 # 应用场景词
    innovation_point: 1.0     # 创新点词
```

```yaml
# Snowballing 配置
snowballing:
  max_forward_citations: 20   # 前向引用最大检索数
  max_backward_citations: 30  # 后向引用最大检索数
  top_n_seeds: 10             # 用于 seed 的 Top N 文献
```

---

## 如何解读结果

### 如何判断一篇文献是否值得读

看 Excel 表格的这几列（按优先级）：

1. **相关性** = high → 必读
2. **综合分数** > 0.6 → 优先读
3. **被引次数** > 10 且年份较新 → 可能是热点
4. **影响因子** > 5 → 高水平期刊，可信度高
5. **分类** = 直接竞争文献 → 必须精读

### 如何判断创新点是否新颖

1. 看最终报告中的竞争文献数量
2. 如果竞争文献数为 0 或 1-2 篇且确有差异 → 大概率新颖
3. 如果竞争文献超过 5 篇 → 需要仔细分析差异，调整创新点表述

---

## 最佳实践

### 1. 输入技巧

- ✅ **好的输入**：具体的、包含研究方法的方向
  > "寒冷地区双层日光温室热湿环境动态模型"
- ❌ **差的输入**：太宽泛
  > "温室"

### 2. 迭代优化

```text
第一轮: 宽泛检索（from-year 2015, classic-count 50）
    ↓
阅读 Top 10，了解领域概况
    ↓
第二轮: 精确检索（根据第一轮结果调整关键词，缩小范围）
    ↓
聚焦竞争文献和近年文献
    ↓
第三轮: 引用句生成（基于前两轮的精选文献）
```

### 3. 人工介入点

| 环节 | 你需要做什么 |
|------|------------|
| 关键词审核 | 检查 AI 生成的关键词是否准确 |
| 文献筛选 | 在 Excel 中筛掉明显不相关的文献 |
| 竞争判断 | 阅读竞争文献的摘要，判断是否真的构成竞争 |
| 综述修改 | 调整 AI 生成的综述，融入你自己的理解 |
| 引用核实 | 确认每条引用句对应的文献信息正确 |

---

## 故障排查

### 问题 0：`zsh: command not found: python`（🍎 macOS 最常见）

macOS 系统没有 `python` 这个命令，只有 `python3`。所有命令都用 `python3`。

### 问题 1：`ModuleNotFoundError: No module named 'xxx'`

```bash
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

### 问题 2：`DEEPSEEK_API_KEY not set`

检查 `.env` 文件：
```bash
cat .env | grep DEEPSEEK
# 正确: DEEPSEEK_API_KEY=sk-xxxxxxxx
# 错误: DEEPSEEK_API_KEY = "sk-xxxxxxxx"
```

### 问题 3：OpenAlex 返回空结果

可能原因：检索词太精确、年份范围太窄、网络问题。

```bash
# 测试网络连通性
curl "https://api.openalex.org/works?search=solar+greenhouse&per_page=1"

# 用更宽泛的关键词搜索
python3 scripts/main.py --topic "greenhouse thermal model" --from-year 2010
```

### 问题 4：easyScholar 查询失败

检查 secretKey 是否正确：
```bash
curl "https://www.easyscholar.cc/open/getPublicationInfo?secretKey=你的KEY&publicationName=Nature"
```

如果不需要影响因子信息，使用 `--skip-journal-info` 跳过。

### 问题 5：DeepSeek 返回错误

检查 API 余额：https://platform.deepseek.com/

临时跳过：`python3 scripts/main.py --topic "..." --skip-deepseek`

---

## 项目文件结构

```
academic-research-flow/
├── README.md
├── .env.example
├── .env
├── requirements.txt
├── config.yaml
│
├── skill/
│   ├── SKILL.md
│   ├── prompts/
│   │   ├── 01_topic_analysis.md
│   │   ├── 02_keyword_expansion.md
│   │   ├── 03_search_strategy.md
│   │   ├── 04_paper_classification.md
│   │   ├── 05_novelty_check.md
│   │   ├── 06_literature_review.md
│   │   ├── 07_citation_integration.md
│   │   └── 08_zotero_import.md
│   └── examples/
│       ├── example_greenhouse.md
│       ├── example_pcm_floor.md
│       └── example_pvt.md
│
├── scripts/
│   ├── __init__.py
│   ├── main.py                         # 🎯 主程序入口
│   ├── config_loader.py                # 配置加载器
│   ├── search_openalex.py             # OpenAlex API 检索 + snowballing
│   ├── verify_crossref.py             # CrossRef DOI 验证
│   ├── enrich_semantic_scholar.py     # Semantic Scholar 信息补充
│   ├── enrich_journal_info.py         # easyScholar 影响因子查询
│   ├── deepseek_client.py             # DeepSeek API 客户端
│   ├── deduplicate_papers.py          # 文献去重
│   ├── rank_papers.py                 # 文献排序评分 (关键词加权)
│   ├── classify_papers.py             # 规则分类
│   ├── generate_review.py             # 综述生成模块
│   ├── generate_citation_sentences.py # 引用句生成模块
│   └── export_results.py              # 多格式导出 + 增强报告
│
├── outputs/
│
└── tests/
    ├── test_openalex.py
    ├── test_crossref.py
    ├── test_deepseek.py
    └── test_pipeline.py
```

---

## 致谢

本项目使用了以下开放学术数据源：

- [OpenAlex](https://openalex.org/) — 开放学术文献索引
- [CrossRef](https://www.crossref.org/) — DOI 注册和验证
- [Semantic Scholar](https://www.semanticscholar.org/) — AI 驱动的学术搜索引擎
- [DeepSeek](https://platform.deepseek.com/) — 大语言模型 API
- [easyScholar](https://www.easyscholar.cc) — 期刊影响因子和分区数据

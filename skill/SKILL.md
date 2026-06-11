# ☕ Academic Research Flow Skill

> **一杯咖啡的功夫，完成一篇文献综述。**

为硕士/博士论文写作、开题报告、文献综述、创新点论证提供自动化支持。

## 适用场景

- 论文开题时的文献调研
- 文献综述初稿生成
- 创新点可行性判断（是否已有直接竞争）
- 引文素材整理

## 输入格式

用户需要提供：

```text
研究方向：[必填] 你的研究方向或研究问题
创新点：[选填] 初步创新点（提供后可进行竞争分析）
时间范围：[选填] 默认 2020-2026
```

## 输出格式

运行完成后，在 `outputs/{topic_slug}/` 下生成：

| 文件 | 内容 |
|------|------|
| `final_report.md` | 增强版最终报告（文献概览、年份/期刊/IF分布、每篇文献卡片） |
| `06_ranked_papers.xlsx` | 排序文献表（含影响因子、SCI分区、中科院分区） |
| `10_literature_review.md` | 文献综述初稿 |
| `11_citation_sentences.md` | 可嵌入论文的中文引用句 |
| `07_classified_papers.md` | 按 8 类整理的文献列表 |
| `08_competitor_papers.md` | 直接竞争文献详情 |
| `01_topic_analysis.json` | 选题分析结果 |
| `04_raw_papers.json` | 原始检索结果 |

## 工作流步骤

| 步骤 | 说明 |
|------|------|
| 1. 选题分析 | DeepSeek 分析研究对象、方法、场景 |
| 2. 关键词矩阵 | 生成研究对象/方法/场景/创新点四类关键词 |
| 3. 文献检索 | OpenAlex 多轮检索，concept filter 排除噪音 |
| 4. 去重 | DOI + 标题相似度去重 |
| 5. DOI 验证 | CrossRef 逐条验证 |
| 6. 信息补充 | Semantic Scholar 补充引用量、AI摘要 |
| 7. 分类 | 规则 + DeepSeek 双重分类（8类） |
| 8. 排序 | 多维加权排序（相关性/引用量/新近性/DOI可靠） |
| 9. 引用追溯 | 前后向 snowballing |
| 10. 期刊信息 | easyScholar 影响因子/SCI分区/中科院分区 |
| 11. 综述生成 | DeepSeek 生成结构化综述 |
| 12. 引用句 | 生成 6 种句式的中文引用句 |
| 13. 导出 | Markdown + JSON + Excel |

## 文献分类标准

```text
1. 直接竞争文献 — 与创新点高度重叠
2. 可引用支撑文献 — 可支撑论述和方法
3. 经典基础文献 — 领域奠基性工作，高被引
4. 近年前沿文献 — 近 3 年发表
5. 方法模型文献 — 提供方法论参考
6. 工程应用文献 — 工程实践和案例
7. 背景政策文献 — 政策标准综述类
8. 噪音文献 — 不相关，排除
```

## 禁止编造引用

- ❌ 禁止在任何输出中编造作者、标题、DOI、期刊名称
- ❌ 禁止让 DeepSeek 凭空生成文献条目
- ✅ 只允许基于检索到且经过 CrossRef 验证的文献进行写作
- ✅ 所有引用句必须关联到已有文献的 DOI 或标题

## 调用方式

Skill 通过 Claude Code 的 Bash 工具调用 `run.sh`：

```bash
cd <project_dir>
./run.sh "研究方向"
```

或直接调用 Python 脚本：

```bash
cd <project_dir>
source .venv/bin/activate
python3 scripts/main.py -t "研究方向"
```

## 示例指令

### 完整分析
> 用 Academic Research Flow 分析"寒冷地区双层日光温室热湿环境动态模型"，判断创新点是否新颖，生成综述

### 快速检索
> 用 Academic Research Flow 快速检索"模块化相变电热地板低碳供暖"，只看近三年

### 创新点验证
> 帮我判断"基于 NSGA-II 的双层日光温室保温被多目标优化控制"是否已有文献做过类似工作

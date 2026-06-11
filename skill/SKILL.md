# Academic Research Flow Skill

从选题到文献综述到 Zotero 入库的**本地科研自动化工作流**。

## 用途

本 Skill 为硕士/博士论文写作、开题报告、文献综述、创新点论证和论文引用整理提供自动化支持。输入研究方向后，自动完成选题分析、关键词拆解、多数据库检索、文献分类排序、综述生成和 Zotero 入库清单。

## 适用场景

- 论文开题时的文献调研
- 文献综述初稿生成
- 创新点可行性判断（是否已有直接竞争）
- 引文素材整理
- Zotero 批量入库和标签管理

## 输入格式

用户需要提供：

```text
研究方向：[必填] 你的研究方向或研究问题
创新点：[选填] 你的初步创新点（如果提供，可以进行竞争分析）
时间范围：[选填] 文献检索的年份范围，默认 2020-2026
经典文献数量：[选填] 默认 30
近年文献数量：[选填] 默认 30
竞争文献数量：[选填] 默认 20
```

## 输出格式

运行完成后，在 `outputs/{topic_slug}/` 下生成：

| 文件 | 内容 |
|------|------|
| `01_topic_analysis.json` | 选题分析（研究对象、方法、创新点、关键词歧义风险） |
| `02_keyword_matrix.md` | 关键词矩阵表 |
| `03_search_queries.json` | OpenAlex 检索式列表 |
| `04_raw_papers.json` | 原始检索结果 |
| `05_verified_papers.json` | DOI 验证后的文献 |
| `06_ranked_papers.xlsx` | 排序评分后的文献表 |
| `07_classified_papers.md` | 文献分类结果 |
| `08_competitor_papers.md` | 直接竞争文献详情 |
| `09_support_papers.md` | 可引用支撑文献详情 |
| `10_literature_review.md` | 文献综述初稿 |
| `11_citation_sentences.md` | 可嵌入论文的引用句 |
| `12_zotero_import_list.txt` | Zotero DOI 导入清单 |
| `13_zotero_collection_plan.md` | Zotero 集合/标签方案 |
| `14_need_vpn_download.md` | 需学校 VPN 下载 PDF 的文献清单 |
| `final_report.md` | 最终汇总报告 |

## 工作流步骤

1. **选题分析**：调用 DeepSeek 分析研究对象、方法、应用场景、创新点、关键词歧义风险
2. **关键词矩阵生成**：拆分为研究对象、方法、场景、创新点四类关键词
3. **构造检索式**：生成经典文献、近年文献、竞争文献三组检索式
4. **OpenAlex 多轮检索**：执行多轮 API 检索
5. **文献去重**：按 DOI + 标题相似度去重
6. **CrossRef DOI 验证**：验证每篇文献的 DOI 是否有效
7. **Semantic Scholar 补充**：补充引用量、研究领域等元数据
8. **文献排序评分**：综合相关性、引用量、新近性、DOI 可靠性评分
9. **DeepSeek 分类**：AI 辅助判断文献类别和相关性
10. **生成文献综述**：按章节生成结构化综述初稿
11. **生成引用句**：生成可嵌入论文的中文引用句
12. **生成 Zotero 清单**：输出 DOI 导入清单和标签方案
13. **导出文件**：输出 Markdown、JSON、Excel 格式结果

## 文献检索规则

### 四轮检索策略

```text
第一轮：研究对象检索 — 搜索与研究对象直接相关的文献
第二轮：方法模型检索 — 搜索与建模方法相关的文献
第三轮：应用场景检索 — 搜索与应用场景相关的文献
第四轮：创新点/竞争文献检索 — 搜索可能构成直接竞争的文献
```

### 文献分类标准

```text
1. 直接竞争文献：研究内容与你的创新点高度重叠
2. 可引用支撑文献：可用于支撑你的论述和方法
3. 经典基础文献：领域奠基性工作，高被引
4. 近年前沿文献：近3年发表的最新进展
5. 方法模型文献：提供方法论参考，可借鉴
6. 工程应用文献：工程实践和案例研究
7. 背景政策文献：政策和标准类文献
8. 噪音文献：不相关的检索结果，需排除
```

## 文献验证规则

1. **DOI 必须通过 CrossRef 验证**，未通过验证的标记为"需人工核验"
2. **标题去重**：DOI 相同或标题相似度 > 85% 视为同一文献
3. **引用量从 Semantic Scholar 获取**，确保数据可信
4. **不编造任何文献**：如果检索结果为 0，明确说明，绝不自造文献条目

## 禁止编造引用

- ❌ **严禁**在任何输出中编造作者、标题、DOI、期刊名称
- ❌ **严禁**让 DeepSeek 凭空生成文献条目
- ✅ **只允许**基于检索到且经过 CrossRef 验证的文献进行写作
- ✅ 所有引用句必须关联到已有文献的 DOI 或标题

## 调用本地 Python 脚本

Skill 通过 Claude Code 的 Bash 工具调用本地脚本：

```bash
cd /Users/xiaochenchener/Documents/Studys/academic-workflow/academic-research-flow
source .venv/bin/activate
python scripts/main.py --topic "{用户输入的研究方向}" --from-year {起始年} --to-year {结束年}
```

## Zotero 入库

### 前置条件

1. Zotero 桌面端已安装并运行
2. Zotero 已开启本地 API: Settings → Advanced → Allow other applications
3. Zotero MCP 已配置完成

### 配置方法

```bash
# 方法1: Zoteus (推荐)
claude mcp add --transport stdio zoteus -- npx -y @oscardvs/zoteus

# 方法2: zotero-mcp
claude mcp add --transport stdio zotero -- npx -y zotero-mcp
```

### 入库流程

1. 读取 `12_zotero_import_list.txt` 中的 DOI 列表
2. 通过 Zotero MCP 按 DOI 逐条导入
3. 根据 `13_zotero_collection_plan.md` 创建集合并移入文献
4. 为每条文献添加分类标签
5. 检查是否已有重复条目（按 DOI 检测）

## 提醒用户下载 PDF

系统会在 `14_need_vpn_download.md` 中列出需要手动下载 PDF 的文献清单，并提醒：

> ⚠️ 以下文献需要通过学校 VPN 连接后手动下载全文 PDF：
> 1. [标题] - [期刊] ([年份]) - DOI: [doi]
> 2. ...

## 示例指令

### 示例 1: 完整分析

```text
用 Academic Research Flow 分析这个方向：
寒冷地区双层日光温室热湿环境动态模型。

要求：
1. 检索经典文献和 2023-2026 年前沿文献
2. 判断我的创新点是否已有直接竞争研究
3. 生成文献综述初稿
4. 生成 Zotero 入库清单
5. 输出需要 VPN 下载的 PDF 清单
```

### 示例 2: 快速检索

```text
用 Academic Research Flow 快速检索：
模块化相变电热地板低碳供暖
只看近三年的文献，输出 Excel 和 Zotero 导入清单。
```

### 示例 3: 创新点验证

```text
用 Academic Research Flow 帮我判断：
我的创新点"基于 NSGA-II 的双层日光温室保温被多目标优化控制"
是否已有文献做过类似工作。
如果有，请帮我列出直接竞争文献并分析差异。
```

## Human-in-the-loop 检查点

| 步骤 | 检查内容 |
|------|----------|
| 关键词确认 | 用户确认关键词矩阵是否合理 |
| 文献筛选 | 用户可从 Excel 中筛除不相关文献 |
| 综述质量 | 用户确认综述段落是否可直接用于论文 |
| Zotero 入库 | 用户确认是否批量导入 Zotero |
| PDF 下载 | 用户通过学校 VPN 手动下载全文 |

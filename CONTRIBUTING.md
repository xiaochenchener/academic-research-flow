# Contributing

## Getting Started

```bash
git clone https://github.com/xiaochenchener/academic-research-flow.git
cd academic-research-flow
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入你的 API Key
```

## Running Tests

```bash
source .venv/bin/activate
python tests/test_pipeline.py
```

## Submitting Issues

提交 Issue 时请说明：
- 你的操作系统和 Python 版本
- 使用的命令
- 完整的错误日志

## Pull Requests

1. Fork 本仓库
2. 创建 feature 分支
3. 确保 `python tests/test_pipeline.py` 全部通过
4. 提交 PR

## Security

- **不要提交 `.env`、API Key 或任何私人凭据**
- 不要提交 `outputs/` 目录下的运行结果
- 如果不小心提交了密钥，请立即在对应平台重置

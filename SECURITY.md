# Security Policy

## Reporting a Vulnerability

如果你发现安全漏洞，请通过 GitHub Issues 报告，不要公开披露。

## API Key Safety

- 本项目需要 DeepSeek API Key、easyScholar Secret Key 等第三方凭证
- 请将凭证写入 `.env` 文件，该文件已被 `.gitignore` 排除
- 永远不要将 `.env` 提交到 Git
- 如果不小心提交了密钥，请立即：
  1. 删除 Git 历史中的敏感信息
  2. 在对应平台（DeepSeek / easyScholar）重置密钥
- 用户需要自行管理自己的 API Key、VPN、学校账号等私人凭据

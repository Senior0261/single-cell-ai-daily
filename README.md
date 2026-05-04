# 🔬 单细胞与AI细胞前沿日报 (Single-Cell & AI Frontier Daily)

这是一个自动化的网页项目，旨在每日追踪和聚合单细胞生物学、空间组学以及人工智能在细胞生物学应用领域的最新研究论文和行业新闻。

## ✨ 特点

*   **每日自动更新**：通过 GitHub Actions 每日凌晨 00:00 (UTC+8) 自动运行，抓取最新内容。
*   **智能摘要**：使用 LLM (Large Language Model) 将复杂的科学摘要提炼成非技术人员也能理解的 50-100 字中文核心摘要。
*   **极简设计**：采用“学术极简低饱和度”设计风格，提供舒适的阅读体验。
*   **内容来源**：聚合来自 Nature、bioRxiv、arXiv 等权威期刊和预印本平台的内容。

## ⚙️ 技术栈

*   **内容抓取与处理**：Python (requests, feedparser, BeautifulSoup)
*   **智能提炼**：OpenAI API (LLM)
*   **前端**：HTML/CSS (极简风格)
*   **自动化**：GitHub Actions (定时任务与部署)

## 🚀 部署与访问

本网站已部署到 GitHub Pages，可公开访问。

**访问链接**：[链接将在部署完成后提供]

## 🛠️ 本地运行 (可选)

1.  克隆仓库：`git clone [仓库地址]`
2.  安装依赖：`pip install -r requirements.txt` (如果创建了 requirements.txt)
3.  设置 `OPENAI_API_KEY` 环境变量。
4.  运行脚本：`python fetch_content.py`

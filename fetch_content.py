import feedparser
import requests
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime, timedelta
from openai import OpenAI
import os

# --- Configuration ---
# 确保从环境变量中读取 API 密钥
# 即使在 Actions 中设置了 env，Python 脚本也需要显式从 os.environ 读取
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    print("Error: OPENAI_API_KEY environment variable not set.")
    # 退出或使用一个默认值，这里选择使用默认的 client()，它会尝试读取环境变量
    client = OpenAI()
else:
    client = OpenAI(api_key=api_key) 

# 关键词列表，用于过滤和标签生成
KEYWORDS = [
    "single-cell", "spatial omics", "AI", "machine learning", 
    "virtual cell", "scRNA-seq", "genomics", "transcriptomics",
    "deep learning", "foundation model"
]

# RSS 源列表
RSS_FEEDS = {
    "bioRxiv_Genomics": "https://www.biorxiv.org/rss/genomics",
    "bioRxiv_Cell_Biology": "https://www.biorxiv.org/rss/cell-biology",
    "arXiv_Genomics": "http://export.arxiv.org/rss/q-bio.GN",
    # Nature 的 RSS 很难精确到关键词，这里使用一个广谱的，后续通过关键词过滤
    "Nature_Research": "https://www.nature.com/latest-research.rss" 
}

OUTPUT_FILE = "/home/ubuntu/latest_news.json"
MAX_ITEMS = 10

def fetch_and_filter_feeds():
    """从所有 RSS 源抓取内容并根据关键词过滤。"""
    all_entries = []
    
    # 设定时间窗口：只抓取过去 7 天内的文章，避免抓取大量旧文章
    seven_days_ago = datetime.now() - timedelta(days=7)

    for source, url in RSS_FEEDS.items():
        print(f"Fetching {source} from {url}...")
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                # 尝试获取发布日期
                published_date = None
                if hasattr(entry, 'published_parsed'):
                    published_date = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, 'updated_parsed'):
                    published_date = datetime(*entry.updated_parsed[:6])
                
                # 过滤掉太旧的文章
                if published_date and published_date < seven_days_ago:
                    continue

                title = entry.title
                summary = entry.summary if hasattr(entry, 'summary') else entry.description
                link = entry.link
                
                # 关键词过滤
                text_to_check = (title + " " + summary).lower()
                if any(keyword in text_to_check for keyword in KEYWORDS):
                    all_entries.append({
                        "title": title,
                        "summary_raw": summary,
                        "link": link,
                        "source": source,
                        "published": published_date.strftime("%Y-%m-%d") if published_date else "Unknown"
                    })
        except Exception as e:
            print(f"Error fetching {source}: {e}")
            
    # 移除重复项（基于链接）
    unique_entries = {entry['link']: entry for entry in all_entries}.values()
    
    # 按日期降序排序
    sorted_entries = sorted(list(unique_entries), key=lambda x: x.get('published', '1900-01-01'), reverse=True)
    
    return sorted_entries

def generate_llm_content(entry):
    """使用 LLM 提炼摘要和生成标签。"""
    
    # 清理摘要中的 HTML 标签
    soup = BeautifulSoup(entry['summary_raw'], 'html.parser')
    cleaned_summary = soup.get_text()
    
    # 构造 LLM 提示
    prompt = """
    你是一个专业的生物医学新闻编辑。请根据以下文章信息，完成两项任务：
    1. **核心摘要提炼**：用非技术人员也能理解的语言，将文章的核心发现和意义概括为 50-100 字的中文摘要。
    2. **关键词标签生成**：从提供的关键词列表中选择最相关的 1-3 个标签，或生成新的相关标签。标签必须以 '#' 开头，例如 #单细胞RNA测序。

    文章标题: {title}
    文章摘要: {summary}
    
    请直接输出一个 JSON 对象，格式如下：
    {{
        "abstract_zh": "提炼后的中文摘要...",
        "tags": ["#标签1", "#标签2"]
    }}
    """.format(title=entry['title'], summary=cleaned_summary)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini", # 使用配置的 LLM 模型
            messages=[
                {"role": "system", "content": "你是一个专业的生物医学新闻编辑，擅长将复杂的科学内容转化为易懂的中文摘要和关键词标签。请严格按照用户要求的 JSON 格式输出。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        # 尝试解析 JSON 字符串
        llm_output = json.loads(response.choices[0].message.content)
        entry['abstract_zh'] = llm_output.get('abstract_zh', '摘要生成失败。')
        entry['tags'] = llm_output.get('tags', ['#未知'])
        
        # 标记为今日亮点（随机选择第一个，后续可以优化逻辑）
        entry['is_highlight'] = False
        
    except Exception as e:
        print(f"LLM generation failed for {entry['title']}: {e}")
        entry['abstract_zh'] = "摘要生成失败，请查看原文。"
        entry['tags'] = ['#LLM_Error']
        entry['is_highlight'] = False
        
    return entry

def generate_html(data):
    """根据 JSON 数据生成最终的 HTML 页面。"""
    
    # 找到今日亮点（默认为第一条）
    if data:
        data[0]['is_highlight'] = True
        highlight_item = data[0]
    else:
        highlight_item = None

    # 网页设计：学术极简低饱和度
    CSS_STYLE = """
    <style>
        :root {
            --color-bg: #f5f5f5; /* 浅米白 */
            --color-card-bg: #ffffff; /* 纯白 */
            --color-text-dark: #333333; /* 深灰 */
            --color-text-light: #666666; /* 中灰 */
            --color-tag-bg: #e0e6ed; /* 灰蓝 */
            --color-tag-text: #4a6582; /* 深灰蓝 */
            --color-highlight-border: #a9b9c9; /* 柔和蓝灰 */
            --font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        }
        body {
            font-family: var(--font-family);
            background-color: var(--color-bg);
            color: var(--color-text-dark);
            line-height: 1.6;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 1000px;
            margin: 0 auto;
        }
        h1 {
            color: var(--color-text-dark);
            font-weight: 300;
            border-bottom: 1px solid #e0e0e0;
            padding-bottom: 10px;
            margin-bottom: 30px;
        }
        .highlight-area {
            background-color: var(--color-card-bg);
            border: 2px solid var(--color-highlight-border);
            padding: 25px;
            margin-bottom: 40px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        }
        .highlight-area h2 {
            color: #2c3e50; /* 略深的蓝灰 */
            margin-top: 0;
            font-size: 1.5em;
        }
        .highlight-area .abstract {
            font-size: 1.1em;
            color: var(--color-text-dark);
        }
        .news-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .news-card {
            background-color: var(--color-card-bg);
            padding: 20px;
            border-radius: 6px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03);
            transition: transform 0.2s;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .news-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        }
        .news-card h3 {
            margin-top: 0;
            font-size: 1.1em;
            color: var(--color-text-dark);
            font-weight: 500;
        }
        .news-card a {
            text-decoration: none;
            color: var(--color-text-dark);
        }
        .news-card a:hover {
            color: #4a6582;
        }
        .abstract {
            color: var(--color-text-light);
            font-size: 0.9em;
            margin-bottom: 15px;
        }
        .tags {
            margin-top: 10px;
        }
        .tag {
            display: inline-block;
            background-color: var(--color-tag-bg);
            color: var(--color-tag-text);
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.75em;
            margin-right: 5px;
            margin-bottom: 5px;
            font-weight: 600;
        }
        .footer {
            text-align: center;
            margin-top: 50px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
            color: var(--color-text-light);
            font-size: 0.8em;
        }
    </style>
    """

    # HTML 结构
    date_str = datetime.now().strftime("%Y年%m月%d日")
    datetime_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    highlight_html = ""
    if highlight_item:
        tags_html = " ".join(f'<span class="tag">{tag}</span>' for tag in highlight_item["tags"])
        highlight_html = f"""
                <h3><a href="{highlight_item["link"]}" target="_blank">{highlight_item["title"]}</a></h3>
                <p class="abstract">{highlight_item["abstract_zh"]}</p>
                <div class="tags">{tags_html}</div>
                <p style="font-size: 0.8em; color: #999;">来源: {highlight_item["source"]} | 发布日期: {highlight_item["published"]}</p>
        """
    else:
        highlight_html = "<h3>暂无亮点新闻</h3>"

    news_list_html = ''.join(generate_card_html(item) for item in data if not item['is_highlight'])

    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>单细胞与AI细胞前沿日报 - {date_str}</title>
        {CSS_STYLE}
    </head>
    <body>
        <div class="container">
            <h1>单细胞与AI细胞前沿日报 - {date_str}</h1>
            
            <!-- 今日亮点区域 -->
            <h2>今日亮点</h2>
            <div class="highlight-area">
                {highlight_html}
            </div>

            <!-- 新闻列表区域 -->
            <h2>最新追踪</h2>
            <div class="news-grid">
                {news_list_html}
            </div>

            <div class="footer">
                <p>数据更新于 {datetime_str} UTC+8 | 自动追踪 Nature, bioRxiv, arXiv 等权威来源。</p>
                <p>由 Manus AI 自动生成与部署。</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

def generate_card_html(item):
    """生成单个新闻卡片的 HTML。"""
    tags_html = " ".join(f'<span class="tag">{tag}</span>' for tag in item['tags'])
    
    return f"""
    <div class="news-card">
        <div>
            <h3><a href="{item['link']}" target="_blank">{item['title']}</a></h3>
            <p class="abstract">{item['abstract_zh']}</p>
        </div>
        <div>
            <div class="tags">{tags_html}</div>
            <p style="font-size: 0.8em; color: #999; margin-top: 10px;">来源: {item['source']} | 发布日期: {item['published']}</p>
        </div>
    </div>
    """

def main():
    """主函数：抓取、处理并生成 HTML。"""
    # 1. 抓取和过滤
    filtered_entries = fetch_and_filter_feeds()
    
    # 2. 限制数量
    selected_entries = filtered_entries[:MAX_ITEMS]
    
    # 3. LLM 处理
    processed_entries = []
    for entry in selected_entries:
        processed_entries.append(generate_llm_content(entry))
        
    # 4. 生成 HTML
    html_output = generate_html(processed_entries)
    
    # 5. 保存 HTML
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_output)
        
    print(f"Successfully generated index.html with {len(processed_entries)} items.")

if __name__ == "__main__":
    main()

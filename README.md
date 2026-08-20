# Help-you-read 📚

帮你读书 —— 上传一本书，AI 按《如何阅读一本书》的「渐进阅读法」生成结构化阅读报告，帮你判断「值不值得读」。

## 工作原理（两段式）

```
上传 EPUB / 文字版 PDF
        ↓
book_parser.py  解析 → {书名, 作者, 序言, 目录, 章节原文}
        ↓
第一段：只喂「书名+序言+目录」→ DeepSeek 挑出 2–4 个关键章节
        ↓
第二段：只喂挑中章节全文 → 生成完整报告（结论速览/检视阅读/分析阅读/评论/总结）
        ↓
前端用 marked 渲染 Markdown 报告
```

两段式的好处：不用把整本书喂给模型，省 token、避免长文迷失，报告更准。

## 技术栈

- Flask（后端）
- DeepSeek `deepseek-v4-flash`（OpenAI 兼容接口）
- PyPDF2（PDF 书签解析）、纯标准库（EPUB 解析）
- marked（前端 Markdown 渲染）

## 本地运行

```bash
pip install -r requirements.txt
export DEEPSEEK_API_KEY=你的key
python app.py
# 访问 http://localhost:5000
```

## 部署到 Render

1. 把本仓库连到 Render 的 Web Service（Build: `pip install -r requirements.txt`，Start: `gunicorn app:app`）。
2. 在 Render 的 **Environment → Environment Variables** 里添加 `DEEPSEEK_API_KEY`（不要写进代码，仓库是公开的）。
3. 推送代码即可自动部署。

## 支持格式

- ✅ EPUB（目录/章节结构化提取）
- ✅ 文字版 PDF（带书签、有文字层）
- ❌ 扫描版 PDF（需先 OCR）、TXT / DOCX / MOBI（需先转成 EPUB）

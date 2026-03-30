import os
import re
import uuid
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import PyPDF2
import docx
from ebooklib import epub
from bs4 import BeautifulSoup
import requests

app = Flask(__name__)
CORS(app)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB 限制

# 创建上传目录
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# DeepSeek API 配置
DEEPSEEK_API_KEY = "sk-f93e785590d64239a68a9ace32679b5b"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


def extract_text_from_pdf(file_path):
    """提取 PDF 文本"""
    text = ""
    with open(file_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


def extract_text_from_txt(file_path):
    """提取 TXT 文本"""
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()


def extract_text_from_docx(file_path):
    """提取 Word 文档文本"""
    doc = docx.Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs])


def extract_text_from_epub(file_path):
    """提取 EPUB 文本"""
    text = ""
    book = epub.read_epub(file_path)
    for item in book.get_items():
        if item.get_type() == 9:  # 文档类型
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            text += soup.get_text() + "\n"
    return text


def extract_text_from_mobi(file_path):
    """MOBI 文本提取（简单方式：尝试读取二进制并提取可读文本）"""
    try:
        with open(file_path, 'rb') as f:
            raw = f.read()
        # 尝试解码为 utf-8 并过滤
        text = raw.decode('utf-8', errors='ignore')
        # 提取中英文和标点
        cleaned = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\.,;:!?()《》<>“”\-\s]', ' ', text)
        return re.sub(r'\s+', ' ', cleaned)[:50000]  # 限制长度
    except Exception as e:
        return f"MOBI 解析失败: {str(e)}"


def call_deepseek_analysis(book_title, book_content):
    """调用 DeepSeek API 进行 Qing 阅读分析法分析"""
    
    # 限制内容长度（DeepSeek 上下文限制）
    max_content_len = 15000
    if len(book_content) > max_content_len:
        book_content = book_content[:max_content_len] + "\n...(内容过长，已截取前部分)"
    
    system_prompt = """你是一位专业的书籍分析专家，精通「Qing阅读分析法」。请严格按照以下框架对书籍进行分析，输出格式为 Markdown，结构清晰。

## 第一阶段：检视阅读
1. **书名/封面/序言判断**：类型、主题
2. **目录架构**：全书架构，每章主旨一句话概括
3. **核心概念**：识别关键词，给出书中定义
4. **出版者介绍**：外部判断
5. **关键章节略读**：
   - 选择2-4个最关键章节及理由
   - 开头/中间/结尾的关键发现
   - 值不值得读的判断

## 第二阶段：分析阅读
### 找出一本书在谈什么
- **规则1 分类**：理论/实用/想象文学等
- **规则2 一句话概括全书**
- **规则3 大纲与串联逻辑**：章节间逻辑链条
- **规则4 作者要解决的问题**：问题与回答

### 诠释一本书的内容
- **规则5 关键字与通俗解释**
- **规则6 重要主旨句**
- **规则7 论述逻辑重构**：
  - 总论点
  - 子论点（论点-论据-论证结构）
  - 可视化逻辑链
- **规则8 已解决/未解决的问题**

## 第三阶段：评论一本书
- 规则9-11：批评前提
- 规则12-15 批评标准：
  - 知识不足
  - 知识错误
  - 不合逻辑
  - 分析不完整

## 第四阶段：主题阅读
1. 建立书目（同主题推荐）
2. 找出相关章节
3. 建立中立词汇
4. 厘清核心问题
5. 界定议题
6. 分析讨论与模型

请基于用户提供的书籍内容进行专业、详细的分析。"""
    
    user_prompt = f"""请分析以下书籍：

**书名**：{book_title}

**书籍内容摘要**：
{book_content}

请严格按照 Qing 阅读分析法输出完整分析报告。"""
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 4096
    }
    
    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content']
    except Exception as e:
        return f"AI 分析失败: {str(e)}"


def extract_text_by_format(file_path, file_ext):
    """根据文件格式提取文本"""
    if file_ext == '.pdf':
        return extract_text_from_pdf(file_path)
    elif file_ext == '.txt':
        return extract_text_from_txt(file_path)
    elif file_ext == '.docx':
        return extract_text_from_docx(file_path)
    elif file_ext == '.epub':
        return extract_text_from_epub(file_path)
    elif file_ext == '.mobi':
        return extract_text_from_mobi(file_path)
    else:
        return None


@app.route('/')
def index():
    """首页"""
    return render_template('index.html')


@app.route('/analyze', methods=['POST'])
def analyze_book():
    """分析书籍"""
    if 'file' not in request.files:
        return jsonify({'error': '未上传文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400
    
    # 获取文件扩展名
    original_filename = file.filename
    file_ext = os.path.splitext(original_filename)[1].lower()
    allowed_extensions = ['.pdf', '.txt', '.docx', '.epub', '.mobi']
    
    if file_ext not in allowed_extensions:
        return jsonify({'error': f'不支持的文件格式，请上传: {", ".join(allowed_extensions)}'}), 400
    
    # 保存临时文件
    temp_filename = f"{uuid.uuid4().hex}{file_ext}"
    temp_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
    file.save(temp_path)
    
    try:
        # 提取文本
        book_content = extract_text_by_format(temp_path, file_ext)
        
        if not book_content or len(book_content.strip()) < 50:
            return jsonify({'error': '无法从文件中提取足够文本内容'}), 400
        
        # 获取书名（去掉扩展名）
        book_title = os.path.splitext(original_filename)[0]
        
        # 调用 DeepSeek 分析
        analysis_result = call_deepseek_analysis(book_title, book_content)
        
        return jsonify({
            'success': True,
            'book_title': book_title,
            'analysis': analysis_result
        })
        
    except Exception as e:
        return jsonify({'error': f'分析失败: {str(e)}'}), 500
    finally:
        # 删除临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
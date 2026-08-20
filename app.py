import os
import uuid
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

import book_parser
import analyzer

app = Flask(__name__)
CORS(app)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB 限制

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 支持格式：EPUB / 文字版 PDF / TXT / DOCX / MOBI（mobi 依赖服务器装有 calibre）
ALLOWED_EXTENSIONS = {'.epub', '.pdf', '.txt', '.docx', '.mobi'}


@app.route('/')
def index():
    """首页"""
    return render_template('index.html')


@app.route('/analyze', methods=['POST'])
def analyze_book():
    """上传书籍 → 两段式（挑章节 + 出报告）分析。"""
    if not os.environ.get('DEEPSEEK_API_KEY'):
        return jsonify({'error': '服务器未配置 DEEPSEEK_API_KEY 环境变量，请联系管理员'}), 500

    if 'file' not in request.files:
        return jsonify({'error': '未上传文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({'error': f'暂不支持 {ext} 格式，请上传 EPUB、PDF、TXT、DOCX 或 MOBI'}), 400

    temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{uuid.uuid4().hex}{ext}")
    file.save(temp_path)

    try:
        report, sel, book = analyzer.analyze_book(temp_path, verbose=True)
        return jsonify({
            'success': True,
            'book_title': book.get('title') or os.path.splitext(file.filename)[0],
            'analysis': report,
            'selected_chapters': [t for t, _ in sel],
        })
    except Exception as e:
        return jsonify({'error': f'分析失败：{e}'}), 500
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

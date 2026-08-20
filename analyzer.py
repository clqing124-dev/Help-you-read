#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyzer.py —— 编排层：解析书 → 两段式调用 DeepSeek → 产出阅读分析报告。

流程：
    parse_book() → 第一段挑章节(JSON) → 第二段出报告(Markdown)

用法：
    python3 analyzer.py 书.epub
    python3 analyzer.py 书.pdf -o report.md

环境变量（生产走 DeepSeek 官方 OpenAI 兼容接口）：
    DEEPSEEK_API_KEY   必填
    DEEPSEEK_BASE_URL  可选，默认 https://api.deepseek.com
    DEEPSEEK_MODEL     可选，默认 deepseek-v4-flash
"""

import os
import re
import json
import argparse

import book_parser

API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
BASE_URL = os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
MODEL = os.environ.get('DEEPSEEK_MODEL', 'deepseek-v4-flash')

# ---------------------------------------------------------------------------
# 第一段提示词：挑章节（要求输出 JSON）
# ---------------------------------------------------------------------------

PASS1_SYSTEM_PROMPT = """你是一位阅读策划师。你的任务是从一本书的目录里，挑出 2–4 个最关键的章节，供后续深度分析使用。

你会收到：书名、作者、序言/引言（可选）、完整目录。

挑选标准（按重要性排序）：
1. 承载全书核心方法论 / 核心主张的章节，而不是案例堆砌或具体应用细节；
2. 读它就能判断「这本书值不值得读」的章节；
3. 优先选「章」这一级，不要选「小节」；
4. 流程型（步骤递进）的书，优先覆盖：定框架的首章 + 核心方法章 + 收尾心态章。

硬性要求：
1. 章节标题必须与目录里的原文【逐字一致】，不得改写、缩写、翻译。
2. 只输出一个 JSON 对象，不要输出任何其他文字或解释。

严格按以下 JSON 格式输出：
{"one_line_gist": "一句话概括全书主旨", "selected_chapters": [{"title": "与目录逐字一致的章节标题", "reason": "为什么选它（一两句话）"}]}"""

# ---------------------------------------------------------------------------
# 第二段提示词：出报告（Qing 阅读分析法，完整版）
# ---------------------------------------------------------------------------

PASS2_SYSTEM_PROMPT = """你是一位精通《如何阅读一本书》（莫提默·艾德勒 / 查尔斯·范多伦）方法论的资深阅读分析师。
你的任务：根据用户提供的书籍素材，产出一份结构化阅读分析报告，帮读者判断「这本书值不值得读」，并在值得读之后提供深度解读。

你严格遵循「Qing 阅读分析法」，分为三个阶段：检视阅读、分析阅读、评论。

## 铁律（必须无条件遵守）

1. 只基于给定素材分析。禁止编造素材中不存在的情节、数据、人名、引文或结论。
2. 素材不足以支撑某项分析时，如实写「素材不足，无法判断」，绝不脑补。
3. 凡标注「原文」的引用，必须从素材中逐字复制，不得改写、省略、杜撰。
4. 严格区分「书里的内容」（引用/概括）与「你的评价」（评论），二者分列。
5. 对专业术语，必须同时给出：书中的定义 + 一句大众能懂的通俗解释。
6. 严格按「输出格式」的标题层级输出，格式不得自创、不得遗漏主要板块。

## 分析方法

### 第一阶段：检视阅读（目标：快速判断值不值得读）
1. 看书名/封面/副标题/序言：判断书的类型（理论型/实用型/想象文学等）与主题。
2. 研究目录：掌握全书架构，用一句话概括每章主旨。
3. 检阅索引/关键词：识别核心概念，给出每个核心概念在书中的一句话定义。
4. 读出版者介绍：提取外部定位与卖点。
5. 挑相关篇章略读（最关键步骤）：对给出的每个关键章节，分别摘录其【开头】【中间】【结尾】的关键原文（逐字引用），并给出「略读收获」。
6. 结论：给出「值不值得读」的判断 + 决策维度表。

### 第二阶段：分析阅读
第一阶层——找出一本书在谈什么：
- 规则1 分类（理论/实用/想象文学等，说明依据）；
- 规则2 一句话概括全书主旨；
- 规则3 列出大纲（不要照抄目录，梳理各章节「解决什么问题、核心结论」及章节间串联逻辑）；
- 规则4 找出作者要解决的核心问题，并简洁总结书中给出的回答。

第二阶层——诠释一本书的内容：
- 规则5 关键字：列出关键字 → 给书中的定义 → 对陌生复杂概念补一句通俗解释；
- 规则6 重要主旨：找出代表全书观点的核心句子（至少 3 条，逐字引用）；
- 规则7 论述逻辑重构：用「论点 → 论据 → 论证」结构，论据标注原文引证；
- 规则8 确定已解决/未解决的问题。

### 第三阶段：评论
先遵守评论三原则（未完全了解前不轻易批评、不争强好辩、区分知识与观点），再按四条标准批评（有则指出、无则说明「未发现明显问题」）：知识不足、知识错误、不合逻辑、分析不完整。

### 总结
核心收获（3–5 条）/ 适合人群 / 阅读建议。

## 输出格式（Markdown，标题层级固定）

# 《书名》阅读分析报告

## 结论速览（值不值得读）
一句话结论 + 决策维度表（核心论点 / 理论价值 / 实用价值 / 阅读难度 / 推荐指数）

## 第一阶段：检视阅读
### 1.1 书名 / 封面 / 序言
### 1.2 目录架构（每章一句话主旨）
### 1.3 核心概念（一句话定义）
### 1.4 出版者介绍
### 1.5 挑关键章节略读（选择理由 / 开头原文 / 中间原文 / 结尾原文 / 略读收获）
### 1.6 略读结论

## 第二阶段：分析阅读
### 2.1 找出一本书在谈什么
### 2.2 诠释一本书的内容

## 第三阶段：评论
### 3.1 评论原则说明
### 3.2 按四条标准批评

## 总结
### 核心收获 / 适合人群 / 阅读建议"""


# ---------------------------------------------------------------------------
# LLM 调用（DeepSeek OpenAI 兼容接口）
# ---------------------------------------------------------------------------

def call_llm(system, user, json_mode=False, max_tokens=4000):
    import requests
    if not API_KEY:
        raise RuntimeError('缺少 DEEPSEEK_API_KEY 环境变量')
    url = BASE_URL.rstrip('/') + '/chat/completions'
    payload = {
        'model': MODEL,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user},
        ],
        'temperature': 0.3,
        'stream': False,
        'max_tokens': max_tokens,
    }
    if json_mode:
        payload['response_format'] = {'type': 'json_object'}
    r = requests.post(url, json=payload,
                      headers={'Authorization': f'Bearer {API_KEY}',
                               'Content-Type': 'application/json'},
                      timeout=600)
    r.raise_for_status()
    return r.json()['choices'][0]['message']['content']


# ---------------------------------------------------------------------------
# 编排逻辑
# ---------------------------------------------------------------------------

def build_pass1_input(book):
    toc_lines = '\n'.join(t['title'] for t in book['toc'])
    preface = (book.get('preface') or '')[:3000]
    return (f"书名：{book['title']}\n作者：{book['author']}\n\n"
            f"序言/引言：\n{preface}\n\n目录：\n{toc_lines}")


def build_pass2_input(book, picked):
    toc_lines = '\n'.join(t['title'] for t in book['toc'])
    chapters_text = '\n\n'.join(f"=== {t} ===\n{b}" for t, b in picked)
    return (f"【书籍基本信息】\n书名：{book['title']}\n作者：{book['author']}\n\n"
            f"【序言/引言】\n{(book.get('preface') or '')[:2000]}\n\n"
            f"【目录】\n{toc_lines}\n\n【关键章节原文】\n{chapters_text}")


def parse_selection(raw):
    """从第一段输出里稳健地抠出 JSON 对象（容忍代码围栏/多余文字）。"""
    m = re.search(r'\{.*\}', raw, re.S)
    if not m:
        raise ValueError(f'第一段输出中找不到 JSON：{raw[:200]}')
    return json.loads(m.group(0))


def resolve_chapters(sel, book):
    """把第一段挑出的标题映射到 book['chapters'] 里的正文（逐字→包含→放弃）。"""
    picked = []
    for ch in sel.get('selected_chapters', []):
        title = (ch.get('title') or '').strip()
        body = None
        if title in book['chapters']:
            body = book['chapters'][title]
        else:
            for k in book['chapters']:
                if title and (title in k or k in title):
                    title, body = k, book['chapters'][k]
                    break
        if body:
            picked.append((title, body))
        else:
            print(f'  ⚠️ 目录中找不到章节，已跳过：{title}')
    return picked


def analyze_book(path, verbose=True):
    book = book_parser.parse_book(path)
    if verbose:
        print(f"解析完成：《{book['title']}》，{len(book['chapters'])} 章，"
              f"序言 {len(book.get('preface') or '')} 字")

    if verbose:
        print('第一段：挑章节 …')
    raw1 = call_llm(PASS1_SYSTEM_PROMPT, build_pass1_input(book),
                    json_mode=True, max_tokens=2000)
    sel = parse_selection(raw1)
    picked = resolve_chapters(sel, book)
    if verbose:
        print(f"  主旨：{sel.get('one_line_gist', '')}")
        print(f"  选中 {len(picked)} 章：{', '.join(t for t, _ in picked)}")

    if verbose:
        print('第二段：出报告 …')
    user2 = build_pass2_input(book, picked)
    report = call_llm(PASS2_SYSTEM_PROMPT, user2, json_mode=False, max_tokens=32000)
    # 完整性检查：报告必须含「第三阶段：评论」和「总结」，缺失则重试一次（模型偶发早停）
    if ('第三阶段' not in report) or ('总结' not in report):
        if verbose:
            print('  ⚠️ 报告不完整（缺评论/总结），重试一次…')
        report = call_llm(PASS2_SYSTEM_PROMPT, user2, json_mode=False, max_tokens=40000)
    return report, sel, book


def main():
    ap = argparse.ArgumentParser(description='按 Qing 两段式分析一本书')
    ap.add_argument('book', help='书文件（.epub 或文字版 .pdf）')
    ap.add_argument('-o', '--out', help='报告另存为文件')
    args = ap.parse_args()

    report, sel, book = analyze_book(args.book)
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f'\n已写入 {args.out}')
    else:
        print('\n' + '=' * 60 + '\n报告：\n' + report)


if __name__ == '__main__':
    main()

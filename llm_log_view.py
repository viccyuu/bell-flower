#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Log Viewer
将 llm-log.db 中的 llm_input 和 llm_output 数据导出为 HTML 报告
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Any


def connect_db(db_path: str) -> sqlite3.Connection:
    """连接数据库"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_llm_pairs(conn: sqlite3.Connection, limit: int = 100) -> list[dict]:
    """获取关联的 llm_input 和 llm_output 数据"""
    query = """
    SELECT 
        i.id as input_id,
        i.created_at as input_time,
        o.id as output_id,
        o.created_at as output_time,
        i.event as input_event,
        o.event as output_event,
        i.ctx as input_ctx,
        o.ctx as output_ctx,
        json_extract(i.event, '$.runId') as run_id,
        json_extract(i.event, '$.sessionId') as session_id,
        json_extract(i.event, '$.sessionKey') as session_key
    FROM llm_input i
    INNER JOIN llm_output o 
        ON json_extract(i.event, '$.runId') = json_extract(o.event, '$.runId')
        AND json_extract(i.event, '$.sessionId') = json_extract(o.event, '$.sessionId')
    ORDER BY i.created_at DESC
    LIMIT ?
    """
    cursor = conn.execute(query, (limit,))
    return [dict(row) for row in cursor.fetchall()]


def fetch_session_ids(conn: sqlite3.Connection, limit: int = 100) -> list[str]:
    """获取所有唯一的 session_id"""
    query = """
    SELECT DISTINCT json_extract(event, '$.sessionId') as session_id
    FROM llm_input
    ORDER BY created_at DESC
    LIMIT ?
    """
    cursor = conn.execute(query, (limit,))
    return [row['session_id'] for row in cursor.fetchall() if row['session_id']]


def fetch_run_ids(conn: sqlite3.Connection, limit: int = 100) -> list[str]:
    """获取所有唯一的 run_id"""
    query = """
    SELECT DISTINCT json_extract(event, '$.runId') as run_id
    FROM llm_input
    ORDER BY created_at DESC
    LIMIT ?
    """
    cursor = conn.execute(query, (limit,))
    return [row['run_id'] for row in cursor.fetchall() if row['run_id']]


def format_value(value: Any) -> str:
    """格式化值用于 HTML 显示"""
    if value is None:
        return '<span class="null">null</span>'
    elif isinstance(value, bool):
        return f'<span class="bool">{str(value).lower()}</span>'
    elif isinstance(value, (int, float)):
        return f'<span class="number">{value}</span>'
    elif isinstance(value, str):
        # 不截断，完整展示
        # 转义 HTML 特殊字符
        value = value.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')
        return f'<span class="string">{value}</span>'
    else:
        return f'<span class="other">{value}</span>'


def generate_html(pairs: list[dict], session_ids: list[str], run_ids: list[str], output_path: str) -> None:
    """生成 HTML 报告"""

    # 生成 session 选项
    session_options = ''.join([
        f'<option value="{sid}">{sid[:12]}...{sid[-12:] if len(sid) > 24 else ""}</option>'
        for sid in session_ids
    ])

    # 生成 run_id 选项
    run_options = ''.join([
        f'<option value="{rid}">{rid[:8]}...{rid[-8:] if len(rid) > 16 else ""}</option>'
        for rid in run_ids
    ])

    # 生成所有记录的 JSON 数据用于前端筛选
    records_json = json.dumps(pairs, ensure_ascii=False)

    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LLM Log Viewer</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }
        .container {
            max-width: 1800px;
            margin: 0 auto;
        }
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 30px;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 10px;
        }
        .controls {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            display: grid;
            grid-template-columns: 1fr 1fr 1fr 1fr;
            gap: 20px;
            align-items: center;
        }
        .control-group {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .control-group label {
            font-weight: bold;
            color: #555;
            font-size: 14px;
        }
        .control-group select {
            padding: 10px;
            border: 2px solid #e0e0e0;
            border-radius: 5px;
            font-size: 13px;
            cursor: pointer;
        }
        .control-group select:focus {
            outline: none;
            border-color: #667eea;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            text-align: center;
        }
        .stat-card h3 {
            color: #666;
            font-size: 14px;
            margin-bottom: 10px;
        }
        .stat-card .value {
            font-size: 28px;
            font-weight: bold;
            color: #667eea;
        }
        .tabs {
            background: white;
            border-radius: 10px 10px 0 0;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            display: flex;
            overflow: hidden;
        }
        .tab {
            flex: 1;
            padding: 15px 30px;
            text-align: center;
            cursor: pointer;
            background: #f8f9fa;
            border: none;
            font-size: 16px;
            font-weight: bold;
            color: #666;
            transition: all 0.3s;
        }
        .tab:hover {
            background: #e9ecef;
        }
        .tab.active {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .tab-content {
            background: white;
            padding: 30px;
            border-radius: 0 0 10px 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            display: none;
        }
        .tab-content.active {
            display: block;
        }
        .section-title {
            font-size: 18px;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
        }
        .top-level-list {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        .top-level-item {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 20px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
            text-align: center;
            font-weight: bold;
        }
        .top-level-item:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        .top-level-item.active {
            background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.6);
        }
        .top-level-content {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            display: none;
        }
        .top-level-content.active {
            display: block;
        }
        .field {
            display: grid;
            grid-template-columns: 350px 1fr;
            gap: 10px;
            padding: 12px 15px;
            border-bottom: 1px solid #e9ecef;
        }
        .field:last-child {
            border-bottom: none;
        }
        .field-key {
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 13px;
            color: #495057;
            word-break: break-all;
            font-weight: 600;
        }
        .field-value {
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 13px;
            word-break: break-all;
            white-space: pre-wrap;
            background: white;
            padding: 10px;
            border-radius: 5px;
            border: 1px solid #e9ecef;
        }
        .string { color: #28a745; }
        .number { color: #007bff; }
        .bool { color: #fd7e14; }
        .null { color: #6c757d; }
        .other { color: #6c757d; }
        .duration {
            font-weight: bold;
            color: #28a745;
            background: #d4edda;
            padding: 5px 10px;
            border-radius: 5px;
        }
        .token-usage {
            display: inline-flex;
            gap: 15px;
            background: #e7f3ff;
            padding: 10px 15px;
            border-radius: 5px;
            margin-top: 10px;
        }
        .token-usage span {
            font-size: 14px;
        }
        .record-card {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            border-left: 4px solid #667eea;
        }
        .record-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            flex-wrap: wrap;
            gap: 10px;
        }
        .record-info {
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            font-size: 13px;
            color: #666;
        }
        .record-info span {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .hidden {
            display: none;
        }

        /* Tree view styles */
        .tree {
            padding-left: 20px;
        }
        .tree-item {
            margin: 5px 0;
        }
        .tree-key {
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 13px;
            color: #495057;
            font-weight: 600;
            cursor: pointer;
            user-select: none;
        }
        .tree-key:hover {
            color: #667eea;
        }
        .tree-children {
            padding-left: 25px;
            border-left: 2px solid #e9ecef;
            margin-left: 10px;
        }
        .tree-toggle {
            display: inline-block;
            width: 15px;
            text-align: center;
            margin-right: 5px;
            color: #667eea;
            font-weight: bold;
        }
        .tree-collapsed .tree-children {
            display: none;
        }
        .tree-collapsed .tree-toggle::before {
            content: '▶';
        }
        .tree-expanded .tree-toggle::before {
            content: '▼';
        }

        @media (max-width: 768px) {
            .controls {
                grid-template-columns: 1fr 1fr;
            }
            .field {
                grid-template-columns: 1fr;
            }
            .record-header {
                flex-direction: column;
                align-items: flex-start;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 LLM Log Viewer</h1>

        <!-- Controls -->
        <div class="controls">
            <div class="control-group">
                <label for="sessionFilter">📁 Session ID</label>
                <select id="sessionFilter" onchange="filterBySession()">
                    <option value="">全部 Session</option>
                    """ + session_options + """
                </select>
            </div>
            <div class="control-group">
                <label for="runFilter">🔑 Run ID</label>
                <select id="runFilter" onchange="filterByRun()">
                    <option value="">全部 Run</option>
                    """ + run_options + """
                </select>
            </div>
            <div class="control-group">
                <label>📊 统计信息</label>
                <div style="display: flex; gap: 20px; align-items: center;">
                    <div>
                        <div style="font-size: 12px; color: #666;">总记录数</div>
                        <div id="totalCount" style="font-size: 24px; font-weight: bold; color: #667eea;">""" + str(
        len(pairs)) + """</div>
                    </div>
                    <div>
                        <div style="font-size: 12px; color: #666;">筛选后</div>
                        <div id="filteredCount" style="font-size: 24px; font-weight: bold; color: #28a745;">""" + str(
        len(pairs)) + """</div>
                    </div>
                </div>
            </div>
            <div class="control-group">
                <label>🕐 时间范围</label>
                <div id="timeRange" style="font-size: 13px; color: #666;">
                    """ + (pairs[-1]['input_time'][:16] if pairs else 'N/A') + """ 至 """ + (
               pairs[0]['input_time'][:16] if pairs else 'N/A') + """
                </div>
            </div>
        </div>

        <!-- Tabs -->
        <div class="tabs">
            <button class="tab active" onclick="switchTab('input')">📥 LLM-INPUT</button>
            <button class="tab" onclick="switchTab('output')">📤 LLM-OUTPUT</button>
        </div>

        <!-- LLM-INPUT Tab -->
        <div id="inputTab" class="tab-content active">
            <div class="section-title">📥 LLM Input Events</div>
            <div id="inputTopLevelList" class="top-level-list"></div>
            <div id="inputContent"></div>
        </div>

        <!-- LLM-OUTPUT Tab -->
        <div id="outputTab" class="tab-content">
            <div class="section-title">📤 LLM Output Events</div>
            <div id="outputTopLevelList" class="top-level-list"></div>
            <div id="outputContent"></div>
        </div>
    </div>

    <script>
        // 所有记录数据
        const allRecords = """ + records_json + """;
        let filteredRecords = [...allRecords];
        let currentTab = 'input';

        // 初始化
        document.addEventListener('DOMContentLoaded', () => {
            renderTopLevelList('input');
        });

        // 按 Session 筛选
        function filterBySession() {
            const sessionId = document.getElementById('sessionFilter').value;
            const runId = document.getElementById('runFilter').value;
            applyFilters(sessionId, runId);
        }

        // 按 Run 筛选
        function filterByRun() {
            const runId = document.getElementById('runFilter').value;
            const sessionId = document.getElementById('sessionFilter').value;
            applyFilters(sessionId, runId);
        }

        // 应用筛选
        function applyFilters(sessionId, runId) {
            filteredRecords = allRecords.filter(r => {
                const matchSession = !sessionId || r.session_id === sessionId;
                const matchRun = !runId || r.run_id === runId;
                return matchSession && matchRun;
            });

            // 更新计数
            document.getElementById('filteredCount').textContent = filteredRecords.length;

            // 重新渲染
            renderTopLevelList(currentTab);
        }

        // 切换 Tab
        function switchTab(tab) {
            currentTab = tab;

            // 更新 Tab 样式
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');

            // 更新内容显示
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.getElementById(tab + 'Tab').classList.add('active');

            // 渲染顶层列表
            renderTopLevelList(tab);
        }

        // 渲染顶层元素列表
        function renderTopLevelList(tab) {
            const container = document.getElementById(tab + 'TopLevelList');
            const contentContainer = document.getElementById(tab + 'Content');

            if (filteredRecords.length === 0) {
                container.innerHTML = '<p style="color: #666; text-align: center; padding: 40px;">暂无数据</p>';
                contentContainer.innerHTML = '';
                return;
            }

            // 获取第一个记录的 event
            const eventKey = tab === 'input' ? 'input_event' : 'output_event';
            const firstEvent = JSON.parse(filteredRecords[0][eventKey]);
            const topLevelKeys = Object.keys(firstEvent);

            // 生成顶层元素按钮
            container.innerHTML = topLevelKeys.map(key => 
                '<div class="top-level-item" onclick="showTopLevelContent(\\'' + tab + '\\', \\'' + key + '\\')">' + key + '</div>'
            ).join('');

            // 默认显示第一个元素
            if (topLevelKeys.length > 0) {
                showTopLevelContent(tab, topLevelKeys[0]);
            }
        }

        // 显示顶层元素内容
        function showTopLevelContent(tab, topLevelKey) {
            const contentContainer = document.getElementById(tab + 'Content');

            // 更新按钮样式
            document.querySelectorAll('#' + tab + 'TopLevelList .top-level-item').forEach(item => {
                item.classList.remove('active');
                if (item.textContent.trim() === topLevelKey) {
                    item.classList.add('active');
                }
            });

            // 获取所有记录的该顶层元素数据
            const eventKey = tab === 'input' ? 'input_event' : 'output_event';
            const records = filteredRecords.map((r, index) => {
                const event = JSON.parse(r[eventKey]);
                return {
                    index: index + 1,
                    runId: r.run_id,
                    time: tab === 'input' ? r.input_time : r.output_time,
                    duration: r.duration_ms,
                    value: event[topLevelKey]
                };
            });

            // 生成内容 HTML
            let html = '<div class="top-level-content active">';
            html += '<h3 style="margin-bottom: 20px; color: #667eea;">' + topLevelKey + '</h3>';

            records.forEach(record => {
                html += '<div class="record-card">';
                html += '<div class="record-header">';
                html += '<div style="font-weight: bold; color: #667eea;">#<span style="color: #333;">' + record.index + '</span></div>';
                html += '<div class="record-info">';
                html += '<span>🔑 RunID: ' + record.runId + '</span>';
                html += '<span>🕐 ' + record.time + '</span>';
                html += '<span class="duration">⏱️ ' + record.duration + 'ms</span>';
                html += '</div></div>';

                // 使用树形展示
                html += '<div class="tree">';
                html += renderTree(record.value, topLevelKey);
                html += '</div>';

                // Token usage 特殊处理
                if (topLevelKey === 'usage') {
                    html += '<div class="token-usage">';
                    html += '<span>📊 Total: <strong>' + (record.value.total || 'N/A') + '</strong></span>';
                    html += '<span>📥 Input: <strong>' + (record.value.input || 'N/A') + '</strong></span>';
                    html += '<span>📤 Output: <strong>' + (record.value.output || 'N/A') + '</strong></span>';
                    html += '</div>';
                }

                html += '</div>';
            });

            html += '</div>';
            contentContainer.innerHTML = html;
        }

        // 渲染树形结构
        function renderTree(obj, key) {
            if (obj === null) {
                return '<div class="tree-item"><span class="tree-key">' + key + '</span>: <span class="null">null</span></div>';
            }

            if (typeof obj !== 'object') {
                return '<div class="tree-item"><span class="tree-key">' + key + '</span>: ' + formatValue(obj) + '</div>';
            }

            let html = '<div class="tree-item">';

            if (Array.isArray(obj)) {
                html += '<span class="tree-key tree-expanded" onclick="toggleTree(this)">';
                html += '<span class="tree-toggle">▼</span>[' + key + '] <span style="color: #666;">(Array[' + obj.length + '])</span></span>';
                html += '<div class="tree-children">';
                obj.forEach((item, index) => {
                    html += renderTree(item, '[' + index + ']');
                });
                html += '</div>';
            } else {
                html += '<span class="tree-key tree-expanded" onclick="toggleTree(this)">';
                html += '<span class="tree-toggle">▼</span>' + key + ' <span style="color: #666;">(Object)</span></span>';
                html += '<div class="tree-children">';
                for (const [k, v] of Object.entries(obj)) {
                    html += renderTree(v, k);
                }
                html += '</div>';
            }

            html += '</div>';
            return html;
        }

        // 切换树节点
        function toggleTree(element) {
            const parent = element.parentElement;
            if (parent.classList.contains('tree-collapsed')) {
                parent.classList.remove('tree-collapsed');
                parent.classList.add('tree-expanded');
            } else {
                parent.classList.remove('tree-expanded');
                parent.classList.add('tree-collapsed');
            }
        }

        // 格式化值
        function formatValue(value) {
            if (value === null) return '<span class="null">null</span>';
            if (typeof value === 'boolean') return '<span class="bool">' + value.toString() + '</span>';
            if (typeof value === 'number') return '<span class="number">' + value + '</span>';
            if (typeof value === 'string') {
                let displayValue = value;
                displayValue = displayValue
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;')
                    .replace(/\\n/g, '<br>');
                return '<span class="string">' + displayValue + '</span>';
            }
            return '<span class="other">' + value + '</span>';
        }
    </script>
</body>
</html>
"""

    # 写入文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)


def main():
    # 数据库路径
    db_path = r"D:\openclaw_src\openclaw\.data\workspace\.openclaw\llm-log.db"

    # 输出路径
    output_path = r"D:\PycharmProjects\PythonProject\output\llm-log-report.html"

    # 检查数据库文件
    if not Path(db_path).exists():
        print(f"❌ 数据库文件不存在：{db_path}")
        return

    print(f"📂 数据库：{db_path}")

    # 连接数据库
    conn = connect_db(db_path)
    print("✅ 数据库连接成功")

    # 获取 session_id 列表
    print("🔍 获取 Session ID 列表...")
    session_ids = fetch_session_ids(conn, limit=100)
    print(f"✅ 获取到 {len(session_ids)} 个 Session")

    # 获取 run_id 列表
    print("🔍 获取 Run ID 列表...")
    run_ids = fetch_run_ids(conn, limit=100)
    print(f"✅ 获取到 {len(run_ids)} 个 Run")

    # 获取数据
    print("🔍 查询数据...")
    pairs = fetch_llm_pairs(conn, limit=100)
    print(f"✅ 获取到 {len(pairs)} 条记录")

    # 生成 HTML
    print("📝 生成 HTML 报告...")
    generate_html(pairs, session_ids, run_ids, output_path)
    print(f"✅ HTML 报告已生成：{output_path}")

    # 关闭连接
    conn.close()

    # 自动打开
    import webbrowser
    webbrowser.open(output_path)
    print("🌐 已在浏览器中打开报告")


if __name__ == '__main__':
    main()

# =============================================================
# AION Connect — Server
# =============================================================
# Handles the web server for AION Connect.
# Serves the frontend and provides JSON APIs.

import sys
import os
import json
import sqlite3
from datetime import datetime

sys.path.insert(0, r'C:\Users\HomePC\Desktop\AION')

from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__,
            static_folder='static',
            static_url_path='/static')

DB_PATH = 'aion_connect.db'


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ideas (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            description TEXT,
            author      TEXT,
            tags        TEXT,
            upvotes     INTEGER DEFAULT 0,
            created     TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            idea_id INTEGER,
            author  TEXT,
            content TEXT,
            created TEXT
        )
    ''')

    # Seed sample data if empty
    cursor.execute('SELECT COUNT(*) FROM ideas')
    if cursor.fetchone()[0] == 0:
        ideas = [
            ('AI Resume Builder',
             'Build an AI-powered resume generator using AION language',
             'Emmanuel', 'ai python tool', 12,
             '2026-05-01'),
            ('Nigerian Slang Translator',
             'Translate Nigerian slang to formal English using AI',
             'Emmanuel', 'ai nigeria language', 8,
             '2026-05-02'),
            ('AION Web IDE',
             'Browser-based IDE for writing and running AION code online',
             'Emmanuel', 'aion tool web', 24,
             '2026-05-03'),
            ('Student Grade Tracker',
             'Track grades and get AI-powered study tips',
             'Emmanuel', 'education ai tool', 6,
             '2026-05-04'),
            ('Local Business Finder',
             'Find and discover local businesses in Nigerian cities',
             'Emmanuel', 'nigeria business location', 15,
             '2026-05-05'),
        ]
        cursor.executemany(
            'INSERT INTO ideas (title, description, author, tags, upvotes, created) VALUES (?,?,?,?,?,?)',
            ideas
        )

    conn.commit()
    conn.close()
    print('✓ Database ready')


# ── Routes ────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/api/status')
def status():
    return jsonify({
        'status':  'running',
        'version': '1.0.0',
        'name':    'AION Connect'
    })


@app.route('/api/ideas', methods=['GET'])
def get_ideas():
    conn   = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM ideas ORDER BY upvotes DESC')
    ideas  = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({'ideas': ideas, 'total': len(ideas)})


@app.route('/api/ideas', methods=['POST'])
def create_idea():
    data  = request.get_json()
    title = data.get('title', '').strip()
    desc  = data.get('description', '').strip()
    tags  = data.get('tags', '').strip()
    author = data.get('author', 'Anonymous').strip()

    if not title:
        return jsonify({'error': 'Title required'}), 400

    conn   = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO ideas (title, description, author, tags, upvotes, created) VALUES (?,?,?,?,?,?)',
        (title, desc, author, tags, 0,
         datetime.now().strftime('%Y-%m-%d'))
    )
    idea_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({'id': idea_id, 'success': True})


@app.route('/api/ideas/<int:idea_id>/upvote',
           methods=['POST'])
def upvote_idea(idea_id):
    conn   = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE ideas SET upvotes = upvotes + 1 WHERE id = ?',
        (idea_id,)
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/ideas/<int:idea_id>')
def get_idea(idea_id):
    conn   = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM ideas WHERE id = ?', (idea_id,))
    idea = cursor.fetchone()
    conn.close()
    if not idea:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(dict(idea))


if __name__ == '__main__':
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    print()
    print('  AION Connect v1.0.0')
    print('  Developer Community Platform')
    print('  ─────────────────────────────')
    print('  ✓ Running at http://localhost:5000')
    print('  Press Ctrl+C to stop')
    print()

    init_db()
    app.run(host='0.0.0.0', port=5000,
            debug=False, use_reloader=False)
import os
import sqlite3
from pathlib import Path
from typing import Dict, Any, List
from django.conf import settings
from .models import File, sanitize_name

DB_EXTENSIONS = ['.db', '.sqlite', '.sqlite3']

def list_user_databases(user) -> List[Dict[str, Any]]:
    """
    Scans user's files and disk directory for SQLite database files.
    Auto-registers any disk-created SQLite databases.
    """
    storage_base = getattr(settings, 'USER_STORAGE_ROOT', Path(settings.MEDIA_ROOT) / 'users')
    user_root = Path(storage_base) / str(user.id)
    if user_root.exists():
        for p in user_root.rglob('*'):
            if p.is_file() and p.suffix.lower() in DB_EXTENSIONS:
                rel_path = p.relative_to(user_root)
                parts = rel_path.parts
                folder = None
                file_name = parts[-1]

                existing = File.objects.filter(owner=user, name=file_name).first()
                if not existing:
                    size_kb = round(p.stat().st_size / 1024.0, 3)
                    File.objects.create(
                        owner=user,
                        name=file_name,
                        extension=p.suffix.lower(),
                        size_kb=size_kb
                    )

    db_files = File.objects.filter(owner=user, extension__in=DB_EXTENSIONS).order_by('-updated_at')
    result = []

    for f in db_files:
        disk_path = f.get_disk_path()
        tables_count = 0
        is_valid = False

        if disk_path.exists():
            try:
                uri = f"file:{disk_path.as_posix()}?mode=ro"
                with sqlite3.connect(uri, uri=True, timeout=2.0) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
                    tables_count = cursor.fetchone()[0]
                    is_valid = True
            except Exception:
                is_valid = False

        result.append({
            'id': f.id,
            'name': f.name,
            'extension': f.extension,
            'size_kb': round(f.size_kb, 2),
            'relative_path': f.get_relative_path(),
            'tables_count': tables_count,
            'is_valid': is_valid,
            'updated_at': f.updated_at.strftime('%Y-%m-%d %H:%M') if f.updated_at else ''
        })

    return result

def get_database_schema(user, file_id: int) -> Dict[str, Any]:
    """
    Returns the table list and column definitions for a given database file.
    """
    file_obj = File.objects.filter(id=file_id, owner=user).first()
    if not file_obj:
        raise ValueError("Ma'lumotlar bazasi fayli topilmadi.")

    disk_path = file_obj.get_disk_path()
    if not disk_path.exists():
        raise ValueError("Baza fayli diskda mavjud emas.")

    tables = []
    uri = f"file:{disk_path.as_posix()}?mode=ro"

    try:
        with sqlite3.connect(uri, uri=True, timeout=3.0) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
            table_names = [row[0] for row in cursor.fetchall()]

            for t_name in table_names:
                cursor.execute(f"PRAGMA table_info('{t_name}');")
                cols = cursor.fetchall()
                columns_info = [
                    {
                        'cid': c[0],
                        'name': c[1],
                        'type': c[2] or 'TEXT',
                        'notnull': bool(c[3]),
                        'dflt_value': c[4],
                        'pk': bool(c[5])
                    }
                    for c in cols
                ]

                try:
                    cursor.execute(f"SELECT count(*) FROM '{t_name}';")
                    row_count = cursor.fetchone()[0]
                except Exception:
                    row_count = 0

                tables.append({
                    'name': t_name,
                    'columns': columns_info,
                    'row_count': row_count
                })

    except Exception as e:
        raise ValueError(f"SQLite bazasini o'qishda xatolik: {str(e)}")

    return {
        'file_id': file_obj.id,
        'file_name': file_obj.name,
        'file_size_kb': round(file_obj.size_kb, 2),
        'tables': tables
    }

def get_table_data(user, file_id: int, table_name: str, page: int = 1, page_size: int = 25, search: str = "") -> Dict[str, Any]:
    """
    Safely fetches paginated table rows with optional search.
    """
    file_obj = File.objects.filter(id=file_id, owner=user).first()
    if not file_obj:
        raise ValueError("Ma'lumotlar bazasi fayli topilmadi.")

    disk_path = file_obj.get_disk_path()
    if not disk_path.exists():
        raise ValueError("Baza fayli diskda mavjud emas.")

    page = max(1, page)
    page_size = min(max(10, page_size), 100)
    offset = (page - 1) * page_size

    uri = f"file:{disk_path.as_posix()}?mode=ro"

    with sqlite3.connect(uri, uri=True, timeout=3.0) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = ?;", (table_name,))
        if not cursor.fetchone():
            raise ValueError(f"'{table_name}' nomli jadval topilmadi.")

        cursor.execute(f"PRAGMA table_info('{table_name}');")
        col_rows = cursor.fetchall()
        columns = [c['name'] for c in col_rows]
        column_meta = [{'name': c['name'], 'type': c['type'], 'pk': bool(c['pk'])} for c in col_rows]

        where_sql = ""
        params = []
        clean_search = search.strip()
        if clean_search and columns:
            conditions = [f'"{col}" LIKE ?' for col in columns]
            where_sql = f"WHERE ({' OR '.join(conditions)})"
            params = [f"%{clean_search}%" for _ in columns]

        count_query = f'SELECT count(*) FROM "{table_name}" {where_sql};'
        cursor.execute(count_query, params)
        total_rows = cursor.fetchone()[0]

        data_query = f'SELECT * FROM "{table_name}" {where_sql} LIMIT ? OFFSET ?;'
        cursor.execute(data_query, params + [page_size, offset])
        raw_rows = cursor.fetchall()

        rows = []
        for r in raw_rows:
            row_dict = {}
            for col in columns:
                val = r[col]
                if isinstance(val, (bytes, bytearray)):
                    val = f"<BLOB {len(val)} bytes>"
                row_dict[col] = val
            rows.append(row_dict)

        total_pages = (total_rows + page_size - 1) // page_size if total_rows > 0 else 1

        return {
            'file_id': file_obj.id,
            'table_name': table_name,
            'columns': column_meta,
            'total_rows': total_rows,
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages,
            'rows': rows
        }

def create_sample_database(user) -> Dict[str, Any]:
    """
    Creates a realistic sample SQLite database with users, orders, and bot_logs tables.
    """
    storage_base = getattr(settings, 'USER_STORAGE_ROOT', Path(settings.MEDIA_ROOT) / 'users')
    user_root = Path(storage_base) / str(user.id)
    user_root.mkdir(parents=True, exist_ok=True)

    base_name = "bot_database.db"
    file_path = user_root / base_name

    counter = 1
    while file_path.exists():
        base_name = f"bot_database_{counter}.db"
        file_path = user_root / base_name
        counter += 1

    with sqlite3.connect(file_path.as_posix()) as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                balance REAL DEFAULT 0.0,
                is_admin INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item_name TEXT NOT NULL,
                amount REAL NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cursor.executemany("""
            INSERT INTO users (telegram_id, username, first_name, balance, is_admin)
            VALUES (?, ?, ?, ?, ?);
        """, [
            (123456789, 'shohruh_dev', 'Shohruh', 50000.0, 1),
            (987654321, 'nodir_99', 'Nodir', 12500.0, 0),
            (554433221, 'malika_uz', 'Malika', 0.0, 0),
            (776655443, 'azamat_tg', 'Azamat', 250000.0, 0)
        ])

        cursor.executemany("""
            INSERT INTO orders (user_id, item_name, amount, status)
            VALUES (?, ?, ?, ?);
        """, [
            (1, 'Python Premium Kursi', 450000.0, 'completed'),
            (2, 'Telegram Bot Obunasi (1 oy)', 50000.0, 'completed'),
            (3, 'VIP Guruhga Kirish', 75000.0, 'pending'),
            (4, 'Server Hosting (1 yil)', 240000.0, 'completed')
        ])

        cursor.executemany("""
            INSERT INTO bot_logs (action, details)
            VALUES (?, ?);
        """, [
            ('BOT_START', 'Bot @pyhosting_demo_bot polling rejimida ishga tushdi'),
            ('COMMAND', '/start buyrug\'i qabul qilindi (user_id: 123456789)'),
            ('ORDER_CREATED', 'Yangi buyurtma #1 yaratildi'),
            ('PAYMENT_SUCCESS', 'To\'lov muvaffaqiyatli qabul qilindi (50,000 so\'m)')
        ])

        conn.commit()

    size_kb = round(file_path.stat().st_size / 1024.0, 3)
    file_obj = File.objects.create(
        owner=user,
        name=base_name,
        extension='.db',
        size_kb=size_kb
    )

    if hasattr(user, 'quota'):
        user.quota.recalculate_usage()

    return {
        'id': file_obj.id,
        'name': file_obj.name,
        'size_kb': size_kb,
        'message': f"'{base_name}' nomli namuna SQLite baza yaratildi!"
    }

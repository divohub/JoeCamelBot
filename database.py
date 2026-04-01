import aiosqlite
import datetime

import os

DB_PATH = os.getenv("DB_PATH", "data/shnyaga.db")

async def init_db():
    # Ensure directory exists
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
        
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                score INTEGER DEFAULT 0,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                description TEXT,
                points INTEGER,
                category TEXT,
                is_mega BOOLEAN DEFAULT 0,
                is_approved BOOLEAN DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                activity_id INTEGER,
                voter_id INTEGER,
                PRIMARY KEY (activity_id, voter_id),
                FOREIGN KEY (activity_id) REFERENCES activities (id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_memories (
                user_id INTEGER PRIMARY KEY,
                memory_text TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)

        await db.execute('''
            CREATE TABLE IF NOT EXISTS disputes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id INTEGER,
                chat_id INTEGER,
                message_id INTEGER,
                poll_id TEXT,
                status TEXT DEFAULT 'gathering',
                target_votes INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (activity_id) REFERENCES activities (id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS dispute_signatures (
                dispute_id INTEGER,
                user_id INTEGER,
                PRIMARY KEY (dispute_id, user_id),
                FOREIGN KEY (dispute_id) REFERENCES disputes (id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS audits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS audit_awards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                points INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        await db.commit()


async def get_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

async def update_user(user_id, username, full_name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (user_id, username, full_name) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET username = excluded.username, "
            "full_name = excluded.full_name, last_seen = CURRENT_TIMESTAMP",
            (user_id, username, full_name)
        )
        await db.commit()

async def update_score(user_id, points):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET score = score + ? WHERE user_id = ?", (points, user_id))
        await db.commit()

async def add_activity(user_id, description, points, category, is_mega=False, is_approved=True):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO activities (user_id, description, points, category, is_mega, is_approved) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, description, points, category, int(is_mega), int(is_approved))
        )
        activity_id = cursor.lastrowid
        await db.commit()
        return activity_id

async def apply_daily_penalty():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET score = score - 10")
        await db.commit()

async def get_top_users(limit=10):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users ORDER BY score DESC LIMIT ?", (limit,)) as cursor:
            return await cursor.fetchall()

async def get_user_activities(user_id, limit=5, offset=0):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM activities WHERE user_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?", (user_id, limit, offset)) as cursor:
            return await cursor.fetchall()

async def get_user_activities_count(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM activities WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def get_activity(activity_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM activities WHERE id = ?", (activity_id,)) as cursor:
            return await cursor.fetchone()

async def delete_activity(activity_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM activities WHERE id = ?", (activity_id,)) as cursor:
            activity = await cursor.fetchone()
            if activity:
                # If it was already approved, we need to revert the points
                if activity['is_approved']:
                    await db.execute("UPDATE users SET score = score - ? WHERE user_id = ?", (activity['points'], activity['user_id']))
                
                await db.execute("DELETE FROM votes WHERE activity_id = ?", (activity_id,))
                await db.execute("DELETE FROM activities WHERE id = ?", (activity_id,))
                await db.commit()
                return activity
    return None

async def add_vote(activity_id, voter_id):
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("INSERT INTO votes (activity_id, voter_id) VALUES (?, ?)", (activity_id, voter_id))
            await db.commit()
            async with db.execute("SELECT COUNT(*) FROM votes WHERE activity_id = ?", (activity_id,)) as cursor:
                count = (await cursor.fetchone())[0]
                return count
        except aiosqlite.IntegrityError:
            return -1

async def approve_activity(activity_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM activities WHERE id = ?", (activity_id,)) as cursor:
            activity = await cursor.fetchone()
            if activity and not activity['is_approved']:
                await db.execute("UPDATE activities SET is_approved = 1 WHERE id = ?", (activity_id,))
                await db.execute("UPDATE users SET score = score + ? WHERE user_id = ?", (activity['points'], activity['user_id']))
                await db.commit()
                return activity
    return None

async def get_setting(key, default=None):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default

async def set_setting(key, value):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        await db.commit()

async def get_user_memory(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT memory_text FROM user_memories WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def update_user_memory(user_id, memory_text):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO user_memories (user_id, memory_text, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(user_id) DO UPDATE SET memory_text = excluded.memory_text, updated_at = CURRENT_TIMESTAMP",
            (user_id, memory_text)
        )
        await db.commit()


async def create_dispute(activity_id, chat_id, message_id, target_votes):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO disputes (activity_id, chat_id, message_id, target_votes) VALUES (?, ?, ?, ?)",
            (activity_id, chat_id, message_id, target_votes)
        )
        dispute_id = cursor.lastrowid
        await db.commit()
        return dispute_id

async def get_dispute_by_activity(activity_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM disputes WHERE activity_id = ?", (activity_id,)) as cursor:
            return await cursor.fetchone()

async def add_dispute_signature(dispute_id, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("INSERT INTO dispute_signatures (dispute_id, user_id) VALUES (?, ?)", (dispute_id, user_id))
            await db.commit()
            async with db.execute("SELECT COUNT(*) FROM dispute_signatures WHERE dispute_id = ?", (dispute_id,)) as cursor:
                count = (await cursor.fetchone())[0]
                return count
        except aiosqlite.IntegrityError:
            return -1

async def update_dispute_poll(dispute_id, poll_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE disputes SET status = 'polling', poll_id = ? WHERE id = ?", (poll_id, dispute_id))
        await db.commit()

async def get_dispute_by_poll_id(poll_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM disputes WHERE poll_id = ?", (poll_id,)) as cursor:
            return await cursor.fetchone()

async def set_dispute_status(dispute_id, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE disputes SET status = ? WHERE id = ?", (status, dispute_id))
        await db.commit()

async def delete_dispute(dispute_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM dispute_signatures WHERE dispute_id = ?", (dispute_id,))
        await db.execute("DELETE FROM disputes WHERE id = ?", (dispute_id,))
        await db.commit()

async def add_audit(chat_id, comment):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO audits (chat_id, comment) VALUES (?, ?)", (chat_id, comment))
        await db.commit()

async def get_last_audits(chat_id, limit=3):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT comment FROM audits WHERE chat_id = ? ORDER BY created_at DESC LIMIT ?", (chat_id, limit)) as cursor:
            rows = await cursor.fetchall()
            return [row['comment'] for row in rows]

async def add_audit_award(user_id, points):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO audit_awards (user_id, points) VALUES (?, ?)", (user_id, points))
        await db.commit()

async def check_audit_cooldown(user_id, hours=3):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT created_at FROM audit_awards WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return True
            last_time_str = row['created_at']
            # Parse SQLite default timestamp
            # SQLite default CURRENT_TIMESTAMP format is 'YYYY-MM-DD HH:MM:SS'
            import datetime
            last_time = datetime.datetime.strptime(last_time_str, '%Y-%m-%d %H:%M:%S')
            now = datetime.datetime.utcnow()
            if (now - last_time).total_seconds() >= hours * 3600:
                return True
            return False

"""Additive identity foundation for a database bound to one trading store."""
import hashlib
import secrets
import sqlite3
from datetime import datetime, timezone

ITERATIONS = 600_000


def hash_password(password):
    if not 12 <= len(password) <= 128 or not password.isascii() or not password.isprintable():
        raise ValueError('현재 Basic 인증의 비밀번호는 출력 가능한 ASCII 12~128자여야 합니다.')
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, ITERATIONS)
    return f'pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}'


def verify_password(password, encoded):
    try:
        algorithm, iterations, salt, digest = encoded.split('$')
        if algorithm != 'pbkdf2_sha256' or int(iterations) != ITERATIONS or len(password) > 128:
            return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), int(iterations))
        return secrets.compare_digest(actual.hex(), digest)
    except (ValueError, TypeError):
        return False


DUMMY_HASH = f"pbkdf2_sha256${ITERATIONS}${'00'*16}${'00'*32}"


def migrate_identity(db, store_id, store_name):
    """Caller owns one transaction; unknown versions must never be downgraded."""
    db.execute('CREATE TABLE IF NOT EXISTS identity_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)')
    versions = {r[0] for r in db.execute('SELECT version FROM identity_migrations')}
    if versions - {1, 2}:
        raise RuntimeError('지원하지 않는 계정 DB 버전입니다. 서버 버전을 확인하세요.')
    if 1 not in versions:
        for sql in [
            """CREATE TABLE stores(id TEXT PRIMARY KEY NOT NULL, name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)))""",
            """CREATE TABLE owner_accounts(id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)))""",
            """CREATE TABLE store_memberships(store_id TEXT NOT NULL REFERENCES stores(id),
                owner_id INTEGER NOT NULL REFERENCES owner_accounts(id),
                active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)), PRIMARY KEY(store_id,owner_id))""",
            """CREATE TABLE deployment_store(singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                store_id TEXT NOT NULL REFERENCES stores(id))""",
        ]:
            db.execute(sql)
        db.execute('INSERT INTO stores(id,name) VALUES (?,?)', (store_id, store_name))
        db.execute('INSERT INTO deployment_store VALUES(1,?)', (store_id,))
        db.execute('INSERT INTO identity_migrations VALUES(1,?)', (datetime.now(timezone.utc).isoformat(),))
    bound = db.execute('SELECT store_id FROM deployment_store WHERE singleton=1').fetchone()
    if not bound or bound[0] != store_id:
        raise RuntimeError('이 DB는 다른 매장에 연결되어 있습니다. STORE_ID를 임의 변경할 수 없습니다.')
    if 2 not in versions:
        db.execute('''CREATE TABLE membership_audit (
            id INTEGER PRIMARY KEY, store_id TEXT NOT NULL REFERENCES stores(id),
            owner_id INTEGER NOT NULL REFERENCES owner_accounts(id),
            action TEXT NOT NULL CHECK(action IN ('grant','revoke')),
            reason TEXT NOT NULL, operator TEXT NOT NULL, created_at TEXT NOT NULL)''')
        db.execute('INSERT INTO identity_migrations VALUES(2,?)', (datetime.now(timezone.utc).isoformat(),))


class IdentityMixin:
    def memberships(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('''SELECT a.username,a.active account_active,
                m.active membership_active,s.id store_id,s.active store_active
                FROM store_memberships m JOIN owner_accounts a ON a.id=m.owner_id
                JOIN stores s ON s.id=m.store_id WHERE m.store_id=? ORDER BY a.username''', (self.store_id,))]

    def change_membership(self, username, active, reason, operator):
        reason, operator = reason.strip(), operator.strip()
        if not reason or len(reason) > 300 or not operator or len(operator) > 200:
            raise ValueError('변경 사유(1~300자)와 작업자(1~200자)가 필요합니다.')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            account = db.execute('SELECT id,active FROM owner_accounts WHERE username=?', (username,)).fetchone()
            if not account:
                raise ValueError('계정을 찾을 수 없습니다.')
            if active:
                current_store = db.execute('SELECT active FROM stores WHERE id=?', (self.store_id,)).fetchone()
                if not account['active'] or not current_store or not current_store['active']:
                    raise ValueError('비활성 계정 또는 매장에는 소속 권한을 부여할 수 없습니다.')
            membership = db.execute('SELECT active FROM store_memberships WHERE store_id=? AND owner_id=?',
                                    (self.store_id, account['id'])).fetchone()
            if (membership is not None and bool(membership['active']) == active) or (membership is None and not active):
                return False
            db.execute('''INSERT INTO store_memberships(store_id,owner_id,active) VALUES(?,?,?)
                ON CONFLICT(store_id,owner_id) DO UPDATE SET active=excluded.active''',
                (self.store_id, account['id'], int(active)))
            db.execute('''INSERT INTO membership_audit(store_id,owner_id,action,reason,operator,created_at)
                VALUES(?,?,?,?,?,?)''', (self.store_id, account['id'], 'grant' if active else 'revoke',
                                        reason, operator, datetime.now(timezone.utc).isoformat()))
            return True

    def membership_history(self, limit=100):
        if not 1 <= limit <= 1000:
            raise ValueError('조회 개수는 1~1000입니다.')
        with self.connect() as db:
            return [dict(row) for row in db.execute('''SELECT h.id,a.username,h.action,h.reason,h.operator,h.created_at
                FROM membership_audit h JOIN owner_accounts a ON a.id=h.owner_id
                WHERE h.store_id=? ORDER BY h.id DESC LIMIT ?''', (self.store_id, limit))]

    def authenticate_owner(self, username, password):
        with self.connect() as db:
            row = db.execute('SELECT * FROM owner_accounts WHERE username=?', (username,)).fetchone()
        valid = verify_password(password, row['password_hash'] if row else DUMMY_HASH)
        if not row or not valid or not row['active']:
            self.error(401, '점주 아이디 또는 비밀번호가 올바르지 않습니다.')
        return dict(id=row['id'], username=row['username'])

    def owner_stores(self, owner_id):
        with self.connect() as db:
            return [dict(r) for r in db.execute('''SELECT s.id,s.name FROM stores s
                JOIN store_memberships m ON m.store_id=s.id JOIN owner_accounts a ON a.id=m.owner_id
                WHERE m.owner_id=? AND m.active=1 AND s.active=1 AND a.active=1 ORDER BY s.id''', (owner_id,))]

    def require_store(self, owner_id):
        if not any(s['id'] == self.store_id for s in self.owner_stores(owner_id)):
            self.error(403, '현재 매장에 접근할 권한이 없습니다.')

    def provision_owner(self, username, password):
        if not username or len(username) > 80 or username != username.strip() or ':' in username or not username.isascii():
            raise ValueError('아이디는 공백 없는 ASCII 1~80자이며 콜론을 포함할 수 없습니다.')
        if any(c.isspace() or ord(c) < 33 for c in username):
            raise ValueError('아이디에는 공백/제어문자를 사용할 수 없습니다.')
        encoded = hash_password(password)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM owner_accounts WHERE username=?', (username,)).fetchone():
                raise ValueError('이미 존재하는 계정입니다. 비밀번호를 덮어쓰지 않았습니다.')
            cursor = db.execute('INSERT INTO owner_accounts(username,password_hash) VALUES (?,?)', (username, encoded))
            db.execute('INSERT INTO store_memberships(store_id,owner_id) VALUES (?,?)', (self.store_id, cursor.lastrowid))

    def set_owner_active(self, username, active):
        with self.connect() as db:
            if not db.execute('UPDATE owner_accounts SET active=? WHERE username=?', (int(active), username)).rowcount:
                raise ValueError('계정을 찾을 수 없습니다.')

    def reset_owner_password(self, username, password):
        encoded = hash_password(password)
        with self.connect() as db:
            if not db.execute('UPDATE owner_accounts SET password_hash=? WHERE username=?', (encoded, username)).rowcount:
                raise ValueError('계정을 찾을 수 없습니다.')

    def backup(self, destination):
        from pathlib import Path
        target = Path(destination)
        # Exclusive creation prevents accidental overwrite of an existing backup.
        with target.open('xb'):
            pass
        with self.connect() as source:
            copy = sqlite3.connect(str(target))
            try:
                source.backup(copy)
            finally:
                copy.close()

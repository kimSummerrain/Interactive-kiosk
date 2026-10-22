"""Device registration and anonymous ordering sessions; raw credentials are never stored."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4


def now():
    return datetime.now(timezone.utc)


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def initialize_kiosk(db):
    for sql in [
        '''CREATE TABLE IF NOT EXISTS kiosk_pairings(
            code_hash TEXT PRIMARY KEY, name TEXT NOT NULL, expires_at TEXT NOT NULL, used INTEGER NOT NULL DEFAULT 0)''',
        '''CREATE TABLE IF NOT EXISTS kiosk_devices(
            id TEXT PRIMARY KEY, store_id TEXT NOT NULL REFERENCES stores(id), name TEXT NOT NULL,
            token_hash TEXT NOT NULL UNIQUE, active INTEGER NOT NULL DEFAULT 1, last_seen TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS kiosk_sessions(
            id TEXT PRIMARY KEY, device_id TEXT NOT NULL REFERENCES kiosk_devices(id),
            token_hash TEXT NOT NULL UNIQUE, expires_at TEXT NOT NULL, hard_expires_at TEXT NOT NULL,
            ended INTEGER NOT NULL DEFAULT 0, face INTEGER NOT NULL DEFAULT 0,
            voice INTEGER NOT NULL DEFAULT 0, recommendation INTEGER NOT NULL DEFAULT 0)''',
        '''CREATE TABLE IF NOT EXISTS kiosk_order_links(
            order_id INTEGER PRIMARY KEY REFERENCES orders(id),
            session_id TEXT NOT NULL UNIQUE REFERENCES kiosk_sessions(id))''',
        '''CREATE INDEX IF NOT EXISTS kiosk_session_device ON kiosk_sessions(device_id,ended)''',
        '''CREATE TABLE IF NOT EXISTS kiosk_audit(
            id INTEGER PRIMARY KEY, store_id TEXT NOT NULL REFERENCES stores(id),
            device_id TEXT NOT NULL REFERENCES kiosk_devices(id), device_name TEXT NOT NULL,
            action TEXT NOT NULL CHECK(action IN ('register','revoke')), operator TEXT,
            reason TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)''',
        '''CREATE INDEX IF NOT EXISTS kiosk_audit_store_time ON kiosk_audit(store_id,created_at,id)''',
        '''CREATE INDEX IF NOT EXISTS kiosk_audit_device_time ON kiosk_audit(store_id,device_id,created_at,id)''',
    ]:
        db.execute(sql)
    if 'issued_by' not in {r[1] for r in db.execute('PRAGMA table_info(kiosk_pairings)')}:
        db.execute('ALTER TABLE kiosk_pairings ADD COLUMN issued_by TEXT')
    if 'session_id' not in {r[1] for r in db.execute('PRAGMA table_info(quotes)')}:
        db.execute('ALTER TABLE quotes ADD COLUMN session_id TEXT REFERENCES kiosk_sessions(id)')


class KioskMixin:
    def pairing(self, name, operator=None):
        code = secrets.token_urlsafe(24)
        expires = (now() + timedelta(minutes=10)).isoformat()
        with self.connect() as db:
            db.execute('DELETE FROM kiosk_pairings WHERE expires_at < ?', (now().isoformat(),))
            db.execute('INSERT INTO kiosk_pairings(code_hash,name,expires_at,issued_by) VALUES(?,?,?,?)',
                       (digest(code), name, expires, operator))
        return dict(code=code, expires_at=expires)

    def register_device(self, code):
        token, device_id = secrets.token_urlsafe(32), str(uuid4())
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM kiosk_pairings WHERE code_hash=? AND used=0 AND expires_at>?',
                             (digest(code), now().isoformat())).fetchone()
            if not row:
                self.error(401, '등록 코드가 잘못되었거나 만료되었습니다.')
            if not db.execute('SELECT 1 FROM stores WHERE id=? AND active=1', (self.store_id,)).fetchone():
                self.error(403, '운영하지 않는 매장입니다.')
            db.execute('UPDATE kiosk_pairings SET used=1 WHERE code_hash=?', (digest(code),))
            db.execute('INSERT INTO kiosk_devices(id,store_id,name,token_hash,last_seen) VALUES(?,?,?,?,?)',
                       (device_id,self.store_id,row['name'],digest(token),now().isoformat()))
            self.record_kiosk_event(db, device_id, row['name'], 'register', row['issued_by'])
        return dict(device_id=device_id, store_id=self.store_id, device_token=token)

    def device(self, db, token):
        row = db.execute('''SELECT d.* FROM kiosk_devices d JOIN stores s ON s.id=d.store_id
            WHERE d.token_hash=? AND d.active=1 AND s.active=1 AND d.store_id=?''',
                         (digest(token),self.store_id)).fetchone()
        if not row:
            self.error(401, '등록된 키오스크 인증이 필요합니다.')
        return row

    def heartbeat(self, token):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            device = self.device(db, token)
            db.execute('UPDATE kiosk_devices SET last_seen=? WHERE id=?', (now().isoformat(), device['id']))
        return {'ok': True}

    def devices(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT id,name,active,last_seen FROM kiosk_devices WHERE store_id=? ORDER BY name,id', (self.store_id,))]

    def revoke_device(self, device_id, operator=None, reason=''):
        reason = reason.strip()
        if len(reason) > 300:
            self.error(422, '회수 사유는 300자 이하로 입력해 주세요.')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            device = db.execute('SELECT name,active FROM kiosk_devices WHERE id=? AND store_id=?',
                                (device_id, self.store_id)).fetchone()
            if not device:
                self.error(404, '기기를 찾을 수 없습니다.')
            if not device['active']:
                return {'ok': True}
            db.execute('UPDATE kiosk_devices SET active=0 WHERE id=?', (device_id,))
            db.execute('UPDATE kiosk_sessions SET ended=1,face=0,voice=0,recommendation=0 WHERE device_id=?', (device_id,))
            self.record_kiosk_event(db, device_id, device['name'], 'revoke', operator, reason)
        return {'ok': True}

    def record_kiosk_event(self, db, device_id, name, action, operator, reason=''):
        db.execute('''INSERT INTO kiosk_audit(store_id,device_id,device_name,action,operator,reason,created_at)
            VALUES(?,?,?,?,?,?,?)''',
            (self.store_id, device_id, name, action, operator, reason, now().isoformat()))

    def kiosk_history(self, start, end, device_id=None, action=None, page=1, page_size=20):
        if start == datetime.min.date() or start > end or (end-start).days > 366 or end == datetime.max.date():
            self.error(422, '조회 기간은 시작일 이후 최대 366일로 지정해 주세요.')
        if page < 1 or not 1 <= page_size <= 100 or action not in (None, 'register', 'revoke'):
            self.error(422, '이력 조회 조건을 확인해 주세요.')
        seoul = timezone(timedelta(hours=9))
        lower = datetime.combine(start, datetime.min.time(), seoul).astimezone(timezone.utc).isoformat()
        upper = datetime.combine(end+timedelta(days=1), datetime.min.time(), seoul).astimezone(timezone.utc).isoformat()
        where = 'store_id=? AND created_at>=? AND created_at<?'
        params = [self.store_id, lower, upper]
        if device_id is not None:
            where += ' AND device_id=?'
            params.append(device_id)
        if action is not None:
            where += ' AND action=?'
            params.append(action)
        with self.connect() as db:
            # Count and page share one read snapshot while devices are being registered/revoked.
            db.execute('BEGIN')
            total = db.execute(f'SELECT COUNT(*) FROM kiosk_audit WHERE {where}', params).fetchone()[0]
            events = [dict(row) for row in db.execute(f'''SELECT id,device_id,device_name,action,operator,reason,created_at
                FROM kiosk_audit WHERE {where} ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?''',
                [*params, page_size, (page-1)*page_size])]
        return dict(events=events, total=total, page=page, page_size=page_size)

    def start_session(self, token):
        session_token, session_id = secrets.token_urlsafe(32), str(uuid4())
        instant = now()
        expires = (instant + timedelta(minutes=15)).isoformat()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            device = self.device(db, token)
            # Starting a new customer invalidates the previous customer's credentials on this device only.
            db.execute('UPDATE kiosk_sessions SET ended=1,face=0,voice=0,recommendation=0 WHERE device_id=? AND ended=0', (device['id'],))
            db.execute('INSERT INTO kiosk_sessions(id,device_id,token_hash,expires_at,hard_expires_at) VALUES(?,?,?,?,?)',
                       (session_id,device['id'],digest(session_token),expires,(instant+timedelta(hours=1)).isoformat()))
            db.execute('UPDATE kiosk_devices SET last_seen=? WHERE id=?', (instant.isoformat(),device['id']))
        return dict(session_id=session_id, session_token=session_token, expires_at=expires,
                    preferences=dict(face=False, voice=False, recommendation=False))

    def session(self, db, token):
        instant = now()
        row = db.execute('''SELECT x.* FROM kiosk_sessions x JOIN kiosk_devices d ON d.id=x.device_id
            JOIN stores s ON s.id=d.store_id WHERE x.token_hash=? AND x.ended=0 AND x.expires_at>?
            AND x.hard_expires_at>? AND d.active=1 AND s.active=1 AND d.store_id=?''',
                         (digest(token),instant.isoformat(),instant.isoformat(),self.store_id)).fetchone()
        if not row:
            self.error(401, '주문 세션이 없거나 만료되었습니다.')
        expires = min((instant+timedelta(minutes=15)).isoformat(),row['hard_expires_at'])
        db.execute('UPDATE kiosk_sessions SET expires_at=? WHERE id=?', (expires,row['id']))
        return row

    def require_recommendation(self, token):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            session = self.session(db, token)
            if not session['face'] or not session['recommendation']:
                self.error(403, '사진 분석과 추천을 먼저 허용해 주세요.')

    def preferences(self, token, changes):
        if not set(changes).issubset({'face', 'voice', 'recommendation'}):
            self.error(422, '지원하지 않는 세션 설정입니다.')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            session = self.session(db, token)
            if changes:
                db.execute(f"UPDATE kiosk_sessions SET {','.join(k+'=?' for k in changes)} WHERE id=?", [*changes.values(),session['id']])
            row = db.execute('SELECT face,voice,recommendation FROM kiosk_sessions WHERE id=?',(session['id'],)).fetchone()
        return {k:bool(row[k]) for k in row.keys()}

    def end_session(self, token):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            session = self.session(db, token)
            db.execute('UPDATE kiosk_sessions SET ended=1,face=0,voice=0,recommendation=0 WHERE id=?', (session['id'],))
        return {'ok': True}

    def session_order(self, token, order_id):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            session = self.session(db, token)
            if not db.execute('SELECT 1 FROM kiosk_order_links WHERE order_id=? AND session_id=?', (order_id,session['id'])).fetchone():
                self.error(404, '주문을 찾을 수 없습니다.')
            return self.read_order(db, order_id)

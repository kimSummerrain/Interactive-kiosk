"""Local-only account administration; never expose as an HTTP endpoint."""
import argparse
import getpass
import json
import os
import sqlite3
from pathlib import Path

from src.config import BACKEND_ROOT, Settings
from src.storage import Store


def main():
    parser = argparse.ArgumentParser(description='매장 점주 계정 및 SQLite 백업 관리')
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('create-owner')
    create.add_argument('--username', required=True)
    for command in ('disable-owner', 'enable-owner', 'reset-password'):
        commands.add_parser(command).add_argument('--username', required=True)
    commands.add_parser('backup').add_argument('--output', required=True)
    for command in ('grant-membership', 'revoke-membership'):
        membership = commands.add_parser(command)
        membership.add_argument('--username', required=True)
        membership.add_argument('--reason', required=True)
    commands.add_parser('list-memberships')
    commands.add_parser('membership-history').add_argument('--limit', type=int, default=100)
    args = parser.parse_args()
    settings = Settings.load()
    store = Store(settings.sqlite_db_path, os.getenv('STORE_ID', 'primary'), os.getenv('STORE_NAME', '기본 매장'))
    try:
        if args.command == 'backup':
            if not Path(store.path).is_file():
                raise ValueError('백업할 DB 파일이 없습니다.')
            store.backup(args.output)
            print('백업 완료. 기존 파일을 덮어쓰지 않았습니다.')
            return
        store.initialize(seed_path=BACKEND_ROOT / 'data/seed.db')
        if args.command == 'list-memberships':
            print(json.dumps(store.memberships(), ensure_ascii=False, indent=2))
            return
        if args.command == 'membership-history':
            print(json.dumps(store.membership_history(args.limit), ensure_ascii=False, indent=2))
            return
        if args.command in ('grant-membership', 'revoke-membership'):
            changed = store.change_membership(args.username, args.command == 'grant-membership',
                                             args.reason, getpass.getuser())
            print('매장 소속 변경 및 이력 기록 완료.' if changed else '이미 요청한 상태입니다. 변경하지 않았습니다.')
            return
        if args.command in ('create-owner', 'reset-password'):
            password = getpass.getpass('새 비밀번호(ASCII 12~128자): ')
            if password != getpass.getpass('비밀번호 확인: '):
                raise ValueError('비밀번호가 일치하지 않습니다.')
            if args.command == 'create-owner':
                store.provision_owner(args.username, password)
                print('점주 계정과 현재 매장 소속 등록 완료.')
            else:
                store.reset_owner_password(args.username, password)
                print('비밀번호 재설정 완료. 계정 활성 상태는 유지됩니다.')
        else:
            store.set_owner_active(args.username, args.command == 'enable-owner')
            print('점주 계정 상태 변경 완료. 다음 인증 요청부터 적용됩니다.')
    except (ValueError, RuntimeError, sqlite3.Error, OSError) as exc:
        parser.exit(1, f'실패: {exc}\n')


if __name__ == '__main__':
    main()

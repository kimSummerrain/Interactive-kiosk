# 매장·점주 계정 기반 및 안전한 전환

## 1. 이번 구현 범위

SQLite에 stores / owner_accounts / store_memberships / deployment_store / identity_migrations를 추가한다.
기존 메뉴·주문 테이블은 그대로 유지한다. 한 DB의 거래 데이터는 deployment_store의 매장 하나에 귀속된다.
매장 목록/소속 모델은 여러 매장을 표현할 수 있지만, 거래 데이터를 매장별로 분리한 다매장 DB는 아직 아니다.
STORE_ID를 변경해 다른 매장 데이터로 재해석하지 못하도록 시작 시 DB에 저장된 ID와 비교한다.

PostgreSQL 전환·공유 DB 다매장 거래·Bearer 토큰·고객 기기 인증은 이번 구현에 포함하지 않았다.
기존 SQLite 전용 SQL을 이관하고 동일 DB 엔진에서 통합 검증한 뒤 별도 단계로 전환한다.

## 2. DB 계정 모드로 전환

저장소 루트 PowerShell에서 실행한다. 먼저 운영 서버를 중지하고 백업한다.
백업에는 주문 및 계정 해시가 포함될 수 있으므로 저장소 외부에 보관한다.

```powershell
.venv\Scripts\python.exe apps/backend/manage.py backup --output C:/SmartKiosk/kiosk-before-identity.db
.venv\Scripts\python.exe apps/backend/manage.py create-owner --username owner1
```

백업은 SQLite backup API를 사용하며 기존 파일이 있으면 실패한다. DB가 없는 신규 환경은 백업 단계를 생략한다.
create-owner는 현재 STORE_ID에 점주를 연결한다. 기존 username이 있으면 비밀번호나 권한을 덮어쓰지 않는다.
비밀번호는 화면에 표시되지 않는 대화형 입력으로 두 번 받으며 CLI 인수·로그에 기록하지 않는다.
현재 Basic 구현과 호환되도록 출력 가능한 ASCII 12~128자로 제한한다.

`apps/backend/.env`:

```dotenv
STORE_ID=primary
STORE_NAME=기본 매장
OWNER_AUTH_MODE=database
```

기존 .env의 다른 설정은 유지한다. 최초 초기화 뒤 STORE_ID를 바꾸면 서버가 시작되지 않는다.
STORE_NAME은 최초 등록에만 사용하며 기존 매장 이름을 자동 덮어쓰지 않는다.
서버 재시작 후 등록한 계정으로 `/api/owner/me` 및 `/api/owner/stores`를 확인한다.
현재 운영 DB나 .env를 개발 과정에서 자동으로 변경하지 않는다.

## 3. 인증 정책

- legacy(기본): 기존 ADMIN_USERNAME/ADMIN_PASSWORD, 기존 웹 호환 모드. DB 계정·소속 검사를 사용하지 않는다.
- database: owner_accounts의 비밀번호 해시/활성 상태와 현재 매장 소속/활성 상태를 검사한다.
- database에서는 ADMIN_PASSWORD로 fallback하지 않는다. 기존 /api/admin 별칭·CSV도 같은 검사를 적용한다.
- 인증 실패/비활성 계정은 401, 현재 매장 권한 없음 또는 비활성 매장은 403.
- HTTPS 필요. 요청마다 Basic 인증을 수행하며 access/refresh 토큰·로그아웃·로그인 시도 제한은 미구현이다.
- PBKDF2-HMAC-SHA256 600,000회, 무작위 salt, 상수 시간 해시 비교. [OWASP 참고](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).

## 4. OWN-014 — 내 매장 목록

GET `/api/owner/stores`, DB 계정의 Basic 인증 필수. 입력 없음.

```json
{"stores":[{"id":"primary","name":"기본 매장"}],"active_store_id":"primary"}
```

활성 계정의 활성 소속/매장만 반환한다. 소속이 없으면 빈 배열이며 그 계정의 거래 API는 403이다.
active_store_id는 현재 서버 DB가 처리하는 매장 ID이며 이 응답으로 매장을 전환할 수 없다.
legacy 모드에서는 503이다. 비밀번호 해시·계정 내부 키는 반환하지 않는다.

## 5. 운영 명령

```powershell
.venv\Scripts\python.exe apps/backend/manage.py disable-owner --username owner1
.venv\Scripts\python.exe apps/backend/manage.py enable-owner --username owner1
.venv\Scripts\python.exe apps/backend/manage.py reset-password --username owner1
```

비활성화/재설정은 다음 인증부터 적용한다. 이미 실행 중인 요청을 중단하지는 않는다.
비밀번호 재설정은 계정 활성 상태를 바꾸지 않는다. 계정 공개 가입/원격 관리 API는 제공하지 않는다.
현재 서버 매장에 대한 소속 부여·회수 및 조회 명령:

```powershell
.venv\Scripts\python.exe apps/backend/manage.py list-memberships
.venv\Scripts\python.exe apps/backend/manage.py revoke-membership --username owner1 --reason "운영 담당 변경"
.venv\Scripts\python.exe apps/backend/manage.py grant-membership --username owner1 --reason "운영 담당 복귀"
.venv\Scripts\python.exe apps/backend/manage.py membership-history --limit 100
```

등록된 계정에 대해서만 실행하며 소속 변경 대상은 현재 DB의 STORE_ID로 고정된다.
소속 회수는 계정 삭제/비활성화와 다르며 다른 매장 소속을 변경하지 않는다.
비활성 계정 또는 매장에는 소속을 부여할 수 없다. 부여 명령이 계정을 자동 활성화하지 않는다.
같은 상태를 재요청하면 변경과 이력을 생략한다. 변경 사유는 앞뒤 공백 제외 1~300자다.
소속 변경과 membership_audit의 기록은 한 트랜잭션이며 이력 저장 실패 시 권한 변경도 롤백된다.
작업자는 로컬 OS 사용자명으로 기록한다. 이는 암호학적으로 검증된 사용자 신원이나 변조 방지 로그가 아니다.
최초 계정 생성·계정 활성 상태·비밀번호 변경은 이 소속 변경 이력에 포함하지 않는다.
마지막 점주의 소속 회수도 허용된다. 이 경우 로컬 운영자가 grant-membership으로 복구할 수 있다.
이 기능은 신뢰할 수 있는 로컬 운영 명령이며 점주가 자기 권한을 올리는 HTTP API를 제공하지 않는다.

## 6. 이관·복구 정책

identity_migrations 1번은 트랜잭션으로 테이블과 매장 연결을 생성한다. 실패하면 해당 단계 전체가 롤백된다.
2번은 membership_audit 테이블을 추가한다. 버전 1 DB의 기존 계정·소속을 유지하며 반복 적용하지 않는다.
버전 2 적용 뒤 버전 1만 지원하는 이전 서버는 시작을 거부한다. 롤백은 백업/코드 버전을 함께 복구한다.
미지원 버전 또는 다른 STORE_ID 연결은 시작을 거부한다. 재실행은 기존 계정·거래를 유지한다.
이 버전 관리는 새 계정 스키마 전용이며 기존 카탈로그 이관 전체를 대체하지 않는다.
되돌릴 때는 서버를 중지하고 백업 DB와 그 시점 코드/설정을 함께 복구한다.
백업 이후 새 주문이 있으면 복구로 유실될 수 있으므로 임의로 덮어쓰지 말고 변경 데이터를 먼저 보존한다.
legacy로 되돌리는 것은 공용 계정을 다시 활성화하는 권한 정책 변경이므로 자동 fallback하지 않는다.

## 7. 검증

신규/기존 DB 이관, 반복/동시 초기화, 부분 실패 롤백, 미지원 버전 차단, 매장 재연결 거부,
백업 보존/덮어쓰기 거부, 해시 검증, 중복 계정 원자성, 기존 계정 우회 차단,
소속/매장/계정 비활성화, 비밀번호 재설정과 기존 메뉴·주문·통계·CSV 회귀 테스트.

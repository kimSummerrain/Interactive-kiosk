# 개발 가이드

프로젝트 개요는 [README](../README.md)를 참고하세요. 이 문서는 개발 환경 구성과 API 연동을 설명합니다.

## 실행

아래 명령은 저장소 루트에서 실행합니다. `.env`는 실행 위치와 관계없이 `apps/backend/.env`에서 읽습니다. 상대 경로 `SQLITE_DB_PATH` 역시 `apps/backend` 기준입니다.


Python 3.9 이상에서 실행할 수 있습니다. 신규 배포는 Python 3.11 이상을 권장합니다.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r apps/backend/requirements.txt
Copy-Item apps/backend/.env.example apps/backend/.env
# apps/backend/.env의 ADMIN_PASSWORD를 직접 설정하세요. 기본 비밀번호는 없습니다.
.venv\Scripts\python.exe -m uvicorn app:app --app-dir apps/backend --host 127.0.0.1 --port 8000 --reload
```

환경 변수:

| 변수 | 기본값 / 용도 |
| --- | --- |
| `ADMIN_USERNAME` | `admin` |
| `ADMIN_PASSWORD` | 기본값 없음. 미설정 시 관리자 API는 503 응답 |
| `SQLITE_DB_PATH` | `apps/backend/instance/kiosk.db` |
| `SERVE_WEB` | `true`. `false`면 프론트 파일 없이 API 서버만 실행 |
| `CORS_ORIGINS` | `http://localhost:8000,http://127.0.0.1:8000` (쉼표 구분) |

최초 실행 시 기존 메뉴 DB인 `apps/backend/data/seed.db`를 실행용 DB로 복사하고 주문 테이블을 추가합니다. 원본 DB와 기존 메뉴 가격/연령별 집계는 유지합니다. 새 빈 DB에는 기본 메뉴 14개를 생성합니다. 과거 데이터에는 개별 주문 기록이 없어 관리자 판매내역으로 역산하지 않습니다.

## 주문 및 관리자 기능

- 메뉴 ID와 수량으로 주문합니다. 금액·메뉴 이름은 서버 DB를 기준으로 계산하고 주문 당시 값을 저장합니다.
- `request_id`는 UUID입니다. 네트워크 오류 시 **동일한 UUID와 동일한 본문**으로 재전송하면 기존 주문을 반환합니다. 같은 UUID에 다른 내용은 409입니다.
- 주문 상태: `pending` → `preparing` → `completed`. 미결제 상태에서만 `cancelled`로 변경할 수 있습니다.
- 결제 상태: 신규 주문은 `unpaid`. 관리자가 카운터 결제를 확인하면 `paid`가 됩니다. 결제 확인 전에는 주문을 완료할 수 없습니다.
- 결제 단말기/PG 및 자동 환불은 연결하지 않았습니다. 결제 완료 표시는 관리자의 수동 확인입니다.
- 매출은 **조회 기간에 접수되었고 결제 확인된 주문**의 금액입니다. 조회 날짜와 표시 시간은 한국 시간(KST) 기준입니다.
- 관리자 웹은 HTTP Basic 인증을 사용하며 비밀번호를 브라우저 저장소에 보관하지 않습니다. 새로고침 시 다시 로그인합니다. 외부 배포 시 HTTPS를 사용하세요.
- 고객 주문 API는 매장 키오스크의 신뢰된 네트워크를 전제로 합니다. 공개 인터넷에 배포할 때는 단말 인증과 요청 제한을 추가해야 합니다.

## Flutter 연동 계약

UI와 독립적인 JSON API를 사용합니다. 네이티브 Flutter는 CORS 설정이 필요 없으며 Flutter Web은 개발 서버 Origin을 `CORS_ORIGINS`에 추가합니다. Android 에뮬레이터에서 로컬 서버 주소는 `http://10.0.2.2:8000`입니다. 실제 단말 테스트는 서버를 `--host 0.0.0.0`으로 실행한 뒤 같은 네트워크의 PC IP로 접속합니다.

| 메서드 | 경로 | 기능 |
| --- | --- | --- |
| GET | `/api/menus` | 전체 메뉴·가격·카테고리·이미지 |
| POST | `/api/recommend` | 선택 기능: `file` 필드로 사진 업로드 |
| POST | `/api/orders` | 주문 접수, 재전송 시 기존 주문 반환 |
| GET | `/api/weather/now` | 현재 시간의 저장된 날씨, 없으면 null |
| GET | `/api/admin/me` | 관리자 인증 확인 |
| GET | `/api/admin/orders` | 기간·상태 필터, 페이지 단위 주문 목록 |
| GET | `/api/admin/orders/{id}` | 주문 상세 |
| PATCH | `/api/admin/orders/{id}` | 주문 상태 / 결제 확인 |
| GET | `/api/admin/sales` | 매출 요약·일별 판매·메뉴별 판매량 |

관리자 API에는 `Authorization: Basic <base64(username:password)>` 헤더가 필요합니다. 일반 고객 앱에는 관리자 자격 증명을 넣지 마세요.

주문 요청 예시:

```json
{
  "request_id": "30d7a05f-d3d2-4d10-a826-084861b732d8",
  "order_mode": "takeout",
  "payment_method": "card",
  "age_group": null,
  "items": [{"menu_id": "ame_ice", "qty": 2}]
}
```

응답은 `{"result":"OK","order":{...}}`이며 `order`에 `id`, `order_number`, `created_at`, `order_mode`, `payment_method`, `payment_status`, `status`, `total`, `items`가 포함됩니다. `items`는 주문 시점의 이름·단가·수량입니다. 고객 앱에서는 성공 응답을 확인한 뒤 장바구니를 비우세요. 서버 주소를 기준으로 이미지의 `/static/...` 상대 경로를 해석하세요.

관리자 조회 예시: `/api/admin/orders?start=2026-10-01&end=2026-10-02&status=pending&page=1&page_size=20`. 날짜 미지정 시 KST 오늘이며 조회 범위는 최대 366일 차이입니다. `page_size`는 1~100입니다. 판매 API는 같은 날짜 조건을 사용하고 주문 상태 필터는 적용하지 않습니다.

오류는 HTTP 상태 코드와 `detail` 필드로 반환합니다. 입력 검증 오류(422)의 `detail`은 필드별 오류 배열일 수 있습니다. 응답 모델과 전체 필드는 `/openapi.json`에서 확인할 수 있습니다.


## 사진 추천 (선택)

일반 메뉴와 주문·관리자 기능은 AI 패키지 없이 실행됩니다. 사진 추천을 사용할 때만 별도로 설치합니다.

```powershell
.venv\Scripts\python.exe -m pip install -r apps/backend/requirements-face.txt
```

DeepFace는 최초 호출에 모델을 다운로드할 수 있습니다. 미설치 또는 모델 준비 실패 시 추천 API가 503을 반환하고 고객은 일반 메뉴로 돌아갈 수 있습니다. 얼굴 인식 실패는 422, 파일 크기 제한은 10MB입니다. 임시 사진은 처리 후 삭제합니다. 기존 연령 그룹 코드 `10_40`, `41_50`을 호환성 때문에 유지하며 `41_50`은 기존 로직상 40세 초과 전체를 뜻합니다.

## 검증

```powershell
.venv\Scripts\python.exe -m pip install -r apps/backend/requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
node --check apps/frontend-app/kiosk/static/app.js
node --check apps/frontend-web/admin/static/app.js
```

API 테스트는 임시 DB만 사용합니다. 주문 상태, 서버 가격 계산, 스냅샷, 중복/동시 요청, 권한, 날짜/페이지 필터, 선택형 얼굴 추천과 기존 DB 보존을 검증합니다.

## 구조

```text
apps/
  frontend-app/
    kiosk/                 고객용 앱 UI 프로토타입 (향후 Flutter 전환 위치)
      index.html
      static/              고객 전용 app.js, style.css
  frontend-web/
    admin/                 관리자 웹
      index.html
      static/              관리자 전용 app.js, style.css
  backend/
    app.py                 FastAPI 진입점
    src/                   API, 스키마, 저장소, 선택형 얼굴 분석
    tests/                 API 회귀 테스트
    static/images/         Flutter에서도 사용할 메뉴 이미지
    data/seed.db           기존 메뉴/집계 원본 (버전 관리)
    instance/kiosk.db      실행용 DB (Git 제외)
    requirements*.txt
    .env.example
scripts/
  dev.ps1                  루트에서 개발 서버 실행
  check.ps1                백엔드 테스트 + 프론트 문법 검사
pytest.ini                 모노레포 테스트 경로
README.md
```

두 프론트는 빌드 도구가 필요 없는 정적 앱입니다. 로컬에서는 FastAPI가 각 앱을 `/kiosk`, `/admin`에 연결하고, 정적 파일은 `/kiosk-static`, `/admin-static`으로 분리해 제공합니다. Flutter 개발 시 고객 웹을 교체해도 백엔드 계약과 관리자 웹은 유지됩니다. API만 별도 배포하려면 `SERVE_WEB=false`로 실행할 수 있습니다. 별도 웹 호스팅 시 `/api`와 해당 정적 경로를 같은 Origin으로 프록시하세요.


구현 참고: [FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/), [파일 업로드](https://fastapi.tiangolo.com/tutorial/request-files/).

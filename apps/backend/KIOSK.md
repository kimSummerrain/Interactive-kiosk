# 키오스크 기기 및 고객 세션

단일 거래 DB에 연결된 매장 범위에서 동작한다. 점주 인증은 기존 OWNER_AUTH_MODE 설정을 따른다.
모든 토큰은 HTTPS에서 전송하고 로그·URL에 넣지 않는다. DB에는 등록 코드와 토큰의 SHA-256 해시만 저장한다.

## 등록과 주문 순서

1. 점주 Basic 인증으로 `POST /api/owner/kiosks/pairing-codes`에 `{"name":"입구"}` 전송.
   응답 `code`, `expires_at`: 등록 코드는 10분 유효하며 한 번만 사용할 수 있다.
2. 기기에서 `POST /api/kiosk/register`에 `{"code":"발급된 코드"}` 전송.
   응답 `device_id`, `store_id`, `device_token`. 기기 토큰은 이 응답에서만 제공하며 기기의 보안 저장소에 보관한다.
3. `X-Kiosk-Device: <device_token>`으로 `POST /api/kiosk/sessions` 호출.
   응답 `session_id`, `session_token`, `expires_at`, `preferences`.
4. `X-Kiosk-Session: <session_token>`으로 견적 생성 → 내용 확인 → `/api/orders/confirm` 호출.
   요청은 [API 안내](API.md)의 현장 결제(counter) 형식을 사용한다.
5. 같은 세션으로 `GET /api/kiosk/orders/{order_id}`에서 결과 확인.
6. 고객이 나가면 `POST /api/kiosk/session/end` 호출 후 클라이언트의 토큰·장바구니·임시 입력을 지운다.

새 고객 세션을 시작하면 같은 기기의 이전 세션과 선택 설정은 종료·초기화된다. 다른 기기의 세션은 유지한다.
세션은 15분 동안 활동이 없으면 만료되며 유효한 세션 작업은 만료 시간을 연장한다.
발급 후 최대 1시간을 넘기지 않는다. 발급 응답의 expires_at은 최초 만료 시각이며 이후 연장 값을 알리는 API는 없다.
세션이 종료되거나 만료되면 기존 주문도 조회할 수 없다. 점주는 기존 주문 조회 API로 대응한다.

## 관리 및 선택 설정

| 메서드 | 경로 | 인증·동작 |
| --- | --- | --- |
| GET | `/api/owner/kiosks` | 점주, 기기 ID·이름·active·last_seen 조회 |
| POST | `/api/owner/kiosks/{device_id}/revoke` | 점주, 기기 토큰 회수와 소속 세션 종료 |
| POST | `/api/kiosk/heartbeat` | X-Kiosk-Device, 마지막 연결 시각 갱신 |
| PATCH | `/api/kiosk/session/preferences` | X-Kiosk-Session, face/voice/recommendation 불리언 부분 갱신 |
| POST | `/api/kiosk/session/end` | X-Kiosk-Session, 종료 및 선택 초기화 |

선택은 모두 false로 시작한다. 사진 추천(`/api/recommend`)은 face와 recommendation이 모두 true일 때만 분석한다.
분석이 끝난 후에도 세션과 선택을 다시 확인해 종료·철회 시 결과를 반환하지 않는다.
진행 중인 모델 연산 자체를 중단하는 기능은 없다. voice는 선택 저장만 지원하며 STT는 아직 없다.
이 설정은 별도 연령 통계 활용 동의나 학습 동의의 구현을 뜻하지 않는다.

## 주문 격리와 오류

- 세션별 주문은 1건. 같은 request_id·quote_id·본문 재시도는 기존 결과를 반환하며 재고를 다시 차감하지 않는다.
- 다른 세션의 견적·주문 요청 ID는 409. 다른 세션의 주문 조회는 404.
- `/api/orders`에도 같은 세션·견적·counter 검증을 적용한다.
- 없거나 만료·회수된 토큰은 401. 선택 미허용 사진 추천은 403. 잘못된 입력은 422.
- 매장 중지 또는 기기 회수 후 기존 토큰으로 신규 작업을 수행할 수 없다.

## 적용과 호환성

`KIOSK_AUTH_REQUIRED=true`가 기본이다. 생략해도 true이며 true/false 외 값은 서버 시작을 거부한다.
기존 HTML 프로토타입의 세션 없는 주문·사진 추천은 기본 설정에서 401이 된다.
로컬 프로토타입을 유지할 때만 false로 설정한다. false에서도 전달된 세션 토큰은 검증하며 세션 주문의 격리는 유지한다.
보안 모드에서는 먼저 기기를 등록하고 고객 세션을 시작하는 클라이언트가 필요하다. Flutter·웹의 등록 화면은 후속 작업이다.

시작 시 kiosk_pairings/kiosk_devices/kiosk_sessions/kiosk_order_links 테이블과 quotes.session_id를 추가한다.
기존 주문·견적은 보존하며 기존 견적의 session_id는 null이다. 배포 전 DB를 백업한다.
코드 롤백 시 이전 견적 INSERT 문이 새 열과 호환되지 않을 수 있으므로 DB 백업 복원까지 함께 계획한다.
토큰 회전·등록 시도 제한·만료 세션 보관 정리는 후속 작업이며 공개 운영 준비 완료를 의미하지 않는다.

검증: `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`.

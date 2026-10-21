# 점주·고객 핵심 API

현재 범위는 단일 매장 개발용 API다. 실행 후 `/docs`에서 요청을 시험할 수 있다.
점주 인증은 기존 `ADMIN_USERNAME`, `ADMIN_PASSWORD` HTTP Basic 설정을 사용한다.
`/api/owner`는 점주 경로이고 기존 `/api/admin` 주문·매출 경로는 웹 호환을 위해 유지한다.
전체 시스템 관리자 기능이나 다매장 인증을 구현한 상태가 아니다. 외부 배포 시 HTTPS가 필요하다.

## 점주

| 메서드 | 경로 | 기능 |
| --- | --- | --- |
| GET | `/api/owner/me` | 인증 확인 |
| GET / POST | `/api/owner/menus` | 메뉴 목록 / 메뉴 등록 |
| PATCH | `/api/owner/menus/{menu_id}` | 이름·가격·판매 여부·판매 가능 수량 변경 |
| POST | `/api/owner/menus/{menu_id}/options` | 메뉴에 허용할 옵션 등록·수정 |
| GET | `/api/owner/orders` | 기간·상태·페이지별 주문 조회 |
| GET / PATCH | `/api/owner/orders/{order_id}` | 주문 상세 / 상태·현장 결제 확인 |
| GET | `/api/owner/sales` | 결제 매출·일별 매출·메뉴 판매 수량 |
| GET | `/api/owner/sales/hourly` | 시간대별 주문 건수·메뉴 수량·결제 매출 |
| GET | `/api/owner/stock-movements` | 메뉴별 수량 조정·주문 차감·취소 복구 이력 |

재고 이력 query: start/end(KST 날짜, 종료일 포함), menu_id(선택),
reason(order/cancel/owner_adjustment, 선택), page(기본 1), page_size(기본 20, 최대 100).
응답은 movements/total/page/page_size이며 이력은 created_at 및 id 내림차순이다.
각 이력에는 id/menu_id/order_id/delta/reason/note/created_at(UTC)이 포함된다.
메뉴 PATCH에서 유한 stock 변경과 함께 stock_note(1~300자)를 보낼 수 있다.
stock_note만 수정하거나 공백만 입력하면 422, 같은 수량 저장은 이력을 만들지 않는다.
null 수량 제한 전환에는 사유 입력을 지원하지 않아 stock_note를 보내면 422다.
현재 최초 수량·무제한 전환의 기록은 없어 원장 합계만으로 현재 재고를 재구성할 수 없다.

시간별 통계 query: start/end(날짜, 종료일 포함), start_hour(기본 0, 포함),
end_hour(기본 24, 미포함), menu_id(선택). KST 주문 생성 시각 기준으로 같은 시간을 합산한다.
반환: timezone, basis, 필터 값, totals, hours. 각 집계는 order_count(취소 제외),
paid_order_count, ordered_quantity, sold_quantity, revenue를 포함한다.
hours[].menus는 메뉴별 같은 지표를 제공한다. 메뉴별 주문 건수는 중복될 수 있어 합산하지 않는다.
없는 시간은 0으로 채운다. 메뉴 필터 사용 시 해당 항목의 수량·금액만 포함한다.

메뉴 등록 예시:

```json
{"menu_id":"vanilla_latte","name":"바닐라라떼","price":3500,"stock":20,"available":true}
```

`stock`은 메뉴별 판매 가능 잔 수이며 원재료 재고가 아니다. `null`은 수량 제한 없음이다.
`available=false`로 품절/판매 중지를 적용한다. 판매 종료는 삭제 대신 판매 중지를 사용한다.
초기 메뉴 분류는 기존 ID 기반 규칙을 유지하며 사진 업로드·분류 편집은 후속 범위다.
옵션은 메뉴별로 허용되며 한 잔당 한 번씩 적용한다. 시럽 펌프 수와 옵션 자체 재고는 아직 지원하지 않는다.

`POST /api/owner/menus/latte_hot/options`:

```json
{"option_id":"vanilla","name":"바닐라 시럽","price":500,"available":true}
```

## 고객: 견적 → 명시적 확인 → 주문

1. `GET /api/menus`로 메뉴·가격·옵션·판매 여부 확인.
2. `POST /api/order-quotes`에 UUID request_id와 주문 내용을 전달.
3. 응답의 항목·옵션·total을 고객에게 표시하고 확인받는다.
4. 동일한 요청 내용에 응답의 quote_id를 추가해 `POST /api/orders/confirm` 호출.
5. 통신 오류 시 같은 request_id 및 quote_id로 재시도한다.

```json
{
  "request_id":"55f4c35a-06f7-4bdc-9c9b-a0717e732aac",
  "order_mode":"takeout",
  "payment_method":"counter",
  "items":[{"menu_id":"latte_hot","qty":2,"option_ids":["vanilla"]}]
}
```

견적은 5분 동안 유효하며 재고를 예약하지 않는다. 확정 시 가격·판매 여부·옵션·수량을 다시 검증한다.
가격/요청 변경·만료는 409, 잘못된 메뉴·옵션은 422다. 새 견적을 표시하고 다시 확인받는다.
견적은 request_id와 전체 주문 내용에 묶인다. 견적 생성 전 request_id를 발급하고 확정까지 유지한다.
같은 메뉴라도 옵션 조합이 다르면 별도 주문 항목이다. 조합이 같으면 수량을 합쳐서 요청한다.

확정과 재고 차감은 한 트랜잭션이다. 확정 주문 재시도는 재고를 다시 차감하지 않는다.
미결제 주문 취소 시 원래 차감한 수량만 한 번 복구한다. 현장 결제 대기 주문은 점주가 취소할 때까지 수량을 점유한다.
주문 가격과 옵션 이름·가격은 스냅샷으로 저장하여 이후 변경과 무관하게 보존한다.
기존 SQLite 주문 항목은 시작 시 보존하며 새 구조로 이관한다. 배포 전 기존 DB를 백업한다.

## 현재 결제·인증 범위

- 새 확정 API는 현장 결제(counter)만 받는다. PG 승인·실제 환불은 미구현이다.
- 점주가 `payment_status=paid`로 결제를 확인한다. 결제 전 완료 불가, 결제 후 취소는 현재 차단한다.
- 기존 HTML 키오스크의 `/api/orders`는 유지한다. 옵션 없는 주문은 견적 없이 가능하지만 수량/판매 여부 검증은 동일하다.
- 고객 세션·기기 인증, 다매장 권한, 동의 설정 API는 아직 없다. 공개 운영 전 구현이 필요하다.
- 재료·레시피 기반 재고, 자동 예약 만료, 날씨/연령별 통계, PostgreSQL 전환은 후속 작업이다.

검증: 저장소 루트에서 `.venv\Scripts\python.exe -m pytest -q`.

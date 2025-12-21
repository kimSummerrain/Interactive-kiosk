# -hackathon-season3
카이로스 해커톤 시즌3 

AI-Based Smart Kiosk

얼굴 연령 추정과 주문 데이터를 결합한 지능형 키오스크 시스템

Overview

본 프로젝트는 얼굴 이미지 기반 연령대 추정, 날씨 정보, 연령대별 누적 주문 데이터를 결합하여
사용자에게 우선순위가 반영된 메뉴를 추천하고,
주문 완료 시 해당 데이터가 다시 통계에 반영되는 순환 구조의 스마트 키오스크 시스템이다.

단순 추천을 넘어,

“실제 키오스크 환경에서 지속적으로 학습되는 메뉴 추천 구조”
를 구현하는 것을 목표로 한다.

Core Features
1. Face-based Age Group Estimation

사용자가 업로드한 얼굴 이미지를 기반으로 연령을 추정

추정된 연령을 연령대(age group) 로 변환하여 UI 및 추천 로직에 활용

얼굴이 인식되지 않는 경우 명확한 예외 응답 제공

2. Weather-aware Recommendation

현재 시간 기준 날씨 정보를 DB에서 조회

기온/날씨 상태에 따라 메뉴 점수에 가중치 부여
(예: 저온 → hot 메뉴 가중, 고온 → ice 메뉴 가중)

3. Age-based Menu Statistics

연령대별 메뉴 주문 횟수를 DB에 누적 저장

추천 시 가장 중요한 1순위 요소로 사용

주문 완료 시 통계 자동 업데이트

4. Priority-based Menu Ranking

추천 점수는 다음 요소의 합으로 계산된다.

연령대별 누적 주문량 (주요 가중치)

날씨 보정 점수

(확장 가능) GPT 기반 추천 가중치

최종적으로 전체 메뉴를 점수순으로 정렬하여 프론트엔드에 전달한다.

Tech Stack
Backend

Python 3.9

Flask

SQLite

DeepFace

TensorFlow (CPU)

Frontend

HTML / CSS / Vanilla JavaScript

Single-page screen transition 구조

Fetch API 기반 백엔드 연동

Face Age Estimation Model
Model

DeepFace (VGG-Face 기반 Age Regression 모델)

Keras / TensorFlow 기반

대규모 얼굴 데이터셋으로 사전 학습된 공개 모델

Inference Strategy

모델은 최초 실행 시 1회 자동 다운로드

이후 로컬 캐시에 저장되어 오프라인 추론 가능

실제 키오스크 배포 환경에서는 사전 다운로드 완료 후 운영

Accuracy (실무 기준)

평균 절대 오차(MAE): 약 3~5세 수준

본 프로젝트에서는 정확한 나이 값이 아닌 연령대 분류가 목적이므로,
UI/추천 용도로 충분한 정확도를 가짐

Database Schema
menus
CREATE TABLE menus (
  menu_id TEXT PRIMARY KEY,
  menu_index INTEGER NOT NULL,
  name TEXT NOT NULL,
  price INTEGER NOT NULL,
  image_path TEXT
);

age_menu_stats
CREATE TABLE age_menu_stats (
  age_group TEXT PRIMARY KEY,
  menu_1 INTEGER DEFAULT 0,
  menu_2 INTEGER DEFAULT 0,
  ...
);

weather_hourly
CREATE TABLE weather_hourly (
  datetime TEXT PRIMARY KEY,
  temperature REAL,
  weather TEXT
);

Environment Variables (.env)

프로젝트 실행을 위해 다음 환경변수가 필요하다.

# Azure Face API (현재는 사용하지 않음, 확장 대비)
AZURE_FACE_ENDPOINT=your_endpoint
AZURE_FACE_KEY=your_key

# OpenAI (선택, GPT 추천 확장 시)
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4.1-mini

# SQLite DB 경로
SQLITE_DB_PATH=./kiosk.db


현재 얼굴 인식은 DeepFace 로컬 모델을 사용하며,
Azure Face API는 비용 및 정책 제약으로 인해 사용하지 않는다.

API Overview
얼굴 기반 추천
POST /api/recommend
multipart/form-data:
- file: 얼굴 이미지


Response:

{
  "menus": [
    {
      "menu_id": "ame_hot",
      "name": "핫아메리카노",
      "price": 1500,
      "image": "/static/images/ame_hot.png",
      "score": 42
    }
  ],
  "_debug": {
    "age": 29,
    "age_group": "10_40",
    "weather": {...}
  }
}

주문 완료
POST /api/order/complete


Payload:

{
  "age_group": "10_40",
  "items": [
    { "menu_index": 1, "qty": 2 },
    { "menu_index": 3, "qty": 1 }
  ]
}


Effect:

age_menu_stats 테이블에 주문 수량 누적 반영

Project Intention

이 프로젝트는
“AI 기술을 단순 시연이 아닌 실제 서비스 구조에 녹여내는 것”을 목표로 한다.

얼굴 인식 → UI 분기

추천 → 주문 → 통계 → 다시 추천으로 이어지는 폐쇄 루프

네트워크 의존성을 최소화한 로컬 추론 구조

키오스크 환경을 고려한 명확한 예외 처리

학습용 프로젝트를 넘어,
현장 배포를 전제로 한 설계 판단에 중점을 두었다.

Future Work

GPT 기반 추천 점수 실서비스 적용

연령대 세분화 및 사용자 유형 클러스터링

주문 데이터 기반 시간대별 추천

Docker 기반 배포

How to Run
python app.py

Author

Backend / AI Logic / System Design

Frontend Integration Collaboration

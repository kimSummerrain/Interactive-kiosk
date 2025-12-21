# -hackathon-season3
카이로스 해커톤 시즌3 
# AI-Based Smart Kiosk

얼굴 이미지 기반 연령대 추정과 주문 데이터를 결합한 지능형 키오스크 시스템

---

## Overview

본 프로젝트는 사용자의 얼굴 이미지를 기반으로 연령대를 추정하고,  
날씨 정보 및 연령대별 누적 주문 데이터를 결합하여  
우선순위가 반영된 메뉴를 추천하는 스마트 키오스크 시스템이다.

추천 → 주문 → 통계 누적 → 다시 추천으로 이어지는  
실제 서비스 환경을 고려한 **데이터 순환 구조**를 구현하는 것이 핵심 목표이다.

---

## Core Features

### 1. Face-based Age Group Estimation
- 업로드된 얼굴 이미지를 기반으로 연령 추정
- 추정된 연령을 연령대(`10_40`, `41_50`)로 변환
- 얼굴 인식 실패 시 명확한 예외 응답 제공

### 2. Weather-aware Recommendation
- 현재 시간 기준 날씨 정보를 DB에서 조회
- 기온 및 날씨 상태에 따라 메뉴 점수 가중치 적용
  - 저온 → hot 메뉴 가중
  - 고온 → ice 메뉴 가중

### 3. Age-based Menu Statistics
- 연령대별 메뉴 주문 횟수 누적 저장
- 추천 시 가장 중요한 1순위 요소로 사용
- 주문 완료 시 통계 자동 업데이트

### 4. Priority-based Menu Ranking
메뉴 추천 점수는 다음 요소의 합으로 계산된다.

1. 연령대별 누적 주문량
2. 날씨 보정 점수
3. (확장 가능) GPT 기반 추천 가중치

최종적으로 모든 메뉴를 점수 기준으로 정렬하여 프론트엔드에 전달한다.

---

## Tech Stack

### Backend
- Python 3.9
- Flask
- SQLite
- DeepFace
- TensorFlow (CPU)

### Frontend
- HTML / CSS / Vanilla JavaScript
- Single Page Screen Transition 구조
- Fetch API 기반 백엔드 연동

---

## Face Age Estimation Model

### Model
- DeepFace (VGG-Face 기반 Age Regression 모델)
- TensorFlow / Keras 기반
- 공개 사전학습 모델 사용

### Inference Strategy
- 최초 실행 시 모델 자동 다운로드
- 이후 로컬 캐시에 저장되어 오프라인 추론 가능
- 키오스크 환경을 고려한 네트워크 의존성 최소화

### Accuracy
- 평균 오차 약 3~5세 수준
- 본 프로젝트에서는 정확한 나이 값이 아닌 연령대 분류가 목적이므로
  추천 및 UI 분기 용도로 충분한 정확도를 제공한다.

---


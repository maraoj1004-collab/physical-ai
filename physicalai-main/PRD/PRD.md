# PRD — HarvestEdge: Edge AI 스마트 수확 보조 시스템

## 1. 제품 개요

### 제품명
HarvestEdge (Edge AI-Based Fruit Harvest Readiness Detection and Smart Harvesting Assistance System)

### 한 줄 소개
카메라로 과일을 인식하고, **Raspberry Pi 같은 Edge Device에서 수확 적기를 실시간으로 판단**한 뒤, 그 결과를 화면과 LED로 작업자에게 알려주는 스마트 농업용 Physical AI 시스템

### 제품 목표
작업자가 경험과 육안에만 의존하지 않고, AI가 표시한 **수확 대상 과일**을 중심으로 빠르고 일관되게 수확할 수 있도록 돕는다.

---

# 2. 문제 정의

현재 과일의 수확 시기는 작업자의 경험과 육안에 크게 의존한다.

이로 인해 다음과 같은 문제가 발생한다.

- 작업자마다 숙도 판단 기준이 다르다
- 넓은 과수원에서 수확 대상 과일을 찾는 데 시간이 오래 걸린다
- 잎이나 가지에 가려진 과일을 놓치기 쉽다
- 덜 익은 과일을 잘못 수확할 수 있다
- 적정 시기를 놓쳐 과숙되는 과일이 생긴다
- 반복적인 육안 선별로 노동 부담이 크다

또한 영상을 클라우드로 보내 처리하는 방식은 **과수원의 불안정한 네트워크 환경**에서 지연이 크고, 오프라인에서는 사용할 수 없다.

---

# 3. 해결 방법

카메라 영상에서 과일을 탐지하고, 색상·크기를 분석하여 수확 적기 여부를 판단한다.
모든 추론은 **현장의 Edge Device에서 직접 수행**하고, 결과는 화면과 물리 장치(LED)로 즉시 전달한다.

### 기본 흐름

카메라 촬영
↓
Edge Device(Raspberry Pi 5)로 영상 입력
↓
YOLO 과일 객체 탐지
↓
OpenCV 색상(HSV)·크기 분석
↓
수확 적기 판단
↓
화면 표시 + LED 출력

### 숙도 분류

| 상태 | 의미 | 화면 표시 | LED |
|---|---|---|---|
| Unripe | 아직 수확하기 이른 과일 | 🟢 초록 박스 | — |
| Harvest Ready | 수확 적기의 과일 | 🟡 노란 박스 | 🟡 노란 LED ON |
| Overripe / Warning | 과숙 또는 주의가 필요한 과일 | 🔴 빨간 박스 | 🔴 빨간 LED ON |

---

# 4. 핵심 사용자

### Primary User
과수원·비닐하우스에서 수확 작업을 하는 작업자 및 농가

### Secondary User
- 스마트팜 도입을 검토하는 농업 법인
- 수확량·품질 데이터를 관리하려는 농장 관리자

### 대표 사용자 시나리오
> 작업자가 수확철 과수원에서 작업을 시작한다.
> 나무마다 익은 과일을 일일이 확인하던 기존과 달리, 카메라를 나무 쪽으로 비춘다.
> Edge Device가 영상 속 과일을 탐지하고 노란 박스로 수확 적기 과일을 표시한다.
> 화면에는 "수확 대상 7개"가 표시되고, 노란 LED가 켜진다.
> 작업자는 표시된 과일만 골라 수확한 뒤 다음 나무로 이동한다.

---

# 5. MVP 범위

초기 POC는 **하나의 작물**을 대상으로 한다.

## 반드시 구현할 기능

### 5.1 영상 입력
- 카메라/웹캠 실시간 영상 입력
- Raspberry Pi 5로 프레임 전달

### 5.2 과일 객체 탐지
- YOLO 기반 과일 탐지 및 Bounding Box 생성
- 기존 모델 활용 또는 직접 학습

### 5.3 숙도 분석 및 수확 적기 판단
- 탐지된 과일 영역 Crop
- HSV 색상 분석
- Bounding Box 면적 기반 크기 분석
- Rule 기반으로 Unripe / Harvest Ready / Overripe 분류

### 5.4 결과 표시
- 숙도별 색상 박스 표시
- 수확 대상 과일 개수 표시
- 추론 시간(ms)·FPS 표시

### 5.5 Physical Output
- GPIO로 LED 제어
- 수확 적기 과일 발견 시 노란 LED ON

---

# 6. AI / Computer Vision 처리 과정

```text
Camera Input
      ↓
Image Preprocessing
      ↓
YOLO Object Detection
      ↓
Fruit Bounding Box
      ↓
Fruit Crop
      ↓
HSV Color Analysis + Size Analysis
      ↓
Harvest Readiness Decision
      ↓
Result Visualization
      ↓
Client UI + LED Output
```

초기 POC에서는 데이터 구축과 개발 난이도를 고려하여 **YOLO 객체 탐지 + OpenCV 색상·크기 Rule**을 사용한다.
충분한 데이터가 확보되면 숙도 분류 모델을 추가하여 AI 기반 판단으로 고도화한다.

---

# 7. 기술 스택

| 분야 | 기술 |
|---|---|
| Programming | Python |
| Object Detection | YOLO |
| Computer Vision | OpenCV |
| Edge Device | Raspberry Pi 5 |
| AI Runtime | ONNX Runtime / TFLite |
| Communication | MQTT / WebSocket |
| Input Device | Camera / Webcam |
| Physical Output | GPIO / LED |
| Client UI | Streamlit 또는 Web UI |
| Version Control | Git / GitHub |

---

# 8. 시스템 구조

**Device → Edge Server → Client** 구조를 기반으로 설계한다.

```text
                    ┌─────────────────┐
                    │     Camera      │
                    └────────┬────────┘
                             │ MQTT
                             ▼
              ┌──────────────────────────┐
              │      Raspberry Pi 5      │
              │  YOLO Edge Inference     │
              │          ↓               │
              │  OpenCV Analysis         │
              │          ↓               │
              │  Harvest Decision        │
              └───────────┬──────────────┘
                          │ WebSocket / MQTT
             ┌────────────┴────────────┐
             ▼                         ▼
      ┌──────────────┐          ┌─────────────┐
      │ Client UI    │          │ LED / GPIO  │
      │ 결과 표시     │          │ 물리 출력    │
      └──────────────┘          └─────────────┘
```

---

# 9. 사용자 화면

### 메인 화면 구성
- 실시간 카메라 화면
- 숙도별 색상 Bounding Box
- 수확 대상 / 미숙 / 과숙 개수
- 추론 시간(ms) 및 FPS
- LED 출력 상태

예:

**실시간 분석 중** · Raspberry Pi 5

🟡 수확 적기 **7개** · 🟢 미숙 **12개** · 🔴 과숙 **1개**

`추론 시간 82ms · 12 FPS`

**→ 노란 LED ON: 수확 대상이 있습니다.**

---

# 10. Edge AI 적용 이유

| 항목 | Cloud AI | Edge AI |
|---|---|---|
| 추론 위치 | Cloud Server | Raspberry Pi |
| 네트워크 의존성 | 높음 | 낮음 |
| 지연시간 | 네트워크 왕복 포함 | 현장에서 즉시 |
| 오프라인 사용 | 어려움 | 가능 |
| 영상 데이터 외부 전송 | 필요 | 불필요 |

POC에서는 **동일한 입력 영상으로 Cloud와 Edge의 Latency·FPS를 직접 측정**하여, "Edge가 빠르다"는 주장을 실제 수치로 검증한다.

---

# 11. 데이터 수집 계획 (현장 조사)

인식 정확도는 촬영 환경에 크게 좌우되므로, 학습·테스트 데이터 수집 전에 현장 조사를 실시한다.
상세 체크리스트는 `report/field_survey_guide.md`를 따른다.

### 주요 조사 항목
- **촬영 환경:** 시간대, 날씨, 노지/비닐하우스/온실
- **조명:** 밝기, 직사광선, 그림자, 역광
- **배경:** 잎·가지·토양 등 배경과 과일의 색상 차이
- **과일 상태:** 숙도, 색상, 표면 상태, 크기와 형태
- **가림·겹침:** 잎/가지에 의한 가림, 과일끼리 겹침
- **카메라 조건:** 카메라 종류, 촬영 거리·각도, 흔들림, 초점
- **이미지 품질:** 과노출, 저노출, 노이즈

조사 결과를 바탕으로 숙도 판단 기준(HSV 범위, 크기 기준)과 데이터 증강 방향을 정한다.

---

# 12. 개발 단계

| Phase | 내용 |
|---|---|
| 1. 데이터 및 Vision 구축 | 이미지 확보, Bounding Box annotation, YOLO 학습/활용, 색상 분석 구현 |
| 2. 숙도 판단 | 색상·크기 기준 정의, 미숙/적기/과숙 판단 로직 구현 |
| 3. Edge AI 적용 | Raspberry Pi 환경 구축, ONNX/TFLite 변환, FPS·Latency 측정 |
| 4. 실시간 시스템 구축 | 실시간 입력·추론, 박스 및 개수 표시 |
| 5. Physical AI 연동 | GPIO·LED 연결, 판단 결과에 따른 LED 출력, 전체 Pipeline 테스트 |

---

# 13. 성공 지표 (KPI)

| 평가 항목 | 목표 |
|---|---:|
| 과일 탐지 mAP | ≥ 90% |
| 수확 적기 분류 정확도 | ≥ 85% |
| **수확 대상 Recall** | **≥ 90%** |
| **Edge 추론 시간** | **≤ 100ms/frame** |
| 실시간 처리 속도 | ≥ 10 FPS |
| 수확 대상 개수 정확도 | ≥ 90% |
| Cloud 대비 Latency | Edge 방식 개선 확인 |

핵심 KPI는 **수확 대상 Recall**(수확해야 할 과일을 놓치지 않는가)과 **Edge 추론 Latency**(현장에서 얼마나 빨리 판단하는가)이다.

---

# 14. MVP에서 제외하는 기능

- 대규모 과수원 전체 자동화
- 로봇팔을 이용한 실제 과일 수확
- 여러 종류의 과일 동시 지원
- 완벽한 숙도 판정
- 장시간 야외 환경에서의 상용 수준 안정성 검증

---

# 15. 향후 확장 기능

### Phase 2 — AI 숙도 분류 모델
Rule 기반 판단을 학습된 숙도 분류 모델로 대체하여 정확도를 높인다.

### Phase 3 — 스마트 농업 기능 확장
- 생육 상태 분석
- 병해충 탐지
- 과일 개수 기반 수확량 예측
- 품질 등급 분류

### Phase 4 — 자동 수확 로봇
```text
과일 탐지 → 수확 적기 판단 → 3D 위치 추정 → Robot Arm → 자동 수확
```
**Vision → Decision → Action**의 완전한 Physical AI 시스템으로 발전한다.

---

# 16. 핵심 차별점

단순한 과일 이미지 분류가 아니라,

> **카메라 → Edge AI 추론 → 수확 적기 판단 → 실시간 전달 → 물리적 출력**

의 전체 흐름을 하나의 시스템으로 구현한다.
AI의 판단이 화면에 머무르지 않고 **현장의 실제 장치 동작으로 이어진다**는 점이 본 프로젝트의 Physical AI 요소다.

---

# 17. 프로젝트 핵심 가치

### 기존
나무마다 과일 확인 → 경험으로 숙도 판단 → 놓치거나 잘못 수확 → 재확인

### HarvestEdge
카메라로 비추기 → **Edge AI가 수확 대상 표시 + LED 알림** → 표시된 과일만 수확 → 다음 나무로 이동

즉, **네트워크 없이도 현장에서 즉시 수확 적기를 알려주는 Edge 기반 Physical AI 수확 보조 도구**를 제공하는 것이 본 프로젝트의 핵심이다.

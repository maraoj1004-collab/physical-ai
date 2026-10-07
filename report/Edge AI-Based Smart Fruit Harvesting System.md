# Edge AI 기반 과일 수확 적기 판단 및 스마트 수확 보조 시스템

## 1. 프로젝트 개요

### 1.1 프로젝트명

**Edge AI-Based Fruit Harvest Readiness Detection and Smart Harvesting Assistance System**

### 1.2 프로젝트 목적

과수원에서 작업자가 육안과 경험에 의존하여 판단하던 과일의 수확 적기를 **카메라와 Edge AI를 통해 자동으로 판단**하고, 수확이 필요한 과일의 위치를 작업자에게 실시간으로 제공하는 스마트 농업 시스템을 개발한다.

특히 클라우드 서버에 영상을 전송하여 처리하는 방식이 아닌 **Raspberry Pi와 같은 Edge Device에서 AI 추론을 수행**하여 낮은 지연시간과 실시간성을 확보하는 것을 목표로 한다.

최종적으로는 AI의 판단 결과를 LED 등의 실제 장치와 연동하여 **AI의 인식 결과가 물리적 장치의 동작으로 이어지는 Physical AI 형태의 POC**를 구현한다.

---

# 2. 문제 정의

## 2.1 기존 문제

현재 과일의 수확 시기는 작업자의 경험과 육안에 크게 의존한다.

이에 따라 다음과 같은 문제가 발생할 수 있다.

- 작업자에 따라 숙도 판단 기준이 다름
- 넓은 과수원에서 수확 대상 과일을 찾는 데 많은 시간이 필요함
- 잎이나 가지에 가려진 과일을 놓칠 수 있음
- 덜 익은 과일을 잘못 수확할 가능성이 있음
- 적정 수확 시기를 놓쳐 과숙되는 과일이 발생할 수 있음
- 반복적인 육안 선별 작업으로 노동 부담이 증가함

## 2.2 해결하고자 하는 문제

카메라 영상에서 과일을 자동으로 탐지하고 색상·크기 등의 시각적 특징을 분석하여 **수확 적기 여부를 판단하는 Edge AI 시스템**을 구축한다.

AI가 판단한 결과를 작업자에게 실시간으로 제공하여 수확 대상 과일을 빠르게 확인할 수 있도록 한다.

---

# 3. 핵심 아이디어

본 시스템의 핵심은 단순히 과일을 탐지하는 것이 아니라,

> **카메라 → Edge AI 추론 → 수확 적기 판단 → 실시간 결과 전달 → 물리적 출력**

의 전체 흐름을 구현하는 것이다.

### 핵심 기능

1. 카메라를 통한 과일 영상 입력
2. YOLO 기반 과일 객체 탐지
3. OpenCV를 활용한 색상·크기 분석
4. 과일별 수확 적기 판단
5. Edge Device에서 실시간 AI 추론
6. 수확 대상 과일 위치 및 개수 표시
7. LED 등의 물리 장치를 이용한 결과 출력

---

# 4. 서비스 시나리오

### Step 1. 과일 촬영

작업자가 카메라를 이용하여 과수원 또는 과일 모형을 촬영한다.

### Step 2. Edge Device로 영상 입력

카메라에서 입력된 영상이 Raspberry Pi 등의 Edge Device로 전달된다.

### Step 3. 과일 객체 탐지

YOLO 모델이 영상 속 과일을 탐지하고 각각의 Bounding Box를 생성한다.

### Step 4. 과일 특징 분석

탐지된 과일 영역을 Crop하여 OpenCV를 통해 색상과 크기를 분석한다.

- 색상 정보: RGB / HSV
- 크기 정보: Bounding Box 면적 및 상대적 크기
- 형태 및 영상 상태: 향후 확장

### Step 5. 수확 적기 판단

AI 분석 결과를 기반으로 과일을 다음과 같이 분류한다.

| 상태 | 의미 |
|---|---|
| Unripe | 아직 수확하기 이른 과일 |
| Harvest Ready | 수확 적기의 과일 |
| Overripe / Warning | 과숙 또는 주의가 필요한 과일 |

### Step 6. 결과 표시

수확 적기로 판단된 과일을 화면에 표시한다.

예:

- 🟡 Yellow Box → Harvest Ready
- 🟢 Green Box → Unripe
- 🔴 Red Box → Overripe / Warning

동시에 전체 수확 대상 개수를 표시한다.

### Step 7. Physical Output

AI 판단 결과를 GPIO와 연결하여 실제 LED 등의 장치로 출력한다.

예:

**수확 적기 → 노란색 LED ON**

이를 통해 AI의 판단 결과가 실제 물리 환경의 출력으로 연결되는 Physical AI 구조를 구현한다.

---

# 5. 시스템 아키텍처

본 프로젝트는 학습 과정에서 다루는 **Device → Edge Server → Client** 구조를 기반으로 설계한다.

```text
                    ┌─────────────────┐
                    │     Camera      │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Device / Input  │
                    └────────┬────────┘
                             │ MQTT
                             ▼
              ┌──────────────────────────┐
              │      Raspberry Pi 5      │
              │                          │
              │  YOLO Edge Inference     │
              │          ↓               │
              │     OpenCV Analysis      │
              │          ↓               │
              │  Harvest Decision        │
              └───────────┬──────────────┘
                          │
                 WebSocket / MQTT
                          │
             ┌────────────┴────────────┐
             ▼                         ▼
      ┌──────────────┐          ┌─────────────┐
      │ Client UI    │          │ LED / GPIO  │
      │ 결과 표시     │          │ 물리 출력    │
      └──────────────┘          └─────────────┘
```

---

# 6. Edge AI 적용 이유

본 프로젝트에서는 클라우드 기반 AI보다 **Edge AI 방식**을 핵심으로 사용한다.

## Cloud 방식

```text
Camera
 ↓
Network
 ↓
Cloud Server
 ↓
AI Inference
 ↓
Network
 ↓
Result
```

네트워크 상태에 따라 지연시간이 발생할 수 있으며 실시간 영상 처리에는 부담이 될 수 있다.

## Edge 방식

```text
Camera
 ↓
Raspberry Pi
 ↓
AI Inference
 ↓
Result
```

현장에서 직접 추론하기 때문에 네트워크 의존성을 줄이고 실시간 처리에 유리하다.

따라서 본 프로젝트에서는 **Cloud와 Edge 방식의 추론 시간을 직접 측정하여 Edge AI 적용 효과를 비교**한다.

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

# 8. AI 처리 Pipeline

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
HSV Color Analysis
      +
Size Analysis
      ↓
Harvest Readiness Decision
      ↓
Result Visualization
      ↓
Client + LED Output
```

초기 POC에서는 데이터 구축과 개발 난이도를 고려하여 **YOLO 객체 탐지 + OpenCV 기반 색상·크기 분석 Rule**을 사용한다.

향후 충분한 데이터가 확보되면 숙도 분류 모델을 추가하여 AI 기반 숙도 판단으로 고도화한다.

---

# 9. POC 개발 단계

## Phase 1. 데이터 및 Vision 구축

- 과일 이미지 데이터 확보
- 과일 Bounding Box annotation
- YOLO 모델 학습 또는 기존 모델 활용
- 과일 객체 탐지 테스트
- OpenCV 기반 색상 분석 구현

## Phase 2. 숙도 판단

- 과일 색상 기준 정의
- 크기 기준 정의
- 미숙 / 수확 적기 / 과숙 기준 설정
- 수확 적기 판단 로직 구현

## Phase 3. Edge AI 적용

- Raspberry Pi 환경 구축
- ONNX/TFLite 기반 모델 변환
- Raspberry Pi에서 직접 추론
- FPS 및 추론 latency 측정

## Phase 4. 실시간 시스템 구축

- Camera 실시간 입력
- YOLO 실시간 추론
- 수확 대상 Bounding Box 표시
- 수확 대상 개수 표시

## Phase 5. Physical AI 연동

- GPIO 제어
- LED 연결
- AI 판단 결과에 따른 LED 출력
- 실제 디바이스에서 전체 Pipeline 테스트

---

# 10. KPI

| 평가 항목 | 목표 |
|---|---:|
| 과일 탐지 mAP | ≥ 90% |
| 수확 적기 분류 정확도 | ≥ 85% |
| 수확 대상 Recall | ≥ 90% |
| Edge 추론 시간 | ≤ 100ms/frame |
| 실시간 처리 속도 | ≥ 10 FPS |
| 수확 대상 개수 정확도 | ≥ 90% |
| Cloud 대비 Latency | Edge 방식 개선 확인 |

### 핵심 KPI

가장 중요한 지표는 **수확 대상 Recall**과 **Edge 추론 latency**로 설정한다.

수확해야 하는 과일을 AI가 놓치는 것을 최소화하면서 실제 Edge Device에서 얼마나 빠르게 판단할 수 있는지를 검증한다.

---

# 11. Edge AI 성능 비교

POC에서는 동일한 입력 영상을 이용하여 다음을 비교한다.

| 항목 | Cloud AI | Edge AI |
|---|---:|---:|
| 추론 위치 | Cloud Server | Raspberry Pi |
| 네트워크 의존성 | 높음 | 낮음 |
| 평균 Latency | 측정 | 측정 |
| FPS | 측정 | 측정 |
| 실시간성 | 비교 | 비교 |
| 오프라인 사용 | 어려움 | 가능 |

이를 통해 단순히 “Edge가 빠르다”라고 주장하는 것이 아니라 **실제 측정값을 기반으로 Edge AI의 필요성을 검증한다.**

---

# 12. Physical AI 요소

본 프로젝트의 Physical AI 요소는 AI 모델 자체가 아니라 **AI의 판단이 실제 환경에서 행동 또는 출력으로 연결되는 구조**에 있다.

### 현재 POC

```text
Camera
 ↓
AI 판단
 ↓
LED 출력
```

### 향후 확장

```text
Camera
 ↓
과일 탐지
 ↓
수확 적기 판단
 ↓
3D 위치 추정
 ↓
Robot Arm
 ↓
자동 수확
```

향후 로봇팔까지 확장하면 **Vision → Decision → Action**의 완전한 Physical AI 시스템으로 발전할 수 있다.

---

# 13. 기대 효과

### ① 수확 작업 효율 향상

작업자가 모든 과일을 직접 확인하지 않고 AI가 표시한 수확 대상 중심으로 작업할 수 있다.

### ② 숙도 판단 보조

작업자의 경험에 의존하던 숙도 판단을 AI가 보조하여 판단 편차를 줄일 수 있다.

### ③ Edge 기반 실시간 처리

현장에서 직접 AI 추론을 수행하여 네트워크 상황에 따른 지연을 줄일 수 있다.

### ④ 스마트 농업 확장 가능성

수확 적기 판단뿐 아니라 향후 다음 기능으로 확장할 수 있다.

- 생육 상태 분석
- 병해충 탐지
- 과일 개수 및 수확량 예측
- 품질 분류
- 자동 수확 로봇

---

# 14. Out of Scope

초기 POC에서는 프로젝트 범위를 과도하게 확대하지 않기 위해 다음 기능은 제외한다.

- 실제 대규모 과수원 전체 자동화
- 로봇팔을 이용한 실제 과일 수확
- 모든 종류의 과일 지원
- 완벽한 숙도 판정
- 장시간 야외 환경에서의 상용 수준 안정성 검증

우선 **하나의 작물을 대상으로 Edge Vision 기반 수확 적기 판단을 성공적으로 구현하는 것**을 목표로 한다.

---

# 15. 최종 목표

본 프로젝트의 최종 목표는 단순한 과일 이미지 분류가 아니라,

> **카메라로 과일을 인식하고, Edge Device에서 수확 적기를 실시간으로 판단한 후, 그 결과를 화면과 실제 하드웨어로 전달하는 스마트 농업용 Physical AI POC를 구현하는 것**

이다.

최종적으로 **Vision → Edge Inference → Decision → Communication → Physical Output**의 전체 과정을 하나의 시스템으로 구현하고, Cloud와 Edge의 성능 비교를 통해 Edge AI가 실제 농업 환경에서 갖는 장점을 검증한다.
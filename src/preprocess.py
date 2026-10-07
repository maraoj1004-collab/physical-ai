"""
HarvestEdge — OpenCV 전처리 및 수확 적기 판단 파이프라인

현장 조사 체크리스트(report/field_survey_guide.md)의 항목을 단계별로 반영한다.

    입력 이미지 (전체 프레임)
      → 1. 품질 검사        : Blur(7-4, 7-5), 과노출/저노출(8-1, 8-2), 노이즈(8-3)
      → 2. 노이즈 제거      : 노이즈가 기준 이상일 때만 Bilateral Filter
      → 3. 밝기 보정        : 직사광선/어두움(2-1, 2-2) → Gamma Correction
      → 4. 국소 대비 보정   : 그림자/역광(2-3, 2-4) → Lab L 채널에만 CLAHE
      → 5. 과일 Crop        : YOLO Bounding Box + Padding (없으면 전체 이미지)
      → 6. 과일 영역 분리   : GrabCut으로 잎·가지·토양 배경 제거(3-1, 3-2, 3-3)
      → 7. 신뢰 불가 픽셀 제외
             - 핫스팟(반사광·물방울, 4-3) : 고명도 + 저채도
             - 그림자(2-3)               : 저명도
      → 8. 형태 특징        : 면적, 원형도, 종횡비, Solidity(5-1, 5-2, 6-1)
      → 9. 색상 특징        : Hue 기반 숙도 픽셀 비율(4-1, 4-2)
      → 10. 수확 적기 판단  : unripe / harvest_ready / overripe / unknown

색상 변화(시간대·날씨에 따른 색온도 변화) 대응 원칙:
    - 숙도 판단은 조명 세기에 덜 민감한 Hue(색상) 위주로 한다.
    - 밝기 보정은 L(명도)·Gamma에만 적용하고 Hue를 직접 바꾸는 보정은 하지 않는다.
    - Hue가 불안정한 저채도/저명도 픽셀은 판단에서 제외한다.
    - 화이트밸런스(Gray World)는 잎이 많은 장면에서 색을 왜곡할 수 있어 기본값은 끈다.

※ 아래 Config의 기준값은 "녹색 → 빨간색"으로 익는 과일을 가정한 초기값이다.
  현장 조사와 대표 이미지(9장) 분석 후 대상 작물에 맞게 반드시 보정해야 한다.

사용 예:
    python src/preprocess.py fruit.jpg
    python src/preprocess.py frame.jpg --bbox 120,80,90,90 --debug out.png
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass, field

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# 설정값 (현장 조사 결과로 보정할 값은 모두 여기에 모은다)
# OpenCV HSV 범위: H 0~179, S 0~255, V 0~255
# ---------------------------------------------------------------------------

@dataclass
class Config:
    # 1. 품질 검사
    blur_var_min: float = 60.0          # Laplacian 분산이 이보다 낮으면 흐린 이미지
    overexposed_v: int = 250            # 이 값 이상이면 과노출(색 정보 손실) 픽셀
    underexposed_v: int = 15            # 이 값 이하면 저노출 픽셀
    exposure_reject_ratio: float = 0.5  # 과/저노출 픽셀이 이 비율을 넘으면 판단 불가
    noise_sigma_max: float = 6.0        # 추정 노이즈가 이보다 크면 노이즈 제거 적용

    # 3. Gamma 보정 (평균 밝기가 이 범위를 벗어날 때만 적용)
    brightness_ok_range: tuple[int, int] = (90, 170)
    gamma_target_v: int = 128
    gamma_clamp: tuple[float, float] = (0.5, 2.0)

    # 4. CLAHE (그림자/역광으로 어두운 영역이 많을 때만 적용)
    clahe_dark_v: int = 60              # 이 값 이하를 "어두운 영역"으로 본다
    clahe_dark_ratio: float = 0.15      # 어두운 영역 비율이 이보다 크면 CLAHE 적용
    clahe_clip_limit: float = 2.0
    clahe_tile: int = 8

    # 화이트밸런스: "none" | "grayworld"
    white_balance: str = "none"

    # 5. Crop
    crop_padding: float = 0.15          # Bounding Box 크기 대비 여백 비율
    max_crop_side: int = 160            # Raspberry Pi 연산량을 줄이기 위한 Crop 최대 변 길이

    # 7. 신뢰 불가 픽셀
    hotspot_v_min: int = 230            # 핫스팟: V가 높고
    hotspot_s_max: int = 40             #         S가 낮은 픽셀 (반사광·물방울)
    hotspot_dilate: int = 2             # 핫스팟 주변 번짐까지 제외
    shadow_v_max: int = 40              # 그림자: V가 매우 낮은 픽셀
    hue_s_min: int = 50                 # 채도가 이보다 낮으면 Hue를 신뢰하지 않음

    # 9. 숙도별 Hue 범위 [(H_min, H_max), ...]  — 대상 작물에 맞게 보정
    hue_unripe: list[tuple[int, int]] = field(default_factory=lambda: [(25, 85)])        # 황록~녹색
    hue_ripe: list[tuple[int, int]] = field(default_factory=lambda: [(0, 20), (160, 179)])  # 빨강~주황
    overripe_v_max: int = 90            # 익은 색 계열이면서 이 V 이하이면 과숙(검붉음/갈변)

    # 8. 형태 검증
    min_circularity: float = 0.45       # 이보다 낮으면 가림이 크거나 과일이 아닐 가능성
    min_solidity: float = 0.80          # 오목한 부분이 많으면 잎/가지에 가려진 것으로 판단
    min_area_px: int = 0                # 최소 과일 면적(Crop 원본 기준). 0이면 크기 조건 미사용

    # 10. 판단 규칙
    min_valid_ratio: float = 0.30       # 과일 영역 중 판단 가능한 픽셀이 이보다 적으면 unknown
    ready_ratio_min: float = 0.60       # 익은 색 픽셀 비율이 이 이상이면 수확 적기
    overripe_ratio_min: float = 0.35    # 과숙 픽셀 비율이 이 이상이면 과숙


# ---------------------------------------------------------------------------
# 결과 구조
# ---------------------------------------------------------------------------

@dataclass
class QualityReport:
    blur_var: float
    overexposed_ratio: float
    underexposed_ratio: float
    noise_sigma: float
    mean_v: float
    dark_ratio: float
    usable: bool
    issues: list[str] = field(default_factory=list)


@dataclass
class ShapeFeatures:
    area_px: float
    circularity: float
    aspect_ratio: float
    solidity: float


@dataclass
class ColorFeatures:
    valid_ratio: float      # 과일 영역 중 판단에 사용한 픽셀 비율
    hotspot_ratio: float
    shadow_ratio: float
    unripe_ratio: float     # 아래 비율들은 판단 가능한 픽셀 기준
    ripe_ratio: float
    overripe_ratio: float
    mean_hue: float         # 원형 평균 (0~179)
    mean_saturation: float
    mean_value: float


@dataclass
class HarvestResult:
    label: str              # unripe | harvest_ready | overripe | unknown
    confidence: float
    reasons: list[str]
    applied: list[str]      # 실제 적용된 전처리 단계
    quality: QualityReport
    shape: ShapeFeatures | None
    color: ColorFeatures | None


# ---------------------------------------------------------------------------
# 1. 품질 검사
# ---------------------------------------------------------------------------

def estimate_noise(gray: np.ndarray) -> float:
    """중앙값 필터와의 차이로 노이즈 표준편차를 추정한다 (MAD 기반)."""
    residual = gray.astype(np.int16) - cv2.medianBlur(gray, 3).astype(np.int16)
    mad = np.median(np.abs(residual - np.median(residual)))
    return float(1.4826 * mad)


def check_quality(bgr: np.ndarray, cfg: Config) -> QualityReport:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    v = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[:, :, 2]

    # Laplacian 분산은 밝기의 제곱에 비례하므로, 어두운 이미지가 흐림으로 오판되지 않도록
    # 평균 밝기를 128로 맞춘 뒤 측정한다 (과도한 증폭을 막기 위해 최대 4배)
    gain = min(4.0, 128.0 / max(float(gray.mean()), 1.0))
    blur_var = float(cv2.Laplacian(gray.astype(np.float64) * gain, cv2.CV_64F).var())
    over = float(np.mean(v >= cfg.overexposed_v))
    under = float(np.mean(v <= cfg.underexposed_v))
    noise = estimate_noise(gray)

    issues = []
    if blur_var < cfg.blur_var_min:
        issues.append(f"흐림(Laplacian 분산 {blur_var:.1f} < {cfg.blur_var_min})")
    if over > cfg.exposure_reject_ratio:
        issues.append(f"과노출 {over:.0%}")
    if under > cfg.exposure_reject_ratio:
        issues.append(f"저노출 {under:.0%}")
    if noise > cfg.noise_sigma_max:
        issues.append(f"노이즈 많음(σ≈{noise:.1f})")

    # 흐림·과노출·저노출은 색/형태 정보 자체가 손실되므로 판단하지 않는다.
    # 노이즈는 다음 단계에서 보정 가능하므로 usable을 유지한다.
    usable = blur_var >= cfg.blur_var_min and over <= cfg.exposure_reject_ratio \
        and under <= cfg.exposure_reject_ratio

    return QualityReport(
        blur_var=round(blur_var, 1),
        overexposed_ratio=round(over, 3),
        underexposed_ratio=round(under, 3),
        noise_sigma=round(noise, 2),
        mean_v=round(float(v.mean()), 1),
        dark_ratio=round(float(np.mean(v <= cfg.clahe_dark_v)), 3),
        usable=usable,
        issues=issues,
    )


# ---------------------------------------------------------------------------
# 2~4. 이미지 보정 (전체 프레임 기준)
# ---------------------------------------------------------------------------

def gray_world_white_balance(bgr: np.ndarray) -> np.ndarray:
    means = bgr.reshape(-1, 3).mean(axis=0)
    scale = means.mean() / np.maximum(means, 1e-6)
    return np.clip(bgr * scale, 0, 255).astype(np.uint8)


def gamma_correction(bgr: np.ndarray, mean_v: float, cfg: Config) -> tuple[np.ndarray, float]:
    """평균 밝기를 목표값으로 옮기는 Gamma 값을 계산해 LUT로 적용한다.
    세 채널에 같은 곡선을 적용하므로 Hue는 거의 유지된다."""
    m = min(max(mean_v / 255.0, 1e-3), 0.999)
    gamma = math.log(cfg.gamma_target_v / 255.0) / math.log(m)
    gamma = float(np.clip(gamma, *cfg.gamma_clamp))
    lut = np.array([((i / 255.0) ** gamma) * 255 for i in range(256)], dtype=np.uint8)
    return cv2.LUT(bgr, lut), gamma


def clahe_on_luminance(bgr: np.ndarray, cfg: Config) -> np.ndarray:
    """그림자/역광 영역의 명도만 국소적으로 끌어올린다. a/b(색) 채널은 건드리지 않는다."""
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    clahe = cv2.createCLAHE(clipLimit=cfg.clahe_clip_limit,
                            tileGridSize=(cfg.clahe_tile, cfg.clahe_tile))
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def enhance(bgr: np.ndarray, q: QualityReport, cfg: Config) -> tuple[np.ndarray, list[str]]:
    applied = []
    out = bgr

    if q.noise_sigma > cfg.noise_sigma_max:
        out = cv2.bilateralFilter(out, d=5, sigmaColor=40, sigmaSpace=40)
        applied.append("bilateral_denoise")

    if cfg.white_balance == "grayworld":
        out = gray_world_white_balance(out)
        applied.append("grayworld_wb")

    lo, hi = cfg.brightness_ok_range
    if not lo <= q.mean_v <= hi:
        out, gamma = gamma_correction(out, q.mean_v, cfg)
        applied.append(f"gamma({gamma:.2f})")

    if q.dark_ratio > cfg.clahe_dark_ratio:
        out = clahe_on_luminance(out, cfg)
        applied.append("clahe_L")

    return out, applied


# ---------------------------------------------------------------------------
# 5~6. Crop 및 과일 영역 분리
# ---------------------------------------------------------------------------

def crop_with_padding(bgr: np.ndarray, bbox: tuple[int, int, int, int] | None,
                      cfg: Config) -> tuple[np.ndarray, tuple[int, int, int, int], float]:
    """Bounding Box 주변에 여백을 두고 자른다.
    반환: (crop, crop 안에서의 원래 bbox 위치, 축소 배율)"""
    h, w = bgr.shape[:2]
    if bbox is None:
        x, y, bw, bh = 0, 0, w, h
    else:
        x, y, bw, bh = bbox

    pad_x, pad_y = int(bw * cfg.crop_padding), int(bh * cfg.crop_padding)
    x0, y0 = max(0, x - pad_x), max(0, y - pad_y)
    x1, y1 = min(w, x + bw + pad_x), min(h, y + bh + pad_y)
    crop = bgr[y0:y1, x0:x1]
    inner = (x - x0, y - y0, bw, bh)

    scale = min(1.0, cfg.max_crop_side / max(crop.shape[:2]))
    if scale < 1.0:
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        inner = tuple(int(round(c * scale)) for c in inner)
    return crop, inner, scale


def segment_fruit(crop: np.ndarray, inner: tuple[int, int, int, int]) -> np.ndarray:
    """GrabCut으로 잎·가지·토양 배경을 제거하고, 가장 큰 덩어리를 과일 영역으로 본다.
    과일 내부의 핫스팟 구멍은 채워서 형태 분석에 영향을 주지 않게 한다."""
    h, w = crop.shape[:2]
    x, y, bw, bh = inner
    # bbox가 Crop 전체와 같으면(=bbox 없음) 가장자리를 조금 안쪽으로 잡는다
    if bw >= w - 2 or bh >= h - 2:
        mx, my = max(1, int(w * 0.05)), max(1, int(h * 0.05))
        x, y, bw, bh = mx, my, w - 2 * mx, h - 2 * my

    mask = np.zeros((h, w), np.uint8)
    if min(w, h) >= 20 and bw > 4 and bh > 4:
        bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
        try:
            cv2.grabCut(crop, mask, (x, y, bw, bh), bgd, fgd, 3, cv2.GC_INIT_WITH_RECT)
            mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
        except cv2.error:
            mask[:] = 0

    if cv2.countNonZero(mask) == 0:
        # GrabCut 실패 시: bbox에 내접하는 타원을 과일 영역으로 가정
        cv2.ellipse(mask, (x + bw // 2, y + bh // 2), (bw // 2, bh // 2), 0, 0, 360, 255, -1)

    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(mask)
    if contours:
        cv2.drawContours(filled, [max(contours, key=cv2.contourArea)], -1, 255, cv2.FILLED)
    return filled


# ---------------------------------------------------------------------------
# 7~9. 특징 추출
# ---------------------------------------------------------------------------

def shape_features(fruit_mask: np.ndarray, scale: float) -> ShapeFeatures | None:
    contours, _ = cv2.findContours(fruit_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return None
    c = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(c)
    perimeter = cv2.arcLength(c, True)
    if area <= 0 or perimeter <= 0:
        return None
    _, (rw, rh), _ = cv2.minAreaRect(c)
    hull_area = cv2.contourArea(cv2.convexHull(c))
    return ShapeFeatures(
        area_px=round(area / (scale * scale), 1),   # 축소 전 원본 기준 면적
        circularity=round(4 * math.pi * area / perimeter ** 2, 3),
        aspect_ratio=round(max(rw, rh) / max(min(rw, rh), 1e-6), 3),
        solidity=round(area / hull_area, 3) if hull_area > 0 else 0.0,
    )


def in_hue_ranges(h: np.ndarray, ranges: list[tuple[int, int]]) -> np.ndarray:
    m = np.zeros(h.shape, bool)
    for lo, hi in ranges:
        m |= (h >= lo) & (h <= hi)
    return m


def color_features(crop: np.ndarray, fruit_mask: np.ndarray,
                   cfg: Config) -> tuple[ColorFeatures | None, dict[str, np.ndarray]]:
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    fruit = fruit_mask > 0
    n_fruit = int(fruit.sum())
    if n_fruit == 0:
        return None, {}

    hotspot = ((v >= cfg.hotspot_v_min) & (s <= cfg.hotspot_s_max)).astype(np.uint8)
    if cfg.hotspot_dilate > 0:
        k = np.ones((2 * cfg.hotspot_dilate + 1,) * 2, np.uint8)
        hotspot = cv2.dilate(hotspot, k)
    hotspot = hotspot.astype(bool) & fruit
    shadow = (v <= cfg.shadow_v_max) & fruit
    low_sat = (s < cfg.hue_s_min) & fruit

    valid = fruit & ~hotspot & ~shadow & ~low_sat
    n_valid = int(valid.sum())

    ripe_hue = in_hue_ranges(h, cfg.hue_ripe)
    overripe = valid & ripe_hue & (v <= cfg.overripe_v_max)
    ripe = valid & ripe_hue & ~overripe
    unripe = valid & in_hue_ranges(h, cfg.hue_unripe)

    if n_valid:
        # Hue는 원형(0과 179가 이웃)이므로 각도로 바꿔 평균을 구한다
        ang = h[valid].astype(np.float64) * (2 * math.pi / 180.0)
        mean_h = (math.degrees(math.atan2(np.sin(ang).mean(), np.cos(ang).mean())) / 2.0) % 180
        mean_s, mean_v = float(s[valid].mean()), float(v[valid].mean())
    else:
        mean_h = mean_s = mean_v = 0.0

    def ratio(m: np.ndarray, base: int) -> float:
        return round(float(m.sum()) / base, 3) if base else 0.0

    feats = ColorFeatures(
        valid_ratio=ratio(valid, n_fruit),
        hotspot_ratio=ratio(hotspot, n_fruit),
        shadow_ratio=ratio(shadow, n_fruit),
        unripe_ratio=ratio(unripe, n_valid),
        ripe_ratio=ratio(ripe, n_valid),
        overripe_ratio=ratio(overripe, n_valid),
        mean_hue=round(mean_h, 1),
        mean_saturation=round(mean_s, 1),
        mean_value=round(mean_v, 1),
    )
    masks = {"hotspot": hotspot, "shadow": shadow, "unripe": unripe,
             "ripe": ripe, "overripe": overripe}
    return feats, masks


# ---------------------------------------------------------------------------
# 10. 수확 적기 판단
# ---------------------------------------------------------------------------

def decide(shape: ShapeFeatures | None, color: ColorFeatures | None,
           cfg: Config) -> tuple[str, float, list[str]]:
    if shape is None or color is None:
        return "unknown", 0.0, ["과일 영역을 찾지 못함"]

    reasons = []
    if color.valid_ratio < cfg.min_valid_ratio:
        return "unknown", 0.0, [
            f"판단 가능한 픽셀 부족({color.valid_ratio:.0%}): "
            f"핫스팟 {color.hotspot_ratio:.0%}, 그림자 {color.shadow_ratio:.0%}"]

    # 형태가 이상하면 판단은 하되 신뢰도를 낮춘다 (가림·겹침 가능성)
    penalty = 1.0
    if shape.circularity < cfg.min_circularity:
        penalty *= 0.7
        reasons.append(f"원형도 낮음({shape.circularity:.2f}) → 가림/겹침 의심")
    if shape.solidity < cfg.min_solidity:
        penalty *= 0.8
        reasons.append(f"Solidity 낮음({shape.solidity:.2f}) → 잎/가지 가림 의심")

    if color.overripe_ratio >= cfg.overripe_ratio_min:
        label, score = "overripe", color.overripe_ratio
        reasons.insert(0, f"과숙 색상 비율 {color.overripe_ratio:.0%}")
    elif color.ripe_ratio + color.overripe_ratio >= cfg.ready_ratio_min:
        if cfg.min_area_px and shape.area_px < cfg.min_area_px:
            label, score = "unripe", 0.5
            reasons.insert(0, f"색은 익었으나 크기 미달({shape.area_px:.0f}px < {cfg.min_area_px}px)")
        else:
            label, score = "harvest_ready", color.ripe_ratio + color.overripe_ratio
            reasons.insert(0, f"익은 색상 비율 {color.ripe_ratio + color.overripe_ratio:.0%}")
    else:
        label, score = "unripe", max(color.unripe_ratio, 1.0 - color.ripe_ratio)
        reasons.insert(0, f"익은 색상 비율 {color.ripe_ratio:.0%} (기준 {cfg.ready_ratio_min:.0%} 미만)")

    # 신뢰도: 규칙 점수 × 유효 픽셀 비율 × 형태 페널티
    confidence = float(np.clip(score, 0, 1)) * min(1.0, color.valid_ratio / 0.7) * penalty
    return label, round(confidence, 3), reasons


# ---------------------------------------------------------------------------
# 전체 파이프라인
# ---------------------------------------------------------------------------

def analyze_fruit(frame_bgr: np.ndarray, bbox: tuple[int, int, int, int] | None = None,
                  cfg: Config | None = None, return_debug: bool = False):
    """프레임 한 장과 (선택) YOLO Bounding Box를 받아 수확 적기를 판단한다.

    프레임 단위 보정(품질 검사, 밝기 보정)은 과일이 여러 개일 때 프레임당 한 번만
    하는 것이 효율적이다. 이 경우 preprocess_frame()과 analyze_crop()을 따로 호출한다.
    """
    cfg = cfg or Config()
    enhanced, quality, applied = preprocess_frame(frame_bgr, cfg)
    return analyze_crop(enhanced, quality, applied, bbox, cfg, return_debug)


def preprocess_frame(frame_bgr: np.ndarray, cfg: Config):
    quality = check_quality(frame_bgr, cfg)
    enhanced, applied = enhance(frame_bgr, quality, cfg) if quality.usable else (frame_bgr, [])
    return enhanced, quality, applied


def analyze_crop(enhanced: np.ndarray, quality: QualityReport, applied: list[str],
                 bbox: tuple[int, int, int, int] | None, cfg: Config, return_debug: bool = False):
    if not quality.usable:
        result = HarvestResult("unknown", 0.0, ["이미지 품질 불량: " + ", ".join(quality.issues)],
                               applied, quality, None, None)
        return (result, None) if return_debug else result

    crop, inner, scale = crop_with_padding(enhanced, bbox, cfg)
    fruit_mask = segment_fruit(crop, inner)
    shape = shape_features(fruit_mask, scale)
    color, masks = color_features(crop, fruit_mask, cfg)
    label, confidence, reasons = decide(shape, color, cfg)
    result = HarvestResult(label, confidence, reasons, applied, quality, shape, color)

    if not return_debug:
        return result
    return result, draw_debug(crop, fruit_mask, masks, result)


def draw_debug(crop: np.ndarray, fruit_mask: np.ndarray, masks: dict[str, np.ndarray],
               result: HarvestResult) -> np.ndarray:
    """왼쪽: 보정된 Crop + 과일 윤곽 / 오른쪽: 픽셀별 분류 결과."""
    left = crop.copy()
    contours, _ = cv2.findContours(fruit_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(left, contours, -1, (255, 255, 0), 1)

    right = np.zeros_like(crop)
    colors = {"unripe": (60, 174, 95), "ripe": (5, 183, 242), "overripe": (47, 69, 214),
              "hotspot": (255, 255, 255), "shadow": (90, 90, 90)}   # BGR
    for name, c in colors.items():
        if name in masks:
            right[masks[name]] = c

    panel = np.hstack([left, right])
    scale = max(1, 320 // panel.shape[1])
    panel = cv2.resize(panel, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
    bar = np.full((28, panel.shape[1], 3), 30, np.uint8)
    cv2.putText(bar, f"{result.label} ({result.confidence:.2f})", (6, 19),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return np.vstack([bar, panel])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_bbox(text: str) -> tuple[int, int, int, int]:
    parts = [int(p) for p in text.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("bbox 형식: x,y,w,h")
    return tuple(parts)  # type: ignore[return-value]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="과일 이미지의 수확 적기를 판단합니다.")
    parser.add_argument("image", help="입력 이미지 경로")
    parser.add_argument("--bbox", type=_parse_bbox, help="YOLO Bounding Box (x,y,w,h). 생략하면 전체 이미지")
    parser.add_argument("--debug", help="디버그 시각화 이미지를 저장할 경로")
    args = parser.parse_args(argv)

    frame = cv2.imread(args.image)
    if frame is None:
        print(f"이미지를 읽을 수 없습니다: {args.image}", file=sys.stderr)
        return 1

    result, debug = analyze_fruit(frame, args.bbox, return_debug=True)
    sys.stdout.reconfigure(encoding="utf-8")  # Windows에서 파이프로 넘길 때 한글 깨짐 방지
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    if args.debug and debug is not None:
        cv2.imwrite(args.debug, debug)
    return 0


if __name__ == "__main__":
    sys.exit(main())

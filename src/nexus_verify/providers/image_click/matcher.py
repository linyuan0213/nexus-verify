"""Matching utilities for image click captchas."""

from itertools import permutations

import cv2
import numpy as np
from PIL import Image

from nexus_verify.preprocessing import cv2_to_pil
from nexus_verify.providers.click_features import cosine_similarity, extract_click_feature
from nexus_verify.providers.click_solver import ClickCaptchaSolver, _preprocess_for_hog


def compute_scores(provider, target_icons, target_masks, candidates, background, background_mask):
    n_targets = len(target_icons)
    n_candidates = len(candidates)
    label_scores = np.zeros((n_targets, n_candidates))
    shape_scores = np.zeros((n_targets, n_candidates))
    mask_scores = np.zeros((n_targets, n_candidates))

    target_labels = [provider._recognize_icon(icon) for icon in target_icons]
    target_contours = [provider._get_outer_contour(mask) for mask in target_masks]

    for j, (x, y, w, h) in enumerate(candidates):
        candidate_img = background[y : y + h, x : x + w]
        candidate_label = provider._recognize_icon(candidate_img)
        candidate_mask = background_mask[y : y + h, x : x + w]
        candidate_contour = provider._get_outer_contour(candidate_mask)

        for i in range(n_targets):
            if target_labels[i] and candidate_label == target_labels[i]:
                label_scores[i, j] = 1.0

            t_contour = target_contours[i]
            if t_contour is not None and candidate_contour is not None:
                dist = cv2.matchShapes(t_contour, candidate_contour, cv2.CONTOURS_MATCH_I1, 0.0)
                shape_scores[i, j] = 1.0 / (1.0 + dist)
            else:
                shape_scores[i, j] = 0.0

            mask_scores[i, j] = provider._mask_correlation(target_masks[i], candidate_mask)

    return label_scores, shape_scores, mask_scores


def select_methods(label_scores, shape_scores):
    methods = []
    for i in range(label_scores.shape[0]):
        if label_scores[i].max() > 0.0:
            methods.append("label")
        elif shape_scores[i].max() >= 0.5:
            methods.append("shape")
        else:
            methods.append("mask")
    return methods


def solve_assignment(cost, candidates):
    n_targets = cost.shape[0]
    n_candidates = cost.shape[1]
    if n_targets == 0:
        return []
    if n_candidates < n_targets:
        return []

    if n_candidates > 12:
        areas = [w * h for _, _, w, h in candidates]
        top_indices = sorted(range(n_candidates), key=lambda idx: areas[idx], reverse=True)[:12]
        cost = cost[:, top_indices]
        selected_candidates = [candidates[idx] for idx in top_indices]
    else:
        selected_candidates = candidates

    best_assignment = None
    best_total = float("inf")
    for perm in permutations(range(cost.shape[1]), n_targets):
        total = sum(cost[i, perm[i]] for i in range(n_targets))
        if total < best_total:
            best_total = total
            best_assignment = perm

    if best_assignment is None:
        return []

    return [selected_candidates[j] for j in best_assignment]


def _box_center(box):
    x1, y1, x2, y2 = box
    return (x1 + x2) // 2, (y1 + y2) // 2


def hog_match(provider, target_icons, background):
    if provider._det_ocr is None:
        return [], 0.0

    pil_image = cv2_to_pil(background)
    boxes = ClickCaptchaSolver._merge_boxes(provider._det_ocr.detection(pil_image))
    if not boxes:
        return [], 0.0

    detections = []
    for box in boxes:
        x1, y1, x2, y2 = box
        crop = pil_image.crop((x1, y1, x2, y2))
        feat = extract_click_feature(_preprocess_for_hog(crop))
        detections.append((box, feat))

    target_feats = []
    for icon in target_icons:
        icon_pil = Image.fromarray(cv2.cvtColor(icon, cv2.COLOR_BGR2RGB))
        feat = extract_click_feature(_preprocess_for_hog(icon_pil))
        target_feats.append(feat)

    n_targets = len(target_feats)
    n_dets = len(detections)
    if n_dets < n_targets:
        return [], 0.0

    score = np.zeros((n_targets, n_dets))
    for i, tf in enumerate(target_feats):
        for j, (_, df) in enumerate(detections):
            score[i, j] = cosine_similarity(tf, df)

    best = None
    best_total = -float("inf")
    for perm in permutations(range(n_dets), n_targets):
        total = sum(score[i, perm[i]] for i in range(n_targets))
        if total > best_total:
            best_total = total
            best = perm

    if best is None:
        return [], 0.0

    max_score = max(score[i, best[i]] for i in range(n_targets))
    points = [_box_center(detections[j][0]) for j in best]
    return points, max_score


def match_icons(provider, target_icons, candidates, background):
    background_mask = (
        (background[:, :, 0] < 30)
        & (background[:, :, 1] < 30)
        & (background[:, :, 2] < 30)
    )

    target_masks = []
    for icon in target_icons:
        icon_gray = cv2.cvtColor(icon, cv2.COLOR_BGR2GRAY)
        _, icon_mask = cv2.threshold(icon_gray, 50, 255, cv2.THRESH_BINARY_INV)
        target_masks.append(icon_mask > 0)

    label_scores, shape_scores, mask_scores = compute_scores(
        provider, target_icons, target_masks, candidates, background, background_mask
    )
    methods = select_methods(label_scores, shape_scores)

    cost = np.zeros(label_scores.shape)
    for i, method in enumerate(methods):
        if method == "label":
            cost[i] = -10.0 * label_scores[i]
        elif method == "shape":
            cost[i] = -shape_scores[i]
        else:
            cost[i] = -mask_scores[i]

    assigned_boxes = solve_assignment(cost, candidates)
    icon_points = []
    for x, y, w, h in assigned_boxes:
        mask_region = background_mask[y : y + h, x : x + w].astype(np.uint8)
        area = cv2.countNonZero(mask_region)
        fill_ratio = area / (w * h) if w * h > 0 else 1.0
        aspect = h / w if w > 0 else 1.0
        if fill_ratio < 0.8 and aspect > 0.8:
            region = mask_region[: h // 2, : w // 2]
        else:
            region = mask_region
        moments = cv2.moments(region)
        if moments["m00"] > 0:
            cx = int(moments["m10"] / moments["m00"]) + x
            cy = int(moments["m01"] / moments["m00"]) + y
        else:
            cx, cy = x + w // 2, y + h // 2
        icon_points.append((cx, cy))

    hog_points, hog_max = hog_match(provider, target_icons, background)
    if label_scores.max() == 0 and hog_points and len(hog_points) >= len(target_icons) and hog_max > 0.5:
        return hog_points

    return icon_points

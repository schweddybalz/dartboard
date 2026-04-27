"""
board_map.py - Maps pixel coordinates to dartboard segments using homography

Uses calibration.json to compute a perspective transform from camera pixel
space to a top-down board coordinate system (mm from center).
"""

import json
import math
import numpy as np
import cv2

# Dartboard segment layout - clockwise from top (12 o'clock = 20)
SEGMENTS = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]

# Real board coordinates for each calibration point (x_mm, y_mm)
# Origin = bullseye, x positive = right (toward 6), y negative = up (toward 20)
POINT_REAL_COORDS = {
    "bullseye": (0.0,    0.0),
    "20_outer": (0.0,   -170.0),   # 0 deg
    "18_outer": (104.5, -137.4),   # 36 deg
    "6_outer":  (170.0,  0.0),     # 90 deg
    "10_outer": (137.4,  99.7),    # 126 deg
    "3_outer":  (0.0,    170.0),   # 180 deg
    "11_outer": (-170.0, 0.0),     # 270 deg
    "14_outer": (-161.8, -52.6),   # 288 deg
    "5_outer":  (-52.6,  -161.8),  # 342 deg
}

# Board ring radii in mm
OUTER_BULL_R    = 6.35
INNER_BULL_R    = 15.9
TRIPLE_INNER_R  = 99.0
TRIPLE_OUTER_R  = 107.0
DOUBLE_INNER_R  = 162.0
DOUBLE_OUTER_R  = 170.0


def compute_homography(cam_data):
    """
    Compute homography matrix from pixel space to board mm space.
    """
    src_pts = []
    dst_pts = []

    for point_name, real_coord in POINT_REAL_COORDS.items():
        if point_name not in cam_data:
            continue
        px, py = cam_data[point_name]
        rx, ry = real_coord
        src_pts.append([float(px), float(py)])
        dst_pts.append([float(rx), float(ry)])

    src = np.array(src_pts, dtype=np.float32)
    dst = np.array(dst_pts, dtype=np.float32)

    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
    return H


def pixel_to_board_mm(px, py, H):
    """
    Transform pixel coordinate to board mm coordinate using homography.
    Returns (x_mm, y_mm) where (0,0) is bullseye.
    """
    pt = np.array([[[float(px), float(py)]]], dtype=np.float32)
    result = cv2.perspectiveTransform(pt, H)
    x_mm = float(result[0][0][0])
    y_mm = float(result[0][0][1])
    return x_mm, y_mm


def board_mm_to_segment_ring(x_mm, y_mm):
    """
    Convert board mm coordinates to segment number and ring.
    Returns (segment, ring, dist_mm, angle_deg)
    """
    dist_mm = math.sqrt(x_mm**2 + y_mm**2)
    angle_deg = (math.degrees(math.atan2(x_mm, -y_mm))) % 360

    if dist_mm <= OUTER_BULL_R:
        ring = "bull"
        segment = 25
    elif dist_mm <= INNER_BULL_R:
        ring = "inner_bull"
        segment = 25
    elif dist_mm <= TRIPLE_INNER_R:
        ring = "single_inner"
        segment = angle_to_segment(angle_deg)
    elif dist_mm <= TRIPLE_OUTER_R:
        ring = "triple"
        segment = angle_to_segment(angle_deg)
    elif dist_mm <= DOUBLE_INNER_R:
        ring = "single_outer"
        segment = angle_to_segment(angle_deg)
    elif dist_mm <= DOUBLE_OUTER_R:
        ring = "double"
        segment = angle_to_segment(angle_deg)
    else:
        ring = "miss"
        segment = 0

    return segment, ring, dist_mm, angle_deg


def pixel_to_board(px, py, cam_data):
    """
    Full pipeline: pixel -> board mm -> segment/ring.
    Returns (segment, ring, dist_mm, angle_deg)
    """
    H = compute_homography(cam_data)
    x_mm, y_mm = pixel_to_board_mm(px, py, H)
    return board_mm_to_segment_ring(x_mm, y_mm)


def angle_to_segment(angle_deg):
    """Convert board angle (0=top, clockwise) to segment number."""
    normalized = (angle_deg + 9) % 360
    index = int(normalized / 18)
    return SEGMENTS[index % 20]


def score_from_ring(segment, ring):
    """Convert segment + ring to score value."""
    if ring == "bull":
        return 50
    elif ring == "inner_bull":
        return 25
    elif ring == "triple":
        return segment * 3
    elif ring == "double":
        return segment * 2
    elif ring in ("single_inner", "single_outer"):
        return segment
    else:
        return 0


def load_calibration(path="calibration.json"):
    with open(path) as f:
        data = json.load(f)
    return {int(k): v for k, v in data.items()}


if __name__ == "__main__":
    cal = load_calibration()

    for cam_id, cam_data in cal.items():
        H = compute_homography(cam_data)
        print(f"\nCam {cam_id} homography computed OK")

        # Test bullseye
        bx, by = cam_data["bullseye"]
        x_mm, y_mm = pixel_to_board_mm(bx, by, H)
        print(f"  Bullseye pixel ({bx},{by}) -> ({x_mm:.1f}, {y_mm:.1f}) mm (should be 0,0)")

        # Test each calibration point
        for name, (rx, ry) in POINT_REAL_COORDS.items():
            if name not in cam_data:
                continue
            px, py = cam_data[name]
            mx, my = pixel_to_board_mm(px, py, H)
            print(f"  {name}: ({mx:.1f},{my:.1f}) mm (expected ({rx:.1f},{ry:.1f}))")

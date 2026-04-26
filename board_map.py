"""
board_map.py - Maps pixel coordinates to dartboard segments

Uses calibration.json to compute angle/distance from bullseye
and determine which segment a dart landed in.
"""

import json
import math

# Dartboard segment layout - clockwise from top (12 o'clock = 20)
SEGMENTS = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]

# Each segment is 18 degrees wide, starting at -9 degrees from top
# Angle 0 = top (12 o'clock = segment 20)

# Known outer edge points and their real angles on the board
POINT_ANGLES = {
    "20_outer": 0,
    "6_outer":  90,
    "11_outer": 270,
    "14_outer": 288,
    "9_outer":  306,
    "12_outer": 324,
    "5_outer":  342,
}


def compute_scale_and_rotation(cam_data):
    """
    Given calibration points for one camera, compute:
    - bullseye pixel (cx, cy)
    - rotation offset: difference between pixel angle and real board angle
    - scale: pixels per mm (using outer ring radius ~170mm)
    Returns (cx, cy, rotation_offset_deg, pixels_per_mm)
    """
    cx, cy = cam_data["bullseye"]

    angles_pixel = []
    angles_real = []
    distances = []

    for point_name, real_angle in POINT_ANGLES.items():
        if point_name not in cam_data:
            continue
        px, py = cam_data[point_name]
        dx = px - cx
        dy = py - cy
        # pixel angle: 0=right, going clockwise. Convert to board convention (0=up)
        pixel_angle = math.degrees(math.atan2(dy, dx))  # -180 to 180
        # Convert to 0=up clockwise
        pixel_angle_board = (pixel_angle + 90) % 360

        dist = math.sqrt(dx*dx + dy*dy)
        distances.append(dist)

        # Compute rotation offset for this point
        offset = (real_angle - pixel_angle_board) % 360
        angles_pixel.append(pixel_angle_board)
        angles_real.append(real_angle)

    # Average rotation offset (handle wraparound)
    offsets = [(r - p) % 360 for r, p in zip(angles_real, angles_pixel)]
    # Unwrap offsets to avoid averaging across 0/360 boundary
    offsets_unwrapped = []
    base = offsets[0]
    for o in offsets:
        diff = (o - base + 180) % 360 - 180
        offsets_unwrapped.append(base + diff)
    rotation_offset = sum(offsets_unwrapped) / len(offsets_unwrapped)

    # Average distance to outer ring (double ring outer = 170mm)
    avg_dist = sum(distances) / len(distances)
    pixels_per_mm = avg_dist / 170.0

    return cx, cy, rotation_offset, pixels_per_mm


def pixel_to_board(px, py, cam_data):
    """
    Convert pixel coordinate to board position.
    Returns (segment, ring, distance_from_center_mm, angle_deg)
    ring: 'bull', 'inner_bull', 'single_inner', 'triple', 'single_outer', 'double', 'miss'
    """
    cx, cy, rotation_offset, pixels_per_mm = compute_scale_and_rotation(cam_data)

    dx = px - cx
    dy = py - cy

    # Distance in pixels, convert to mm
    dist_px = math.sqrt(dx*dx + dy*dy)
    dist_mm = dist_px / pixels_per_mm

    # Angle in pixel space (0=right, ccw positive) -> board space (0=top, cw positive)
    pixel_angle = math.degrees(math.atan2(dy, dx))
    board_angle = (pixel_angle + 90 + rotation_offset) % 360

    # Determine ring
    if dist_mm <= 6.35:
        ring = "bull"
        segment = 25
    elif dist_mm <= 15.9:
        ring = "inner_bull"
        segment = 25
    elif dist_mm <= 99:
        ring = "single_inner"
        segment = angle_to_segment(board_angle)
    elif dist_mm <= 107:
        ring = "triple"
        segment = angle_to_segment(board_angle)
    elif dist_mm <= 162:
        ring = "single_outer"
        segment = angle_to_segment(board_angle)
    elif dist_mm <= 170:
        ring = "double"
        segment = angle_to_segment(board_angle)
    else:
        ring = "miss"
        segment = 0

    return segment, ring, dist_mm, board_angle


def angle_to_segment(angle_deg):
    """Convert board angle (0=top, clockwise) to segment number."""
    # Each segment is 18 degrees, segment 20 is centered at 0 degrees
    # So segment 20 spans -9 to +9 degrees (351 to 9)
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
    # Keys come in as strings from JSON
    return {int(k): v for k, v in data.items()}


if __name__ == "__main__":
    # Quick test
    cal = load_calibration()
    for cam_id, cam_data in cal.items():
        cx, cy, rot, scale = compute_scale_and_rotation(cam_data)
        print(f"Cam {cam_id}: bullseye=({cx},{cy}) rotation={rot:.1f}deg scale={scale:.3f}px/mm")

    # Test: bullseye pixel should map to bull
    for cam_id, cam_data in cal.items():
        cx, cy = cam_data["bullseye"]
        seg, ring, dist, angle = pixel_to_board(cx, cy, cam_data)
        print(f"Cam {cam_id} bullseye test: segment={seg} ring={ring} dist={dist:.1f}mm")

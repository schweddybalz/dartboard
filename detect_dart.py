import cv2
import numpy as np
from picamera2 import Picamera2
import board_map

def capture(cam_id):
    picam = Picamera2(cam_id)
    config = picam.create_still_configuration(main={"size": (2304, 1296)})
    picam.configure(config)
    picam.set_controls({"AwbEnable": True, "AeEnable": True})
    picam.start()
    frame = picam.capture_array()
    picam.stop()
    picam.close()
    return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

def diff(base, current, threshold=30):
    gray_base = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY)
    gray_curr = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)
    delta = cv2.absdiff(gray_base, gray_curr)
    _, mask = cv2.threshold(delta, threshold, 255, cv2.THRESH_BINARY)
    return mask

def find_tip(mask, bullseye):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    largest = max(contours, key=cv2.contourArea)
    pts = largest[:, 0, :]

    # Fit line to get shaft direction
    result = cv2.fitLine(largest, cv2.DIST_L2, 0, 0.01, 0.01).flatten()
    vx, vy = float(result[0]), float(result[1])
    x, y = float(result[2]), float(result[3])

    # Project all points onto shaft axis
    projections = np.array([(pt[0] - x) * vx + (pt[1] - y) * vy for pt in pts])
    
    # Sort points by projection value
    sorted_idx = np.argsort(projections)
    sorted_pts = pts[sorted_idx]
    sorted_proj = projections[sorted_idx]
    
    # Divide into 10 slices along the shaft
    n_slices = 10
    slice_size = len(sorted_pts) // n_slices
    widths = []
    centers = []
    for i in range(n_slices):
        start = i * slice_size
        end = start + slice_size
        slice_pts = sorted_pts[start:end]
        # Width = perpendicular spread in this slice
        perp = np.array([(-vy * (pt[0] - x) + vx * (pt[1] - y)) for pt in slice_pts])
        width = perp.max() - perp.min() if len(perp) > 1 else 0
        widths.append(width)
        centers.append(slice_pts.mean(axis=0))
    
    # Tip is the slice with smallest width (narrowest = pointiest end)
    # but exclude the first and last slice to avoid noise
    inner_widths = widths[1:-1]
    min_idx = inner_widths.index(min(inner_widths)) + 1
    
    # Check both ends - pick the narrower one
    if widths[0] < widths[-1]:
        tip_center = centers[0]
    else:
        tip_center = centers[-1]
    
    return (int(tip_center[0]), int(tip_center[1]))

cal = board_map.load_calibration()

print("Capturing baseline...")
base0 = capture(0)
base1 = capture(1)
print("Baseline saved. Throw a dart, then press Enter...")
input()

print("Capturing after dart...")
curr0 = capture(0)
curr1 = capture(1)

mask0 = diff(base0, curr0)
mask1 = diff(base1, curr1)

tip0 = find_tip(mask0, cal[0]["bullseye"])
tip1 = find_tip(mask1, cal[1]["bullseye"])

# Save tip visualization
vis0 = curr0.copy()
vis1 = curr1.copy()
if tip0:
    cv2.circle(vis0, tip0, 10, (0, 0, 255), -1)
if tip1:
    cv2.circle(vis1, tip1, 10, (0, 0, 255), -1)
cv2.imwrite("tip_cam0.jpg", vis0)
cv2.imwrite("tip_cam1.jpg", vis1)

print(f"\nCam0 tip pixel: {tip0}")
print(f"Cam1 tip pixel: {tip1}")

if tip0:
    seg, ring, dist, angle = board_map.pixel_to_board(tip0[0], tip0[1], cal[0])
    score = board_map.score_from_ring(seg, ring)
    print(f"Cam0 -> segment={seg} ring={ring} dist={dist:.1f}mm angle={angle:.1f}deg score={score}")

if tip1:
    seg, ring, dist, angle = board_map.pixel_to_board(tip1[0], tip1[1], cal[1])
    score = board_map.score_from_ring(seg, ring)
    print(f"Cam1 -> segment={seg} ring={ring} dist={dist:.1f}mm angle={angle:.1f}deg score={score}")

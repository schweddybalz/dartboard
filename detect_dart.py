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
    img = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    return cv2.resize(img, (1280, 720))

def diff(base, current, threshold=30):
    gray_base = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY)
    gray_curr = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)
    delta = cv2.absdiff(gray_base, gray_curr)
    _, mask = cv2.threshold(delta, threshold, 255, cv2.THRESH_BINARY)
    return mask

def find_tip(mask, bullseye, H):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    bx, by = bullseye

    # Filter contours to only those near the board area
    board_contours = []
    for c in contours:
        pts = c[:, 0, :]
        dists = np.sqrt((pts[:, 0] - bx)**2 + (pts[:, 1] - by)**2)
        if dists.min() < 400:
            board_contours.append(c)

    if not board_contours:
        return None

    largest = max(board_contours, key=cv2.contourArea)
    pts = largest[:, 0, :]

    # Filter points to those within 250mm of board center in mm space
    board_pts = []
    for pt in pts:
        x_mm, y_mm = board_map.pixel_to_board_mm(int(pt[0]), int(pt[1]), H)
        dist_mm = np.sqrt(x_mm**2 + y_mm**2)
        if dist_mm <= 250:
            board_pts.append(pt)

    if not board_pts:
        # Fall back to full contour if no points in board area
        board_pts = list(pts)

    board_pts = np.array(board_pts)
    # Tip = bottommost board point (highest y value)
    tip = tuple(board_pts[board_pts[:, 1].argmax()])
    return tip

cal = board_map.load_calibration()

# Precompute homographies
H0 = board_map.compute_homography(cal[0])
H1 = board_map.compute_homography(cal[1])

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
cv2.imwrite("diff_cam0.jpg", mask0)
cv2.imwrite("diff_cam1.jpg", mask1)

tip0 = find_tip(mask0, cal[0]["bullseye"], H0)
tip1 = find_tip(mask1, cal[1]["bullseye"], H1)

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

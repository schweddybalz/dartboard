import cv2
import numpy as np
import board_map

def find_tip(mask, bullseye, H):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    bx, by = bullseye

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

    board_pts = []
    for pt in pts:
        x_mm, y_mm = board_map.pixel_to_board_mm(int(pt[0]), int(pt[1]), H)
        dist_mm = np.sqrt(x_mm**2 + y_mm**2)
        if dist_mm <= 250:
            board_pts.append(pt)

    if not board_pts:
        board_pts = list(pts)

    board_pts = np.array(board_pts)
    tip = tuple(board_pts[board_pts[:, 1].argmax()])
    return tip

cal = board_map.load_calibration()
H0 = board_map.compute_homography(cal[0])
H1 = board_map.compute_homography(cal[1])

# Load saved images
curr0 = cv2.imread("tip_cam0.jpg")
curr1 = cv2.imread("tip_cam1.jpg")
mask0 = cv2.imread("diff_cam0.jpg", cv2.IMREAD_GRAYSCALE)
mask1 = cv2.imread("diff_cam1.jpg", cv2.IMREAD_GRAYSCALE)

tip0 = find_tip(mask0, cal[0]["bullseye"], H0)
tip1 = find_tip(mask1, cal[1]["bullseye"], H1)

vis0 = curr0.copy()
vis1 = curr1.copy()
if tip0:
    cv2.circle(vis0, tip0, 10, (0, 0, 255), -1)
if tip1:
    cv2.circle(vis1, tip1, 10, (0, 0, 255), -1)
cv2.imwrite("test_tip_cam0.jpg", vis0)
cv2.imwrite("test_tip_cam1.jpg", vis1)

print(f"Cam0 tip: {tip0}")
print(f"Cam1 tip: {tip1}")

if tip0:
    seg, ring, dist, angle = board_map.pixel_to_board(tip0[0], tip0[1], cal[0])
    score = board_map.score_from_ring(seg, ring)
    print(f"Cam0 -> segment={seg} ring={ring} dist={dist:.1f}mm angle={angle:.1f}deg score={score}")

if tip1:
    seg, ring, dist, angle = board_map.pixel_to_board(tip1[0], tip1[1], cal[1])
    score = board_map.score_from_ring(seg, ring)
    print(f"Cam1 -> segment={seg} ring={ring} dist={dist:.1f}mm angle={angle:.1f}deg score={score}")
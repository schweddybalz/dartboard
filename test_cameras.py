from picamera2 import Picamera2
import cv2

for cam_id in [0, 1]:
    picam = Picamera2(cam_id)
    picam.start()
    frame = picam.capture_array()
    picam.stop()
    picam.close()
    filename = f"test_cam{cam_id}.jpg"
    cv2.imwrite(filename, frame)
    print(f"Camera {cam_id} OK -> {filename}")

print("Done")

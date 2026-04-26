"""
Dartboard Camera Calibration Tool
Run on the Pi: python calibrate.py
Open in browser: http://dartboard.local:8001
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import threading
import cv2
from picamera2 import Picamera2

CALIBRATION_POINTS = {
    "bullseye": None,       # center of board
    "20_outer": None,       # outer edge of 20 segment
    "6_outer": None,
    "11_outer": None,
    "14_outer": None,
    "9_outer": None,
    "12_outer": None,
    "5_outer": None,
}

# Real board coordinates (mm from center, angle in degrees)
# Segment centers clockwise from top: 20,1,18,4,13,6,10,15,2,17,3,19,7,16,8,11,14,9,12,5
SEGMENT_ANGLES = {
    20: 0, 1: 18, 18: 36, 4: 54, 13: 72, 6: 90,
    10: 108, 15: 126, 2: 144, 17: 162, 3: 180,
    19: 198, 7: 216, 16: 234, 8: 252, 11: 270,
    14: 288, 9: 306, 12: 324, 5: 342
}
OUTER_BULL_R = 6.35    # mm
INNER_BULL_R = 15.9
TRIPLE_INNER = 99
TRIPLE_OUTER = 107
DOUBLE_INNER = 162
DOUBLE_OUTER = 170

def capture_images():
    imgs = {}
    for cam_id in [0, 1]:
        picam = Picamera2(cam_id)
        config = picam.create_still_configuration(main={"size": (2304, 1296)})
        picam.configure(config)
        picam.set_controls({"AwbEnable": True, "AeEnable": True})
        picam.start()
        frame = picam.capture_array()
        picam.stop()
        picam.close()
        img = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        display = cv2.resize(img, (1280, 720))
        path = f"/tmp/calib_cam{cam_id}.jpg"
        cv2.imwrite(path, display)
        imgs[cam_id] = path
    return imgs

HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Dartboard Calibration</title>
<style>
  body { background: #111; color: #eee; font-family: monospace; margin: 0; padding: 20px; }
  h1 { color: #4af; }
  .container { display: flex; gap: 20px; flex-wrap: wrap; }
  .cam-panel { flex: 1; min-width: 400px; }
  h2 { color: #4af; }
  .canvas-wrap { position: relative; display: inline-block; }
  canvas { border: 1px solid #444; cursor: crosshair; max-width: 100%; }
  .points-list { margin-top: 10px; font-size: 12px; }
  .point-row { display: flex; justify-content: space-between; padding: 3px 0; border-bottom: 1px solid #333; }
  .point-row.set { color: #4f4; }
  .point-row.unset { color: #888; }
  select { background: #222; color: #eee; border: 1px solid #444; padding: 4px; margin-bottom: 10px; }
  button { background: #4af; color: #000; border: none; padding: 8px 16px; cursor: pointer; margin-top: 10px; font-weight: bold; }
  button:hover { background: #6cf; }
  .instructions { background: #1a1a2e; border: 1px solid #4af; padding: 12px; margin-bottom: 20px; border-radius: 4px; }
  .dot { width: 10px; height: 10px; border-radius: 50%; background: red; position: absolute; transform: translate(-50%, -50%); pointer-events: none; }
</style>
</head>
<body>
<h1>🎯 Dartboard Calibration</h1>
<div class="instructions">
  <b>Instructions:</b> For each camera, select a point type from the dropdown, then click that location on the image.
  Mark: bullseye center, then the outer edge center of segments 20, 6, 11, 14, 9, 12, 5.
  When done, click Save Calibration.
</div>
<div class="container">
  <div class="cam-panel">
    <h2>Camera 0</h2>
    <select id="select0">
      <option value="bullseye">Bullseye Center</option>
      <option value="20_outer">20 - Outer Edge</option>
      <option value="6_outer">6 - Outer Edge</option>
      <option value="11_outer">11 - Outer Edge</option>
      <option value="14_outer">14 - Outer Edge</option>
      <option value="9_outer">9 - Outer Edge</option>
      <option value="12_outer">12 - Outer Edge</option>
      <option value="5_outer">5 - Outer Edge</option>
    </select>
    <div class="canvas-wrap" id="wrap0">
      <canvas id="cam0" width="1280" height="720"></canvas>
    </div>
    <div class="points-list" id="list0"></div>
  </div>
  <div class="cam-panel">
    <h2>Camera 1</h2>
    <select id="select1">
      <option value="bullseye">Bullseye Center</option>
      <option value="20_outer">20 - Outer Edge</option>
      <option value="6_outer">6 - Outer Edge</option>
      <option value="11_outer">11 - Outer Edge</option>
      <option value="14_outer">14 - Outer Edge</option>
      <option value="9_outer">9 - Outer Edge</option>
      <option value="12_outer">12 - Outer Edge</option>
      <option value="5_outer">5 - Outer Edge</option>
    </select>
    <div class="canvas-wrap" id="wrap1">
      <canvas id="cam1" width="1280" height="720"></canvas>
    </div>
    <div class="points-list" id="list1"></div>
  </div>
</div>
<button onclick="saveCalibration()">💾 Save Calibration</button>
<button onclick="shutdown()" style="background:#f44;margin-left:10px;">Exit</button>
<div id="status" style="margin-top:10px;color:#4f4;"></div>

<script>
const points = { 0: {}, 1: {} };
const pointNames = ['bullseye','20_outer','6_outer','11_outer','14_outer','9_outer','12_outer','5_outer'];

function loadImage(camId) {
  const canvas = document.getElementById('cam' + camId);
  const ctx = canvas.getContext('2d');
  const img = new Image();
  img.onload = () => {
    canvas.width = img.width;
    canvas.height = img.height;
    ctx.drawImage(img, 0, 0);
  };
  img.src = '/image/' + camId + '?' + Date.now();
}

function setupCanvas(camId) {
  const canvas = document.getElementById('cam' + camId);
  canvas.addEventListener('click', (e) => {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = Math.round((e.clientX - rect.left) * scaleX);
    const y = Math.round((e.clientY - rect.top) * scaleY);
    const select = document.getElementById('select' + camId);
    const selected = select.value;
    points[camId][selected] = [x, y];
    redraw(camId);
    updateList(camId);
    // Auto-advance to next point
    const currentIdx = pointNames.indexOf(selected);
    if (currentIdx < pointNames.length - 1) {
      select.value = pointNames[currentIdx + 1];
    }
  });
}

function redraw(camId) {
  const canvas = document.getElementById('cam' + camId);
  const ctx = canvas.getContext('2d');
  const img = new Image();
  img.onload = () => {
    ctx.drawImage(img, 0, 0);
    for (const [name, pt] of Object.entries(points[camId])) {
      ctx.beginPath();
      ctx.arc(pt[0], pt[1], 8, 0, 2 * Math.PI);
      ctx.fillStyle = name === 'bullseye' ? 'cyan' : 'red';
      ctx.fill();
      ctx.fillStyle = 'white';
      ctx.font = '14px monospace';
      ctx.fillText(name, pt[0] + 10, pt[1] + 5);
    }
  };
  img.src = '/image/' + camId + '?' + Date.now();
}

function updateList(camId) {
  const list = document.getElementById('list' + camId);
  list.innerHTML = pointNames.map(name => {
    const pt = points[camId][name];
    const cls = pt ? 'set' : 'unset';
    const val = pt ? `(${pt[0]}, ${pt[1]})` : 'not set';
    return `<div class="point-row ${cls}"><span>${name}</span><span>${val}</span></div>`;
  }).join('');
}

async function saveCalibration() {
  const res = await fetch('/save', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(points)
  });
  const data = await res.json();
  document.getElementById('status').textContent = data.message;
}

async function shutdown() {
  await fetch('/shutdown', { method: 'POST' });
  document.getElementById('status').textContent = 'Server stopped.';
}

loadImage(0);
loadImage(1);
setupCanvas(0);
setupCanvas(1);
updateList(0);
updateList(1);
</script>
</body>
</html>
"""

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress request logs

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML.encode())

        elif self.path.startswith('/image/'):
            cam_id = int(self.path.split('/')[-1].split('?')[0])
            path = f"/tmp/calib_cam{cam_id}.jpg"
            if not os.path.exists(path):
                self.send_response(404)
                self.end_headers()
                return
            with open(path, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'image/jpeg')
            self.send_header('Content-Length', len(data))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/save':
            length = int(self.headers['Content-Length'])
            body = json.loads(self.rfile.read(length))
            # Convert string keys to int
            calibration = {}
            for cam_id_str, pts in body.items():
                calibration[int(cam_id_str)] = pts
            with open('calibration.json', 'w') as f:
                json.dump(calibration, f, indent=2)
            print("Calibration saved to calibration.json")
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"message": "Calibration saved!"}).encode())
        elif self.path == '/shutdown':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"message": "Shutting down"}).encode())
            threading.Thread(target=self.server.shutdown).start()
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    print("Capturing images from both cameras...")
    capture_images()
    print("Images captured.")
    print("Starting calibration server at http://dartboard.local:8001")
    server = HTTPServer(('0.0.0.0', 8001), Handler)
    server.serve_forever()

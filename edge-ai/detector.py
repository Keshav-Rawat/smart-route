"""
SMART_ROUTE - Advanced Edge AI Vehicle Detector
- YOLOv8m for accuracy
- ByteTrack for unique vehicle tracking
- ROI-based lane counting
- Direction-aware detection
"""

import cv2
import time
import subprocess
import json
import os
import requests
import numpy as np
from ultralytics import YOLO
from collections import defaultdict
# pyrefly: ignore [missing-import]
from shapely.geometry import Point, Polygon

# ============ CONFIG ============
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
INTERSECTION_ID = os.getenv("INTERSECTION_ID", "intersection_1")
SEND_INTERVAL = int(os.getenv("SEND_INTERVAL", 2))
VIDEO_SOURCE = os.getenv("VIDEO_SOURCE", "sample_traffic.mp4")

MODEL_NAME = "yolov8m.pt"   # m = medium (better accuracy)
CONFIDENCE_THRESHOLD = 0.4
IOU_THRESHOLD = 0.5
FRAME_RESIZE = (1280, 720)  # standard resolution
# ================================

# Vehicle classes
VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck"
}

# Load model
print(f"🔄 Loading {MODEL_NAME}...")
model = YOLO(MODEL_NAME)
print("✅ Model loaded\n")

# Load lane config
try:
    with open("lanes_config.json") as f:
        LANE_CONFIG = json.load(f)[INTERSECTION_ID]
    print(f"✅ Loaded {len(LANE_CONFIG['lanes'])} lanes from config")
except FileNotFoundError:
    print("⚠️  lanes_config.json not found, using whole frame")
    LANE_CONFIG = None


class VehicleTracker:
    """Tracks unique vehicles across frames"""
    
    def __init__(self):
        # Track which vehicles we've already counted per lane
        self.counted_per_lane = defaultdict(set)  # {lane_name: {track_ids}}
        # Current frame counts
        self.current_counts = defaultdict(lambda: defaultdict(int))
        # Total cumulative counts
        self.total_counts = defaultdict(lambda: defaultdict(int))
    
    def get_lane_for_point(self, x, y):
        """Find which lane a point belongs to"""
        if not LANE_CONFIG:
            return "main"
        
        point = Point(x, y)
        for lane_name, lane_data in LANE_CONFIG["lanes"].items():
            polygon = Polygon(lane_data["polygon"])
            if polygon.contains(point):
                return lane_name
        return None
    
    def update(self, detections):
        """
        detections: list of (track_id, class_name, x_center, y_center)
        """
        # Reset current frame counts
        self.current_counts = defaultdict(lambda: defaultdict(int))
        
        for track_id, class_name, x, y in detections:
            lane = self.get_lane_for_point(x, y)
            if lane is None:
                continue
            
            # Count for current frame
            self.current_counts[lane][class_name] += 1
            
            # Count uniquely (cumulative)
            unique_key = f"{track_id}"
            if unique_key not in self.counted_per_lane[lane]:
                self.counted_per_lane[lane].add(unique_key)
                self.total_counts[lane][class_name] += 1
    
    def get_summary(self):
        """Get full summary for backend"""
        summary = {
            "total_vehicles_now": 0,
            "total_unique_seen": 0,
            "lanes": {}
        }
        
        for lane_name in (LANE_CONFIG["lanes"].keys() if LANE_CONFIG else ["main"]):
            current = dict(self.current_counts[lane_name])
            total = dict(self.total_counts[lane_name])
            
            current_sum = sum(current.values())
            total_sum = sum(total.values())
            
            summary["lanes"][lane_name] = {
                "current": current_sum,
                "cumulative": total_sum,
                "breakdown": current,
                "direction": LANE_CONFIG["lanes"][lane_name]["direction"] if LANE_CONFIG else "unknown"
            }
            
            summary["total_vehicles_now"] += current_sum
            summary["total_unique_seen"] += total_sum
        
        return summary


def draw_lanes(frame):
    """Draw ROI polygons on frame"""
    if not LANE_CONFIG:
        return frame
    
    overlay = frame.copy()
    for lane_name, lane_data in LANE_CONFIG["lanes"].items():
        pts = np.array(lane_data["polygon"], np.int32).reshape((-1, 1, 2))
        color = tuple(lane_data["color"])
        
        # Filled transparent polygon
        cv2.fillPoly(overlay, [pts], color)
        # Border
        cv2.polylines(frame, [pts], True, color, 2)
        
        # Label
        center_x = int(np.mean([p[0] for p in lane_data["polygon"]]))
        center_y = int(np.mean([p[1] for p in lane_data["polygon"]]))
        cv2.putText(frame, lane_name.upper(), (center_x - 30, center_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    # Blend overlay
    cv2.addWeighted(overlay, 0.2, frame, 0.8, 0, frame)
    return frame


def draw_stats(frame, summary):
    """Draw stats panel on frame"""
    h, w = frame.shape[:2]
    
    # Semi-transparent panel
    panel = frame.copy()
    cv2.rectangle(panel, (10, 10), (380, 200), (0, 0, 0), -1)
    cv2.addWeighted(panel, 0.7, frame, 0.3, 0, frame)
    
    # Title
    cv2.putText(frame, "SMART_ROUTE LIVE", (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    
    # Stats
    cv2.putText(frame, f"Vehicles NOW: {summary['total_vehicles_now']}", (20, 70),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    cv2.putText(frame, f"Unique Total: {summary['total_unique_seen']}", (20, 95),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
    
    # Per-lane
    y = 130
    for lane_name, data in summary["lanes"].items():
        text = f"{lane_name.upper()}: {data['current']} (Σ{data['cumulative']})"
        cv2.putText(frame, text, (20, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        y += 22
    
    return frame


def send_to_backend(summary):
    """Send detailed lane data to backend"""
    try:
        url = f"{BACKEND_URL}/traffic/{INTERSECTION_ID}/detailed"
        response = requests.post(url, json=summary, timeout=2)
        
        if response.status_code == 200:
            print(f"✅ Backend OK | Now: {summary['total_vehicles_now']} | "
                  f"Unique: {summary['total_unique_seen']} | "
                  f"Lanes: {[(k, v['current']) for k, v in summary['lanes'].items()]}")
        else:
            # Fallback to simple endpoint
            fallback_url = f"{BACKEND_URL}/traffic/{INTERSECTION_ID}/update"
            requests.post(fallback_url, params={"vehicle_count": summary["total_vehicles_now"]}, timeout=2)
            print(f"✅ Sent (simple) | Now: {summary['total_vehicles_now']}")
    except requests.exceptions.ConnectionError:
        print("❌ Backend not running!")
    except Exception as e:
        print(f"❌ Error: {e}")


def get_youtube_stream_url(youtube_url):
    """Uses yt-dlp to extract the direct raw stream URL from a YouTube link"""
    print(f"⏳ Extracting live stream URL from {youtube_url}...")
    try:
        cmd = ["yt-dlp", "-f", "best[height<=720]", "-g", youtube_url]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip().split('\n')[0]
    except Exception as e:
        print(f"❌ Failed to extract stream: {e}")
        return None


def detect_vehicles(video_source):
    """Main detection loop with tracking"""
    if "youtube.com" in video_source or "youtu.be" in video_source:
        actual_source = get_youtube_stream_url(video_source)
        if not actual_source:
            return
    else:
        actual_source = video_source

    cap = cv2.VideoCapture(actual_source)
    
    if not cap.isOpened():
        print(f"❌ Cannot open: {video_source}")
        return
    
    print(f"✅ Detection started on: {video_source}")
    print(f"📡 Sending to: {BACKEND_URL}\n")
    print("Press 'q' to quit | 'r' to reset counts | 's' to save snapshot\n")
    
    tracker = VehicleTracker()
    last_sent_time = time.time()
    frame_count = 0
    fps_start = time.time()
    fps = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("📺 End of video, restarting...")
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # loop video
            continue
        
        # Resize for consistency
        frame = cv2.resize(frame, FRAME_RESIZE)
        frame_count += 1
        
        # Run YOLO with tracking (uses ByteTrack by default)
        results = model.track(
            frame,
            persist=True,
            conf=CONFIDENCE_THRESHOLD,
            iou=IOU_THRESHOLD,
            classes=list(VEHICLE_CLASSES.keys()),
            tracker="bytetrack.yaml",
            verbose=False
        )
        
        # Extract detections
        detections = []
        if results[0].boxes is not None and results[0].boxes.id is not None:
            # pyrefly: ignore [missing-attribute]
            boxes = results[0].boxes.xyxy.cpu().numpy()
            # pyrefly: ignore [missing-attribute]
            track_ids = results[0].boxes.id.cpu().numpy().astype(int)
            # pyrefly: ignore [missing-attribute]
            class_ids = results[0].boxes.cls.cpu().numpy().astype(int)
            # pyrefly: ignore [missing-attribute]
            confidences = results[0].boxes.conf.cpu().numpy()
            
            for box, tid, cid, conf in zip(boxes, track_ids, class_ids, confidences):
                if cid not in VEHICLE_CLASSES:
                    continue
                
                x1, y1, x2, y2 = map(int, box)
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                class_name = VEHICLE_CLASSES[cid]
                
                detections.append((tid, class_name, cx, cy))
                
                # Draw box
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                
                # Draw ID + class
                label = f"#{tid} {class_name} {conf:.2f}"
                cv2.putText(frame, label, (x1, y1 - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                # Center dot
                cv2.circle(frame, (cx, cy), 4, (0, 0, 255), -1)
        
        # Update tracker
        tracker.update(detections)
        summary = tracker.get_summary()
        
        # Draw overlays
        frame = draw_lanes(frame)
        frame = draw_stats(frame, summary)
        
        # FPS counter
        if frame_count % 30 == 0:
            fps = 30 / (time.time() - fps_start)
            fps_start = time.time()
        cv2.putText(frame, f"FPS: {fps:.1f}", (FRAME_RESIZE[0] - 120, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        # Send to backend
        if time.time() - last_sent_time >= SEND_INTERVAL:
            send_to_backend(summary)
            last_sent_time = time.time()
        
        # Display
        cv2.imshow("SMART_ROUTE - Advanced Detection", frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('r'):
            tracker = VehicleTracker()
            print("🔄 Counts reset")
        elif key == ord('s'):
            cv2.imwrite(f"snapshot_{int(time.time())}.jpg", frame)
            print("📸 Snapshot saved")
    
    cap.release()
    cv2.destroyAllWindows()
    
    print(f"\n📊 Final Stats:")
    print(f"   Total unique vehicles seen: {summary['total_unique_seen']}")
    for lane, data in summary["lanes"].items():
        print(f"   {lane}: {data['cumulative']} vehicles")


if __name__ == "__main__":
    detect_vehicles(VIDEO_SOURCE)
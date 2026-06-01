"""
SMART_ROUTE - Edge AI Vehicle Detector
Detects vehicles using YOLOv8 and sends counts to backend API
"""

import cv2
import os
import sys
import time
import requests
from ultralytics import YOLO
from collections import defaultdict

# ============ CONFIG ============
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
INTERSECTION_ID = os.getenv("INTERSECTION_ID", "intersection_1")
SEND_INTERVAL = int(os.getenv("SEND_INTERVAL", 2))

HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

VIDEO_SOURCE = sys.argv[1] if len(sys.argv) > 1 else os.getenv(
    "VIDEO_SOURCE",
    "/app/sample_trafficcopy.mp4"
)
# ================================

print(f"VIDEO_SOURCE = {VIDEO_SOURCE}")
print(f"FILE EXISTS = {os.path.exists(VIDEO_SOURCE)}")

# Load YOLOv8 model
model = YOLO("yolov8n.pt")

# Vehicle classes from COCO
VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck"
}


def send_to_backend(vehicle_count, breakdown):
    """Send vehicle data to FastAPI backend"""
    try:
        url = f"{BACKEND_URL}/traffic/{INTERSECTION_ID}/update"

        response = requests.post(
            url,
            params={"vehicle_count": vehicle_count},
            timeout=2
        )

        if response.status_code == 200:
            data = response.json()

            print(
                f"✅ Sent | Vehicles={vehicle_count} | "
                f"Signal={data.get('signal_state', 'N/A')}"
            )

        else:
            print(f"⚠️ Backend returned {response.status_code}")

    except requests.exceptions.ConnectionError:
        print("❌ Backend connection failed")

    except Exception as e:
        print(f"❌ Backend error: {e}")


def detect_vehicles(video_source):
    """Main detection loop"""

    print(f"Opening video source: {video_source}")

    cap = cv2.VideoCapture(video_source)

    if not cap.isOpened():
        print(f"❌ Cannot open video source: {video_source}")
        return

    print("✅ Starting vehicle detection...")
    print(f"📡 Sending data to: {BACKEND_URL}")

    last_sent_time = time.time()

    while True:

        ret, frame = cap.read()

        if not ret:
            print("🎬 End of video stream")
            break

        try:
            results = model(frame, verbose=False)

        except Exception as e:
            print(f"❌ YOLO inference error: {e}")
            break

        vehicle_counts = defaultdict(int)

        for result in results:

            boxes = result.boxes

            for box in boxes:

                cls_id = int(box.cls[0])

                if cls_id in VEHICLE_CLASSES:

                    vehicle_type = VEHICLE_CLASSES[cls_id]
                    vehicle_counts[vehicle_type] += 1

                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf = float(box.conf[0])

                    cv2.rectangle(
                        frame,
                        (x1, y1),
                        (x2, y2),
                        (0, 255, 0),
                        2
                    )

                    cv2.putText(
                        frame,
                        f"{vehicle_type} {conf:.2f}",
                        (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 255, 0),
                        2
                    )

        total = sum(vehicle_counts.values())

        cv2.putText(
            frame,
            f"Total Vehicles: {total}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2
        )

        current_time = time.time()

        if current_time - last_sent_time >= SEND_INTERVAL:

            send_to_backend(
                total,
                dict(vehicle_counts)
            )

            last_sent_time = current_time

        # Display only when not in Docker/headless mode
        if not HEADLESS:

            cv2.imshow(
                "SMART_ROUTE - Vehicle Detection",
                frame
            )

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()

    if not HEADLESS:
        cv2.destroyAllWindows()

    print("👋 Detection stopped")


if __name__ == "__main__":
    detect_vehicles(VIDEO_SOURCE)
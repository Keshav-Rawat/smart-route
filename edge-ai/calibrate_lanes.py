"""
ROI Calibration Tool
- Click 4 points to define each lane
- Press 'n' for next lane, 's' to save, 'q' to quit
"""

import cv2
import json
import numpy as np

VIDEO_PATH = "sample_traffic.mp4"
OUTPUT_JSON = "lanes_config.json"
INTERSECTION_ID = "intersection_1"

LANE_NAMES = ["north", "south", "east", "west"]
COLORS = [(0, 255, 0), (255, 0, 0), (0, 255, 255), (255, 0, 255)]
DIRECTIONS = ["incoming", "outgoing", "incoming", "outgoing"]

current_lane = 0
current_points = []
all_lanes = {}

def mouse_callback(event, x, y, flags, param):
    global current_points
    if event == cv2.EVENT_LBUTTONDOWN:
        current_points.append([x, y])
        print(f"  Point {len(current_points)}: ({x}, {y})")

def main():
    global current_lane, current_points, all_lanes
    
    cap = cv2.VideoCapture(VIDEO_PATH)
    ret, frame = cap.read()
    if not ret:
        print("❌ Cannot read video")
        return
    
    frame = cv2.resize(frame, (1280, 720))
    H, W = frame.shape[:2]
    
    cv2.namedWindow("Calibrate Lanes")
    # pyrefly: ignore [missing-attribute]
    cv2.setMouseCallback("Calibrate Lanes", mouse_callback)
    
    print("\n=== LANE CALIBRATION ===")
    print(f"Click 4 corners for: {LANE_NAMES[current_lane].upper()}")
    print("Press 'n' = next lane | 's' = save | 'r' = redo | 'q' = quit\n")
    
    while True:
        display = frame.copy()
        
        # Draw saved lanes
        for name, data in all_lanes.items():
            pts = np.array(data["polygon"], np.int32).reshape((-1, 1, 2))
            cv2.polylines(display, [pts], True, tuple(data["color"]), 2)
            cx = int(np.mean([p[0] for p in data["polygon"]]))
            cy = int(np.mean([p[1] for p in data["polygon"]]))
            cv2.putText(display, name.upper(), (cx-30, cy),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
        
        # Draw current points
        for i, pt in enumerate(current_points):
            cv2.circle(display, tuple(pt), 6, (0,0,255), -1)
            cv2.putText(display, str(i+1), (pt[0]+10, pt[1]),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 2)
        
        if len(current_points) > 1:
            cv2.polylines(display, [np.array(current_points)], False, (0,0,255), 2)
        
        # Status
        cv2.putText(display, f"Defining: {LANE_NAMES[current_lane].upper()} ({len(current_points)}/4)",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)
        cv2.putText(display, "n=next  s=save  r=redo  q=quit",
                    (10, H-20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
        
        cv2.imshow("Calibrate Lanes", display)
        key = cv2.waitKey(20) & 0xFF
        
        if key == ord('q'):
            break
        elif key == ord('r'):
            current_points = []
            print("🔄 Cleared current lane points")
        elif key == ord('n'):
            if len(current_points) == 4:
                all_lanes[LANE_NAMES[current_lane]] = {
                    "polygon": current_points.copy(),
                    "direction": DIRECTIONS[current_lane],
                    "color": list(COLORS[current_lane])
                }
                print(f"✅ Saved {LANE_NAMES[current_lane]}")
                current_points = []
                current_lane += 1
                if current_lane >= len(LANE_NAMES):
                    print("✅ All lanes done! Press 's' to save.")
                    current_lane = len(LANE_NAMES) - 1
                else:
                    print(f"\nNow click 4 corners for: {LANE_NAMES[current_lane].upper()}")
            else:
                print(f"⚠️  Need 4 points, got {len(current_points)}")
        elif key == ord('s'):
            config = {
                INTERSECTION_ID: {
                    "video_width": W,
                    "video_height": H,
                    "lanes": all_lanes
                }
            }
            with open(OUTPUT_JSON, 'w') as f:
                json.dump(config, f, indent=2)
            print(f"💾 Saved to {OUTPUT_JSON}")
            break
    
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
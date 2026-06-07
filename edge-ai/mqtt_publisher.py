"""
SmartRoute — MQTT Publisher (Edge AI side)
===========================================
Publishes vehicle detection data from the YOLOv8 detector
to an MQTT broker so any subscriber (backend, dashboard, cloud)
can consume it in real-time.

Topics:
  smartroute/{intersection_id}/vehicles   → vehicle count summary
  smartroute/{intersection_id}/lanes      → per-lane breakdown
  smartroute/{intersection_id}/signal     → current signal state

Usage:
  # Start with detector (replaces direct HTTP calls)
  python detector.py  # set MQTT_ENABLED=1 to use this instead of HTTP

  # Or run standalone to simulate data:
  python mqtt_publisher.py --simulate
"""

import os
import json
import time
import argparse
import threading
import random
import math
from datetime import datetime
from typing import Any, Dict

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    print("⚠  paho-mqtt not installed. Run: pip install paho-mqtt")

# ── Config ───────────────────────────────────────────────────────
MQTT_HOST       = os.getenv("MQTT_HOST",       "localhost")
MQTT_PORT       = int(os.getenv("MQTT_PORT",   "1883"))
MQTT_USERNAME   = os.getenv("MQTT_USERNAME",   "")
MQTT_PASSWORD   = os.getenv("MQTT_PASSWORD",   "")
INTERSECTION_ID = os.getenv("INTERSECTION_ID", "intersection_1")
PUBLISH_INTERVAL = float(os.getenv("PUBLISH_INTERVAL", "2.0"))

BASE_TOPIC = f"smartroute/{INTERSECTION_ID}"
TOPIC_VEHICLES = f"{BASE_TOPIC}/vehicles"
TOPIC_LANES    = f"{BASE_TOPIC}/lanes"
TOPIC_SIGNAL   = f"{BASE_TOPIC}/signal"
TOPIC_ALERT    = f"smartroute/alerts"


class SmartRouteMQTTPublisher:
    """
    Wraps paho-mqtt with SmartRoute-specific topic structure.
    Handles reconnection, QoS, and message serialisation.
    """

    def __init__(self):
        if not MQTT_AVAILABLE:
            raise RuntimeError("paho-mqtt not installed. Run: pip install paho-mqtt")

        self.client = mqtt.Client(
            client_id=f"smartroute-publisher-{INTERSECTION_ID}",
            protocol=mqtt.MQTTv5,
        )

        if MQTT_USERNAME:
            self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

        self.client.on_connect    = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_publish    = self._on_publish

        self.connected    = False
        self.published    = 0

    def connect(self):
        print(f"⏳ Connecting to MQTT broker at {MQTT_HOST}:{MQTT_PORT}…")
        self.client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        self.client.loop_start()
        # Wait up to 5s for connection
        for _ in range(50):
            if self.connected:
                break
            time.sleep(0.1)
        return self.connected

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def _on_connect(self, client, userdata, flags, rc, props=None):
        if rc == 0:
            self.connected = True
            print(f"✅ MQTT connected → {MQTT_HOST}:{MQTT_PORT}")
        else:
            print(f"❌ MQTT connect failed (rc={rc})")

    def _on_disconnect(self, client, userdata, rc, props=None):
        self.connected = False
        if rc != 0:
            print(f"⚠  MQTT disconnected unexpectedly (rc={rc}), will reconnect…")

    def _on_publish(self, client, userdata, mid):
        self.published += 1

    def publish(self, topic: str, payload: Dict[str, Any], qos: int = 1):
        """Publish a JSON payload to a topic."""
        if not self.connected:
            print(f"  ⚠  Not connected, skipping publish to {topic}")
            return False
        msg = json.dumps({ **payload, "_ts": datetime.utcnow().isoformat() + "Z" })
        result = self.client.publish(topic, msg, qos=qos, retain=False)
        return result.rc == mqtt.MQTT_ERR_SUCCESS

    def publish_vehicle_update(self, summary: dict):
        """
        Publish a full vehicle detection summary.
        Called by detector.py after every YOLO frame batch.
        """
        # 1. Total vehicle count
        self.publish(TOPIC_VEHICLES, {
            "intersection_id"    : INTERSECTION_ID,
            "total_vehicles_now" : summary.get("total_vehicles_now", 0),
            "total_unique_seen"  : summary.get("total_unique_seen", 0),
        })

        # 2. Per-lane breakdown
        self.publish(TOPIC_LANES, {
            "intersection_id": INTERSECTION_ID,
            "lanes"          : summary.get("lanes", {}),
        })

        # 3. Congestion alert if high
        total = summary.get("total_vehicles_now", 0)
        if total >= 30:
            self.publish(TOPIC_ALERT, {
                "intersection_id": INTERSECTION_ID,
                "level"          : "HIGH",
                "count"          : total,
                "message"        : f"High congestion at {INTERSECTION_ID}: {total} vehicles",
            }, qos=2)

        print(f"  📡 Published → {TOPIC_VEHICLES} | now={total}")

    def publish_signal_state(self, state: str, algorithm: str = "webster",
                              green_ns: int | None = None, green_ew: int | None = None):
        """Publish signal phase change (called by adaptive_controller.py)."""
        payload: Dict[str, Any] = {
            "intersection_id": INTERSECTION_ID,
            "signal"         : state,
            "algorithm"      : algorithm,
        }
        if green_ns is not None: payload["green_ns"] = green_ns
        if green_ew is not None: payload["green_ew"] = green_ew

        self.publish(TOPIC_SIGNAL, payload, qos=2)
        print(f"  📡 Published → {TOPIC_SIGNAL} | {state}")


# ── Simulator (for testing without a real camera) ────────────────

def simulate(publisher: SmartRouteMQTTPublisher, interval: float = 2.0):
    """Publish synthetic detection data to test the pipeline end-to-end."""
    print(f"\n🎭 Simulation mode — publishing every {interval}s")
    print(f"   Topic base: {BASE_TOPIC}\n")

    step = 0
    while True:
        # Realistic traffic pattern
        t      = step / 30
        q_ns   = max(0, int(25 + 15 * abs(math.sin(t)) + random.gauss(0, 3)))
        q_ew   = max(0, int(10 +  8 * abs(math.cos(t)) + random.gauss(0, 2)))
        total  = q_ns + q_ew

        summary = {
            "total_vehicles_now": total,
            "total_unique_seen" : step * 3,
            "lanes": {
                "north_in": {"current": q_ns // 2, "cumulative": step * 2, "direction": "south"},
                "south_in": {"current": q_ns - q_ns // 2, "cumulative": step * 2, "direction": "north"},
                "east_in":  {"current": q_ew // 2, "cumulative": step, "direction": "west"},
                "west_in":  {"current": q_ew - q_ew // 2, "cumulative": step, "direction": "east"},
            },
        }

        publisher.publish_vehicle_update(summary)

        # Simulate signal change every 30 steps
        if step % 30 == 0:
            signal = "GREEN" if (step // 30) % 2 == 0 else "RED"
            publisher.publish_signal_state(signal, "webster",
                                           green_ns=min(60, 10 + q_ns),
                                           green_ew=min(60, 10 + q_ew))

        step += 1
        time.sleep(interval)


def main():
    import math   # used in simulate()

    parser = argparse.ArgumentParser()
    parser.add_argument("--simulate", action="store_true", help="Run in simulation mode")
    parser.add_argument("--interval", type=float, default=PUBLISH_INTERVAL)
    args = parser.parse_args()

    if not MQTT_AVAILABLE:
        print("Install paho-mqtt first: pip install paho-mqtt")
        return

    publisher = SmartRouteMQTTPublisher()
    if not publisher.connect():
        print(f"❌ Could not connect to MQTT at {MQTT_HOST}:{MQTT_PORT}")
        print("   Make sure Mosquitto is running: brew install mosquitto && brew services start mosquitto")
        return

    try:
        if args.simulate:
            import math
            simulate(publisher, args.interval)
        else:
            print("Publisher ready. Import SmartRouteMQTTPublisher in detector.py to use.")
            print("Or run with --simulate to test the pipeline.")
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n✓ Published {publisher.published} messages total.")
    finally:
        publisher.disconnect()


if __name__ == "__main__":
    main()

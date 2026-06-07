"""
SmartRoute — Backend MQTT Client
==================================
Subscribes to the MQTT broker and feeds incoming
vehicle detection data into the backend's in-memory store.
This replaces the HTTP polling loop when the Edge AI
module uses MQTT for publishing.

Topics subscribed:
  smartroute/+/vehicles  → update vehicle count
  smartroute/+/lanes     → update lane breakdown
  smartroute/+/signal    → log signal state
  smartroute/alerts      → log congestion alerts

Usage (from backend/):
  MQTT_ENABLED=1 python main.py   # main.py starts this in a background thread
"""

import os
import json
import threading
from datetime import datetime
from typing import Callable

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))


class SmartRouteMQTTClient:
    """
    Background MQTT subscriber that calls registered handlers
    when new data arrives on SmartRoute topics.

    Usage:
        client = SmartRouteMQTTClient(on_vehicle_update=my_handler)
        client.start()          # non-blocking
        ...
        client.stop()
    """

    def __init__(
        self,
        on_vehicle_update: Callable[[str, dict], None] | None = None,
        on_lane_update:    Callable[[str, dict], None] | None = None,
        on_signal_change:  Callable[[str, dict], None] | None = None,
        on_alert:          Callable[[dict], None]       | None = None,
    ):
        self.on_vehicle_update = on_vehicle_update
        self.on_lane_update    = on_lane_update
        self.on_signal_change  = on_signal_change
        self.on_alert          = on_alert
        self.connected         = False
        self._client           = None

    def start(self):
        """Start the MQTT listener in a background daemon thread."""
        if not MQTT_AVAILABLE:
            print("⚠  paho-mqtt not installed — MQTT disabled.")
            return False

        self._client = mqtt.Client(
            client_id="smartroute-backend",
            protocol=mqtt.MQTTv5,
        )
        self._client.on_connect    = self._on_connect
        self._client.on_message    = self._on_message
        self._client.on_disconnect = self._on_disconnect

        try:
            self._client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        except Exception as e:
            print(f"⚠  MQTT connect failed: {e}")
            return False

        thread = threading.Thread(target=self._client.loop_forever, daemon=True)
        thread.start()
        print(f"📡 MQTT client started → {MQTT_HOST}:{MQTT_PORT}")
        return True

    def stop(self):
        if self._client:
            self._client.disconnect()

    def _on_connect(self, client, userdata, flags, rc, props=None):
        if rc == 0:
            self.connected = True
            client.subscribe("smartroute/+/vehicles", qos=1)
            client.subscribe("smartroute/+/lanes",    qos=1)
            client.subscribe("smartroute/+/signal",   qos=2)
            client.subscribe("smartroute/alerts",      qos=2)
            print("✅ MQTT subscribed to smartroute/#")
        else:
            print(f"❌ MQTT backend connect failed (rc={rc})")

    def _on_disconnect(self, client, userdata, rc, props=None):
        self.connected = False
        if rc != 0:
            print("⚠  MQTT disconnected, reconnecting…")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
        except json.JSONDecodeError:
            return

        topic  = msg.topic
        parts  = topic.split("/")           # ["smartroute", <id>, <type>]
        iid    = parts[1] if len(parts) > 1 else "unknown"
        kind   = parts[2] if len(parts) > 2 else parts[-1]

        if kind == "vehicles" and self.on_vehicle_update:
            self.on_vehicle_update(iid, payload)

        elif kind == "lanes" and self.on_lane_update:
            self.on_lane_update(iid, payload)

        elif kind == "signal" and self.on_signal_change:
            self.on_signal_change(iid, payload)

        elif kind == "alerts" or topic == "smartroute/alerts":
            if self.on_alert:
                self.on_alert(payload)
            print(f"🚨 ALERT [{payload.get('intersection_id')}]: {payload.get('message')}")


# ── Integration helper for main.py ────────────────────────────────

def create_backend_mqtt_client(traffic_data: dict) -> "SmartRouteMQTTClient | None":
    """
    Factory that wires MQTT messages directly into the backend's
    in-memory traffic_data dict (same format as the REST API).

    Call this from backend/main.py startup:

        from mqtt_client import create_backend_mqtt_client
        mqtt_client = create_backend_mqtt_client(traffic_data)
        if mqtt_client:
            mqtt_client.start()
    """
    if not MQTT_AVAILABLE:
        return None

    def on_vehicle_update(iid: str, payload: dict):
        ts = datetime.now().isoformat()
        if iid not in traffic_data:
            traffic_data[iid] = {"intersection_id": iid, "history": []}

        count  = payload.get("total_vehicles_now", 0)
        signal = _signal_from_count(count)

        traffic_data[iid].update({
            "vehicle_count"  : count,
            "unique_total"   : payload.get("total_unique_seen", 0),
            "signal_state"   : signal,
            "last_updated"   : ts,
        })

        history = traffic_data[iid].setdefault("history", [])
        history.append({"timestamp": ts, "count": count, "signal": signal})
        traffic_data[iid]["history"] = history[-100:]

    def on_lane_update(iid: str, payload: dict):
        if iid in traffic_data:
            traffic_data[iid]["lanes"] = payload.get("lanes", {})

    def on_signal_change(iid: str, payload: dict):
        if iid in traffic_data:
            traffic_data[iid]["signal_state"] = payload.get("signal", "GREEN")
            traffic_data[iid]["algorithm"]     = payload.get("algorithm", "unknown")

    def _signal_from_count(n: int) -> str:
        if n < 5:   return "GREEN"
        if n < 15:  return "YELLOW"
        return "RED"

    return SmartRouteMQTTClient(
        on_vehicle_update=on_vehicle_update,
        on_lane_update=on_lane_update,
        on_signal_change=on_signal_change,
    )

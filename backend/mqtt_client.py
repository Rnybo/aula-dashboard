"""
MQTT client singleton — Familieoverblik
Publiserer intern state til Mosquitto på localhost:1883.
Bruges i dag til session-state; klar til medietjenester senere.
"""
import json
import logging
import threading
import time

log = logging.getLogger("mqtt")

try:
    import paho.mqtt.client as mqtt
    _PAHO_AVAILABLE = True
except ImportError:
    _PAHO_AVAILABLE = False
    log.warning("paho-mqtt ikke installeret — MQTT deaktiveret")


class MqttClient:
    BROKER = "localhost"
    PORT = 1883
    KEEPALIVE = 60

    def __init__(self):
        self._client = None
        self._connected = False
        self._subscriptions: dict[str, list] = {}
        self._lock = threading.Lock()

    def connect(self):
        """Forbind til Mosquitto. Kaldet fra FastAPI startup."""
        if not _PAHO_AVAILABLE:
            return
        try:
            self._client = mqtt.Client(client_id="familieoverblik-server", clean_session=True)
            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect
            self._client.on_message = self._on_message
            self._client.reconnect_delay_set(min_delay=2, max_delay=30)
            self._client.connect_async(self.BROKER, self.PORT, self.KEEPALIVE)
            self._client.loop_start()
            log.info("MQTT: forbinder til %s:%s", self.BROKER, self.PORT)
        except Exception as e:
            log.warning("MQTT: kunne ikke forbinde: %s", e)

    def disconnect(self):
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()

    def publish(self, topic: str, payload: dict | str, retain: bool = False):
        """Publiser JSON-payload til topic. Fejler lydløst hvis broker ikke kører."""
        if not self._client or not self._connected:
            return
        try:
            data = json.dumps(payload) if isinstance(payload, dict) else payload
            self._client.publish(topic, data, qos=0, retain=retain)
        except Exception as e:
            log.debug("MQTT publish fejl: %s", e)

    def subscribe(self, topic: str, callback):
        """Tilmeld callback til topic. Klar til fremtidig brug (Spotify, DR)."""
        with self._lock:
            self._subscriptions.setdefault(topic, []).append(callback)
        if self._client and self._connected:
            self._client.subscribe(topic)

    # ── Interne callbacks ──────────────────────────────────────────────────────

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected = True
            log.info("MQTT: forbundet")
            # Genabonner ved reconnect
            with self._lock:
                for topic in self._subscriptions:
                    client.subscribe(topic)
        else:
            log.warning("MQTT: forbindelsesfejl rc=%s", rc)

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        if rc != 0:
            log.info("MQTT: afbrudt (rc=%s) — genforbinder...", rc)

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        try:
            payload = json.loads(msg.payload.decode())
        except Exception:
            payload = msg.payload.decode()
        with self._lock:
            callbacks = list(self._subscriptions.get(topic, []))
        for cb in callbacks:
            try:
                cb(topic, payload)
            except Exception as e:
                log.warning("MQTT callback fejl på %s: %s", topic, e)


# Singleton
mqtt_client = MqttClient()

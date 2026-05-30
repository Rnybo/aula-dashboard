"""
MQTT client singleton — Familieoverblik
Publiserer intern state til Mosquitto på localhost:1883.
Robust mod crashes via watchdog-tråd der genstarter forbindelsen.
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
    BROKER    = "localhost"
    PORT      = 1883
    KEEPALIVE = 60

    def __init__(self):
        self._client: "mqtt.Client | None" = None
        self._connected  = False
        self._running    = False
        self._subscriptions: dict[str, list] = {}
        self._lock       = threading.Lock()
        self._watchdog: threading.Thread | None = None

    # ── Offentlig API ──────────────────────────────────────────────────────────

    def connect(self):
        """Forbind til Mosquitto og start watchdog. Kaldet fra FastAPI startup."""
        if not _PAHO_AVAILABLE:
            return
        self._running = True
        self._start_client()
        self._watchdog = threading.Thread(
            target=self._watchdog_loop, daemon=True, name="mqtt-watchdog"
        )
        self._watchdog.start()

    def disconnect(self):
        """Stop watchdog og luk forbindelsen rent."""
        self._running = False
        self._stop_client()

    def publish(self, topic: str, payload: dict | str, retain: bool = False):
        """Publiser JSON-payload til topic. Fejler lydløst hvis broker ikke kører."""
        if not self._connected or not self._client:
            return
        try:
            data = json.dumps(payload) if isinstance(payload, dict) else payload
            self._client.publish(topic, data, qos=0, retain=retain)
        except Exception as e:
            log.debug("MQTT publish fejl: %s", e)
            self._connected = False  # markér som disconnected — watchdog genstarter

    def subscribe(self, topic: str, callback):
        """Tilmeld callback til topic."""
        with self._lock:
            self._subscriptions.setdefault(topic, []).append(callback)
        if self._client and self._connected:
            try:
                self._client.subscribe(topic)
            except Exception:
                pass

    # ── Intern klient-håndtering ───────────────────────────────────────────────

    def _start_client(self):
        """Opret og start en ny paho-klient."""
        try:
            client = mqtt.Client(client_id="familieoverblik-server", clean_session=True)
            client.on_connect    = self._on_connect
            client.on_disconnect = self._on_disconnect
            client.on_message    = self._on_message
            client.connect_async(self.BROKER, self.PORT, self.KEEPALIVE)
            client.loop_start()
            self._client = client
            log.info("MQTT: forbinder til %s:%s", self.BROKER, self.PORT)
        except Exception as e:
            log.warning("MQTT: _start_client fejl: %s", e)
            self._client = None

    def _stop_client(self):
        """Stop den nuværende klient lydløst."""
        client = self._client
        self._client    = None
        self._connected = False
        if client:
            try:
                client.loop_stop()
            except Exception:
                pass
            try:
                client.disconnect()
            except Exception:
                pass

    def _watchdog_loop(self):
        """
        Kører som daemon-tråd.
        Tjekker hvert 15. sek om forbindelsen er oppe — genstarter hvis ikke.
        Dette er robust mod paho interne crashes og socket-fejl.
        """
        while self._running:
            time.sleep(15)
            if not self._running:
                break
            if not self._connected:
                log.info("MQTT: watchdog genstarter forbindelsen...")
                self._stop_client()
                time.sleep(2)
                if self._running:
                    self._start_client()

    # ── Paho callbacks ─────────────────────────────────────────────────────────

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected = True
            log.info("MQTT: forbundet")
            with self._lock:
                for topic in self._subscriptions:
                    try:
                        client.subscribe(topic)
                    except Exception:
                        pass
        else:
            log.warning("MQTT: forbindelsesfejl rc=%s", rc)

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        if rc != 0:
            log.info("MQTT: afbrudt (rc=%s) — watchdog genstarter...", rc)
        # Stopper IKKE loop her — watchdog håndterer genstart

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

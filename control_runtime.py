"""Runtime compartilhado pela interface web do Lies of Control.

Este módulo mantém leitura serial, persistência e emissão de comandos separadas
da camada HTTP para que toda a lógica possa ser testada sem hardware.
"""

from __future__ import annotations

import copy
import json
import os
import queue
import threading
import time
from pathlib import Path
from typing import Callable, Optional


REPEAT_CODES = {"0x0", "0xFFFFFFFF", "0xFFFFFFFFFFFFFFFF"}

OUTPUT_CATALOG = [
    {"id": "button_a", "label": "A", "group": "Botões"},
    {"id": "button_b", "label": "B", "group": "Botões"},
    {"id": "button_x", "label": "X", "group": "Botões"},
    {"id": "button_y", "label": "Y", "group": "Botões"},
    {"id": "left_shoulder", "label": "LB", "group": "Botões"},
    {"id": "right_shoulder", "label": "RB", "group": "Botões"},
    {"id": "left_thumb", "label": "L3", "group": "Botões"},
    {"id": "right_thumb", "label": "R3", "group": "Botões"},
    {"id": "back", "label": "View", "group": "Botões"},
    {"id": "start", "label": "Menu", "group": "Botões"},
    {"id": "guide", "label": "Xbox", "group": "Botões"},
    {"id": "dpad_up", "label": "D-pad ↑", "group": "D-pad"},
    {"id": "dpad_down", "label": "D-pad ↓", "group": "D-pad"},
    {"id": "dpad_left", "label": "D-pad ←", "group": "D-pad"},
    {"id": "dpad_right", "label": "D-pad →", "group": "D-pad"},
    {"id": "left_trigger", "label": "LT", "group": "Gatilhos"},
    {"id": "right_trigger", "label": "RT", "group": "Gatilhos"},
    {"id": "left_stick_up", "label": "Analógico E ↑", "group": "Analógico esquerdo"},
    {"id": "left_stick_down", "label": "Analógico E ↓", "group": "Analógico esquerdo"},
    {"id": "left_stick_left", "label": "Analógico E ←", "group": "Analógico esquerdo"},
    {"id": "left_stick_right", "label": "Analógico E →", "group": "Analógico esquerdo"},
    {"id": "right_stick_up", "label": "Analógico D ↑", "group": "Analógico direito"},
    {"id": "right_stick_down", "label": "Analógico D ↓", "group": "Analógico direito"},
    {"id": "right_stick_left", "label": "Analógico D ←", "group": "Analógico direito"},
    {"id": "right_stick_right", "label": "Analógico D →", "group": "Analógico direito"},
]

OUTPUT_LABELS = {item["id"]: item["label"] for item in OUTPUT_CATALOG}
VALID_OUTPUTS = set(OUTPUT_LABELS)

# Migração do `code_map` original. As associações são feitas pelo código IR já
# calibrado no front, portanto independem do nome/posição visual da tecla.
LEGACY_MAPPINGS = {
    "0xBF40FB04": {"behavior": "hold", "outputs": ["left_stick_up"]},
    "0xBE41FB04": {"behavior": "hold", "outputs": ["left_stick_down"]},
    "0xF807FB04": {"behavior": "hold", "outputs": ["left_stick_left"]},
    "0xF906FB04": {"behavior": "hold", "outputs": ["left_stick_right"]},
    "0x50AFFB04": {"behavior": "pulse", "outputs": ["dpad_left"]},
    "0xA35CFB04": {"behavior": "pulse", "outputs": ["dpad_right"]},
    "0x54ABFB04": {"behavior": "pulse", "outputs": ["dpad_down"]},
    "0xA956FB04": {"behavior": "pulse", "outputs": ["dpad_up"]},
    "0xFD02FB04": {"behavior": "hold", "outputs": ["left_trigger"]},
    "0xFC03FB04": {"behavior": "hold", "outputs": ["left_shoulder"]},
    "0xFE01FB04": {"behavior": "pulse", "outputs": ["right_shoulder"]},
    "0xFF00FB04": {"behavior": "hold", "outputs": ["right_trigger"]},
    "0xBB44FB04": {"behavior": "pulse", "outputs": ["right_thumb"]},
    "0xA45BFB04": {"behavior": "pulse", "outputs": ["button_b"]},
    "0x4EB1FB04": {"behavior": "hold", "outputs": ["button_a"]},
    "0x837CFB04": {"behavior": "hold", "outputs": ["button_x"]},
    "0x44BBFB04": {"behavior": "hold", "outputs": ["button_y"]},
    "0xF708FB04": {"behavior": "pulse", "outputs": ["button_a", "dpad_left"]},
    "0x42BDFB04": {"behavior": "hold", "outputs": ["left_shoulder", "button_y"]},
}

DEFAULT_CONFIG = {
    "version": 1,
    "serial": {"port": "COM4", "baudrate": 9600, "autoconnect": False},
    "timing": {"pulse_duration": 0.1, "release_timeout": 0.25},
    "buttons": {},
}


def normalize_code(value: str) -> str:
    value = str(value).strip()
    try:
        return f"0x{int(value, 0):X}"
    except (TypeError, ValueError):
        return value.upper()


def parse_serial_line(line: str) -> Optional[str]:
    line = line.strip()
    if not line.startswith("Codigo:"):
        return None
    parts = line.split()
    return normalize_code(parts[-1]) if len(parts) > 1 else None


class ConfigStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._data = copy.deepcopy(DEFAULT_CONFIG)
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if isinstance(loaded, dict):
            self._data.update({key: value for key, value in loaded.items() if key in DEFAULT_CONFIG})
            self._data["serial"] = {**DEFAULT_CONFIG["serial"], **self._data.get("serial", {})}
            self._data["timing"] = {**DEFAULT_CONFIG["timing"], **self._data.get("timing", {})}
            self._data["buttons"] = self._data.get("buttons", {})

    def snapshot(self):
        with self._lock:
            return copy.deepcopy(self._data)

    def update_settings(self, serial=None, timing=None):
        with self._lock:
            if serial:
                self._data["serial"].update(serial)
            if timing:
                self._data["timing"].update(timing)
            self._save()
            return self.snapshot()

    def assign_code(self, button_id: str, label: str, code: str):
        code = normalize_code(code)
        with self._lock:
            for other_id, other in self._data["buttons"].items():
                if other_id != button_id and other.get("code") == code:
                    other["code"] = None
            item = self._data["buttons"].setdefault(button_id, {})
            item.update({"label": label, "code": code})
            item.setdefault("behavior", "pulse")
            item.setdefault("outputs", [])
            self._save()
            return copy.deepcopy(item)

    def set_mapping(self, button_id: str, label: str, behavior: str, outputs: list[str]):
        if behavior not in {"pulse", "hold"}:
            raise ValueError("Comportamento inválido")
        clean_outputs = list(dict.fromkeys(outputs))
        if not clean_outputs or any(output not in VALID_OUTPUTS for output in clean_outputs):
            raise ValueError("Selecione ao menos uma saída válida")
        with self._lock:
            item = self._data["buttons"].setdefault(button_id, {})
            item.update({"label": label, "behavior": behavior, "outputs": clean_outputs})
            self._save()
            return copy.deepcopy(item)

    def import_legacy_mappings(self):
        """Importa ações antigas para teclas calibradas ainda sem saída.

        Mapeamentos feitos pelo usuário no front sempre vencem: uma tecla com
        `outputs` preenchido é contabilizada como preservada e não é alterada.
        """
        imported = []
        preserved = []
        with self._lock:
            for button_id, item in self._data["buttons"].items():
                legacy = LEGACY_MAPPINGS.get(normalize_code(item.get("code", "")))
                if not legacy:
                    continue
                if item.get("outputs"):
                    preserved.append(button_id)
                    continue
                item.update(copy.deepcopy(legacy))
                imported.append(button_id)
            if imported:
                self._save()
            return {
                "imported": imported,
                "preserved": preserved,
                "matched": len(imported) + len(preserved),
                "available": len(LEGACY_MAPPINGS),
            }

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        temp_path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temp_path, self.path)


class EventHub:
    def __init__(self):
        self._subscribers = set()
        self._lock = threading.Lock()

    def subscribe(self):
        subscriber = queue.Queue(maxsize=50)
        with self._lock:
            self._subscribers.add(subscriber)
        return subscriber

    def unsubscribe(self, subscriber):
        with self._lock:
            self._subscribers.discard(subscriber)

    def publish(self, event: dict):
        payload = {"timestamp": time.time(), **event}
        with self._lock:
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            try:
                subscriber.put_nowait(payload)
            except queue.Full:
                try:
                    subscriber.get_nowait()
                    subscriber.put_nowait(payload)
                except queue.Empty:
                    pass


class VirtualGamepad:
    """Adaptador do vgamepad com uma implementação neutra quando indisponível."""

    BUTTON_NAMES = {
        "button_a": "XUSB_GAMEPAD_A",
        "button_b": "XUSB_GAMEPAD_B",
        "button_x": "XUSB_GAMEPAD_X",
        "button_y": "XUSB_GAMEPAD_Y",
        "left_shoulder": "XUSB_GAMEPAD_LEFT_SHOULDER",
        "right_shoulder": "XUSB_GAMEPAD_RIGHT_SHOULDER",
        "left_thumb": "XUSB_GAMEPAD_LEFT_THUMB",
        "right_thumb": "XUSB_GAMEPAD_RIGHT_THUMB",
        "back": "XUSB_GAMEPAD_BACK",
        "start": "XUSB_GAMEPAD_START",
        "guide": "XUSB_GAMEPAD_GUIDE",
        "dpad_up": "XUSB_GAMEPAD_DPAD_UP",
        "dpad_down": "XUSB_GAMEPAD_DPAD_DOWN",
        "dpad_left": "XUSB_GAMEPAD_DPAD_LEFT",
        "dpad_right": "XUSB_GAMEPAD_DPAD_RIGHT",
    }

    def __init__(self):
        self.available = False
        self.error = None
        self._vg = None
        self._gamepad = None
        try:
            import vgamepad as vg

            self._vg = vg
            self._gamepad = vg.VX360Gamepad()
            self.available = True
        except Exception as exc:  # pragma: no cover - depende do driver local
            self.error = str(exc)

    def press(self, outputs: list[str]):
        if not self.available:
            return
        for output in outputs:
            button_name = self.BUTTON_NAMES.get(output)
            if button_name:
                self._gamepad.press_button(button=getattr(self._vg.XUSB_BUTTON, button_name))
        self._apply_analog(outputs, pressed=True)
        self._gamepad.update()

    def release(self, outputs: list[str]):
        if not self.available:
            return
        for output in outputs:
            button_name = self.BUTTON_NAMES.get(output)
            if button_name:
                self._gamepad.release_button(button=getattr(self._vg.XUSB_BUTTON, button_name))
        self._apply_analog(outputs, pressed=False)
        self._gamepad.update()

    def _apply_analog(self, outputs: list[str], pressed: bool):
        output_set = set(outputs)
        if {"left_trigger", "right_trigger"} & output_set:
            if "left_trigger" in output_set:
                self._gamepad.left_trigger(value=255 if pressed else 0)
            if "right_trigger" in output_set:
                self._gamepad.right_trigger(value=255 if pressed else 0)
        if any(item.startswith("left_stick_") for item in output_set):
            x, y = self._stick_values("left", output_set) if pressed else (0, 0)
            self._gamepad.left_joystick(x_value=x, y_value=y)
        if any(item.startswith("right_stick_") for item in output_set):
            x, y = self._stick_values("right", output_set) if pressed else (0, 0)
            self._gamepad.right_joystick(x_value=x, y_value=y)

    @staticmethod
    def _stick_values(side: str, outputs: set[str]):
        x = (-32768 if f"{side}_stick_left" in outputs else 0) + (
            32767 if f"{side}_stick_right" in outputs else 0
        )
        y = (-32768 if f"{side}_stick_down" in outputs else 0) + (
            32767 if f"{side}_stick_up" in outputs else 0
        )
        return max(-32768, min(32767, x)), max(-32768, min(32767, y))


class ControlEngine:
    def __init__(self, store: ConfigStore, gamepad, publish: Callable[[dict], None]):
        self.store = store
        self.gamepad = gamepad
        self.publish = publish
        self._held = None
        self._pulse = None
        self._last_signal = 0.0
        self._pulse_token = 0
        self._lock = threading.RLock()

    def receive(self, code: str):
        code = normalize_code(code)
        if code in REPEAT_CODES:
            self.repeat()
            return
        config = self.store.snapshot()
        match = next(
            (dict(item, id=button_id) for button_id, item in config["buttons"].items() if item.get("code") == code),
            None,
        )
        if not match or not match.get("outputs"):
            self.publish({"type": "unmapped", "code": code})
            return
        behavior = match.get("behavior", "pulse")
        outputs = match["outputs"]
        event = self._event("input", match, active=True)
        with self._lock:
            if behavior == "hold":
                if self._held and self._held["id"] == match["id"]:
                    self._last_signal = time.monotonic()
                    return
                self._release_locked()
                self.gamepad.press(outputs)
                self._held = match
                self._last_signal = time.monotonic()
                self.publish(event)
                return
            self._release_locked()
            self._pulse_token += 1
            token = self._pulse_token
            self.gamepad.press(outputs)
            self._pulse = match
            self.publish(event)
            duration = float(config["timing"].get("pulse_duration", 0.1))
            timer = threading.Timer(duration, self._finish_pulse, args=(match, token))
            timer.daemon = True
            timer.start()

    def repeat(self):
        with self._lock:
            if self._held:
                self._last_signal = time.monotonic()

    def tick(self):
        timeout = float(self.store.snapshot()["timing"].get("release_timeout", 0.25))
        with self._lock:
            if self._held and time.monotonic() - self._last_signal > timeout:
                self._release_locked()

    def release_all(self):
        with self._lock:
            self._release_locked()

    def _finish_pulse(self, match, token):
        with self._lock:
            if token != self._pulse_token:
                return
            if self._pulse:
                self.gamepad.release(self._pulse["outputs"])
                self.publish(self._event("release", self._pulse, active=False))
                self._pulse = None

    def _release_locked(self):
        if self._pulse:
            match = self._pulse
            self._pulse_token += 1
            self.gamepad.release(match["outputs"])
            self._pulse = None
            self.publish(self._event("release", match, active=False))
        if self._held:
            match = self._held
            self.gamepad.release(match["outputs"])
            self._held = None
            self.publish(self._event("release", match, active=False))

    @staticmethod
    def _event(event_type, match, active):
        outputs = match.get("outputs", [])
        return {
            "type": event_type,
            "active": active,
            "buttonId": match["id"],
            "inputLabel": match.get("label", match["id"]),
            "code": match.get("code"),
            "behavior": match.get("behavior", "pulse"),
            "outputs": outputs,
            "outputLabels": [OUTPUT_LABELS.get(output, output) for output in outputs],
        }


class SerialManager:
    def __init__(self, on_code: Callable[[str], None], on_tick: Callable[[], None], publish):
        self.on_code = on_code
        self.on_tick = on_tick
        self.publish = publish
        self._serial = None
        self._thread = None
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self.port = None
        self.baudrate = None
        self.error = None

    @property
    def connected(self):
        return self._serial is not None and bool(getattr(self._serial, "is_open", True))

    def status(self):
        return {"connected": self.connected, "port": self.port, "baudrate": self.baudrate, "error": self.error}

    def connect(self, port: str, baudrate: int = 9600):
        self.disconnect()
        try:
            import serial

            connection = serial.Serial(port, int(baudrate), timeout=0.05)
        except Exception as exc:
            self.error = str(exc)
            self.publish({"type": "serial", **self.status()})
            raise RuntimeError(self.error) from exc
        with self._lock:
            self._serial = connection
            self.port = port
            self.baudrate = int(baudrate)
            self.error = None
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, daemon=True, name="serial-reader")
            self._thread.start()
        self.publish({"type": "serial", **self.status()})
        return self.status()

    def disconnect(self):
        self._stop.set()
        with self._lock:
            connection = self._serial
            self._serial = None
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=0.5)
        self._thread = None
        if self.port is not None:
            self.publish({"type": "serial", **self.status()})

    def _run(self):
        while not self._stop.is_set():
            try:
                raw = self._serial.readline()
                line = raw.decode(errors="ignore") if raw else ""
                code = parse_serial_line(line)
                if code:
                    self.on_code(code)
                self.on_tick()
            except Exception as exc:
                self.error = str(exc)
                break
        if self.error:
            with self._lock:
                connection = self._serial
                self._serial = None
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass
            self.publish({"type": "serial", **self.status()})


def available_serial_ports():
    try:
        from serial.tools import list_ports

        return [
            {"device": port.device, "description": port.description or port.device}
            for port in list_ports.comports()
        ]
    except Exception:
        return []


class RemoteApplication:
    def __init__(self, config_path: Path, gamepad=None):
        self.store = ConfigStore(config_path)
        self.events = EventHub()
        self.gamepad = gamepad or VirtualGamepad()
        self.engine = ControlEngine(self.store, self.gamepad, self.events.publish)
        self.serial = SerialManager(self._receive_code, self.engine.tick, self.events.publish)
        self._pending = None
        self._pending_lock = threading.Lock()

    def arm_calibration(self, button_id: str, label: str):
        with self._pending_lock:
            self._pending = {"id": button_id, "label": label}
        self.events.publish({"type": "calibration-armed", "buttonId": button_id})

    def cancel_calibration(self):
        with self._pending_lock:
            self._pending = None
        self.events.publish({"type": "calibration-cancelled"})

    def inject_code(self, code: str):
        """Entrada útil para testes e para a prévia sem um Arduino conectado."""
        self._receive_code(normalize_code(code))

    def preview(self, button_id: str):
        item = self.store.snapshot()["buttons"].get(button_id)
        if not item or not item.get("outputs"):
            raise ValueError("Essa tecla ainda não possui uma ação")
        match = {**item, "id": button_id}
        self.events.publish(ControlEngine._event("input", match, active=True))
        timer = threading.Timer(
            0.55,
            lambda: self.events.publish(ControlEngine._event("release", match, active=False)),
        )
        timer.daemon = True
        timer.start()

    def _receive_code(self, code: str):
        if code in REPEAT_CODES:
            self.engine.repeat()
            return
        with self._pending_lock:
            pending = self._pending
            self._pending = None if pending else self._pending
        if pending:
            item = self.store.assign_code(pending["id"], pending["label"], code)
            self.events.publish(
                {
                    "type": "calibrated",
                    "buttonId": pending["id"],
                    "inputLabel": pending["label"],
                    "code": item["code"],
                }
            )
            return
        self.engine.receive(code)

    def close(self):
        self.serial.disconnect()
        self.engine.release_all()

"""Servidor web local para calibrar e usar o controle infravermelho."""

from __future__ import annotations

import argparse
import json
import mimetypes
import queue
import signal
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from control_runtime import OUTPUT_CATALOG, RemoteApplication, available_serial_ports


ROOT = Path(__file__).resolve().parent
STATIC_ROOT = ROOT / "web"
CONFIG_PATH = ROOT / "controller_config.json"


class RemoteHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, application):
        self.application = application
        super().__init__(address, RemoteRequestHandler)


class RemoteRequestHandler(BaseHTTPRequestHandler):
    server_version = "LiesOfControl/1.0"

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/config":
            self._json(
                {
                    "config": self.server.application.store.snapshot(),
                    "serial": self.server.application.serial.status(),
                    "gamepad": {
                        "available": self.server.application.gamepad.available,
                        "error": self.server.application.gamepad.error,
                    },
                    "outputs": OUTPUT_CATALOG,
                }
            )
            return
        if path == "/api/ports":
            self._json({"ports": available_serial_ports()})
            return
        if path == "/api/events":
            self._events()
            return
        if path == "/":
            self._static("index.html")
            return
        if path == "/overlay":
            self._static("overlay.html")
            return
        if path.startswith("/assets/"):
            self._static(path.removeprefix("/assets/"))
            return
        self._json({"error": "Rota não encontrada"}, status=404)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            body = self._read_json()
            app = self.server.application
            if path == "/api/connect":
                port = str(body.get("port", "")).strip()
                if not port:
                    raise ValueError("Selecione ou informe uma porta serial")
                baudrate = int(body.get("baudrate", 9600))
                app.store.update_settings(
                    serial={
                        "port": port,
                        "baudrate": baudrate,
                        "autoconnect": bool(body.get("autoconnect", False)),
                    }
                )
                self._json({"serial": app.serial.connect(port, baudrate)})
                return
            if path == "/api/disconnect":
                app.serial.disconnect()
                app.engine.release_all()
                self._json({"serial": app.serial.status()})
                return
            if path == "/api/calibration/arm":
                app.arm_calibration(str(body["buttonId"]), str(body["label"]))
                self._json({"ok": True})
                return
            if path == "/api/calibration/cancel":
                app.cancel_calibration()
                self._json({"ok": True})
                return
            if path == "/api/mapping":
                item = app.store.set_mapping(
                    str(body["buttonId"]),
                    str(body["label"]),
                    str(body["behavior"]),
                    list(body.get("outputs", [])),
                )
                app.events.publish({"type": "mapping-saved", "buttonId": body["buttonId"]})
                self._json({"mapping": item})
                return
            if path == "/api/settings":
                timing = {}
                if "pulseDuration" in body:
                    timing["pulse_duration"] = max(0.02, min(2.0, float(body["pulseDuration"])))
                if "releaseTimeout" in body:
                    timing["release_timeout"] = max(0.1, min(3.0, float(body["releaseTimeout"])))
                config = app.store.update_settings(timing=timing)
                self._json({"config": config})
                return
            if path == "/api/preview":
                app.preview(str(body["buttonId"]))
                self._json({"ok": True})
                return
            if path == "/api/dev/inject":
                app.inject_code(str(body["code"]))
                self._json({"ok": True})
                return
            self._json({"error": "Rota não encontrada"}, status=404)
        except (KeyError, TypeError, ValueError, RuntimeError) as exc:
            self._json({"error": str(exc)}, status=400)
        except json.JSONDecodeError:
            self._json({"error": "JSON inválido"}, status=400)

    def _events(self):
        subscriber = self.server.application.events.subscribe()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            self.wfile.write(b"retry: 1500\n\n")
            self.wfile.flush()
            while True:
                try:
                    event = subscriber.get(timeout=10)
                    payload = json.dumps(event, ensure_ascii=False).encode("utf-8")
                    self.wfile.write(b"data: " + payload + b"\n\n")
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            self.server.application.events.unsubscribe(subscriber)

    def _static(self, relative_path):
        requested = (STATIC_ROOT / unquote(relative_path)).resolve()
        try:
            requested.relative_to(STATIC_ROOT.resolve())
        except ValueError:
            self._json({"error": "Caminho inválido"}, status=403)
            return
        if not requested.is_file():
            self._json({"error": "Arquivo não encontrado"}, status=404)
            return
        content = requested.read_bytes()
        content_type = mimetypes.guess_type(requested.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8" if content_type.startswith("text/") else content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > 1_000_000:
            raise ValueError("Requisição grande demais")
        return json.loads(self.rfile.read(length).decode("utf-8") or "{}")

    def _json(self, payload, status=200):
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, fmt, *args):
        if args and str(args[1]) == "200":
            return
        super().log_message(fmt, *args)


def main():
    parser = argparse.ArgumentParser(description="Interface web do Lies of Control")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    application = RemoteApplication(CONFIG_PATH)
    server = RemoteHTTPServer((args.host, args.port), application)
    url = f"http://{args.host}:{args.port}"

    config = application.store.snapshot()["serial"]
    if config.get("autoconnect") and config.get("port"):
        try:
            application.serial.connect(config["port"], config.get("baudrate", 9600))
        except RuntimeError as exc:
            print(f"Não foi possível conectar automaticamente: {exc}")

    def shutdown(*_):
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)

    print(f"Lies of Control disponível em {url}")
    print(f"Overlay do OBS: {url}/overlay")
    if not args.no_browser:
        threading.Timer(0.35, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    finally:
        application.close()
        server.server_close()


if __name__ == "__main__":
    main()

# AGENTS.md

## Project overview

Lies of Control turns NEC infrared codes received from an Arduino into input on
a virtual Xbox 360 controller. It is a Windows-oriented Python project built
around `pyserial` and `vgamepad`, with optional OpenCV-based head tracking.

## Repository map

- `codigo.py`: main serial-to-gamepad loop, IR mappings, hold/release logic, and
  gameplay macros.
- `head_tracker.py`: webcam capture, face/motion detection, and gesture
  classification.
- `head_control.py`: translates head gestures into right-stick pulses.
- `control_runtime.py`: testable configuration, serial, event, and virtual
  gamepad runtime used by the web interface.
- `web_server.py`: local standard-library HTTP server and JSON/SSE API.
- `web/`: calibration UI and transparent OBS overlay assets.
- `tests/`: `unittest` tests using fake devices.
- `README.md`: hardware setup, mappings, installation, and usage documentation.

## Setup and commands

Use the local virtual environment when available, or create one and install the
project dependencies:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Optional webcam support:
pip install opencv-python
```

Run the unit tests without requiring physical hardware:

```powershell
python -m unittest discover -s tests -v
```

Run hardware entry points only when the required device is available:

```powershell
python codigo.py
python head_control.py
python web_server.py
```

## Development guidelines

- Keep the code compatible with Python 3 and Windows. The virtual controller
  integration depends on ViGEmBus through `vgamepad`.
- Preserve the Portuguese names used for gestures and directions (`frente`,
  `tras`, `esquerda`, and `direita`) unless all producers, consumers, tests,
  and documentation are updated together.
- Treat values in `code_map` as hardware-specific configuration. Do not change
  IR codes or gameplay mappings incidentally.
- Use `time.monotonic()` for elapsed-time and timeout calculations.
- Keep gamepad state transitions paired: every pressed button, trigger, or
  joystick direction must have a reliable path back to its neutral state and
  must be followed by `gamepad.update()`.
- Keep optional webcam support graceful when OpenCV or a camera is unavailable.
- Avoid broad refactors or formatting changes unrelated to the requested work.
- Update `README.md` when setup, controls, mappings, or user-visible behavior
  changes.

## Testing and hardware safety

- Add or update `unittest` coverage for behavior changes. Prefer fakes for
  serial ports, gamepads, clocks, sleeps, cameras, and OpenCV calls.
- Unit tests must not open COM ports, create a real virtual gamepad, access a
  webcam, display windows, or enter an infinite loop.
- `codigo.py` currently performs device initialization and starts its main loop
  at module import time. Do not import it from tests unless that behavior has
  first been moved behind a callable or an `if __name__ == "__main__":` guard.
- For pulse-related tests, mock or inject sleeping where practical so the suite
  remains fast.
- After changes, run the full unit test command above. If hardware verification
  is needed but unavailable, state that clearly in the handoff.

## Change discipline

- The working tree may contain user changes. Inspect `git status` before
  editing and do not discard or overwrite unrelated modifications.
- Do not commit generated files, virtual environments, caches, camera captures,
  or local device configuration.

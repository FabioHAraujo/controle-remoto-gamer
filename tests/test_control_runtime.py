import tempfile
import time
import unittest
from pathlib import Path

from control_runtime import (
    ConfigStore,
    ControlEngine,
    RemoteApplication,
    normalize_code,
    parse_serial_line,
)


class FakeGamepad:
    available = True
    error = None

    def __init__(self):
        self.calls = []

    def press(self, outputs):
        self.calls.append(("press", list(outputs)))

    def release(self, outputs):
        self.calls.append(("release", list(outputs)))


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "config.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_serial_parser_normalizes_hex_codes(self):
        self.assertEqual(parse_serial_line("Codigo: 0xbf40fb04\r\n"), "0xBF40FB04")
        self.assertEqual(normalize_code("0"), "0x0")
        self.assertIsNone(parse_serial_line("Ruido: 0x1234"))

    def test_assigning_a_code_removes_it_from_the_previous_button(self):
        store = ConfigStore(self.path)
        store.assign_code("power", "Power", "0x1")
        store.assign_code("tv", "TV", "0x1")

        config = store.snapshot()

        self.assertIsNone(config["buttons"]["power"]["code"])
        self.assertEqual(config["buttons"]["tv"]["code"], "0x1")

    def test_hold_action_releases_after_timeout(self):
        store = ConfigStore(self.path)
        store.assign_code("nav-up", "Cima", "0x10")
        store.set_mapping("nav-up", "Cima", "hold", ["left_stick_up"])
        store.update_settings(timing={"release_timeout": 0.1})
        gamepad = FakeGamepad()
        events = []
        engine = ControlEngine(store, gamepad, events.append)

        engine.receive("0x10")
        engine._last_signal = time.monotonic() - 1
        engine.tick()

        self.assertEqual(
            gamepad.calls,
            [("press", ["left_stick_up"]), ("release", ["left_stick_up"])],
        )
        self.assertEqual([event["type"] for event in events], ["input", "release"])

    def test_combo_pulse_presses_and_releases_all_outputs(self):
        store = ConfigStore(self.path)
        store.assign_code("red", "Vermelho", "0x20")
        store.set_mapping("red", "Vermelho", "pulse", ["button_a", "dpad_left"])
        store.update_settings(timing={"pulse_duration": 0.02})
        gamepad = FakeGamepad()
        engine = ControlEngine(store, gamepad, lambda event: None)

        engine.receive("0x20")
        time.sleep(0.06)

        self.assertEqual(
            gamepad.calls,
            [
                ("press", ["button_a", "dpad_left"]),
                ("release", ["button_a", "dpad_left"]),
            ],
        )

    def test_calibration_captures_without_sending_gamepad_output(self):
        gamepad = FakeGamepad()
        app = RemoteApplication(self.path, gamepad=gamepad)
        app.arm_calibration("ok", "OK")

        app.inject_code("0xCAFE")

        self.assertEqual(app.store.snapshot()["buttons"]["ok"]["code"], "0xCAFE")
        self.assertEqual(gamepad.calls, [])
        app.close()


if __name__ == "__main__":
    unittest.main()

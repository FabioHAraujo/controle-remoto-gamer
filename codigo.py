import serial
import vgamepad as vg
import time

arduino = serial.Serial("COM4", 9600, timeout=0.05)

gamepad = vg.VX360Gamepad()

# Direções ativas (analógico)
active_analog = {
    "frente": False,
    "tras": False,
    "esquerda": False,
    "direita": False,
}

opposites = {
    "frente": "tras",
    "tras": "frente",
    "esquerda": "direita",
    "direita": "esquerda",
}

# Códigos IR -> (tipo, direção)
#   analog: setas analógicas (toggle, mantém pressionado)
#   dpad:   setas digitais (pulso único, pressiona e solta)
code_map = {
    "0xBF40FB04": ("analog", "frente"),
    "0xED12FB04": ("dpad", "frente"),
    "0xBE41FB04": ("analog", "tras"),
    "0xE718FB04": ("dpad", "tras"),
    "0xF807FB04": ("analog", "esquerda"),
    "0xEB14FB04": ("dpad", "esquerda"),
    "0xF906FB04": ("analog", "direita"),
    "0xE916FB04": ("dpad", "direita"),
}

# Direção -> botão D-pad no vgamepad
dpad_button = {
    "frente": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
    "tras": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
    "esquerda": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
    "direita": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
}

# Duração do pulso do D-pad (em segundos)
DPAD_PRESS_DURATION = 0.1


while True:

    linha = arduino.readline().decode(errors="ignore").strip()

    if not linha.startswith("Codigo:"):
        continue

    codigo = linha.split()[-1]

    if codigo == "0x0":
        continue

    print(codigo)

    # Neutro: limpa todas as direções ativas do analógico
    if codigo == "0xBB44FB04":
        for direction in active_analog:
            active_analog[direction] = False

    # Direções de movimento
    elif codigo in code_map:
        kind, direction = code_map[codigo]

        if kind == "analog":
            if active_analog[opposites[direction]]:
                active_analog[opposites[direction]] = False
            active_analog[direction] = not active_analog[direction]

        elif kind == "dpad":
            # Pulso único: pressiona, segura, solta
            btn = dpad_button[direction]
            gamepad.press_button(button=btn)
            gamepad.update()
            time.sleep(DPAD_PRESS_DURATION)
            gamepad.release_button(button=btn)
            gamepad.update()
            continue

    x = -32768 if active_analog["esquerda"] else (32767 if active_analog["direita"] else 0)
    y = 32767 if active_analog["frente"] else (-32768 if active_analog["tras"] else 0)

    gamepad.left_joystick(x_value=x, y_value=y)
    gamepad.update()

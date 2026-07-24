import serial
import vgamepad as vg
import time

arduino = serial.Serial("COM4", 9600, timeout=0.05)

gamepad = vg.VX360Gamepad()

# Códigos IR -> (tipo, direção)
#   analog: setas analógicas (SEGURAR para andar, soltar para parar)
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

# Código "neutro" (parada imediata)
NEUTRAL_CODE = "0xBB44FB04"

# Quadros de repetição do protocolo NEC (enviados enquanto o botão fica segurado).
# Eles NÃO carregam o código do botão, só sinalizam "ainda estou segurando".
REPEAT_CODES = {"0x0", "0xFFFFFFFF", "0xFFFFFFFFFFFFFFFF"}

# Duração do pulso do D-pad (em segundos)
DPAD_PRESS_DURATION = 0.1

# Sem nenhum sinal por este tempo -> considera que o botão foi solto.
# NEC manda um repeat a cada ~108ms, então usamos uma folga que tolera 1 quadro perdido.
RELEASE_TIMEOUT = 0.25

# Direção analógica atualmente sendo segurada (ou None) e quando vimos sinal por último.
held_direction = None
last_signal_time = 0.0


def apply_analog():
    """Envia a posição do analógico esquerdo conforme a direção segurada."""
    x = -32768 if held_direction == "esquerda" else (32767 if held_direction == "direita" else 0)
    y = 32767 if held_direction == "frente" else (-32768 if held_direction == "tras" else 0)
    gamepad.left_joystick(x_value=x, y_value=y)
    gamepad.update()


while True:

    linha = arduino.readline().decode(errors="ignore").strip()
    now = time.monotonic()

    # Detecta soltura: passou tempo demais sem sinal -> volta pro neutro.
    if held_direction is not None and (now - last_signal_time) > RELEASE_TIMEOUT:
        held_direction = None
        apply_analog()
        print("(solto)")

    if not linha.startswith("Codigo:"):
        continue

    codigo = linha.split()[-1]

    # Quadro de repetição: mantém a direção viva SÓ se já havia algo segurado.
    if codigo in REPEAT_CODES:
        if held_direction is not None:
            last_signal_time = now
        continue

    print(codigo)

    # Neutro: para tudo imediatamente.
    if codigo == NEUTRAL_CODE:
        held_direction = None
        apply_analog()
        continue

    # Direções de movimento
    if codigo in code_map:
        kind, direction = code_map[codigo]

        if kind == "analog":
            # Segurar para andar: fixa a direção e renova o cronômetro.
            held_direction = direction
            last_signal_time = now
            apply_analog()

        elif kind == "dpad":
            # Pulso único: pressiona, segura, solta.
            btn = dpad_button[direction]
            gamepad.press_button(button=btn)
            gamepad.update()
            time.sleep(DPAD_PRESS_DURATION)
            gamepad.release_button(button=btn)
            gamepad.update()

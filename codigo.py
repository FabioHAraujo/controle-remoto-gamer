import serial
import vgamepad as vg
import time

arduino = serial.Serial("COM4", 9600, timeout=0.05)

gamepad = vg.VX360Gamepad()

# ---------------------------------------------------------------------------
# Mapa de códigos IR -> (tipo, alvo)
#
# Tipos:
#   analog        setas analógicas  -> SEGURAR para andar (solta no timeout)
#   dpad          setas digitais    -> pulso único (aperta e solta)
#   pulse_button  botão             -> pulso único
#   hold_button   botão             -> clique e/ou segurar (solta no timeout)
#   hold_trigger  gatilho (LT/RT)   -> segurar (solta no timeout)
#
# Correspondência PS4 -> Xbox 360 (o que o vgamepad emula):
#   R1 -> RB   R2 -> RT   L1 -> LB   L2 -> LT
#   ◯  -> B    ▢  -> X    ✕  -> A
# ---------------------------------------------------------------------------
code_map = {
    # Movimento (analog) - ficou como estava
    "0xBF40FB04": ("analog", "frente"),
    "0xBE41FB04": ("analog", "tras"),
    "0xF807FB04": ("analog", "esquerda"),
    "0xF906FB04": ("analog", "direita"),

    # Setinhas dpad - agora nos botões R1/R2/L1/L2
    "0x50AFFB04": ("dpad", "esquerda"),  # R1 -> seta esquerda
    "0xA35CFB04": ("dpad", "direita"),   # R2 -> seta direita
    "0x54ABFB04": ("dpad", "tras"),      # L1 -> seta baixo
    "0xA956FB04": ("dpad", "frente"),    # L2 -> seta cima

    # Ações (Lies of P) - agora nas setinhas dpad
    "0xFD02FB04": ("hold_trigger", "left"),                                    # seta cima (dpad) -> L2
    "0xFC03FB04": ("hold_button", vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER),   # seta baixo (dpad) -> L1
    "0xFE01FB04": ("pulse_button", vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER), # seta esquerda (dpad) -> R1
    "0xFF00FB04": ("hold_trigger", "right"),                                   # seta direita (dpad) -> R2

    # Outros (não mexidos)
    "0xBB44FB04": ("pulse_button", vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB),    # R3 -> travar câmera (clique)
    "0xA45BFB04": ("pulse_button", vg.XUSB_BUTTON.XUSB_GAMEPAD_B),              # ◯ -> B, esquiva (clique)
    "0x4EB1FB04": ("hold_button", vg.XUSB_BUTTON.XUSB_GAMEPAD_A),               # ✕ -> A (clique/segurar)
    "0xD728FB04": ("hold_button", vg.XUSB_BUTTON.XUSB_GAMEPAD_X),               # ▢ -> X, uso (clique/segurar)
    "0x44BBFB04": ("hold_button", vg.XUSB_BUTTON.XUSB_GAMEPAD_Y),               # △ -> Y (clique/segurar)
    "0xF708FB04": ("macro", "lanterna"),                                        # ✕ + ← : liga/desliga lanterna
    "0x42BDFB04": ("hold_combo", (vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
                                  vg.XUSB_BUTTON.XUSB_GAMEPAD_Y)),              # L1 + △ segurados: arte das fábulas
}

# Direção -> botão D-pad no vgamepad
dpad_button = {
    "frente": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
    "tras": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
    "esquerda": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
    "direita": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
}

# Quadros de repetição do protocolo NEC (enviados enquanto o botão fica segurado).
# Não carregam o código do botão, só sinalizam "ainda estou segurando".
REPEAT_CODES = {"0x0", "0xFFFFFFFF", "0xFFFFFFFFFFFFFFFF"}

# Duração do pulso (aperta e solta) em segundos.
PULSE_DURATION = 0.1

# Sem nenhum sinal por este tempo -> considera que o botão foi solto.
# NEC manda um repeat a cada ~108ms, então usamos folga que tolera 1 quadro perdido.
RELEASE_TIMEOUT = 0.25

# Controle atualmente segurado (ou None) e quando vimos sinal por último.
#   held = ("analog", direcao) | ("button", vg_button) | ("trigger", "left"/"right")
held = None
last_signal_time = 0.0


def set_trigger(side, value):
    if side == "right":
        gamepad.right_trigger(value=value)
    else:
        gamepad.left_trigger(value=value)


def release_held():
    """Solta o que quer que esteja sendo segurado e volta ao neutro."""
    global held
    if held is None:
        return
    htype, val = held
    if htype == "analog":
        gamepad.left_joystick(x_value=0, y_value=0)
    elif htype == "button":
        gamepad.release_button(button=val)
    elif htype == "trigger":
        set_trigger(val, 0)
    elif htype == "combo":
        for btn in val:
            gamepad.release_button(button=btn)
    gamepad.update()
    held = None


def identity_of(kind, which):
    """Identidade de um controle 'segurável', no mesmo formato de `held`."""
    if kind == "analog":
        return ("analog", which)
    if kind == "hold_button":
        return ("button", which)
    if kind == "hold_trigger":
        return ("trigger", which)
    if kind == "hold_combo":
        return ("combo", tuple(which))
    return None


def engage(kind, which):
    """Ativa (segura) o controle indicado e devolve a identidade para `held`."""
    if kind == "analog":
        x = -32768 if which == "esquerda" else (32767 if which == "direita" else 0)
        y = 32767 if which == "frente" else (-32768 if which == "tras" else 0)
        gamepad.left_joystick(x_value=x, y_value=y)
        gamepad.update()
        return ("analog", which)
    if kind == "hold_button":
        gamepad.press_button(button=which)
        gamepad.update()
        return ("button", which)
    if kind == "hold_trigger":
        set_trigger(which, 255)
        gamepad.update()
        return ("trigger", which)
    if kind == "hold_combo":
        for btn in which:
            gamepad.press_button(button=btn)
        gamepad.update()
        return ("combo", tuple(which))
    return None


def pulse_button(btn):
    """Pressiona e solta um botão (pulso único)."""
    gamepad.press_button(button=btn)
    gamepad.update()
    time.sleep(PULSE_DURATION)
    gamepad.release_button(button=btn)
    gamepad.update()


def macro_lanterna():
    """Segura ✕/A e toca a seta esquerda 1x (liga/desliga a lanterna)."""
    a = vg.XUSB_BUTTON.XUSB_GAMEPAD_A
    left = vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT
    gamepad.press_button(button=a)
    gamepad.update()
    time.sleep(0.05)
    gamepad.press_button(button=left)
    gamepad.update()
    time.sleep(PULSE_DURATION)
    gamepad.release_button(button=left)
    gamepad.update()
    time.sleep(0.05)
    gamepad.release_button(button=a)
    gamepad.update()


# Macros nomeados
macros = {
    "lanterna": macro_lanterna,
}


while True:

    linha = arduino.readline().decode(errors="ignore").strip()
    now = time.monotonic()

    # Detecta soltura: tempo demais sem sinal -> solta o que estava segurado.
    if held is not None and (now - last_signal_time) > RELEASE_TIMEOUT:
        release_held()
        print("(solto)")

    if not linha.startswith("Codigo:"):
        continue

    codigo = linha.split()[-1]

    # Quadro de repetição: mantém o controle vivo SÓ se já havia algo segurado.
    if codigo in REPEAT_CODES:
        if held is not None:
            last_signal_time = now
        continue

    if codigo not in code_map:
        print(codigo, "(nao mapeado)")
        continue

    print(codigo)
    kind, which = code_map[codigo]

    # Pulsos (clique único): solta o que estava segurado e dispara o pulso.
    if kind == "dpad":
        release_held()
        pulse_button(dpad_button[which])
        continue
    if kind == "pulse_button":
        release_held()
        pulse_button(which)
        continue
    if kind == "macro":
        release_held()
        macros[which]()
        continue

    # Controles que podem ser segurados (analog / hold_button / hold_trigger).
    # Se o mesmo controle já está segurado:
    #   - hold_trigger: libera e re-engaja (o jogo precisa ver o gatilho em 0 entre os
    #     ataques para registrar a soltura do R2)
    #   - outros: só renova o cronômetro
    if held is not None and held == identity_of(kind, which):
        if kind == "hold_trigger":
            release_held()
            time.sleep(0.03)
            held = engage(kind, which)
        else:
            last_signal_time = now
        continue
    # Troca de controle: solta o anterior e ativa o novo.
    release_held()
    held = engage(kind, which)
    last_signal_time = now

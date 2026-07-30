# 🎮 Lies of Control

**Jogar Lies of P com um Arduino, um receptor IR e um controle de TV de R$20.**

Este projeto transforma um controle remoto de TV genérico (aquele baratinho de
20 reais) num controle de videogame. Um Arduino com um módulo receptor
infravermelho lê os botões do controle e manda os códigos pela porta serial;
do lado do PC, este script Python traduz cada código num botão de um **controle
de Xbox 360 virtual**, que o Windows (e o Lies of P) enxerga como um joystick de
verdade.

Ou seja: dá pra zerar o Lies of P apertando os botõezinhos de um controle de
televisão. 🕹️

---

## 💡 A ideia

Controles remotos de TV usam o protocolo **NEC** por infravermelho — o mesmo
protocolo, barato e bem documentado, que qualquer receptor IR de Arduino
consegue decodificar. Cada botão manda um código hexadecimal único.

O pulo do gato é o [`vgamepad`](https://github.com/yannbouteiller/vgamepad), que
cria um **controle Xbox 360 virtual** via driver ViGEmBus. Assim não é preciso
mexer no jogo nem em configuração nenhuma: pro Windows, é um Xbox controller
plugado.

```
Controle de TV  ──IR──►  Receptor IR + Arduino  ──USB serial (COM4)──►  codigo.py  ──►  Xbox 360 virtual  ──►  Lies of P
```

---

## 🔧 Hardware

- Um **Arduino** (Uno, Nano, etc.)
- Um **módulo receptor IR** (VS1838B / TSOP ou similar)
- Um **controle remoto de TV** qualquer (protocolo NEC)
- Um PC com **Windows**

O sketch do Arduino (não incluído neste repositório) só precisa decodificar o IR
e imprimir cada código na serial, a 9600 baud, no formato:

```
Codigo: 0xBF40FB04
```

Durante o tempo em que um botão fica **segurado**, o NEC manda "quadros de
repetição" que aparecem como `Codigo: 0x0` — e o script usa isso para saber que
o botão continua pressionado.

---

## 🎯 Mapa de botões

O controle é mapeado como um **PS4** (que foi a referência usada) e convertido
para o equivalente no **Xbox 360**, que é o que o `vgamepad` emula.

### Movimento
| Botão do controle | Ação | Comportamento |
|---|---|---|
| Setas analógicas | Analógico esquerdo | **Segurar para andar** (solta ao largar) |
| Setas digitais | D-pad | Pulso único (clique) |

### Ações (Lies of P)
| PS4 | Xbox 360 | Função no jogo | Comportamento |
|---|---|---|---|
| R1 | RB | Ataque rápido | Clique |
| R2 | RT (gatilho) | Ataque forte | Segurar |
| L1 | LB | Defesa | Clique / segurar |
| L2 | LT (gatilho) | Braço legionário | Segurar |
| R3 (analóg. dir.) | Right Thumb | Travar câmera no inimigo | Clique |
| ◯ Bolinha | B | Esquiva | Clique |
| ✕ | A | Interagir / usar | Clique / segurar |
| ▢ Quadrado | X | Usar item | Clique / segurar |
| △ Triângulo | Y | — | Clique / segurar |

### Macros
| Combo emulado | Função | Comportamento |
|---|---|---|
| Segura A + toca ← 1x | Liga/desliga a **lanterna** | Pulso único |
| Segura L1 + △ juntos | **Arte das Fábulas** da arma | Segurar (enquanto pressionado) |

> Os códigos IR (hex) de cada botão ficam no dicionário `code_map` dentro do
> `codigo.py`. Se seu controle for diferente, é só trocar os hexadecimais.

---

## 📦 Requisitos

- Python 3
- [`pyserial`](https://pypi.org/project/pyserial/)
- [`vgamepad`](https://pypi.org/project/vgamepad/) (instala o driver ViGEmBus)

```bash
python -m venv venv
venv\Scripts\activate
pip install pyserial vgamepad
```

---

## ▶️ Como usar

1. Grave o sketch de leitura IR no Arduino e conecte-o (confira que a porta é
   **COM4** — senão, ajuste a linha `serial.Serial("COM4", 9600, ...)`).
2. Rode o script:
   ```bash
   python codigo.py
   ```
3. O terminal vai logar cada código recebido. Botões sem mapeamento aparecem
   como `(nao mapeado)` — útil pra descobrir o hex de um botão novo.
4. Abra o Lies of P e jogue. 🐺

---

## ⚙️ Ajustes finos

Todos no topo do `codigo.py`:

- **`RELEASE_TIMEOUT`** (padrão `0.25s`) — tempo sem sinal para considerar que o
  botão foi solto. Se o movimento "engasgar" enquanto você segura, aumente; se
  demorar pra parar ao soltar, diminua.
- **`PULSE_DURATION`** (padrão `0.1s`) — duração dos cliques (pulso único).
- **`REPEAT_CODES`** — os códigos tratados como "quadro de repetição" do NEC.

---

## ⚠️ Limitações

- **Um controle por vez.** O receptor IR é ótico: dois controles transmitindo ao
  mesmo tempo colidem e viram ruído. Multiplayer com um só receptor não rola.
- **Sem diagonais no movimento.** Como o IR só manda um botão por vez, só é
  possível segurar **uma** direção de cada vez.
- **Só Windows**, por causa do `vgamepad` / ViGEmBus.

---

*Feito por diversão — porque um controle de TV de R$20 também merece enfrentar o
Rei das Marionetes.*

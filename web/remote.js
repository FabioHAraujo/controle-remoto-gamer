const REMOTE_BUTTONS = [
  { id: "power", label: "Power", text: "⏻", className: "power" },
  { id: "tv", label: "TV", text: "TV" },
  { id: "caption", label: "Caption", text: "CAPTION" },
  { id: "settings", label: "Configurações", text: "⚙" },
  { id: "search", label: "Busca", text: "⌕" },
  { id: "input", label: "Entrada", text: "▱" },
  ...Array.from({ length: 9 }, (_, index) => ({ id: `number-${index + 1}`, label: `${index + 1}`, text: `${index + 1}` })),
  { id: "list", label: "Lista", text: "LIST" },
  { id: "number-0", label: "0", text: "0" },
  { id: "qview", label: "Q.View", text: "Q.VIEW" },
  { id: "volume-up", label: "Volume +", text: "▲\nVOL", className: "rocker rocker-up" },
  { id: "volume-down", label: "Volume −", text: "VOL\n▼", className: "rocker rocker-down" },
  { id: "quick-fav", label: "Favoritos", text: "FAV" },
  { id: "channel-up", label: "Canal +", text: "▲\nCH", className: "rocker rocker-up" },
  { id: "channel-down", label: "Canal −", text: "CH\n▼", className: "rocker rocker-down" },
  { id: "info", label: "Informações", text: "ⓘ INFO" },
  { id: "mute", label: "Mudo", text: "⌁" },
  { id: "netflix", label: "Netflix", text: "NETFLIX", className: "service netflix" },
  { id: "home", label: "Home", text: "⌂", className: "service home" },
  { id: "amazon", label: "Amazon", text: "amazon", className: "service amazon" },
  { id: "guide", label: "Guide", text: "GUIDE" },
  { id: "nav-up", label: "Cima", text: "▲", className: "nav" },
  { id: "live-zoom", label: "Live Zoom", text: "LIVE\nZOOM" },
  { id: "nav-left", label: "Esquerda", text: "◀", className: "nav" },
  { id: "ok", label: "OK", text: "◎\nOK", className: "nav ok" },
  { id: "nav-right", label: "Direita", text: "▶", className: "nav" },
  { id: "back", label: "Back", text: "BACK" },
  { id: "nav-down", label: "Baixo", text: "▼", className: "nav" },
  { id: "exit", label: "Exit", text: "EXIT" },
  { id: "movies", label: "Filmes", text: "◉" },
  { id: "record", label: "Gravar", text: "● REC" },
  { id: "stop", label: "Parar", text: "■" },
  { id: "rewind", label: "Retroceder", text: "◀◀" },
  { id: "play", label: "Reproduzir", text: "▶" },
  { id: "pause", label: "Pausar", text: "Ⅱ" },
  { id: "forward", label: "Avançar", text: "▶▶" },
  { id: "red", label: "Vermelho", text: "●", className: "color red" },
  { id: "green", label: "Verde", text: "●●", className: "color green" },
  { id: "yellow", label: "Amarelo", text: "✣", className: "color yellow" },
  { id: "blue", label: "Azul", text: "✣", className: "color blue" },
];

const REMOTE_ROWS = [
  ["power", null, null, "tv"],
  ["caption", "settings", "search", "input"],
  ["number-1", "number-2", "number-3"],
  ["number-4", "number-5", "number-6"],
  ["number-7", "number-8", "number-9"],
  ["list", "number-0", "qview"],
  [["volume-up", "volume-down"], ["quick-fav", "info", "mute"], ["channel-up", "channel-down"]],
  ["netflix", "home", "amazon"],
  ["guide", "nav-up", "live-zoom"],
  ["nav-left", "ok", "nav-right"],
  ["back", "nav-down", "exit"],
  ["movies", "record", "stop"],
  ["rewind", "play", "pause", "forward"],
  ["red", "green", "yellow", "blue"],
];

const REMOTE_LOOKUP = Object.fromEntries(REMOTE_BUTTONS.map((button) => [button.id, button]));

function createRemote(mount, options = {}) {
  const remote = document.createElement("div");
  remote.className = `remote ${options.compact ? "remote-compact" : ""}`;
  const sensor = document.createElement("div");
  sensor.className = "remote-sensor";
  remote.append(sensor);

  REMOTE_ROWS.forEach((row, rowIndex) => {
    const rowElement = document.createElement("div");
    rowElement.className = `remote-row remote-row-${rowIndex + 1}`;
    row.forEach((entry) => {
      if (entry === null) {
        const spacer = document.createElement("span");
        spacer.className = "remote-spacer";
        rowElement.append(spacer);
        return;
      }
      if (Array.isArray(entry)) {
        const stack = document.createElement("div");
        stack.className = `remote-stack ${entry.length === 2 ? "remote-rocker-stack" : ""}`;
        entry.forEach((id) => stack.append(createRemoteButton(REMOTE_LOOKUP[id], options)));
        rowElement.append(stack);
        return;
      }
      rowElement.append(createRemoteButton(REMOTE_LOOKUP[entry], options));
    });
    remote.append(rowElement);
  });
  const model = document.createElement("div");
  model.className = "remote-model";
  model.innerHTML = "<b>FBG-8035</b><small>AKB75095315</small>";
  remote.append(model);
  mount.replaceChildren(remote);
  return remote;
}

function createRemoteButton(button, options) {
  const element = document.createElement("button");
  element.type = "button";
  element.className = `remote-key ${button.className || ""}`;
  element.dataset.buttonId = button.id;
  element.dataset.label = button.label;
  element.title = button.label;
  element.setAttribute("aria-label", button.label);
  element.innerHTML = button.text.split("\n").map((part) => `<span>${part}</span>`).join("");
  if (options.onPress) element.addEventListener("click", () => options.onPress(button));
  return element;
}

window.RemoteControl = { buttons: REMOTE_BUTTONS, lookup: REMOTE_LOOKUP, create: createRemote };

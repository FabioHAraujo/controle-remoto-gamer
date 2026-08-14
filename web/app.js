const state = {
  config: null,
  outputs: [],
  serial: null,
  gamepad: null,
  step: 1,
  selectedButtonId: null,
  armedButtonId: null,
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const remote = window.RemoteControl.create($("#remoteMount"), { onPress: selectRemoteButton });
let toastTimer;

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Não foi possível concluir a operação");
  return payload;
}

function toast(message, kind = "normal") {
  const element = $("#toast");
  clearTimeout(toastTimer);
  element.textContent = message;
  element.className = `toast show ${kind}`;
  toastTimer = setTimeout(() => (element.className = "toast"), 3200);
}

async function loadConfig() {
  const payload = await request("/api/config");
  state.config = payload.config;
  state.outputs = payload.outputs;
  state.serial = payload.serial;
  state.gamepad = payload.gamepad;
  renderOutputs();
  renderState();
  await refreshPorts();
}

function renderState() {
  if (!state.config) return;
  const buttons = state.config.buttons || {};
  const captured = Object.values(buttons).filter((item) => item.code).length;
  const mapped = Object.values(buttons).filter((item) => item.code && item.outputs?.length).length;
  const total = window.RemoteControl.buttons.length;
  const progress = state.step === 1 ? captured / total : captured ? mapped / captured : 0;

  $$(".remote-key", remote).forEach((element) => {
    const item = buttons[element.dataset.buttonId];
    element.classList.toggle("captured", Boolean(item?.code));
    element.classList.toggle("mapped", Boolean(item?.outputs?.length));
    element.classList.toggle("selected", element.dataset.buttonId === state.selectedButtonId);
  });
  $("#capturedCount").textContent = captured;
  $("#remainingCount").textContent = Math.max(0, total - captured);
  $("#toMapping").disabled = captured === 0;
  $("#progressValue").textContent = `${Math.round(progress * 100)}%`;
  $("#progressRing").style.setProperty("--progress", `${progress * 360}deg`);

  const serialStatus = $("#serialStatus");
  serialStatus.className = `status-pill ${state.serial?.connected ? "online" : state.serial?.error ? "error" : ""}`;
  serialStatus.innerHTML = `<i></i>${state.serial?.connected ? `${state.serial.port} conectada` : "Serial desconectada"}`;
  $("#connectButton").textContent = state.serial?.connected ? "Desconectar" : "Conectar";
  $("#autoconnect").checked = Boolean(state.config.serial.autoconnect);

  const gamepadStatus = $("#gamepadStatus");
  gamepadStatus.className = `status-pill ${state.gamepad?.available ? "online" : "error"}`;
  gamepadStatus.innerHTML = `<i></i>${state.gamepad?.available ? "Xbox virtual pronto" : "Xbox virtual indisponível"}`;
  renderSelectedMapping();
}

function selectRemoteButton(button) {
  state.selectedButtonId = button.id;
  renderState();
  if (state.step === 1) armCalibration(button);
  if (state.step === 2 && !state.config.buttons[button.id]?.code) {
    toast("Essa tecla ainda não foi registrada. Volte à calibração para capturá-la.", "error");
  }
}

async function armCalibration(button) {
  state.armedButtonId = button.id;
  const known = state.config.buttons[button.id];
  $("#captureCard").className = "capture-card armed";
  $("#captureTitle").textContent = `Aperte “${button.label}” no controle`;
  $("#captureCode").textContent = known?.code ? `Atual: ${known.code}` : "Ouvindo o próximo código…";
  $("#remoteHint").innerHTML = `<span class="hint-dot"></span> Aguardando o sinal de ${button.label}`;
  if (!state.serial?.connected) toast("A tecla ficou preparada, mas conecte a porta serial para receber o sinal.");
  try {
    await request("/api/calibration/arm", {
      method: "POST",
      body: JSON.stringify({ buttonId: button.id, label: button.label }),
    });
  } catch (error) {
    toast(error.message, "error");
  }
}

function renderSelectedMapping() {
  if (state.step !== 2) return;
  const button = window.RemoteControl.lookup[state.selectedButtonId];
  const mapping = button ? state.config.buttons[state.selectedButtonId] : null;
  const ready = Boolean(mapping?.code);
  $("#selectedKeyGlyph").textContent = button ? button.text.replaceAll("\n", " ").slice(0, 4) : "?";
  $("#selectedKeyName").textContent = button?.label || "Escolha no controle";
  $("#selectedKeyCode").textContent = mapping?.code || "—";
  $$('input[name="behavior"]').forEach((radio) => {
    radio.checked = radio.value === (mapping?.behavior || "pulse");
    radio.disabled = !ready;
  });
  $$("#outputList input").forEach((input) => {
    input.checked = Boolean(mapping?.outputs?.includes(input.value));
    input.disabled = !ready;
  });
  $("#saveMapping").disabled = !ready || !selectedOutputs().length;
  $("#previewMapping").disabled = !mapping?.outputs?.length;
  updateComboBadge();
}

function renderOutputs() {
  const groups = Object.groupBy
    ? Object.groupBy(state.outputs, (output) => output.group)
    : state.outputs.reduce((result, output) => {
        (result[output.group] ||= []).push(output);
        return result;
      }, {});
  $("#outputList").innerHTML = Object.entries(groups)
    .map(
      ([group, outputs]) => `<div class="output-group"><small>${group}</small><div class="output-options">${outputs
        .map(
          (output) => `<label class="output-option"><input type="checkbox" value="${output.id}"><span>${output.label}</span></label>`,
        )
        .join("")}</div></div>`,
    )
    .join("");
  $$("#outputList input").forEach((input) => input.addEventListener("change", () => {
    $("#saveMapping").disabled = !state.config.buttons[state.selectedButtonId]?.code || !selectedOutputs().length;
    updateComboBadge();
  }));
}

function selectedOutputs() {
  return $$("#outputList input:checked").map((input) => input.value);
}

function updateComboBadge() {
  const count = selectedOutputs().length;
  $("#comboBadge").textContent = count > 1 ? `COMBO · ${count} TECLAS` : count ? "AÇÃO SIMPLES" : "SEM AÇÃO";
  $("#comboBadge").classList.toggle("combo", count > 1);
}

async function saveMapping() {
  const button = window.RemoteControl.lookup[state.selectedButtonId];
  if (!button) return;
  try {
    const payload = await request("/api/mapping", {
      method: "POST",
      body: JSON.stringify({
        buttonId: button.id,
        label: button.label,
        behavior: $('input[name="behavior"]:checked').value,
        outputs: selectedOutputs(),
      }),
    });
    state.config.buttons[button.id] = payload.mapping;
    toast(selectedOutputs().length > 1 ? "Combo salvo com sucesso." : "Ação salva com sucesso.");
    renderState();
  } catch (error) {
    toast(error.message, "error");
  }
}

function setStep(step) {
  state.step = Number(step);
  $$(".step-panel").forEach((panel) => panel.classList.toggle("active", Number(panel.dataset.step) === state.step));
  $$(".step").forEach((item) => {
    const itemStep = Number(item.dataset.stepTarget);
    item.classList.toggle("active", itemStep === state.step);
    item.classList.toggle("complete", itemStep < state.step);
  });
  if (state.step !== 1 && state.armedButtonId) {
    request("/api/calibration/cancel", { method: "POST", body: "{}" }).catch(() => {});
    state.armedButtonId = null;
  }
  const stageText = {
    1: ["CONTROLE FÍSICO", "Escolha uma tecla", "Clique numa tecla do desenho para começar"],
    2: ["MAPA DE AÇÕES", "Vincule cada resposta", "As teclas verdes já possuem uma ação"],
    3: ["VISUALIZAÇÃO", "Teste seu overlay", "Aperte uma tecla mapeada para visualizar"],
  }[state.step];
  $("#stageKicker").textContent = stageText[0];
  $("#stageTitle").textContent = stageText[1];
  $("#remoteHint").innerHTML = `<span class="hint-dot"></span> ${stageText[2]}`;
  $("#overlayUrl").textContent = `${location.origin}/overlay`;
  renderState();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function refreshPorts() {
  try {
    const { ports } = await request("/api/ports");
    const configured = state.config?.serial?.port || "COM4";
    const choices = [...ports];
    if (!choices.some((port) => port.device === configured)) choices.unshift({ device: configured, description: "Porta configurada" });
    $("#portSelect").innerHTML = choices.map((port) => `<option value="${port.device}">${port.device} · ${port.description}</option>`).join("");
    $("#portSelect").value = configured;
  } catch (error) {
    toast(error.message, "error");
  }
}

async function toggleConnection() {
  try {
    if (state.serial?.connected) {
      const payload = await request("/api/disconnect", { method: "POST", body: "{}" });
      state.serial = payload.serial;
      toast("Porta serial desconectada.");
    } else {
      const payload = await request("/api/connect", {
        method: "POST",
        body: JSON.stringify({
          port: $("#portSelect").value,
          baudrate: 9600,
          autoconnect: $("#autoconnect").checked,
        }),
      });
      state.serial = payload.serial;
      state.config.serial = { ...state.config.serial, ...payload.serial, autoconnect: $("#autoconnect").checked };
      toast(`${state.serial.port} conectada. Agora escolha uma tecla.`);
    }
    renderState();
  } catch (error) {
    state.serial = { connected: false, error: error.message };
    renderState();
    toast(error.message, "error");
  }
}

function handleEvent(event) {
  if (event.type === "serial") {
    state.serial = event;
    renderState();
  }
  if (event.type === "calibrated") {
    const existing = state.config.buttons[event.buttonId] || {};
    Object.values(state.config.buttons).forEach((item) => {
      if (item !== existing && item.code === event.code) item.code = null;
    });
    state.config.buttons[event.buttonId] = { ...existing, label: event.inputLabel, code: event.code, behavior: existing.behavior || "pulse", outputs: existing.outputs || [] };
    state.armedButtonId = null;
    $("#captureCard").className = "capture-card";
    $("#captureTitle").textContent = `${event.inputLabel} registrada`;
    $("#captureCode").textContent = event.code;
    $("#remoteHint").innerHTML = '<span class="hint-dot"></span> Sinal recebido — escolha a próxima tecla';
    toast(`${event.inputLabel}: ${event.code}`);
    renderState();
  }
  if (event.type === "input") {
    const key = $(`.remote-key[data-button-id="${event.buttonId}"]`, remote);
    key?.classList.add("active");
  }
  if (event.type === "release") {
    const key = $(`.remote-key[data-button-id="${event.buttonId}"]`, remote);
    key?.classList.remove("active");
  }
  if (event.type === "unmapped" && !state.armedButtonId) toast(`Código sem mapeamento: ${event.code}`);
}

function connectEvents() {
  const source = new EventSource("/api/events");
  source.onmessage = ({ data }) => {
    try { handleEvent(JSON.parse(data)); } catch (_) { /* evento incompleto */ }
  };
}

$("#connectButton").addEventListener("click", toggleConnection);
$("#serialStatus").addEventListener("click", () => setStep(1));
$("#refreshPorts").addEventListener("click", refreshPorts);
$("#toMapping").addEventListener("click", () => {
  setStep(2);
  const first = window.RemoteControl.buttons.find((button) => state.config.buttons[button.id]?.code);
  if (first) {
    state.selectedButtonId = first.id;
    renderState();
  }
});
$("#saveMapping").addEventListener("click", saveMapping);
$("#previewMapping").addEventListener("click", async () => {
  try {
    await request("/api/preview", { method: "POST", body: JSON.stringify({ buttonId: state.selectedButtonId }) });
    toast("Prévia enviada para o overlay.");
  } catch (error) { toast(error.message, "error"); }
});
$("#toOverlay").addEventListener("click", () => setStep(3));
$("#openOverlay").addEventListener("click", () => window.open("/overlay", "lies-overlay"));
$("#copyUrl").addEventListener("click", async () => {
  await navigator.clipboard.writeText(`${location.origin}/overlay`);
  toast("URL do overlay copiada.");
});
$$('[data-step-target]').forEach((button) => button.addEventListener("click", () => setStep(button.dataset.stepTarget)));

loadConfig().then(connectEvents).catch((error) => toast(error.message, "error"));

const overlay = document.querySelector("#overlay");
let visibleSince = 0;
let hideTimer;
let pressTimer;

function showInput(event) {
  clearTimeout(hideTimer);
  clearTimeout(pressTimer);
  visibleSince = Date.now();
  const remoteButton = window.RemoteControl.lookup[event.buttonId];
  const glyph = remoteButton?.text?.replaceAll("\n", " ") || event.inputLabel || "IR";
  document.querySelector("#inputGlyph").textContent = glyph.slice(0, 8);
  document.querySelector("#inputLabel").textContent = event.inputLabel || event.buttonId;
  document.querySelector("#inputCode").textContent = event.code || "PRÉVIA";
  const behavior = document.querySelector("#behavior");
  behavior.textContent = event.behavior === "hold" ? "SEGURANDO" : "CLIQUE";
  behavior.classList.toggle("hold", event.behavior === "hold");
  document.querySelector("#outputChips").innerHTML = (event.outputLabels || event.outputs || [])
    .map((label) => `<b>${escapeHtml(label)}</b>`)
    .join("");
  overlay.classList.add("visible", "pressed");
  pressTimer = setTimeout(() => overlay.classList.remove("pressed"), 260);
}

function releaseInput() {
  const minimumVisible = 850;
  const remaining = Math.max(0, minimumVisible - (Date.now() - visibleSince));
  clearTimeout(hideTimer);
  hideTimer = setTimeout(() => overlay.classList.remove("visible", "pressed"), remaining + 180);
}

function escapeHtml(value) {
  const node = document.createElement("span");
  node.textContent = String(value);
  return node.innerHTML;
}

const events = new EventSource("/api/events");
events.onmessage = ({ data }) => {
  try {
    const event = JSON.parse(data);
    if (event.type === "input") showInput(event);
    if (event.type === "release") releaseInput(event);
  } catch (_) { /* ignora eventos incompletos */ }
};

if (new URLSearchParams(location.search).has("demo")) {
  showInput({
    buttonId: "ok",
    inputLabel: "OK",
    code: "0x42BDFB04",
    behavior: "hold",
    outputLabels: ["LB", "Y"],
  });
}

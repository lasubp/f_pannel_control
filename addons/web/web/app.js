const cards = new Map();
const cardContainer = document.getElementById("machines");
const message = document.getElementById("message");
let refreshing = false;

async function api(path, options = {}) {
  const response = await fetch(path, { cache: "no-store", ...options });
  let result;
  try { result = await response.json(); }
  catch { throw new Error(`Invalid response (${response.status})`); }
  if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
  return result;
}

function notice(text, error = false) {
  message.textContent = text;
  message.classList.toggle("error", error);
}

function button(text, action, machine, className = "") {
  const element = document.createElement("button");
  element.type = "button";
  element.className = `button ${className}`;
  element.textContent = text;
  element.addEventListener("click", () => runAction(machine, action));
  return element;
}

function createCard(name) {
  const card = document.createElement("article");
  card.className = "card";
  const head = document.createElement("div");
  head.className = "card-head";
  const title = document.createElement("h2");
  title.textContent = name;
  const state = document.createElement("span");
  state.className = "state";
  head.append(title, state);

  const leds = document.createElement("div");
  leds.className = "leds";
  function led(label, type) {
    const row = document.createElement("span");
    row.className = "led";
    const light = document.createElement("span");
    light.className = `light ${type}`;
    const text = document.createElement("span");
    text.textContent = `${label} —`;
    row.append(light, text);
    leds.append(row);
    return { light, text };
  }
  const power = led("Power", "power");
  const hdd = led("HDD", "hdd");

  const actions = document.createElement("div");
  actions.className = "actions";
  actions.append(
    button("Power on", "on", name),
    button("Power off", "off", name, "danger"),
    button("Reset", "reset", name, "muted"),
    button("Press power", "press-power", name, "muted"),
    button("Press reset", "press-reset", name, "muted")
  );

  const details = document.createElement("details");
  details.className = "details";
  const summary = document.createElement("summary");
  summary.textContent = "Diagnostics";
  const inputs = button("Read inputs", "inputs", name, "muted");
  const raw = button("Read raw pins", "raw", name, "muted");
  const output = document.createElement("pre");
  output.hidden = true;
  details.append(summary, inputs, document.createTextNode(" "), raw, output);

  const note = document.createElement("p");
  note.className = "card-note";
  card.append(head, leds, actions, details, note);
  cardContainer.append(card);
  const value = { card, state, power, hdd, actions, note, output, busy: false };
  cards.set(name, value);
  return value;
}

function showLed(item, label, value) {
  item.light.classList.toggle("on", value === true);
  item.text.textContent = `${label} ${value === null ? "N/A" : value === undefined ? "—" : value ? "ON" : "OFF"}`;
}

function renderMachine(machine) {
  const name = machine.name;
  const card = cards.get(name) || createCard(name);
  const status = machine.status;
  const valid = status && ["on", "off"].includes(status.power);
  const powerOn = valid ? status.power === "on" : undefined;
  const hddOn = valid ? (status.hdd === null ? null : status.hdd === "active") : undefined;
  card.state.textContent = valid ? status.power.toUpperCase() : "UNAVAILABLE";
  card.state.className = `state ${valid ? status.power : "error"}`;
  showLed(card.power, "Power", powerOn);
  showLed(card.hdd, "HDD", hddOn);
  if (!card.busy) {
    card.note.textContent = machine.error || (valid ? "" : "Invalid status response");
    card.note.classList.toggle("error", Boolean(machine.error || !valid));
  }
  return valid && powerOn;
}

async function refresh() {
  if (refreshing) return;
  refreshing = true;
  try {
    const [snapshot, health] = await Promise.all([
      api("/api/snapshot"), api("/api/health").catch(() => null)
    ]);
    const known = new Set();
    let online = 0;
    for (const machine of snapshot.machines) {
      known.add(machine.name);
      if (renderMachine(machine)) online++;
    }
    for (const [name, card] of cards) {
      if (!known.has(name)) { card.card.remove(); cards.delete(name); }
    }
    document.getElementById("empty").hidden = known.size !== 0;
    document.getElementById("count").textContent = String(known.size);
    document.getElementById("online").textContent = String(online);
    document.getElementById("health").textContent = health ? (health.ok ? "OK" : "Check") : "Unknown";
    document.getElementById("updated").textContent = new Date().toLocaleTimeString();
    const connection = document.getElementById("connection");
    connection.textContent = "Connected";
    connection.classList.remove("error");
  } catch (error) {
    const connection = document.getElementById("connection");
    connection.textContent = error.message;
    connection.classList.add("error");
  } finally {
    refreshing = false;
  }
}

async function runAction(machine, action) {
  const card = cards.get(machine);
  if (!card || card.busy) return;
  card.busy = true;
  for (const element of card.actions.querySelectorAll("button")) element.disabled = true;
  card.note.textContent = `${action} in progress…`;
  card.note.classList.remove("error");
  try {
    const path = `/api/machines/${encodeURIComponent(machine)}/${action}`;
    const result = action === "inputs" || action === "raw"
      ? await api(path)
      : await api(path, { method: "POST", headers: { "X-PCPower-Web": "1" } });
    if (action === "inputs" || action === "raw") {
      card.output.textContent = JSON.stringify(result, null, 2);
      card.output.hidden = false;
    }
    card.note.textContent = `${action} completed`;
    await refresh();
  } catch (error) {
    card.note.textContent = error.message;
    card.note.classList.add("error");
  } finally {
    card.busy = false;
    for (const element of card.actions.querySelectorAll("button")) element.disabled = false;
  }
}

document.getElementById("refresh").addEventListener("click", refresh);
document.getElementById("reload").addEventListener("click", async (event) => {
  event.currentTarget.disabled = true;
  try {
    await api("/api/reload", { method: "POST", headers: { "X-PCPower-Web": "1" } });
    notice("Configuration reloaded.");
    await refresh();
  } catch (error) { notice(error.message, true); }
  finally { event.currentTarget.disabled = false; }
});

refresh();
setInterval(refresh, 5000);

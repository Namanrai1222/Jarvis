const state = {
  speechEnabled: true,
  recognition: null,
  listening: false,
};

const transcript = document.getElementById("transcript");
const promptInput = document.getElementById("prompt-input");
const chatForm = document.getElementById("chat-form");
const micButton = document.getElementById("mic-button");
const voiceToggle = document.getElementById("voice-toggle");
const profileCard = document.getElementById("profile-card");
const factsList = document.getElementById("facts-list");
const activityList = document.getElementById("activity-list");
const taskList = document.getElementById("task-list");
const ingestForm = document.getElementById("ingest-form");
const ingestPath = document.getElementById("ingest-path");
const ingestStatus = document.getElementById("ingest-status");
const modelName = document.getElementById("model-name");
const voiceStatus = document.getElementById("voice-status");
const csrfToken = document.querySelector("meta[name='jarvis-token']")?.content || "";

function addMessage(role, text) {
  const card = document.createElement("article");
  card.className = `message ${role}`;
  const label = document.createElement("span");
  label.className = "label";
  label.textContent = role === "user" ? "You" : "Jarvis";
  const body = document.createElement("div");
  body.textContent = text;
  card.append(label, body);
  transcript.appendChild(card);
  transcript.scrollTop = transcript.scrollHeight;
}

function renderProfile(profile) {
  profileCard.innerHTML = "";
  Object.entries(profile).forEach(([key, value]) => {
    const item = document.createElement("div");
    item.className = "meta-item";
    const keyNode = document.createElement("div");
    keyNode.className = "meta-key";
    keyNode.textContent = key.replaceAll("_", " ");
    const valueNode = document.createElement("div");
    valueNode.className = "meta-value";
    valueNode.textContent = Array.isArray(value) ? value.join(", ") : String(value);
    item.append(keyNode, valueNode);
    profileCard.appendChild(item);
  });
}

function renderFacts(facts) {
  factsList.innerHTML = "";
  if (!facts.length) {
    const item = document.createElement("div");
    item.className = "timeline-item";
    const copy = document.createElement("div");
    copy.className = "timeline-copy";
    copy.textContent = "No saved facts yet.";
    item.appendChild(copy);
    factsList.appendChild(item);
    return;
  }
  facts.forEach((fact) => {
    const item = document.createElement("div");
    item.className = "timeline-item";
    const title = document.createElement("div");
    title.className = "timeline-title";
    title.textContent = fact.key;
    const copy = document.createElement("div");
    copy.className = "timeline-copy";
    copy.textContent = fact.value;
    item.append(title, copy);
    factsList.appendChild(item);
  });
}

function renderActivities(activities) {
  activityList.innerHTML = "";
  if (!activities.length) {
    const item = document.createElement("div");
    item.className = "timeline-item";
    const copy = document.createElement("div");
    copy.className = "timeline-copy";
    copy.textContent = "No missions logged yet.";
    item.appendChild(copy);
    activityList.appendChild(item);
    return;
  }
  activities.forEach((activity) => {
    const item = document.createElement("div");
    item.className = "timeline-item";
    const title = document.createElement("div");
    title.className = "timeline-title";
    title.textContent = activity.title;
    const copy = document.createElement("div");
    copy.className = "timeline-copy";
    copy.textContent = activity.details;
    const time = document.createElement("div");
    time.className = "mini-copy";
    time.textContent = activity.created_at;
    item.append(title, copy, time);
    activityList.appendChild(item);
  });
}

function renderTasks(tasks) {
  taskList.innerHTML = "";
  if (!tasks.length) {
    const item = document.createElement("div");
    item.className = "task-item";
    const meta = document.createElement("div");
    meta.className = "task-meta";
    meta.textContent = "No open tasks right now.";
    item.appendChild(meta);
    taskList.appendChild(item);
    return;
  }
  tasks.forEach((task) => {
    const item = document.createElement("div");
    item.className = "task-item";
    const title = document.createElement("div");
    title.className = "task-title";
    title.textContent = task.title;
    const meta = document.createElement("div");
    meta.className = "task-meta";
    meta.textContent = task.status;
    item.append(title, meta);
    taskList.appendChild(item);
  });
}

function speak(text) {
  if (!state.speechEnabled || !("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1;
  utterance.pitch = 1;
  utterance.volume = 1;
  window.speechSynthesis.speak(utterance);
}

async function refreshState() {
  const response = await fetch("/api/state");
  const data = await response.json();
  modelName.textContent = data.model_name || "offline";
  renderProfile(data.profile);
  renderFacts(data.dashboard.facts || []);
  renderActivities(data.dashboard.activities || []);
  renderTasks((data.dashboard.tasks || []).filter((task) => task.status === "open"));
}

async function sendPrompt(message) {
  addMessage("user", message);
  promptInput.value = "";
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Jarvis-Token": csrfToken },
    body: JSON.stringify({ message }),
  });
  const data = await response.json();
  addMessage("jarvis", data.reply);
  speak(data.reply);
  renderActivities(data.dashboard.activities || []);
  renderTasks((data.dashboard.tasks || []).filter((task) => task.status === "open"));
  renderFacts(data.dashboard.facts || []);
}

function initSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    micButton.disabled = true;
    micButton.textContent = "No Mic";
    micButton.title = "Speech recognition is not available in this browser.";
    if (voiceStatus) {
      voiceStatus.textContent = "Voice input unavailable here";
    }
    return;
  }
  if (voiceStatus) {
    voiceStatus.textContent = "Voice input ready";
  }
  const recognition = new SpeechRecognition();
  recognition.lang = "en-US";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  recognition.onstart = () => {
    state.listening = true;
    micButton.classList.add("listening");
    micButton.textContent = "Listening";
    if (voiceStatus) {
      voiceStatus.textContent = "Listening...";
    }
  };
  recognition.onend = () => {
    state.listening = false;
    micButton.classList.remove("listening");
    micButton.textContent = "Mic";
    if (voiceStatus) {
      voiceStatus.textContent = "Voice input ready";
    }
  };
  recognition.onresult = (event) => {
    const text = event.results[0][0].transcript;
    promptInput.value = text;
    if (voiceStatus) {
      voiceStatus.textContent = "Voice captured";
    }
  };
  recognition.onerror = () => {
    state.listening = false;
    micButton.classList.remove("listening");
    micButton.textContent = "Mic";
    if (voiceStatus) {
      voiceStatus.textContent = "Voice input error";
    }
  };
  state.recognition = recognition;
}

function initSpeechSynthesisState() {
  if (!("speechSynthesis" in window)) {
    state.speechEnabled = false;
    voiceToggle.classList.remove("active");
    voiceToggle.textContent = "Voice N/A";
    voiceToggle.disabled = true;
    voiceToggle.title = "Speech synthesis is not available in this browser.";
    if (voiceStatus && voiceStatus.textContent === "Checking voice...") {
      voiceStatus.textContent = "Voice output unavailable here";
    }
  } else if (voiceStatus && voiceStatus.textContent === "Checking voice...") {
    voiceStatus.textContent = "Voice output ready";
  }
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = promptInput.value.trim();
  if (!message) return;
  await sendPrompt(message);
});

micButton.addEventListener("click", () => {
  if (!state.recognition) return;
  if (state.listening) {
    state.recognition.stop();
    return;
  }
  state.recognition.start();
});

voiceToggle.addEventListener("click", () => {
  state.speechEnabled = !state.speechEnabled;
  voiceToggle.classList.toggle("active", state.speechEnabled);
  voiceToggle.textContent = state.speechEnabled ? "Voice On" : "Voice Off";
  if (!state.speechEnabled && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
});

document.querySelectorAll(".chip").forEach((button) => {
  button.addEventListener("click", () => {
    promptInput.value = button.dataset.prompt || "";
    promptInput.focus();
  });
});

ingestForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const path = ingestPath.value.trim();
  if (!path) return;
  ingestStatus.textContent = "Ingesting...";
  const response = await fetch("/api/ingest", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Jarvis-Token": csrfToken },
    body: JSON.stringify({ path }),
  });
  const data = await response.json();
  ingestStatus.textContent = `Stored ${data.count || 0} file(s).`;
  await refreshState();
});

window.addEventListener("load", async () => {
  if ("speechSynthesis" in window) {
    voiceToggle.classList.add("active");
  }
  initSpeechSynthesisState();
  initSpeechRecognition();
  addMessage("jarvis", "Command deck online. Ask me to open apps, search the browser, create tasks, save notes, or recall your recent work.");
  await refreshState();
});

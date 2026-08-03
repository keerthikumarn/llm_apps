const API_BASE = "http://localhost:8000";

  const state = {
    userId: "",
    sending: false,
  };

  const el = {
    userIdInput: document.getElementById("userIdInput"),
    passengerDisplay: document.getElementById("passengerDisplay"),
    routeName: document.getElementById("routeName"),
    stampsList: document.getElementById("stampsList"),
    stampsEmpty: document.getElementById("stampsEmpty"),
    clearBtn: document.getElementById("clearBtn"),
    lockedOverlay: document.getElementById("lockedOverlay"),
    chatThread: document.getElementById("chatThread"),
    chatEmptyState: document.getElementById("chatEmptyState"),
    errorBanner: document.getElementById("errorBanner"),
    messageInput: document.getElementById("messageInput"),
    sendBtn: document.getElementById("sendBtn"),
  };

  function showError(message) {
    el.errorBanner.textContent = message;
    el.errorBanner.style.display = "block";
  }
  function clearError() {
    el.errorBanner.style.display = "none";
  }

  function setLocked(locked) {
    el.lockedOverlay.style.display = locked ? "flex" : "none";
    el.messageInput.disabled = locked || state.sending;
    el.sendBtn.disabled = locked || state.sending;
    el.clearBtn.disabled = locked;
  }

  function renderStamps(memories) {
    el.stampsList.innerHTML = "";
    if (!memories || memories.length === 0) {
      el.stampsEmpty.style.display = "block";
      return;
    }
    el.stampsEmpty.style.display = "none";
    memories.forEach((m) => {
      const div = document.createElement("div");
      div.className = "stamp";
      const text = m.memory.length > 46 ? m.memory.slice(0, 44) + "…" : m.memory;
      div.textContent = text;
      div.title = m.memory;
      el.stampsList.appendChild(div);
    });
  }

  async function fetchMemories() {
    if (!state.userId) return;
    try {
      const res = await fetch(`${API_BASE}/api/memory/${encodeURIComponent(state.userId)}`);
      if (!res.ok) throw new Error(`Memory desk returned ${res.status}`);
      const data = await res.json();
      renderStamps(data.memories);
    } catch (err) {
      showError(`Couldn't reach the memory desk: ${err.message}`);
    }
  }

  async function clearMemories() {
    if (!state.userId) return;
    el.clearBtn.disabled = true;
    try {
      const res = await fetch(`${API_BASE}/api/memory/${encodeURIComponent(state.userId)}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(`Memory desk returned ${res.status}`);
      renderStamps([]);
    } catch (err) {
      showError(`Couldn't clear memory: ${err.message}`);
    } finally {
      el.clearBtn.disabled = false;
    }
  }

  function addBubble(role, text, memoriesUsed) {
    el.chatEmptyState.style.display = "none";
    const row = document.createElement("div");
    row.className = `bubble-row ${role}`;

    const label = document.createElement("div");
    label.className = "bubble-label";
    label.textContent = role === "user" ? "you" : "wanderline";
    row.appendChild(label);

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text;
    row.appendChild(bubble);

    if (memoriesUsed && memoriesUsed.length > 0) {
      const mu = document.createElement("div");
      mu.className = "memories-used";
      mu.innerHTML = "<span>recalled: " + memoriesUsed.length + " stamp" + (memoriesUsed.length > 1 ? "s" : "") + "</span>";
      row.appendChild(mu);
    }

    el.chatThread.appendChild(row);
    el.chatThread.scrollTop = el.chatThread.scrollHeight;
    return row;
  }

  function addTypingIndicator() {
    const wrap = document.createElement("div");
    wrap.className = "typing";
    wrap.id = "typingIndicator";
    wrap.innerHTML = "<span></span><span></span><span></span>";
    el.chatThread.appendChild(wrap);
    el.chatThread.scrollTop = el.chatThread.scrollHeight;
  }
  function removeTypingIndicator() {
    const t = document.getElementById("typingIndicator");
    if (t) t.remove();
  }

  function appendMemoriesUsedTag(row, memoriesUsed, intent) {
    const hasMemories = memoriesUsed && memoriesUsed.length > 0;
    const showIntent = intent && intent !== "general";
    if (!hasMemories && !showIntent) return;

    const mu = document.createElement("div");
    mu.className = "memories-used";
    let html = "";
    if (showIntent) {
      html += `<span>intent: ${intent.replace("_", " ")}</span>`;
    }
    if (hasMemories) {
      const count = memoriesUsed.length;
      html += `<span>recalled: ${count} stamp${count > 1 ? "s" : ""}</span>`;
    }
    mu.innerHTML = html;
    row.appendChild(mu);
  }

  async function sendMessage() {
    const text = el.messageInput.value.trim();
    if (!text || state.sending || !state.userId) return;

    clearError();
    addBubble("user", text);
    el.messageInput.value = "";
    el.messageInput.style.height = "auto";

    state.sending = true;
    el.sendBtn.disabled = true;
    el.messageInput.disabled = true;
    addTypingIndicator();

    // Placeholder bubble that gets filled in as tokens stream.
    let assistantRow = null;
    let bubbleEl = null;
    let fullText = "";
    let memoriesUsed = [];
    let intent = "general";
    let gotFirstToken = false;

    try {
      const res = await fetch(`${API_BASE}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: state.userId, message: text }),
      });

      if (!res.ok || !res.body) {
        throw new Error(`Travel desk returned ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop(); // last (possibly incomplete) line stays buffered

        for (const line of lines) {
          if (!line.trim()) continue;
          const evt = JSON.parse(line);

          if (evt.type === "intent") {
            intent = evt.data || "general";
          } else if (evt.type === "memories") {
            memoriesUsed = evt.data || [];
          } else if (evt.type === "token") {
            if (!gotFirstToken) {
              removeTypingIndicator();
              assistantRow = addBubble("assistant", "");
              assistantRow.classList.add("streaming");
              bubbleEl = assistantRow.querySelector(".bubble");
              gotFirstToken = true;
            }
            fullText += evt.data;
            bubbleEl.textContent = fullText;
            el.chatThread.scrollTop = el.chatThread.scrollHeight;
          } else if (evt.type === "error") {
            throw new Error(evt.data || "The local model failed to respond.");
          } else if (evt.type === "done") {
            if (assistantRow) {
              assistantRow.classList.remove("streaming");
              appendMemoriesUsedTag(assistantRow, memoriesUsed, intent);
            }
          }
        }
      }

      if (!gotFirstToken) {
        // Stream ended with no tokens at all — surface as an error rather
        // than leaving an empty bubble.
        throw new Error("Received an empty response from the local model.");
      }

      fetchMemories();
    } catch (err) {
      removeTypingIndicator();
      if (assistantRow && !fullText) assistantRow.remove();
      showError(`Flight delayed — ${err.message}. Check that the backend is running on ${API_BASE}.`);
    } finally {
      state.sending = false;
      el.sendBtn.disabled = false;
      el.messageInput.disabled = false;
      el.messageInput.focus();
    }
  }

  el.userIdInput.addEventListener("input", () => {
    const value = el.userIdInput.value.trim();
    state.userId = value;
    el.passengerDisplay.textContent = value;
    el.routeName.textContent = value || "unassigned";
    setLocked(!value);
    if (value) {
      fetchMemories();
    } else {
      renderStamps([]);
    }
  });

  el.sendBtn.addEventListener("click", sendMessage);
  el.messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
  el.messageInput.addEventListener("input", () => {
    el.messageInput.style.height = "auto";
    el.messageInput.style.height = Math.min(el.messageInput.scrollHeight, 120) + "px";
  });
  el.clearBtn.addEventListener("click", clearMemories);

  setLocked(true);
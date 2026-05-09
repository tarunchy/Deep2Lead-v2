// Gemma-powered chatbot widget
(function () {
  const fab = document.getElementById("chat-fab");
  const panel = document.getElementById("chat-panel");
  const closeBtn = document.getElementById("chat-close");
  const messages = document.getElementById("chat-messages");
  const input = document.getElementById("chat-input");
  const sendBtn = document.getElementById("chat-send");

  let history = [];
  let busy = false;

  const CHIPS = [
    "Show my latest experiment",
    "What is my top scoring molecule?",
    "Explain QED and SAS",
    "What makes a good drug candidate?",
  ];

  function open() {
    panel.classList.add("open");
    input.focus();
    if (!messages.children.length) renderWelcome();
  }

  function close() { panel.classList.remove("open"); }

  fab.addEventListener("click", () => panel.classList.contains("open") ? close() : open());
  closeBtn.addEventListener("click", close);

  function renderWelcome() {
    const div = document.createElement("div");
    div.className = "chat-welcome";
    div.innerHTML = `<p>Hi! I'm Gemma — your drug discovery assistant.<br>Ask me anything about your experiments or molecules.</p>
      <div class="chat-chip-row">${CHIPS.map(c => `<span class="chat-chip" data-q="${c}">${c}</span>`).join("")}</div>`;
    div.querySelectorAll(".chat-chip").forEach(chip => {
      chip.addEventListener("click", () => { input.value = chip.dataset.q; sendMessage(); });
    });
    messages.appendChild(div);
  }

  function appendBubble(text, role) {
    const div = document.createElement("div");
    div.className = `chat-bubble ${role}`;
    div.innerHTML = formatMessage(text);
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return div;
  }

  function formatMessage(text) {
    // Render backtick code spans
    return escHtmlChat(text).replace(/`([^`]+)`/g, "<code>$1</code>");
  }

  function escHtmlChat(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function showTyping() {
    const div = document.createElement("div");
    div.className = "chat-typing";
    div.id = "chat-typing-indicator";
    div.innerHTML = "<span></span><span></span><span></span>";
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
  }

  function hideTyping() {
    document.getElementById("chat-typing-indicator")?.remove();
  }

  async function sendMessage() {
    const text = input.value.trim();
    if (!text || busy) return;
    busy = true;
    sendBtn.disabled = true;
    input.value = "";
    input.style.height = "auto";

    appendBubble(text, "user");
    history.push({ role: "user", content: text });

    showTyping();
    try {
      const data = await apiFetch("/api/v2/chat", {
        method: "POST",
        body: JSON.stringify({ message: text, history: history.slice(-8) }),
      });
      hideTyping();
      appendBubble(data.reply, "bot");
      history.push({ role: "assistant", content: data.reply });
    } catch (err) {
      hideTyping();
      const errDiv = appendBubble("Sorry, Gemma is unavailable right now. Make sure the DGX server is reachable.", "bot error");
      errDiv.classList.add("error");
    } finally {
      busy = false;
      sendBtn.disabled = false;
      input.focus();
    }
  }

  sendBtn.addEventListener("click", sendMessage);

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // Auto-resize textarea
  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 80) + "px";
  });
})();

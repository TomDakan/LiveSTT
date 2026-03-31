/**
 * shared.js — Shared transcript rendering and WebSocket logic for Live STT.
 *
 * Used by both index.html (operator view) and display.html (kiosk view).
 * Exposes window.LiveSTT with init(), clearTranscript(), speakerColour().
 */
window.LiveSTT = (() => {
  "use strict";

  const WS_URL = `ws://${window.location.host}/ws/transcripts`;
  const RECONNECT_MS = 3000;

  // ── Speaker colours ──────────────────────────────────────────────────
  const SPEAKER_PALETTE = [
    ["#6366f1", "#1e1b4b"],
    ["#10b981", "#064e3b"],
    ["#f59e0b", "#451a03"],
    ["#ec4899", "#500724"],
    ["#06b6d4", "#082f49"],
    ["#a855f7", "#2e1065"],
    ["#f97316", "#431407"],
  ];

  function speakerColour(name) {
    if (!name || name === "Unknown") return null;
    let hash = 0;
    for (let i = 0; i < name.length; i++)
      hash = (hash * 31 + name.charCodeAt(i)) | 0;
    return SPEAKER_PALETTE[Math.abs(hash) % SPEAKER_PALETTE.length];
  }

  // ── Config (set by init) ─────────────────────────────────────────────
  let cfg = {
    containerEl: null,
    statusDotEl: null,
    statusTextEl: null,
    onSessionStatus: null,
    onSttStatus: null,
    onConnected: null,
    autoScroll: true, // display.html forces true; index.html uses smart scroll
  };

  // ── State ────────────────────────────────────────────────────────────
  let ws = null;
  let reconnectTimer = null;
  let backfillRendered = false;
  let separatorInserted = false;
  let dgState = "ok";
  let userScrolledUp = false;

  // ── Auto-scroll ──────────────────────────────────────────────────────
  // Auto-scroll to bottom unless the user has scrolled up to re-read.
  // Re-engage auto-scroll when the user scrolls back near the bottom.
  function setupAutoScroll() {
    if (!cfg.containerEl) return;
    cfg.containerEl.addEventListener("scroll", () => {
      const el = cfg.containerEl;
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
      userScrolledUp = !nearBottom;
    });
  }

  function scrollToBottom() {
    if (!cfg.containerEl || userScrolledUp) return;
    cfg.containerEl.scrollTop = cfg.containerEl.scrollHeight;
  }

  // ── Connection status ────────────────────────────────────────────────
  function setWsStatus(state) {
    if (!cfg.statusDotEl) return;
    if (state === "connecting") {
      cfg.statusDotEl.className = "dot-pulse bg-yellow-400";
      cfg.statusDotEl.style.animation = "";
      if (cfg.statusTextEl) cfg.statusTextEl.textContent = "Connecting\u2026";
    } else if (state === "offline") {
      cfg.statusDotEl.className = "dot-pulse bg-red-500";
      cfg.statusDotEl.style.animation = "none";
      if (cfg.statusTextEl) cfg.statusTextEl.textContent = "Disconnected";
    } else {
      applyDgStatus();
    }
  }

  function applyDgStatus() {
    if (!cfg.statusDotEl) return;
    if (dgState === "reconnecting") {
      cfg.statusDotEl.className = "dot-pulse bg-amber-400";
      cfg.statusDotEl.style.animation = "";
      if (cfg.statusTextEl)
        cfg.statusTextEl.textContent = "Reconnecting\u2026";
    } else {
      cfg.statusDotEl.className = "dot-pulse bg-green-400";
      cfg.statusDotEl.style.animation = "none";
      if (cfg.statusTextEl) cfg.statusTextEl.textContent = "Live";
    }
  }

  // ── DOM helpers ──────────────────────────────────────────────────────
  function appendFinalLine(text, speaker, isBackfill) {
    if (!text.trim() || !cfg.containerEl) return;

    const row = document.createElement("div");
    row.className = "line-enter py-0.5";

    const body = document.createElement("span");
    body.className = isBackfill
      ? "transcript-text text-white/40 leading-relaxed"
      : "transcript-text text-white/85 leading-relaxed";

    const colours = speakerColour(speaker);
    if (colours) {
      const badge = document.createElement("span");
      badge.className = "speaker-badge";
      badge.style.color = colours[0];
      badge.style.background = colours[1];
      badge.style.border = `1px solid ${colours[0]}44`;
      badge.textContent = speaker;
      body.appendChild(badge);
    }

    body.appendChild(document.createTextNode(text));
    row.appendChild(body);
    cfg.containerEl.appendChild(row);

    scrollToBottom();
  }

  function clearTranscript() {
    if (cfg.containerEl) cfg.containerEl.innerHTML = "";
    backfillRendered = false;
    separatorInserted = false;
    userScrolledUp = false;
  }

  // ── WebSocket ────────────────────────────────────────────────────────
  function connect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    setWsStatus("connecting");

    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      setWsStatus("live");
      if (cfg.onConnected) cfg.onConnected();
    };

    ws.onmessage = (event) => {
      let msg;
      try {
        msg = JSON.parse(event.data);
      } catch {
        return;
      }

      if (msg.type === "transcript") {
        const p = msg.payload || {};
        const isBackfill = p.source === "backfill";
        const isLive = !p.source || p.source === "live";
        if (!isBackfill && !isLive) return;

        // Only render final transcripts
        if (!p.is_final) return;

        const text = (p.text || "").trim();
        const speaker = p.speaker || null;

        if (isLive && backfillRendered && !separatorInserted) {
          separatorInserted = true;
          const sep = document.createElement("div");
          sep.className = "my-2 border-t border-white/10";
          cfg.containerEl.appendChild(sep);
        }
        appendFinalLine(text, speaker, isBackfill);
        if (isBackfill) backfillRendered = true;
        return;
      }

      if (msg.type === "session_status") {
        if (cfg.onSessionStatus) cfg.onSessionStatus(msg.payload || {});
        return;
      }

      if (msg.type === "stt_status") {
        const state = (msg.payload || {}).state;
        dgState = state === "reconnecting" ? "reconnecting" : "ok";
        applyDgStatus();
        if (cfg.onSttStatus) cfg.onSttStatus(msg.payload || {});
        return;
      }
    };

    ws.onclose = () => {
      setWsStatus("offline");
      reconnectTimer = setTimeout(connect, RECONNECT_MS);
    };

    ws.onerror = () => {
      ws.close();
    };
  }

  // ── Public API ───────────────────────────────────────────────────────
  function init(userConfig) {
    Object.assign(cfg, userConfig);
    setupAutoScroll();
    connect();
  }

  return { init, clearTranscript, speakerColour };
})();

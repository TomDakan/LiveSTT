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
    onFirstTranscript: null,
    onSttStatus: null,
    onConnected: null,
    autoScroll: true, // display.html forces true; index.html uses smart scroll
  };

  // ── State ────────────────────────────────────────────────────────────
  let ws = null;
  let reconnectTimer = null;
  let backfillRendered = false;
  let separatorInserted = false;
  let _firstTranscriptFired = false;
  let dgLaneStates = {};  // per-lane Deepgram status
  let userScrolledUp = false;

  // ── Scroll position persistence ──────────────────────────────────────
  const _SCROLL_KEY = "livestt_scroll";
  let _currentSessionId = null;
  let _replayDone = true;
  let _jumpBtn = null;

  function _storageKey() {
    return _currentSessionId ? `${_SCROLL_KEY}_${_currentSessionId}` : null;
  }

  function _saveScrollPos() {
    const key = _storageKey();
    if (!key || !cfg.containerEl) return;
    const el = cfg.containerEl;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
    localStorage.setItem(key, JSON.stringify({
      top: el.scrollTop,
      atBottom,
    }));
  }

  function _restoreScrollPos() {
    const key = _storageKey();
    if (!key || !cfg.containerEl) return;
    try {
      const saved = JSON.parse(localStorage.getItem(key) || "null");
      if (!saved) {
        // No saved position — scroll to bottom, enable auto-scroll
        userScrolledUp = false;
        cfg.containerEl.scrollTop = cfg.containerEl.scrollHeight;
        return;
      }
      if (saved.atBottom) {
        userScrolledUp = false;
        cfg.containerEl.scrollTop = cfg.containerEl.scrollHeight;
      } else {
        cfg.containerEl.scrollTop = saved.top;
        userScrolledUp = true;
      }
    } catch {
      cfg.containerEl.scrollTop = cfg.containerEl.scrollHeight;
    }
    _updateJumpBtn();
  }

  function _createJumpBtn() {
    if (!cfg.containerEl) return;
    _jumpBtn = document.createElement("button");
    _jumpBtn.textContent = "\u2193 Jump to latest";
    _jumpBtn.className = "jump-to-bottom";
    Object.assign(_jumpBtn.style, {
      position: "fixed", bottom: "24px", right: "24px",
      padding: "6px 16px", borderRadius: "20px", fontSize: "0.8rem",
      fontWeight: "600", border: "none", cursor: "pointer", zIndex: "40",
      background: "#6366f1", color: "#fff", opacity: "0",
      pointerEvents: "none", transition: "opacity 0.2s",
    });
    _jumpBtn.addEventListener("click", () => {
      userScrolledUp = false;
      cfg.containerEl.scrollTop = cfg.containerEl.scrollHeight;
      _updateJumpBtn();
    });
    document.body.appendChild(_jumpBtn);
  }

  function _updateJumpBtn() {
    if (!_jumpBtn) return;
    if (userScrolledUp) {
      _jumpBtn.style.opacity = "1";
      _jumpBtn.style.pointerEvents = "auto";
    } else {
      _jumpBtn.style.opacity = "0";
      _jumpBtn.style.pointerEvents = "none";
    }
  }

  // ── Auto-scroll ──────────────────────────────────────────────────────
  // Auto-scroll to bottom unless the user has scrolled up to re-read.
  // Re-engage auto-scroll when the user scrolls back near the bottom.
  function setupAutoScroll() {
    if (!cfg.containerEl) return;
    cfg.containerEl.addEventListener("scroll", () => {
      const el = cfg.containerEl;
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
      userScrolledUp = !nearBottom;
      _updateJumpBtn();
      _saveScrollPos();
    });
    _createJumpBtn();
    window.addEventListener("beforeunload", _saveScrollPos);
  }

  function scrollToBottom() {
    if (!cfg.containerEl || userScrolledUp || !_replayDone) return;
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
    const states = Object.values(dgLaneStates);
    // Show "Reconnecting" only if ALL lanes are reconnecting (or no lanes known)
    const allDown = states.length > 0 && states.every(s => s === "reconnecting");
    if (allDown) {
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
        if (!_firstTranscriptFired && cfg.onFirstTranscript) {
          _firstTranscriptFired = true;
          cfg.onFirstTranscript();
        }
        return;
      }

      if (msg.type === "replay_start") {
        _currentSessionId = (msg.payload || {}).session_id || null;
        _replayDone = false;
        // Purge scroll positions from previous sessions
        for (let i = localStorage.length - 1; i >= 0; i--) {
          const k = localStorage.key(i);
          if (k && k.startsWith(_SCROLL_KEY) && k !== _storageKey()) {
            localStorage.removeItem(k);
          }
        }
        return;
      }

      if (msg.type === "replay_complete") {
        _replayDone = true;
        _restoreScrollPos();
        return;
      }

      if (msg.type === "session_status") {
        const p = msg.payload || {};
        if (p.session_id) _currentSessionId = p.session_id;
        if (p.state === 'starting' || p.state === 'idle') _firstTranscriptFired = false;
        if (cfg.onSessionStatus) cfg.onSessionStatus(p);
        return;
      }

      if (msg.type === "stt_status") {
        const p = msg.payload || {};
        const lane = p.lane || "default";
        dgLaneStates[lane] = p.state === "reconnecting" ? "reconnecting" : "ok";
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

/* =========================================================
   AIRGAP REMOTE CONSOLE — APPLICATION LOGIC
   Vanilla JS, organized into small modules.
   Talks only to the local Flask receiver at /api/*.
   ========================================================= */
(function () {
  "use strict";

  /* =======================================================
     UTILITIES
     ======================================================= */
  const Utils = {
    clamp(v, min, max) { return Math.max(min, Math.min(max, v)); },

    formatHMS(totalSeconds) {
      const s = Math.max(0, Math.floor(totalSeconds || 0));
      const h = Math.floor(s / 3600);
      const m = Math.floor((s % 3600) / 60);
      const sec = s % 60;
      const pad = (n) => String(n).padStart(2, "0");
      return `${pad(h)}:${pad(m)}:${pad(sec)}`;
    },

    debounce(fn, wait) {
      let t = null;
      return (...args) => {
        clearTimeout(t);
        t = setTimeout(() => fn(...args), wait);
      };
    },

    // Coalesces rapid calls into one per animation frame, keeping only the
    // most recently accumulated payload (used for trackpad / laser streams).
    rafThrottle(fn) {
      let scheduled = false;
      let latestArgs = null;
      return (...args) => {
        latestArgs = args;
        if (scheduled) return;
        scheduled = true;
        requestAnimationFrame(() => {
          scheduled = false;
          fn(...latestArgs);
        });
      };
    },

    humanizeError(rawMessage) {
      if (!rawMessage) return "Something went wrong. Please try again.";
      // Backend messages are already short and readable; pass through, but
      // strip stack-trace-like noise if it ever leaks through.
      const msg = String(rawMessage);
      if (msg.length > 140) return "The receiver returned an unexpected error.";
      return msg;
    }
  };

  /* =======================================================
     TOAST NOTIFICATIONS
     ======================================================= */
  const Toast = (() => {
    let root = null;
    const ICONS = { success: "✓", info: "i", warning: "!", error: "✕" };

    function init() {
      root = document.getElementById("toast-stack");
    }

    function show(type, message, duration = 3200) {
      if (!root) return;
      const el = document.createElement("div");
      el.className = `toast toast--${type}`;
      el.setAttribute("role", type === "error" ? "alert" : "status");
      const icon = document.createElement("span");
      icon.className = "toast-icon";
      icon.textContent = ICONS[type] || ICONS.info;
      const text = document.createElement("span");
      text.textContent = message;
      el.appendChild(icon);
      el.appendChild(text);
      root.appendChild(el);
      requestAnimationFrame(() => el.classList.add("is-visible"));

      const remove = () => {
        el.classList.remove("is-visible");
        setTimeout(() => el.remove(), 220);
      };
      setTimeout(remove, duration);
    }

    return { init, show };
  })();

  /* =======================================================
     MODAL (confirmation dialogs)
     ======================================================= */
  const Modal = (() => {
    let backdrop, titleEl, bodyEl, cancelBtn, confirmBtn;
    let resolver = null;
    let lastFocused = null;

    function init() {
      backdrop = document.getElementById("modal-backdrop");
      titleEl = document.getElementById("modal-title");
      bodyEl = document.getElementById("modal-body");
      cancelBtn = document.getElementById("modal-cancel");
      confirmBtn = document.getElementById("modal-confirm");

      cancelBtn.addEventListener("click", () => close(false));
      confirmBtn.addEventListener("click", () => close(true));
      backdrop.addEventListener("click", (e) => { if (e.target === backdrop) close(false); });
      document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && !backdrop.hasAttribute("hidden")) close(false);
      });
    }

    function confirm({ title, body, confirmLabel = "Confirm", danger = true }) {
      titleEl.textContent = title;
      bodyEl.textContent = body;
      confirmBtn.textContent = confirmLabel;
      confirmBtn.className = "btn " + (danger ? "btn-danger" : "btn-primary");

      lastFocused = document.activeElement;
      backdrop.hidden = false;
      requestAnimationFrame(() => backdrop.classList.add("is-visible"));
      confirmBtn.focus();

      return new Promise((resolve) => { resolver = resolve; });
    }

    function close(result) {
      backdrop.classList.remove("is-visible");
      setTimeout(() => { backdrop.hidden = true; }, 200);
      if (lastFocused && lastFocused.focus) lastFocused.focus();
      if (resolver) { resolver(result); resolver = null; }
    }

    return { init, confirm };
  })();

  /* =======================================================
     CONNECTION MANAGER
     ======================================================= */
  const Connection = (() => {
    let state = "connecting"; // connecting | live | offline
    let cluster, dot, label, hostnameEl, ipEl, pingEl;
    let pollTimer = null;
    let hasWarnedOffline = false;

    function init() {
      cluster = document.getElementById("status-cluster");
      dot = document.getElementById("status-dot");
      label = document.getElementById("status-label");
      hostnameEl = document.getElementById("meta-hostname");
      ipEl = document.getElementById("meta-ip");
      pingEl = document.getElementById("meta-ping");

      setState("connecting");
      pollNow();
      pollTimer = setInterval(pollNow, 5000);
    }

    function setState(next) {
      if (state === next) return;
      const prev = state;
      state = next;
      cluster.dataset.state = next;
      label.textContent = next === "live" ? "CONNECTED" : next === "offline" ? "OFFLINE" : "CONNECTING";

      if (next === "offline" && !hasWarnedOffline) {
        Toast.show("warning", "Connection lost. Retrying…");
        hasWarnedOffline = true;
      }
      if (next === "live" && prev === "offline") {
        Toast.show("success", "Reconnected to receiver");
      }
      if (next === "live") hasWarnedOffline = false;
    }

    // Called by the API layer on every network-level success/failure so the
    // header reflects reality even between polling cycles.
    function markOnline() { if (state !== "live") setState("live"); }
    function markOffline() { setState("offline"); }

    async function pollNow() {
      const t0 = performance.now();
      const res = await Api.request("/api/status", { method: "GET", silent: true, timeout: 4000 });
      const rtt = Math.round(performance.now() - t0);

      if (!res.ok) {
        setState("offline");
        setMeta("--", "--", "--");
        DeviceInfo.update(null, null);
        return;
      }
      setState("live");
      const info = res.data;
      setMeta(info.hostname || "--", info.ip || "--", `${rtt}ms`);
      DeviceInfo.update(info, rtt);
    }

    function setMeta(hostname, ip, ping) {
      hostnameEl.hidden = false; hostnameEl.dataset.label = "HOST"; hostnameEl.textContent = hostname;
      ipEl.hidden = false; ipEl.dataset.label = "IP"; ipEl.textContent = ip;
      pingEl.hidden = false; pingEl.dataset.label = "PING"; pingEl.textContent = ping;
    }

    function getState() { return state; }

    return { init, markOnline, markOffline, getState };
  })();

  /* =======================================================
     API CLIENT (centralized fetch wrapper)
     ======================================================= */
  const Api = (() => {
    async function request(path, { method = "GET", body, timeout = 8000, silent = false } = {}) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeout);
      let res, data;

      try {
        res = await fetch(path, {
          method,
          headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
          body: body !== undefined ? JSON.stringify(body) : undefined,
          signal: controller.signal
        });
        clearTimeout(timer);
      } catch (networkErr) {
        clearTimeout(timer);
        Connection.markOffline();
        if (!silent) {
          Toast.show("error", "Unable to reach the PC. Check that AirGap is running and on the same network.");
        }
        return { ok: false, error: networkErr.message, data: null };
      }

      try {
        data = await res.json();
      } catch (parseErr) {
        data = null;
      }

      // A response — even an HTTP error — means the receiver is reachable.
      Connection.markOnline();

      if (!res.ok || !data || data.success === false) {
        const msg = (data && data.error) ? data.error : `Request failed (HTTP ${res.status})`;
        if (!silent) Toast.show("error", Utils.humanizeError(msg));
        return { ok: false, error: msg, data };
      }

      return { ok: true, data };
    }

    // Thin wrapper for the backend's generic run_command action, used for
    // launching named apps (Chrome, PowerPoint, Spotify) that don't have a
    // dedicated controller function. cmd.exe resolves these via each app's
    // registered "App Path", so no hardcoded install paths are needed.
    function runCommand(command, opts = {}) {
      return request("/api/system", {
        method: "POST",
        body: { action: "run_command", command, shell: "cmd" },
        ...opts
      });
    }

    return { request, runCommand };
  })();

  /* =======================================================
     NAVIGATION
     ======================================================= */
  const Navigation = (() => {
    let navButtons, panels;

    function init() {
      navButtons = Array.from(document.querySelectorAll(".nav-btn"));
      panels = Array.from(document.querySelectorAll(".panel"));

      navButtons.forEach((btn) => {
        btn.addEventListener("click", () => goTo(btn.dataset.target));
      });

      goTo("trackpad");
    }

    function goTo(target) {
      panels.forEach((p) => p.classList.toggle("is-active", p.dataset.panel === target));
      navButtons.forEach((b) => {
        const active = b.dataset.target === target;
        b.classList.toggle("is-active", active);
        b.setAttribute("aria-current", active ? "page" : "false");
      });
      document.dispatchEvent(new CustomEvent("airgap:panel-change", { detail: { panel: target } }));
    }

    return { init, goTo };
  })();

  /* =======================================================
     TRACKPAD
     ======================================================= */
  const Trackpad = (() => {
    let surface, glow, feedback, sensSlider, sensValue, leftBtn, rightBtn;
    let sensitivity = 1.0;

    // Gesture state
    let gesture = null; // { fingerCount, moved, startTime, lastX, lastY, lastMidY }
    let pendingMove = { dx: 0, dy: 0 };
    let pendingScroll = { dy: 0 };

    const flushMove = Utils.rafThrottle(() => {
      if (pendingMove.dx === 0 && pendingMove.dy === 0) return;
      const dx = pendingMove.dx, dy = pendingMove.dy;
      pendingMove.dx = 0; pendingMove.dy = 0;
      Api.request("/api/command", {
        method: "POST",
        silent: true,
        body: { action: "move", dx, dy, sensitivity }
      });
    });

    const flushScroll = Utils.rafThrottle(() => {
      if (pendingScroll.dy === 0) return;
      const dy = pendingScroll.dy;
      pendingScroll.dy = 0;
      Api.request("/api/command", {
        method: "POST",
        silent: true,
        body: { action: "scroll", dx: 0, dy }
      });
    });

    function init() {
      surface = document.getElementById("trackpad-surface");
      glow = document.getElementById("trackpad-glow");
      feedback = document.getElementById("trackpad-feedback");
      sensSlider = document.getElementById("sensitivity-slider");
      sensValue = document.getElementById("sensitivity-value");
      leftBtn = document.getElementById("tp-left-click");
      rightBtn = document.getElementById("tp-right-click");

      // Sensitivity: 1-10 slider -> 0.4x - 2.8x multiplier
      updateSensitivityUI(sensSlider.value);
      sensSlider.addEventListener("input", () => updateSensitivityUI(sensSlider.value));

      // Prevent context menu / long-press callout on the surface
      surface.addEventListener("contextmenu", (e) => e.preventDefault());

      surface.addEventListener("touchstart", onTouchStart, { passive: false });
      surface.addEventListener("touchmove", onTouchMove, { passive: false });
      surface.addEventListener("touchend", onTouchEnd, { passive: false });
      surface.addEventListener("touchcancel", onTouchEnd, { passive: false });

      // Desktop pointer fallback (mouse only — touch is handled above)
      let mouseDragging = false;
      surface.addEventListener("pointerdown", (e) => {
        if (e.pointerType !== "mouse") return;
        mouseDragging = true;
        showGlow(e.offsetX, e.offsetY);
        surface.setPointerCapture(e.pointerId);
      });
      surface.addEventListener("pointermove", (e) => {
        if (e.pointerType !== "mouse") return;
        showGlow(e.offsetX, e.offsetY);
        if (!mouseDragging) return;
        if (e.movementX || e.movementY) {
          pendingMove.dx += e.movementX;
          pendingMove.dy += e.movementY;
          flushMove();
        }
      });
      surface.addEventListener("pointerup", (e) => {
        if (e.pointerType !== "mouse") return;
        mouseDragging = false;
        hideGlow();
      });
      surface.addEventListener("pointerleave", () => hideGlow());
      surface.addEventListener("click", (e) => {
        if (e.pointerType && e.pointerType !== "mouse") return;
        sendAction("left_click");
        showFeedback("LEFT CLICK");
      });
      surface.addEventListener("contextmenu", (e) => {
        // On desktop, right-click should trigger a remote right click rather
        // than the browser menu (already prevented above), so fire here too.
        sendAction("right_click");
        showFeedback("RIGHT CLICK");
      });

      leftBtn.addEventListener("click", () => { sendAction("left_click"); showFeedback("LEFT CLICK"); });
      rightBtn.addEventListener("click", () => { sendAction("right_click"); showFeedback("RIGHT CLICK"); });
    }

    function updateSensitivityUI(raw) {
      const v = Number(raw);
      // Map 1-10 -> 0.4 - 2.8
      sensitivity = 0.4 + (v - 1) * (2.4 / 9);
      const pct = ((v - 1) / 9) * 100;
      sensSlider.style.setProperty("--fill", pct + "%");
      sensValue.textContent = v <= 3 ? "LOW" : v <= 7 ? "MEDIUM" : "HIGH";
    }

    function sendAction(action, extra = {}) {
      Api.request("/api/command", { method: "POST", body: { action, ...extra } });
    }

    function showGlow(x, y) {
      glow.style.left = x + "px";
      glow.style.top = y + "px";
      glow.classList.add("is-active");
    }
    function hideGlow() { glow.classList.remove("is-active"); }

    let feedbackTimer = null;
    function showFeedback(text) {
      feedback.textContent = text;
      feedback.classList.add("is-visible");
      clearTimeout(feedbackTimer);
      feedbackTimer = setTimeout(() => feedback.classList.remove("is-visible"), 650);
    }

    function midY(touches) { return (touches[0].clientY + touches[1].clientY) / 2; }

    function onTouchStart(e) {
      e.preventDefault();
      const touches = e.touches;
      if (!gesture || e.touches.length > (gesture.maxFingers || 0)) {
        gesture = gesture || {};
        gesture.maxFingers = Math.max(gesture.maxFingers || 0, touches.length);
      }
      gesture.startTime = gesture.startTime || performance.now();
      gesture.moved = gesture.moved || false;

      if (touches.length === 1) {
        gesture.lastX = touches[0].clientX;
        gesture.lastY = touches[0].clientY;
        const rect = surface.getBoundingClientRect();
        showGlow(touches[0].clientX - rect.left, touches[0].clientY - rect.top);
      } else if (touches.length === 2) {
        gesture.lastMidY = midY(touches);
        hideGlow();
      }
    }

    function onTouchMove(e) {
      e.preventDefault();
      const touches = e.touches;
      if (!gesture) return;

      if (touches.length === 1) {
        const dx = touches[0].clientX - gesture.lastX;
        const dy = touches[0].clientY - gesture.lastY;
        gesture.lastX = touches[0].clientX;
        gesture.lastY = touches[0].clientY;
        if (Math.abs(dx) + Math.abs(dy) > 2) gesture.moved = true;
        const rect = surface.getBoundingClientRect();
        showGlow(touches[0].clientX - rect.left, touches[0].clientY - rect.top);
        pendingMove.dx += dx;
        pendingMove.dy += dy;
        flushMove();
      } else if (touches.length === 2) {
        const mid = midY(touches);
        const delta = mid - (gesture.lastMidY != null ? gesture.lastMidY : mid);
        gesture.lastMidY = mid;
        if (Math.abs(delta) > 2) gesture.moved = true;
        // Dragging fingers up (delta negative) should scroll the page up.
        pendingScroll.dy += -delta * 0.6;
        flushScroll();
      }
    }

    function onTouchEnd(e) {
      e.preventDefault();
      hideGlow();
      if (e.touches.length === 0) {
        if (gesture) {
          const duration = performance.now() - gesture.startTime;
          if (!gesture.moved && duration < 300) {
            if (gesture.maxFingers === 1) {
              sendAction("left_click");
              showFeedback("LEFT CLICK");
            } else if (gesture.maxFingers === 2) {
              sendAction("right_click");
              showFeedback("RIGHT CLICK");
            }
          } else if (gesture.maxFingers === 2 && gesture.moved) {
            showFeedback("SCROLL");
          }
        }
        gesture = null;
      } else if (e.touches.length === 1 && gesture) {
        // Went from 2 fingers to 1 — reset single-finger tracking baseline
        gesture.lastX = e.touches[0].clientX;
        gesture.lastY = e.touches[0].clientY;
      }
    }

    return { init };
  })();

  /* =======================================================
     KEYBOARD
     ======================================================= */
  const Keyboard = (() => {
    let activeModifiers = new Set();

    function init() {
      const textInput = document.getElementById("type-input");
      const fastCheckbox = document.getElementById("type-fast");
      const sendBtn = document.getElementById("btn-send-text");

      sendBtn.addEventListener("click", async () => {
        const text = textInput.value;
        if (!text) { Toast.show("info", "Type something to send first."); return; }
        sendBtn.disabled = true;
        sendBtn.textContent = "Sending…";
        const res = await Api.request("/api/type", {
          method: "POST",
          body: { text, fast: !!fastCheckbox.checked }
        });
        sendBtn.disabled = false;
        sendBtn.textContent = "Send";
        if (res.ok) {
          Toast.show("success", "Text sent");
          textInput.value = "";
        }
      });

      document.querySelectorAll(".key-btn[data-mod]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const mod = btn.dataset.mod;
          if (activeModifiers.has(mod)) {
            activeModifiers.delete(mod);
            btn.classList.remove("is-active");
          } else {
            activeModifiers.add(mod);
            btn.classList.add("is-active");
          }
        });
      });

      document.querySelectorAll(".key-btn[data-key]").forEach((btn) => {
        btn.addEventListener("click", () => sendKey(btn.dataset.key));
      });

      document.querySelectorAll(".key-btn[data-hotkey]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const keys = btn.dataset.hotkey.split(",");
          Api.request("/api/hotkey", { method: "POST", body: { keys } });
          clearModifiers();
        });
      });
    }

    function sendKey(key) {
      if (activeModifiers.size > 0) {
        const keys = [...activeModifiers, key];
        Api.request("/api/hotkey", { method: "POST", body: { keys } });
        clearModifiers();
      } else {
        Api.request("/api/key", { method: "POST", body: { key, action: "press" } });
      }
    }

    function clearModifiers() {
      activeModifiers.clear();
      document.querySelectorAll(".key-btn--modifier.is-active").forEach((b) => b.classList.remove("is-active"));
    }

    return { init };
  })();

  /* =======================================================
     MEDIA
     ======================================================= */
  const Media = (() => {
    let volumeSlider, volumeValue, loaded = false;
    let nowPlayingArt, nowPlayingThumb, nowPlayingPlaceholder, nowPlayingTitle, nowPlayingArtist;
    let nowPlayingPollHandle = null;
    let panelActive = false;
    let lastThumbSignature = null; // avoid re-decoding/re-setting an unchanged image every poll

    function init() {
      volumeSlider = document.getElementById("volume-slider");
      volumeValue = document.getElementById("volume-value");

      document.getElementById("media-prev").addEventListener("click", () => sendMedia("previous"));
      document.getElementById("media-next").addEventListener("click", () => sendMedia("next"));
      document.getElementById("media-playpause").addEventListener("click", () => sendMedia("play_pause"));

      document.getElementById("media-open-spotify").addEventListener("click", () => {
        Api.runCommand("start spotify").then((r) => {
          if (r.ok) Toast.show("success", "Opening Spotify…");
          else Toast.show("info", "Couldn't launch Spotify — is it installed on the PC?");
        });
      });

      const debouncedSetVolume = Utils.debounce((level) => {
        Api.request("/api/media", { method: "POST", body: { action: "set_volume", level }, silent: true });
      }, 180);

      volumeSlider.addEventListener("input", () => {
        const v = Number(volumeSlider.value);
        setSliderFill(v);
        volumeValue.textContent = v + "%";
        debouncedSetVolume(v);
      });

      nowPlayingArt = document.getElementById("now-playing-art");
      nowPlayingThumb = document.getElementById("now-playing-thumb");
      nowPlayingPlaceholder = document.getElementById("now-playing-placeholder");
      nowPlayingTitle = document.getElementById("now-playing-title");
      nowPlayingArtist = document.getElementById("now-playing-artist");

      document.addEventListener("airgap:panel-change", (e) => {
        panelActive = e.detail.panel === "media";
        if (panelActive) {
          if (!loaded) fetchVolume();
          startNowPlayingPolling();
        } else {
          stopNowPlayingPolling();
        }
      });
    }

    function sendMedia(action) {
      Api.request("/api/media", { method: "POST", body: { action } });
    }

    function setSliderFill(v) {
      volumeSlider.style.setProperty("--fill", v + "%");
    }

    async function fetchVolume() {
      const res = await Api.request("/api/media", { method: "POST", body: { action: "get_volume" }, silent: true });
      loaded = true;
      if (res.ok && typeof res.data.volume === "number" && res.data.volume >= 0) {
        volumeSlider.value = res.data.volume;
        setSliderFill(res.data.volume);
        volumeValue.textContent = res.data.volume + "%";
      } else {
        volumeValue.textContent = "N/A";
      }
    }

    function startNowPlayingPolling() {
      stopNowPlayingPolling();
      pollNowPlayingOnce();
      nowPlayingPollHandle = setInterval(pollNowPlayingOnce, 3000);
    }
    function stopNowPlayingPolling() {
      if (nowPlayingPollHandle) { clearInterval(nowPlayingPollHandle); nowPlayingPollHandle = null; }
    }

    async function pollNowPlayingOnce() {
      const res = await Api.request("/api/media", { method: "POST", body: { action: "now_playing" }, silent: true });
      if (!res.ok) return; // leave the last known state on a transient error
      const data = res.data;
      if (!data || !data.active) {
        showNothingPlaying();
        return;
      }
      nowPlayingTitle.textContent = data.title || "Untitled";
      nowPlayingArtist.textContent = data.artist || (data.album || "");

      const sig = data.thumbnail_base64 ? data.thumbnail_base64.slice(0, 32) : null;
      if (data.thumbnail_base64) {
        if (sig !== lastThumbSignature) {
          // The receiver doesn't report the thumbnail's original format; the
          // "image/png" hint is a reasonable default and browsers decode by
          // sniffing the actual bytes anyway.
          nowPlayingThumb.src = "data:image/png;base64," + data.thumbnail_base64;
          lastThumbSignature = sig;
        }
        nowPlayingThumb.hidden = false;
        nowPlayingPlaceholder.hidden = true;
      } else {
        nowPlayingThumb.hidden = true;
        nowPlayingPlaceholder.hidden = false;
        lastThumbSignature = null;
      }
    }

    function showNothingPlaying() {
      nowPlayingTitle.textContent = "Nothing playing";
      nowPlayingArtist.textContent = "Play something on the PC to see it here";
      nowPlayingThumb.hidden = true;
      nowPlayingPlaceholder.hidden = false;
      lastThumbSignature = null;
    }

    return { init };
  })();

  /* =======================================================
     PRESENTATION (slides, laser, timer)
     ======================================================= */
  const Presentation = (() => {
    let laserSurface, laserDot, timerDisplay, timerStartBtn, timerStopBtn;
    let timerPollHandle = null;
    let panelActive = false;

    const flushLaser = Utils.rafThrottle((x, y) => {
      Api.request("/api/presentation", {
        method: "POST",
        silent: true,
        body: { action: "laser", x, y }
      });
    });

    function init() {
      document.getElementById("slide-prev").addEventListener("click", () => sendAction("prev"));
      document.getElementById("slide-next").addEventListener("click", () => sendAction("next"));
      document.getElementById("pres-start").addEventListener("click", () => sendAction("start"));
      document.getElementById("pres-end").addEventListener("click", () => sendAction("end"));
      document.getElementById("pres-black").addEventListener("click", () => sendAction("black"));
      document.getElementById("pres-white").addEventListener("click", () => sendAction("white"));

      laserSurface = document.getElementById("laser-surface");
      laserDot = document.getElementById("laser-dot");
      laserSurface.addEventListener("touchstart", onLaserTouch, { passive: false });
      laserSurface.addEventListener("touchmove", onLaserTouch, { passive: false });
      laserSurface.addEventListener("touchend", onLaserEnd, { passive: false });
      laserSurface.addEventListener("touchcancel", onLaserEnd, { passive: false });

      let mouseDown = false;
      laserSurface.addEventListener("pointerdown", (e) => {
        if (e.pointerType !== "mouse") return;
        mouseDown = true;
        moveLaser(e.clientX, e.clientY);
      });
      laserSurface.addEventListener("pointermove", (e) => {
        if (e.pointerType !== "mouse" || !mouseDown) return;
        moveLaser(e.clientX, e.clientY);
      });
      window.addEventListener("pointerup", (e) => {
        if (e.pointerType === "mouse" && mouseDown) { mouseDown = false; laserDot.hidden = true; }
      });

      timerDisplay = document.getElementById("timer-display");
      timerStartBtn = document.getElementById("timer-start");
      timerStopBtn = document.getElementById("timer-stop");

      timerStartBtn.addEventListener("click", async () => {
        const res = await Api.request("/api/presentation", { method: "POST", body: { action: "timer_start" } });
        if (res.ok) Toast.show("success", "Timer started");
      });
      timerStopBtn.addEventListener("click", async () => {
        const res = await Api.request("/api/presentation", { method: "POST", body: { action: "timer_stop" } });
        if (res.ok && typeof res.data.elapsed_seconds === "number") {
          timerDisplay.textContent = Utils.formatHMS(res.data.elapsed_seconds);
          Toast.show("info", `Timer stopped at ${Utils.formatHMS(res.data.elapsed_seconds)}`);
        }
      });

      document.addEventListener("airgap:panel-change", (e) => {
        panelActive = e.detail.panel === "slides";
        if (panelActive) startTimerPolling(); else stopTimerPolling();
      });
    }

    function sendAction(action) {
      Api.request("/api/presentation", { method: "POST", body: { action } });
    }

    function onLaserTouch(e) {
      e.preventDefault();
      const t = e.touches[0];
      if (!t) return;
      moveLaser(t.clientX, t.clientY);
    }
    function onLaserEnd(e) {
      e.preventDefault();
      laserDot.hidden = true;
    }

    function moveLaser(clientX, clientY) {
      const rect = laserSurface.getBoundingClientRect();
      const localX = Utils.clamp(clientX - rect.left, 0, rect.width);
      const localY = Utils.clamp(clientY - rect.top, 0, rect.height);
      laserDot.style.left = localX + "px";
      laserDot.style.top = localY + "px";
      laserDot.hidden = false;
      const nx = rect.width ? localX / rect.width : 0;
      const ny = rect.height ? localY / rect.height : 0;
      flushLaser(nx, ny);
    }

    function startTimerPolling() {
      stopTimerPolling();
      pollTimerOnce();
      timerPollHandle = setInterval(pollTimerOnce, 1000);
    }
    function stopTimerPolling() {
      if (timerPollHandle) { clearInterval(timerPollHandle); timerPollHandle = null; }
    }
    async function pollTimerOnce() {
      const res = await Api.request("/api/presentation", { method: "POST", body: { action: "timer_get" }, silent: true });
      if (res.ok && typeof res.data.elapsed_seconds === "number") {
        timerDisplay.textContent = Utils.formatHMS(res.data.elapsed_seconds);
      }
    }

    return { init };
  })();

  /* =======================================================
     POWER
     ======================================================= */
  const Power = (() => {
    const CONFIRM_COPY = {
      restart: { title: "Restart the PC?", body: "This will restart the remote computer immediately. Unsaved work may be lost.", label: "Restart" },
      shutdown: { title: "Shut down the PC?", body: "This will power off the remote computer. Unsaved work may be lost.", label: "Shutdown" },
      hibernate: { title: "Hibernate the PC?", body: "The remote computer will save its state and power down.", label: "Hibernate" },
      logoff: { title: "Log off?", body: "This will end the current Windows session on the remote computer.", label: "Log Off" }
    };
    const SAFE_ACTIONS = new Set(["lock", "sleep", "privacy", "wake"]);
    const SAFE_LABELS = { lock: "Lock", sleep: "Sleep", privacy: "Screen off", wake: "Wake screen" };

    function init() {
      document.querySelectorAll(".power-btn").forEach((btn) => {
        btn.addEventListener("click", () => handlePower(btn.dataset.power));
      });
      document.getElementById("power-abort").addEventListener("click", async () => {
        const res = await Api.request("/api/system", { method: "POST", body: { action: "abort" } });
        if (res.ok) Toast.show("success", "Pending shutdown cancelled");
      });
    }

    async function handlePower(action) {
      if (SAFE_ACTIONS.has(action)) {
        const res = await Api.request("/api/system", { method: "POST", body: { action } });
        if (res.ok) Toast.show("success", `${labelFor(action)} sent`);
        return;
      }
      const copy = CONFIRM_COPY[action];
      const confirmed = await Modal.confirm({ title: copy.title, body: copy.body, confirmLabel: copy.label });
      if (!confirmed) return;
      const res = await Api.request("/api/system", { method: "POST", body: { action, delay: 0 } });
      if (res.ok) Toast.show("success", `${copy.label} command sent`);
    }

    function labelFor(action) {
      return SAFE_LABELS[action] || (action.charAt(0).toUpperCase() + action.slice(1));
    }

    return { init };
  })();

  /* =======================================================
     APPS (quick launch + running apps)
     ======================================================= */
  const Apps = (() => {
    let listEl;

    function init() {
      listEl = document.getElementById("apps-list");

      // Chrome and PowerPoint aren't exposed by a dedicated controller
      // function, so these go through the existing generic run_command
      // action. Both "chrome" and "powerpnt" resolve via each app's
      // Windows "App Paths" registry entry — no hardcoded install path.
      document.getElementById("launch-chrome").addEventListener("click", () => {
        Api.runCommand("start chrome").then((r) => {
          if (r.ok) Toast.show("success", "Opening Chrome…");
          else Toast.show("info", "Couldn't launch Chrome — is it installed on the PC?");
        });
      });
      document.getElementById("launch-powerpoint").addEventListener("click", () => {
        Api.runCommand("start powerpnt").then((r) => {
          if (r.ok) Toast.show("success", "Opening PowerPoint…");
          else Toast.show("info", "Couldn't launch PowerPoint — is it installed on the PC?");
        });
      });
      document.getElementById("launch-explorer").addEventListener("click", () => {
        Api.request("/api/apps", { method: "POST", body: { action: "open_explorer" } })
          .then((r) => { if (r.ok) Toast.show("success", "File Explorer opened"); });
      });
      document.getElementById("launch-terminal").addEventListener("click", () => {
        Api.request("/api/apps", { method: "POST", body: { action: "open_terminal" } })
          .then((r) => { if (r.ok) Toast.show("success", "Terminal opened"); });
      });

      document.getElementById("win-minimize").addEventListener("click", () => windowAction("minimize", "Minimized active window"));
      document.getElementById("win-maximize").addEventListener("click", () => windowAction("maximize", "Maximized active window"));
      document.getElementById("win-taskview").addEventListener("click", () => windowAction("task_view", "Opened Task View"));
      document.getElementById("win-switch").addEventListener("click", () => windowAction("switch_window", "Switched window"));

      document.getElementById("apps-refresh").addEventListener("click", refresh);
    }

    function windowAction(action, successMessage) {
      Api.request("/api/apps", { method: "POST", body: { action } })
        .then((r) => { if (r.ok) Toast.show("success", successMessage); });
    }

    async function refresh() {
      listEl.innerHTML = `<p class="empty-state">Loading applications…</p>`;
      const res = await Api.request("/api/apps?type=running", { method: "GET" });
      if (!res.ok) {
        listEl.innerHTML = `<p class="empty-state">Unable to load running applications.</p>`;
        return;
      }
      render(res.data.apps || []);
    }

    function render(apps) {
      if (!apps.length) {
        listEl.innerHTML = `<p class="empty-state">No running applications found.</p>`;
        return;
      }
      listEl.innerHTML = "";
      // Cap the list to keep the panel usable; sort alphabetically.
      apps
        .slice()
        .sort((a, b) => (a.name || "").localeCompare(b.name || ""))
        .forEach((app) => {
          const row = document.createElement("div");
          row.className = "app-row";
          row.innerHTML = `
            <div class="app-row-info">
              <span class="app-name"></span>
              <span class="app-pid"></span>
            </div>
            <button class="app-kill-btn" type="button">Kill</button>
          `;
          row.querySelector(".app-name").textContent = app.name || "Unknown";
          row.querySelector(".app-pid").textContent = "PID " + app.pid;
          row.querySelector(".app-kill-btn").addEventListener("click", () => killApp(app.pid, app.name, row));
          listEl.appendChild(row);
        });
    }

    async function killApp(pid, name, row) {
      const confirmed = await Modal.confirm({
        title: `End ${name || "this process"}?`,
        body: `This will forcibly terminate PID ${pid}. Unsaved data in that application may be lost.`,
        confirmLabel: "Kill Process"
      });
      if (!confirmed) return;
      const res = await Api.request("/api/apps", { method: "POST", body: { action: "kill", pid } });
      if (res.ok) {
        Toast.show("success", `${name || "Process"} terminated`);
        row.remove();
        if (!listEl.children.length) listEl.innerHTML = `<p class="empty-state">No running applications found.</p>`;
      }
    }

    return { init, refresh };
  })();

  /* =======================================================
     CLIPBOARD
     ======================================================= */
  const Clipboard = (() => {
    function init() {
      const textarea = document.getElementById("clipboard-text");
      document.getElementById("clipboard-pull").addEventListener("click", async () => {
        const res = await Api.request("/api/clipboard", { method: "GET" });
        if (res.ok) {
          textarea.value = res.data.text || "";
          Toast.show("success", "Clipboard pulled from PC");
        }
      });
      document.getElementById("clipboard-push").addEventListener("click", async () => {
        const res = await Api.request("/api/clipboard", { method: "POST", body: { text: textarea.value } });
        if (res.ok) Toast.show("success", "Clipboard pushed to PC");
      });
    }
    return { init };
  })();

  /* =======================================================
     DEVICE INFO (More panel)
     ======================================================= */
  const DeviceInfo = (() => {
    let els = {};
    function init() {
      els = {
        connection: document.getElementById("info-connection"),
        hostname: document.getElementById("info-hostname"),
        ip: document.getElementById("info-ip"),
        latency: document.getElementById("info-latency"),
        cpu: document.getElementById("info-cpu"),
        ram: document.getElementById("info-ram"),
        battery: document.getElementById("info-battery")
      };
    }
    function update(info, rtt) {
      if (!els.connection) return;
      if (!info) {
        els.connection.textContent = "Offline";
        return;
      }
      els.connection.textContent = "Connected";
      els.hostname.textContent = info.hostname || "--";
      els.ip.textContent = info.ip || "--";
      els.latency.textContent = rtt != null ? `${rtt}ms` : "--";
      els.cpu.textContent = typeof info.cpu_percent === "number" ? `${info.cpu_percent.toFixed(0)}%` : "--";
      els.ram.textContent = typeof info.ram_percent === "number"
        ? `${info.ram_percent.toFixed(0)}% (${info.ram_used_mb}/${info.ram_total_mb} MB)`
        : "--";
      els.battery.textContent = typeof info.battery_percent === "number"
        ? `${info.battery_percent}%${info.battery_plugged ? " (plugged in)" : ""}`
        : "N/A";
    }
    return { init, update };
  })();

  /* =======================================================
     FULLSCREEN
     ======================================================= */
  const Fullscreen = (() => {
    let btn, nudge, nudgeDismiss;

    function init() {
      btn = document.getElementById("btn-fullscreen");
      nudge = document.getElementById("fs-nudge");
      nudgeDismiss = document.getElementById("fs-nudge-dismiss");

      btn.addEventListener("click", toggle);
      document.addEventListener("fullscreenchange", syncState);
      document.addEventListener("webkitfullscreenchange", syncState);

      nudgeDismiss.addEventListener("click", dismissNudge);

      let dismissed = false;
      try { dismissed = localStorage.getItem("airgap_fs_nudge_dismissed") === "1"; } catch (e) { /* storage unavailable */ }
      if (!dismissed && !document.fullscreenElement) {
        setTimeout(() => { if (nudge) nudge.hidden = false; }, 1400);
      }
      syncState();
    }

    function dismissNudge() {
      if (nudge) nudge.hidden = true;
      try { localStorage.setItem("airgap_fs_nudge_dismissed", "1"); } catch (e) { /* ignore */ }
    }

    function isFullscreen() {
      return !!(document.fullscreenElement || document.webkitFullscreenElement);
    }

    async function toggle() {
      dismissNudge();
      try {
        if (!isFullscreen()) {
          const el = document.documentElement;
          const request = el.requestFullscreen || el.webkitRequestFullscreen;
          if (!request) { Toast.show("info", "Fullscreen isn't supported in this browser."); return; }
          await request.call(el);
          // AirGap's layout is portrait-only. Where the Orientation Lock API
          // is available (mainly installed/standalone PWAs on Android), we
          // lock to it directly; everywhere else the CSS-only
          // .orientation-lock-notice overlay covers the gap.
          if (screen.orientation && screen.orientation.lock) {
            screen.orientation.lock("portrait").catch(() => {});
          }
        } else {
          const exit = document.exitFullscreen || document.webkitExitFullscreen;
          if (exit) await exit.call(document);
          if (screen.orientation && screen.orientation.unlock) {
            try { screen.orientation.unlock(); } catch (e) { /* ignore */ }
          }
        }
      } catch (err) {
        Toast.show("info", "Fullscreen requires a direct tap and may be restricted by your browser.");
      }
    }

    function syncState() {
      const active = isFullscreen();
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-label", active ? "Exit fullscreen" : "Enter fullscreen");
      btn.title = active ? "Exit fullscreen" : "Fullscreen";
      document.body.classList.toggle("is-fullscreen", active);
    }

    return { init };
  })();

  /* =======================================================
     INFO MENU (Help / About / Buy Me a Coffee)
     ======================================================= */
  const InfoMenu = (() => {
    let wrap, btn, menu;

    function init() {
      wrap = document.getElementById("info-menu-wrap");
      btn = document.getElementById("btn-info");
      menu = document.getElementById("info-menu");

      btn.addEventListener("click", (e) => { e.stopPropagation(); toggle(); });
      document.addEventListener("click", (e) => { if (!wrap.contains(e.target)) close(); });
      document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
      menu.querySelectorAll(".info-menu-item").forEach((item) => item.addEventListener("click", close));
    }

    function toggle() { menu.classList.contains("is-open") ? close() : open(); }
    function open() {
      menu.hidden = false;
      requestAnimationFrame(() => menu.classList.add("is-open"));
      btn.setAttribute("aria-expanded", "true");
    }
    function close() {
      menu.classList.remove("is-open");
      btn.setAttribute("aria-expanded", "false");
      setTimeout(() => { if (!menu.classList.contains("is-open")) menu.hidden = true; }, 200);
    }

    return { init };
  })();

  /* =======================================================
     GLOBAL SAFETY NETS
     ======================================================= */
  window.addEventListener("unhandledrejection", (e) => {
    console.error("Unhandled promise rejection:", e.reason);
  });
  window.addEventListener("error", (e) => {
    console.error("Uncaught error:", e.error || e.message);
  });

  // Prevent double-tap-to-zoom and accidental pinch zoom on control surfaces
  // without disabling normal scrolling/selection elsewhere in the app.
  document.addEventListener("dblclick", (e) => {
    if (e.target.closest(".trackpad-surface, .laser-surface, .key-btn, .power-btn, .media-btn")) {
      e.preventDefault();
    }
  });

  /* =======================================================
     INIT
     ======================================================= */
  document.addEventListener("DOMContentLoaded", () => {
    Toast.init();
    Modal.init();
    DeviceInfo.init();
    Navigation.init();
    Trackpad.init();
    Keyboard.init();
    Media.init();
    Presentation.init();
    Power.init();
    Apps.init();
    Clipboard.init();
    Fullscreen.init();
    InfoMenu.init();
    Connection.init();
  });
})();

/* Amplychat chat widget: the chat inside the frame (GR-28). Plain JavaScript, no libraries.
   It opens a session (the server checks the widget id and the site), keeps a visitor key in this
   frame's own storage, sends messages and long-polls for replies. The visitor's session key lives
   in memory only. */
(function () {
  "use strict";

  var body = document.body;
  var WIDGET = body.getAttribute("data-widget") || "";
  var HOST = body.getAttribute("data-host") || "";
  var BRAND_URL = body.getAttribute("data-brand-url") || "https://amplychat.com";
  var root = document.getElementById("root");
  var STORE_KEY = "sh_visitor_" + WIDGET;

  var st = {
    bearer: null,
    config: null,
    messages: [],
    pending: [],
    version: null,
    open: false,
    unread: 0,
    emailDismissed: false,
    sending: false,
    polling: false,
    abort: null,
  };
  var ui = {};

  /* ---- small helpers */

  function el(tag, props, children) {
    var node = document.createElement(tag);
    Object.keys(props || {}).forEach(function (name) {
      if (name === "text") node.textContent = props[name];
      else if (name === "class") node.className = props[name];
      else node.setAttribute(name, props[name]);
    });
    (children || []).forEach(function (child) {
      if (child) node.appendChild(child);
    });
    return node;
  }

  function icon(paths, extra) {
    var ns = "http://www.w3.org/2000/svg";
    var svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    paths.forEach(function (d) {
      var path = document.createElementNS(ns, "path");
      path.setAttribute("d", d);
      svg.appendChild(path);
    });
    if (extra) svg.setAttribute("class", extra);
    return svg;
  }

  function uuid() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    var bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    var hex = Array.prototype.map
      .call(bytes, function (b) {
        return (b + 256).toString(16).slice(1);
      })
      .join("");
    return [hex.slice(0, 8), hex.slice(8, 12), hex.slice(12, 16), hex.slice(16, 20), hex.slice(20)].join("-");
  }

  function readKey() {
    try {
      return localStorage.getItem(STORE_KEY);
    } catch (e) {
      return null;
    }
  }

  function writeKey(value) {
    try {
      localStorage.setItem(STORE_KEY, value);
    } catch (e) {
      /* storage is blocked: the visitor starts fresh on the next page */
    }
  }

  function tell(message) {
    message.socialHood = 1;
    window.parent.postMessage(message, "*");
  }

  function api(method, path, payload, signal) {
    var headers = { Accept: "application/json" };
    if (payload !== undefined) headers["Content-Type"] = "application/json";
    if (st.bearer && path.indexOf("/session") === -1) headers.Authorization = "Bearer " + st.bearer;
    return fetch(path, {
      method: method,
      headers: headers,
      body: payload !== undefined ? JSON.stringify(payload) : undefined,
      credentials: "omit",
      cache: "no-store",
      signal: signal,
    }).then(function (res) {
      return res
        .json()
        .catch(function () {
          return {};
        })
        .then(function (data) {
          if (res.ok) return data;
          var error = new Error(data.detail || "Something went wrong. Try again.");
          error.status = res.status;
          error.data = data;
          throw error;
        });
    });
  }

  /* ---- colours */

  function channel(value) {
    var c = value / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  }

  function onAccent(hex) {
    var r = parseInt(hex.slice(1, 3), 16);
    var g = parseInt(hex.slice(3, 5), 16);
    var b = parseInt(hex.slice(5, 7), 16);
    var lum = 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
    return lum > 0.35 ? "#111318" : "#ffffff";
  }

  /* ---- session and polling */

  function openSession() {
    return api("POST", "/v1/widget/session", {
      widget_id: WIDGET,
      host: HOST,
      visitor_key: readKey() || null,
    }).then(function (data) {
      st.bearer = data.session_key;
      writeKey(data.visitor_key);
      st.config = data.config;
      st.messages = data.messages;
      st.version = data.version;
    });
  }

  function merge(data) {
    var before = st.messages.filter(function (m) {
      return m.author !== "visitor";
    }).length;
    st.messages = data.messages;
    st.version = data.version;
    var after = st.messages.filter(function (m) {
      return m.author !== "visitor";
    }).length;
    if (!st.open && after > before) st.unread += after - before;
    renderLog();
    renderBadge();
    renderCard();
  }

  function startPolling() {
    if (st.polling) return;
    st.polling = true;
    var failures = 0;

    function again(delay) {
      setTimeout(next, delay);
    }

    function next() {
      if (!st.polling) return;
      if (document.hidden) {
        st.polling = false; /* restarted when the tab shows again */
        return;
      }
      st.abort = typeof AbortController === "function" ? new AbortController() : null;
      api(
        "GET",
        "/v1/widget/messages?wait=20&version=" + encodeURIComponent(st.version || ""),
        undefined,
        st.abort ? st.abort.signal : undefined
      )
        .then(function (data) {
          failures = 0;
          if (data.version !== st.version) merge(data);
          again(0);
        })
        .catch(function (error) {
          if (error && error.name === "AbortError") return;
          if (error && error.status === 401) {
            openSession().then(function () {
              again(0);
            }, function () {
              again(15000);
            });
            return;
          }
          if (error && (error.status === 403 || error.status === 404)) {
            st.polling = false;
            tell({ type: "hide" });
            return;
          }
          failures += 1;
          again(Math.min(30000, 2000 * Math.pow(2, failures - 1)));
        });
    }
    next();
  }

  function stopPolling() {
    st.polling = false;
    if (st.abort) st.abort.abort();
  }

  document.addEventListener("visibilitychange", function () {
    if (!st.bearer) return;
    if (document.hidden) {
      stopPolling();
    } else if (st.messages.length) {
      startPolling();
    }
  });

  /* ---- rendering */

  var WHO = { visitor: "You", team: "Team", assistant: "Assistant" };

  function bubble(author, text, pending) {
    var mine = author === "visitor";
    return el("li", { class: "msg " + (mine ? "me" : "them") + (pending ? " pending" : "") }, [
      el("span", { class: "sr", text: WHO[author] + ": " }),
      document.createTextNode(text),
    ]);
  }

  function renderLog() {
    var log = ui.log;
    var nearBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 80;
    log.textContent = "";
    log.appendChild(bubble("team", st.config.greeting, false));
    var last = "team";
    st.messages.forEach(function (m) {
      if (m.author === "assistant" && last !== "assistant") {
        log.appendChild(el("li", { class: "tag", text: "Assistant" }));
      }
      log.appendChild(bubble(m.author, m.text, false));
      last = m.author;
    });
    st.pending.forEach(function (p) {
      log.appendChild(bubble("visitor", p.text, true));
    });
    if (nearBottom || st.pending.length) log.scrollTop = log.scrollHeight;
  }

  function renderBadge() {
    var count = st.unread;
    ui.badge.hidden = count === 0;
    ui.badge.textContent = count > 9 ? "9+" : String(count);
    ui.launcher.setAttribute(
      "aria-label",
      count ? "Open chat, " + count + " new " + (count === 1 ? "message" : "messages") : "Open chat"
    );
  }

  function wantsEmail() {
    var cfg = st.config;
    if (cfg.email_known || cfg.email_capture === "off") return false;
    if (cfg.email_capture === "required") return true;
    var wrote = st.messages.some(function (m) {
      return m.author === "visitor";
    });
    return wrote && !st.emailDismissed;
  }

  function renderCard() {
    var show = wantsEmail();
    ui.card.hidden = !show;
    /* A required email replaces the composer until it is given. */
    ui.composer.hidden = show && st.config.email_capture === "required";
    ui.skip.hidden = st.config.email_capture === "required";
  }

  function setOpen(open) {
    st.open = open;
    ui.panel.hidden = !open;
    ui.launcher.hidden = open;
    ui.launcher.setAttribute("aria-expanded", open ? "true" : "false");
    tell({ type: "layout", open: open, side: st.config.position });
    if (open) {
      st.unread = 0;
      renderBadge();
      ui.log.scrollTop = ui.log.scrollHeight;
      (ui.card.hidden ? ui.input : ui.email).focus();
    } else {
      ui.launcher.focus();
    }
  }

  function focusables() {
    return Array.prototype.filter.call(
      ui.panel.querySelectorAll("a[href], button, input, textarea"),
      function (node) {
        return !node.disabled && !node.closest("[hidden]");
      }
    );
  }

  function trapFocus(event) {
    if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
      return;
    }
    if (event.key !== "Tab") return;
    var items = focusables();
    if (!items.length) return;
    var first = items[0];
    var last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function showError(text) {
    ui.error.textContent = text || "";
    ui.error.hidden = !text;
  }

  /* ---- actions */

  function removePending(id) {
    st.pending = st.pending.filter(function (p) {
      return p.id !== id;
    });
  }

  function send(text, retried) {
    var id = uuid();
    st.pending.push({ id: id, text: text });
    showError("");
    renderLog();
    ui.send.disabled = true;
    api("POST", "/v1/widget/messages", { text: text, client_id: id })
      .then(function (data) {
        removePending(id);
        st.messages = data.messages;
        st.version = data.version;
        renderLog();
        renderCard();
        startPolling();
      })
      .catch(function (error) {
        removePending(id);
        if (error.status === 401 && !retried) {
          return openSession().then(function () {
            removePending(id);
            send(text, true);
          }, function () {
            ui.input.value = text;
            showError("Your chat session ended. Reload the page to continue.");
            renderLog();
          });
        }
        ui.input.value = text;
        resize();
        showError(error.message);
        renderLog();
      })
      .then(function () {
        ui.send.disabled = false;
      });
  }

  function resize() {
    ui.input.style.height = "auto";
    ui.input.style.height = Math.min(ui.input.scrollHeight, 120) + "px";
  }

  function submitMessage(event) {
    if (event) event.preventDefault();
    var text = ui.input.value.trim();
    if (!text || ui.send.disabled) return;
    ui.input.value = "";
    resize();
    send(text, false);
  }

  function submitEmail(event) {
    event.preventDefault();
    var value = ui.email.value.trim();
    if (!value) return;
    ui.save.disabled = true;
    api("POST", "/v1/widget/email", { email: value, marketing_consent: !!ui.consent.checked })
      .then(function () {
        st.config.email_known = true;
        showError("");
        renderCard();
        ui.input.focus();
      })
      .catch(function (error) {
        showError(error.message);
        ui.email.focus();
      })
      .then(function () {
        ui.save.disabled = false;
      });
  }

  /* ---- build */

  function build() {
    var cfg = st.config;
    body.classList.add(cfg.position === "left" ? "left" : "right");
    document.documentElement.style.setProperty("--accent", cfg.accent_color);
    document.documentElement.style.setProperty("--on-accent", onAccent(cfg.accent_color));
    document.title = cfg.title;

    ui.badge = el("span", { class: "badge", "aria-hidden": "true" });
    ui.badge.hidden = true;
    ui.launcher = el(
      "button",
      { type: "button", class: "launcher", "aria-label": "Open chat", "aria-expanded": "false", "aria-controls": "panel" },
      [icon(["M21 11.5a8.4 8.4 0 0 1-9 8.4 9 9 0 0 1-3.6-.8L3 21l1.9-5.4A8.4 8.4 0 1 1 21 11.5z"]), ui.badge]
    );
    ui.launcher.addEventListener("click", function () {
      setOpen(true);
    });

    var close = el("button", { type: "button", class: "close", "aria-label": "Close chat" }, [
      icon(["M6 6l12 12", "M18 6L6 18"]),
    ]);
    close.addEventListener("click", function () {
      setOpen(false);
    });

    ui.log = el("ol", { class: "log", role: "log", "aria-live": "polite", "aria-label": "Conversation" });

    ui.email = el("input", {
      class: "field",
      type: "email",
      name: "email",
      autocomplete: "email",
      "aria-label": "Your email address",
      placeholder: "you@example.com",
      maxlength: "254",
      required: "required",
    });
    ui.save = el("button", { type: "submit", class: "btn", text: "Save" });
    ui.skip = el("button", { type: "button", class: "btn quiet", text: "Not now" });
    ui.skip.addEventListener("click", function () {
      st.emailDismissed = true;
      renderCard();
    });
    ui.consent = el("input", { type: "checkbox", name: "marketing" });
    var consentRow = el("label", { class: "check" }, [ui.consent, el("span", { text: cfg.marketing_consent_text })]);
    consentRow.hidden = !cfg.marketing_consent_enabled;
    ui.card = el("form", { class: "card", novalidate: "novalidate", "aria-label": "Your email address" }, [
      el("p", { text: cfg.email_prompt }),
      el("div", { class: "row" }, [ui.email, ui.save]),
      consentRow,
      el("div", { class: "row" }, [ui.skip]),
    ]);
    ui.card.hidden = true;
    ui.card.addEventListener("submit", submitEmail);

    ui.error = el("p", { class: "error", role: "alert" });
    ui.error.hidden = true;

    ui.input = el("textarea", {
      rows: "1",
      "aria-label": "Your message",
      placeholder: "Write a message",
      maxlength: "1000",
    });
    ui.input.addEventListener("input", resize);
    ui.input.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey && !event.isComposing) submitMessage(event);
    });
    ui.send = el("button", { type: "submit", class: "btn", text: "Send" });
    ui.composer = el("form", { class: "composer" }, [ui.input, ui.send]);
    ui.composer.addEventListener("submit", submitMessage);

    var children = [
      el("header", {}, [el("h1", { text: cfg.title }), close]),
      ui.log,
      ui.card,
      ui.error,
      ui.composer,
    ];
    if (cfg.show_branding) {
      children.push(
        el("footer", {}, [
          el("a", { href: BRAND_URL, target: "_blank", rel: "noopener noreferrer", text: "Powered by Amplychat" }),
        ])
      );
    }
    ui.panel = el("section", { class: "panel", id: "panel", role: "dialog", "aria-label": cfg.title }, children);
    ui.panel.hidden = true;
    ui.panel.addEventListener("keydown", trapFocus);

    root.appendChild(ui.launcher);
    root.appendChild(ui.panel);
    renderLog();
    renderCard();
    renderBadge();
  }

  window.addEventListener("message", function (event) {
    if (event.source !== window.parent) return;
    var data = event.data;
    if (data && data.socialHood === 1 && data.type === "mode") {
      body.classList.toggle("full", !!data.full);
    }
  });

  if (!WIDGET || !HOST) {
    tell({ type: "hide" });
    return;
  }
  openSession().then(
    function () {
      build();
      tell({ type: "layout", open: false, side: st.config.position });
      if (st.messages.length) startPolling();
    },
    function () {
      tell({ type: "hide" });
    }
  );
})();

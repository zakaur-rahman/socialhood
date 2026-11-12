/* Amplychat chat widget: the embed script (GR-28). It adds one iframe from this server and sizes
   it as the chat opens and closes; the chat itself lives inside the frame, so the host page's CSS
   and scripts can't touch it and it can't touch theirs. Nothing is stored on the host page. */
(function () {
  "use strict";
  var script = document.currentScript;
  if (!script || window.__socialHoodWidget) return;
  var id = script.getAttribute("data-widget") || script.getAttribute("data-workspace");
  if (!id) return;
  var base;
  try {
    base = new URL(script.src, location.href).origin;
  } catch (e) {
    return;
  }
  window.__socialHoodWidget = true;

  var side = "right";
  var open = false;
  var frame;

  function sendMode(full) {
    try {
      frame.contentWindow.postMessage({ socialHood: 1, type: "mode", full: full }, base);
    } catch (e) {
      /* the frame is not ready; it asks again when it loads */
    }
  }

  function layout() {
    var s = frame.style;
    var small = window.innerWidth < 520;
    s.left = s.right = s.top = s.bottom = "auto";
    sendMode(open && small);
    if (open && small) {
      s.left = s.top = "0";
      s.width = "100%";
      s.height = "100%";
      return;
    }
    s[side] = "12px";
    s.bottom = "12px";
    if (open) {
      s.width = "400px";
      s.height = "min(680px, calc(100% - 24px))";
      s.maxWidth = "calc(100% - 24px)";
    } else {
      s.width = "84px";
      s.height = "84px";
      s.maxWidth = "none";
    }
  }

  function onMessage(event) {
    if (event.origin !== base || event.source !== frame.contentWindow) return;
    var data = event.data;
    if (!data || data.socialHood !== 1) return;
    if (data.type === "hide") {
      frame.style.display = "none";
      return;
    }
    if (data.type === "layout") {
      open = !!data.open;
      side = data.side === "left" ? "left" : "right";
      frame.style.display = "block";
      layout();
    }
  }

  function mount() {
    frame = document.createElement("iframe");
    frame.title = "Chat";
    frame.setAttribute("allow", "");
    frame.setAttribute("referrerpolicy", "no-referrer");
    frame.src =
      base + "/widget/frame?w=" + encodeURIComponent(id) + "&h=" + encodeURIComponent(location.hostname);
    var s = frame.style;
    s.position = "fixed";
    s.border = "0";
    s.margin = "0";
    s.padding = "0";
    s.background = "transparent";
    s.colorScheme = "normal";
    s.zIndex = "2147483000";
    s.display = "none";
    layout();
    frame.addEventListener("load", layout);
    window.addEventListener("message", onMessage);
    window.addEventListener("resize", layout);
    document.body.appendChild(frame);
  }

  if (document.body) mount();
  else document.addEventListener("DOMContentLoaded", mount);
})();

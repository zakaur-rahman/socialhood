/**
 * The landing page's scenes in motion (C-155, C-157), loaded by LandingMotion once the page has
 * settled. Plain DOM over the server-rendered markup: nothing here re-renders React, and every move
 * is a transform, an opacity or a class, so no layout box moves (CLS stays 0). Layout is read once
 * (when a scene nears the viewport, on a debounced resize, when fonts arrive) and frames only write.
 *
 * - Hero (C-157 motion): the server drew the scattered pile and site.css holds the animations that sort
 *   it. Where the browser has scroll timelines, CSS alone ties them to the scroll; on a wide screen
 *   without, this sets their time from the scroll (one rAF while the hero is on screen); on phones
 *   and tablets it plays them once (1.2 s) when the inbox is on screen, with a pause control.
 * - Cards: where the browser has no scroll timelines, the cards that start off screen rise in as they
 *   arrive (an IntersectionObserver; site.css does it with `view()` elsewhere).
 * - How it works: where its CSS pins the frame (wide screens), the scroll plays it: a scan over the
 *   knowledge, wires to the cited words, the draft writing itself, the hand-off and the gap. Where it
 *   doesn't pin (phones, tablets), it plays once when on screen, with a pause control.
 * - Automations: one round of comments arrives while the scene is on screen (pause control), then
 *   it holds; the keyword field changes what the automation listens for.
 * - Modes: the Off, Suggest and Auto switch.
 * - Your AI assistant (C-168): the example chat plays once as it scrolls in from below (aiApps).
 * - A day in your inbox (C-175): one story loops while on screen, with a pause control (productDemo).
 *
 * With `prefers-reduced-motion: reduce` only the controls work (the demo's steps too) and the scenes stay still.
 */
import { bindMotionControl, type MotionControl } from "@/components/site/motion-control";

import { COMMENT_STREAM, DEFAULT_KEYWORD, DM_SCRIPT, MODES, type ModeKey } from "./data";

const clamp = (v: number, a: number, b: number) => Math.max(a, Math.min(b, v));
const seg = (p: number, a: number, b: number) => clamp((p - a) / (b - a), 0, 1);

/** The site's one-shot ceiling (globals.css, --motion-site-entrance): the hero's whole sort. */
const ENTRANCE_MS = 1200;
/** The share of the pinned scroll the sort takes (site.css: the last row lands at 84%, then it holds). */
const SCRUB_SPAN = 0.84;
/** The hero's play on a phone waits this long after the load event (and then for an idle moment). */
const SORT_AFTER_LOAD_MS = 1500;
/** How long How it works plays by itself where it doesn't pin. */
const DECIDE_PLAY_MS = 9000;

type Cleanup = () => void;

/** Starts every scene under `root`; returns a function that stops them all. */
export function startLandingMotion(root: ParentNode = document): Cleanup {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const cleanups: Cleanup[] = [];
  cleanups.push(modes(root, reduce));
  cleanups.push(comments(root, reduce));
  cleanups.push(productDemo(root, reduce));
  if (!reduce) {
    cleanups.push(aiApps(root));
    cleanups.push(hero(root));
    cleanups.push(decide(root));
    cleanups.push(reveals(root));
  }
  return () => cleanups.forEach((stop) => stop());
}

/** Runs `fn` at most once a frame (resize). */
function perFrame(fn: () => void) {
  let frame = 0;
  const run = () => {
    if (!frame)
      frame = requestAnimationFrame(() => {
        frame = 0;
        fn();
      });
  };
  return Object.assign(run, { cancel: () => frame && cancelAnimationFrame(frame) });
}

// ---------------------------------------------------------------- hero

/** Resolves about 1.5 s after the load event, at an idle moment (C-157 performance). */
function afterLoad(then: () => void): Cleanup {
  let idle = 0;
  const loadEnd = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
  const wait = Math.max(0, (loadEnd?.loadEventEnd || performance.now()) + SORT_AFTER_LOAD_MS - performance.now());
  const timer = window.setTimeout(() => {
    if (typeof window.requestIdleCallback === "function") idle = window.requestIdleCallback(then, { timeout: 500 });
    else then();
  }, wait);
  return () => {
    window.clearTimeout(timer);
    if (idle) window.cancelIdleCallback(idle);
  };
}

/**
 * The hero's scatter-to-sort. site.css owns the animations and says which driver applies
 * (`--hero-mode` on .hero): `native` (CSS scroll timeline, nothing to do here), `scrub` (set the
 * animations' time from the scroll), `play` (run them once), or nothing (no motion: sorted, still).
 */
function hero(root: ParentNode): Cleanup {
  const section = root.querySelector<HTMLElement>(".hero");
  const scrub = section?.querySelector<HTMLElement>("[data-hero-scrub]");
  const sticky = section?.querySelector<HTMLElement>(".hero-sticky");
  const stage = section?.querySelector<HTMLElement>("[data-stage]");
  const inbox = stage?.querySelector<HTMLElement>("[data-inbox]");
  if (!section || !scrub || !sticky || !stage || !inbox) return () => {};
  const heroEl = section;
  const box = scrub;
  const pin = sticky;
  const scene = stage;

  let mode = "";
  let disposed = false;
  let played = false;
  let animations: Animation[] = [];
  const cleanups: Cleanup[] = [];

  // ---- scrub (no scroll timelines): geometry is read on start and on resize; a frame reads scrollY only.
  const geo = { start: 0, length: 1 };
  let visible = false;
  let frame = 0;
  const measure = () => {
    const rect = box.getBoundingClientRect();
    const top = parseFloat(getComputedStyle(pin).top) || 0;
    geo.start = rect.top + window.scrollY - top;
    geo.length = Math.max(1, box.offsetHeight - pin.offsetHeight);
    animations = scene.getAnimations({ subtree: true });
  };
  const draw = () => {
    frame = 0;
    if (disposed || mode !== "scrub") return;
    const p = clamp((window.scrollY - geo.start) / geo.length, 0, 1);
    const time = Math.min(1, p / SCRUB_SPAN) * ENTRANCE_MS;
    for (const animation of animations) animation.currentTime = time;
  };
  const tick = () => {
    if (!frame && visible) frame = requestAnimationFrame(draw);
  };
  const seen = new IntersectionObserver(
    (entries) => {
      visible = entries.some((entry) => entry.isIntersecting);
      tick();
    },
    { rootMargin: "100px" },
  );
  window.addEventListener("scroll", tick, { passive: true });

  // ---- play (phones, tablets): once, when the inbox is on screen, after the page has settled.
  let control: MotionControl | null = null;
  let armed = false;
  const play = () => {
    if (played || disposed) return;
    played = true;
    control = bindMotionControl(scene);
    scene.dataset.play = "";
    const running = scene.getAnimations({ subtree: true });
    void Promise.all(running.map((animation) => animation.finished))
      .then(() => {
        control?.destroy();
        control = null;
      })
      .catch(() => {});
  };
  const arm = () => {
    if (armed || played) return;
    armed = true;
    cleanups.push(
      afterLoad(() => {
        if (disposed) return;
        const onScreen = new IntersectionObserver(
          (entries) => {
            if (!entries.some((entry) => entry.isIntersecting) || mode !== "play") return;
            onScreen.disconnect();
            play();
          },
          { threshold: 0.35 },
        );
        onScreen.observe(inbox);
        cleanups.push(() => onScreen.disconnect());
      }),
    );
  };

  // ---- which driver: CSS's call, read again after a resize.
  const setMode = () => {
    mode = getComputedStyle(heroEl).getPropertyValue("--hero-mode").trim();
    seen.disconnect();
    if (mode === "scrub") {
      measure();
      seen.observe(box);
    } else if (mode === "play") arm();
  };
  const relayout = perFrame(setMode);
  window.addEventListener("resize", relayout);
  void document.fonts?.ready.then(() => !disposed && relayout());
  setMode();

  return () => {
    disposed = true;
    if (frame) cancelAnimationFrame(frame);
    relayout.cancel();
    seen.disconnect();
    window.removeEventListener("scroll", tick);
    window.removeEventListener("resize", relayout);
    cleanups.forEach((stop) => stop());
    control?.destroy();
  };
}

// ---------------------------------------------------------------- cards rising in (no scroll timelines)

const REVEAL = ".feat-lead, .fcard, .crow, .pay, .aud-card, .spec-row, .steps > li, .mh-pt";

/**
 * Where CSS has no `view()` timeline: a card that starts off screen is hidden (`data-rv=""`) when the
 * observer first reports it, and rises in (`data-rv="in"`, site.css's transitions) as it arrives. A
 * card already on screen is never touched, so nothing on screen blinks, and with no script every card
 * simply shows.
 */
function reveals(root: ParentNode): Cleanup {
  if (typeof CSS !== "undefined" && CSS.supports("animation-timeline: view()")) return () => {};
  const cards = [...root.querySelectorAll<HTMLElement>(REVEAL)];
  if (!cards.length) return () => {};
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        const card = entry.target as HTMLElement;
        if (entry.isIntersecting) {
          if (card.dataset.rv === "") card.dataset.rv = "in";
          observer.unobserve(card);
        } else if (card.dataset.rv === undefined) card.dataset.rv = "";
      }
    },
    { rootMargin: "0px" },
  );
  cards.forEach((card) => observer.observe(card));
  return () => {
    observer.disconnect();
    cards.forEach((card) => delete card.dataset.rv);
  };
}

// ---------------------------------------------------------------- how it works

function decide(root: ParentNode): Cleanup {
  const section = root.querySelector<HTMLElement>("[data-decide]");
  const scrub = section?.querySelector<HTMLElement>("[data-decide-scrub]");
  const sticky = section?.querySelector<HTMLElement>("[data-decide-sticky]");
  if (!section || !scrub || !sticky) return () => {};
  const scene = decideScene(section);

  // Whether the frame pins is CSS's call (site.css, the site-md breakpoint and reduced motion): read
  // it from the frame, never restate the breakpoint here (LP-4.6). The nav offset is the frame's own top.
  let pinned = false;
  let pinTop = 0;
  let visible = false;
  let disposed = false;
  let control: MotionControl | null = null;
  let unsubscribe: (() => void) | null = null;
  const auto = { progress: 0, last: 0, done: false };

  const scrubProgress = () => {
    const r = scrub.getBoundingClientRect();
    const total = r.height - sticky.offsetHeight;
    return total <= 0 ? 0 : clamp((pinTop - r.top) / total, 0, 1);
  };

  let frame = 0;
  function draw(now: number) {
    frame = 0;
    if (disposed || !visible) return;
    if (pinned) {
      scene.render(scrubProgress());
      return;
    }
    if (auto.done || control?.paused) {
      auto.last = 0;
      return;
    }
    if (auto.last) auto.progress = Math.min(1, auto.progress + (now - auto.last) / DECIDE_PLAY_MS);
    auto.last = now;
    scene.render(auto.progress);
    if (auto.progress >= 1) {
      auto.done = true;
      unsubscribe?.();
      control?.destroy();
      return;
    }
    tick();
  }
  function tick() {
    if (!frame) frame = requestAnimationFrame(draw);
  }

  const setMode = () => {
    const style = getComputedStyle(sticky);
    pinned = style.position === "sticky";
    pinTop = parseFloat(style.top) || 0;
    if (pinned) {
      unsubscribe?.();
      unsubscribe = null;
      control?.destroy();
      control = null;
    } else if (!control && !auto.done) {
      control = bindMotionControl(section);
      unsubscribe = control.subscribe((paused) => {
        auto.last = 0;
        if (!paused) tick();
      });
    }
  };
  // The scene's geometry is read only once it nears the viewport (and again after a resize there):
  // until then the band is skipped by the browser (site.css, content-visibility), and reading it at
  // start-up would force its layout for nothing (C-157 performance).
  let measured = false;
  const measure = () => {
    scene.layout();
    measured = true;
  };
  const relayout = perFrame(() => {
    setMode();
    if (!visible) {
      measured = false;
      return;
    }
    measure();
    if (!pinned) scene.render(auto.progress, true);
    tick();
  });

  const observer = new IntersectionObserver(
    (entries) => {
      visible = entries.some((entry) => entry.isIntersecting);
      auto.last = 0;
      if (!visible) return;
      if (!measured) measure();
      tick();
    },
    { rootMargin: "100px" },
  );
  observer.observe(scrub);
  const onScroll = () => {
    if (pinned && visible) tick();
  };
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", relayout);
  void document.fonts?.ready.then(() => !disposed && relayout());
  setMode();

  return () => {
    disposed = true;
    if (frame) cancelAnimationFrame(frame);
    relayout.cancel();
    observer.disconnect();
    window.removeEventListener("scroll", onScroll);
    window.removeEventListener("resize", relayout);
    unsubscribe?.();
    control?.destroy();
    scene.dispose();
  };
}

function decideScene(section: HTMLElement) {
  const q = <T extends Element = HTMLElement>(selector: string) => section.querySelector(selector) as T;
  const kb = q("[data-kb]");
  const scan = q("[data-scan]");
  const wires = q<SVGSVGElement>("[data-wires]");
  const grid = q("[data-dgrid]");
  const lines = [...kb.querySelectorAll<HTMLElement>(".line")];
  const text = q("[data-dtext]");
  const draft = q("[data-draft]");
  const parts = { read: q("[data-read]"), cites: q("[data-cites]"), q2: q("[data-q2]"), hand: q("[data-hand]"), gap: q("[data-gap]") };
  const state = q("[data-dstate]");
  const steps = [...section.querySelectorAll<HTMLElement>("[data-dsteps] li")];

  // The draft writes itself a word at a time: each word in its own span.
  const walker = document.createTreeWalker(text, NodeFilter.SHOW_TEXT);
  const textNodes: Text[] = [];
  while (walker.nextNode()) textNodes.push(walker.currentNode as Text);
  for (const node of textNodes) {
    const fragment = document.createDocumentFragment();
    for (const piece of (node.nodeValue ?? "").split(/(\s+)/)) {
      if (!piece) continue;
      if (/^\s+$/.test(piece)) fragment.appendChild(document.createTextNode(piece));
      else {
        const word = document.createElement("span");
        word.className = "w";
        word.textContent = piece;
        fragment.appendChild(word);
      }
    }
    node.parentNode?.replaceChild(fragment, node);
  }
  const words = [...text.querySelectorAll<HTMLElement>(".w")];
  text.classList.add("is-typing");
  section.dataset.live = "";

  type Wire = { path: SVGPathElement; len: number; c1: SVGCircleElement; c2: SVGCircleElement };
  let wireDefs: Wire[] = [];
  /** Read in layout(), so a frame never reads: the knowledge's height and each line's top. */
  let kbHeight = 0;
  let lineTops: number[] = [];
  let last = -1;
  const NS = "http://www.w3.org/2000/svg";

  function layout() {
    // Reads first, together.
    const kbBox = kb.getBoundingClientRect();
    kbHeight = kbBox.height;
    lineTops = lines.map((line) => line.getBoundingClientRect().top - kbBox.top);
    const drawWires = getComputedStyle(wires).display !== "none" && kbHeight > 0;
    let geometry: { x1: number; y1: number; x2: number; y2: number }[] = [];
    let box = { width: 0, height: 0 };
    if (drawWires) {
      const wasOff = draft.classList.contains("off");
      draft.style.transition = "none";
      draft.classList.remove("off");
      const gr = grid.getBoundingClientRect();
      const dr = draft.getBoundingClientRect();
      box = { width: gr.width, height: gr.height };
      geometry = ["a", "b", "c"].flatMap((key) => {
        const line = kb.querySelector(`.line[data-m="${key}"]`)?.getBoundingClientRect();
        const word = text.querySelector(`.src[data-m="${key}"] .w`)?.getBoundingClientRect();
        if (!line || !word) return [];
        return [{ x1: line.right - gr.left + 6, y1: line.top + line.height / 2 - gr.top, x2: dr.left - gr.left - 1, y2: word.top + word.height / 2 - gr.top }];
      });
      if (wasOff) draft.classList.add("off");
      draft.style.transition = "";
    }
    // Then the writes.
    wires.replaceChildren();
    wireDefs = [];
    if (drawWires) {
      wires.setAttribute("viewBox", `0 0 ${box.width} ${box.height}`);
      for (const { x1, y1, x2, y2 } of geometry) {
        const dx = Math.max(40, (x2 - x1) * 0.5);
        const path = document.createElementNS(NS, "path");
        path.setAttribute("d", `M${x1} ${y1} C${x1 + dx} ${y1} ${x2 - dx} ${y2} ${x2} ${y2}`);
        const c1 = document.createElementNS(NS, "circle");
        const c2 = document.createElementNS(NS, "circle");
        for (const [c, x, y] of [[c1, x1, y1], [c2, x2, y2]] as const) {
          c.setAttribute("cx", String(x));
          c.setAttribute("cy", String(y));
          c.setAttribute("r", "3");
        }
        wires.append(path, c1, c2);
        wireDefs.push({ path, len: 0, c1, c2 });
      }
      // The paths' lengths: geometry, read once here, never in a frame.
      for (const wire of wireDefs) wire.len = wire.path.getTotalLength();
      for (const wire of wireDefs) wire.path.style.strokeDasharray = String(wire.len);
    }
    render(Math.max(0, last), true);
  }

  const show = (el: HTMLElement, on: boolean) => el.classList.toggle("off", !on);

  /** Writes only. p = 0 is the question, already tagged, and the AI starting its draft (never an empty
   * frame); p = 1 is everything. */
  function render(p: number, force = false) {
    if (!force && p === last) return;
    last = p;
    const scanning = (p > 0.06 && p < 0.26) || (p > 0.7 && p < 0.84);
    const sp = p < 0.5 ? seg(p, 0.06, 0.26) : seg(p, 0.7, 0.84);
    const scanTop = 24 + sp * Math.max(0, kbHeight - 24);
    scan.style.opacity = scanning ? "1" : "0";
    scan.style.transform = `translate3d(0, ${scanTop.toFixed(1)}px, 0)`;
    kb.classList.toggle("scanning", scanning);
    const hit = p >= 0.27 && p < 0.7;
    lines.forEach((line, i) => {
      line.classList.toggle("seen", scanning && scanTop > (lineTops[i] ?? 0));
      line.classList.toggle("hit", hit && !!line.dataset.m);
    });
    kb.classList.toggle("miss", p >= 0.84);
    const wt = seg(p, 0.32, 0.52);
    const out = p >= 0.7 ? 1 - seg(p, 0.7, 0.74) : 1;
    wireDefs.forEach((wire, i) => {
      const t = clamp(wt * 1.4 - i * 0.2, 0, 1);
      wire.path.style.strokeDashoffset = (wire.len * (1 - t)).toFixed(1);
      wire.path.style.opacity = String(out);
      wire.c1.style.opacity = String((t > 0 ? 1 : 0) * out);
      wire.c2.style.opacity = String((t >= 1 ? 1 : 0) * out);
    });
    show(parts.read, true);
    show(draft, true);
    const shown = Math.floor(seg(p, 0.32, 0.56) * words.length + (p >= 0.56 ? 1 : 0));
    words.forEach((word, i) => word.classList.toggle("on", i < shown));
    show(parts.cites, p >= 0.56);
    state.textContent = p < 0.56 ? "Writing" : p < 0.64 ? "Ready to send" : "Sent by you";
    show(parts.q2, p >= 0.66);
    show(parts.hand, p >= 0.86);
    show(parts.gap, p >= 0.92);
    const marks = [0, 0.06, 0.27, 0.66, 1];
    steps.forEach((step, i) => {
      step.style.setProperty("--f", seg(p, marks[i], marks[i + 1]).toFixed(3));
      step.classList.toggle("on", p >= marks[i] && (i === steps.length - 1 || p < marks[i + 1]));
    });
  }

  return {
    layout,
    render,
    dispose: () => {
      delete section.dataset.live;
      text.classList.remove("is-typing");
    },
  };
}

// ---------------------------------------------------------------- comments to DMs

function comments(root: ParentNode, reduce: boolean): Cleanup {
  const machine = root.querySelector<HTMLElement>("[data-machine]");
  if (!machine) return () => {};
  const q = (selector: string) => machine.querySelector<HTMLElement>(selector)!;
  const list = q("[data-comments]");
  const dm = q("[data-dm]");
  const token = q("[data-token]");
  const rule = q("[data-rule]");
  const input = q("[data-kw]") as HTMLInputElement;
  const kwShow = q("[data-kw-show]");
  const sentEl = q("[data-sent]");
  const dmName = q("[data-dm-name]");
  const dmAvatar = q("[data-dm-av]");
  let keyword = DEFAULT_KEYWORD;
  let sent = Number(sentEl.textContent) || 0;
  let index = 4; // the server rendered the first four
  let busy = false;
  let timer: number | undefined;
  const timeouts = new Set<number>();
  const later = (fn: () => void, ms: number) => {
    const id = window.setTimeout(() => {
      timeouts.delete(id);
      fn();
    }, ms);
    timeouts.add(id);
  };

  const el = (tag: string, className: string, text?: string) => {
    const node = document.createElement(tag);
    node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  function addComment() {
    const item = COMMENT_STREAM[index % COMMENT_STREAM.length];
    index += 1;
    const text = item.text.replace("{K}", keyword).replace("{k}", keyword.toLowerCase());
    const row = el("li", `cmt enter${item.spam ? " spam" : ""}`);
    const avatar = el("span", "av", item.user.charAt(0).toUpperCase());
    avatar.style.setProperty("--bg", `var(--av-${item.avatar})`);
    avatar.setAttribute("aria-hidden", "true");
    const body = el("span", "body");
    body.append(el("b", "", item.user));
    if (item.match) body.append(el("span", "kw", text));
    else body.append(text);
    row.append(avatar, body);
    if (item.spam) row.append(el("span", "tag t-stop", "Hidden"));
    list.insertBefore(row, list.firstChild);
    while (list.children.length > 6) list.lastElementChild?.remove();
    if (item.match) {
      later(() => row.classList.add("match"), 350);
      if (!busy) later(() => fly(row, item), 700);
    }
  }

  const rectIn = (node: Element) => {
    const a = node.getBoundingClientRect();
    const b = machine!.getBoundingClientRect();
    return { x: a.left - b.left, y: a.top - b.top, w: a.width, h: a.height };
  };

  function fly(row: HTMLElement, item: (typeof COMMENT_STREAM)[number]) {
    busy = true;
    const a = rectIn(row);
    const b = rectIn(rule);
    const c = rectIn(dm);
    const p0 = { x: a.x + a.w - 70, y: a.y + a.h / 2 - 13 };
    const p1 = { x: b.x + b.w / 2 - 26, y: b.y + 40 };
    const p2 = { x: c.x + 20, y: c.y + 20 };
    token.animate?.(
      [
        { transform: `translate(${p0.x}px,${p0.y}px)`, opacity: 0 },
        { transform: `translate(${p0.x}px,${p0.y}px)`, opacity: 1, offset: 0.1 },
        { transform: `translate(${p1.x}px,${p1.y}px)`, opacity: 1, offset: 0.5 },
        { transform: `translate(${p2.x}px,${p2.y}px)`, opacity: 1, offset: 0.92 },
        { transform: `translate(${p2.x}px,${p2.y}px)`, opacity: 0 },
      ],
      { duration: 1300, easing: "cubic-bezier(.45,0,.25,1)" },
    );
    later(() => {
      rule.classList.remove("pulse");
      void rule.offsetWidth;
      rule.classList.add("pulse");
      sent += 1;
      sentEl.textContent = String(sent);
    }, 600);
    later(() => playDm(item), 1250);
  }

  const bubble = (className: string, text: string, extra?: HTMLElement) => {
    const node = el("p", `${className} enter`, text);
    if (extra) node.append(extra);
    dm.append(node);
    return node;
  };

  function playDm(item: (typeof COMMENT_STREAM)[number]) {
    dm.replaceChildren();
    dmName.textContent = item.user;
    dmAvatar.textContent = item.user.charAt(0).toUpperCase();
    dmAvatar.style.setProperty("--bg", `var(--av-${item.avatar})`);
    const button = el("span", "tapbtn", DM_SCRIPT.button);
    bubble("pb l", DM_SCRIPT.opener, button);
    later(() => {
      button.classList.add("press");
      later(() => button.classList.remove("press"), 220);
    }, 1300);
    later(() => bubble("pb r", DM_SCRIPT.button), 1600);
    let typing: HTMLElement | null = null;
    later(() => {
      typing = el("div", "dm-typing");
      typing.append(el("i", ""), el("i", ""), el("i", ""));
      dm.append(typing);
    }, 2100);
    later(() => {
      typing?.remove();
      bubble("pb l", DM_SCRIPT.link, el("span", "lnk", DM_SCRIPT.url));
    }, 2900);
    later(() => {
      bubble("dm-note", DM_SCRIPT.followNote);
      bubble("pb l", DM_SCRIPT.follow);
      busy = false;
    }, 3800);
  }

  const onInput = () => {
    const value = input.value.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 10);
    if (input.value !== value) input.value = value;
    keyword = value || DEFAULT_KEYWORD;
    kwShow.textContent = keyword;
    for (const match of list.querySelectorAll<HTMLElement>(".cmt.match .kw")) {
      match.textContent = /[a-z]/.test(match.textContent ?? "") ? `${keyword.toLowerCase()} please` : keyword;
    }
  };
  input.addEventListener("input", onInput);

  // One round of the stream while the scene is on screen, then it holds (C-157). The pause control
  // (WCAG 2.2.2) stops it; a DM already on its way finishes (a few seconds at most).
  const scope = machine.closest<HTMLElement>("[data-motion-scope]");
  const control = !reduce && scope ? bindMotionControl(scope) : null;
  let added = 0;
  let onScreen = false;
  const step = () => {
    addComment();
    added += 1;
    if (added >= COMMENT_STREAM.length) finish();
  };
  const stop = () => {
    if (timer !== undefined) window.clearInterval(timer);
    timer = undefined;
  };
  const start = () => {
    if (timer !== undefined || !onScreen || control?.paused || added >= COMMENT_STREAM.length) return;
    step();
    if (added < COMMENT_STREAM.length) timer = window.setInterval(step, 1900);
  };
  const finish = () => {
    stop();
    unsubscribe?.();
    control?.destroy();
  };
  const unsubscribe = control?.subscribe((paused) => (paused ? stop() : start()));

  let observer: IntersectionObserver | null = null;
  if (!reduce) {
    observer = new IntersectionObserver(
      (entries) => {
        onScreen = entries.some((entry) => entry.isIntersecting);
        if (onScreen) start();
        else stop();
      },
      { threshold: 0.2 },
    );
    observer.observe(machine);
  }

  return () => {
    input.removeEventListener("input", onInput);
    observer?.disconnect();
    finish();
    timeouts.forEach((id) => window.clearTimeout(id));
  };
}

// ---------------------------------------------------------------- modes

function modes(root: ParentNode, reduce: boolean): Cleanup {
  const section = root.querySelector<HTMLElement>("[data-modes]");
  if (!section) return () => {};
  const buttons = [...section.querySelectorAll<HTMLButtonElement>("[data-mode]")];
  const description = section.querySelector<HTMLElement>("[data-mode-desc]")!;
  const outs = [...section.querySelectorAll<HTMLElement>("[data-out]")];

  function setMode(mode: ModeKey) {
    for (const button of buttons) button.setAttribute("aria-pressed", String(button.dataset.mode === mode));
    description.textContent = MODES[mode].description;
    outs.forEach((out, i) => {
      const [tone, tag, note] = MODES[mode].outcomes[i];
      const chip = document.createElement("span");
      chip.className = `tag t-${tone}`;
      chip.textContent = tag;
      const small = document.createElement("small");
      small.textContent = note;
      out.replaceChildren(chip, small);
      if (!reduce) {
        out.classList.remove("swap");
        void out.offsetWidth;
        out.style.animationDelay = `${i * 40}ms`; // the stagger token (40 ms), 120 ms in all
        out.classList.add("swap");
      }
    });
  }

  const onClick = (event: Event) => {
    const mode = (event.currentTarget as HTMLElement).dataset.mode as ModeKey;
    setMode(mode);
  };
  for (const button of buttons) button.addEventListener("click", onClick);
  return () => buttons.forEach((button) => button.removeEventListener("click", onClick));
}

// ---------------------------------------------------------------- your AI assistant (C-168)

/** When each part of the example chat appears, in ms from the start (under 5 s in all, WCAG 2.2.2). */
export const AI_APPS_TIMELINE: { at: number; step?: number; press?: true; confirm?: true }[] = [
  { at: 0, step: 0 },
  { at: 700, step: 1 },
  { at: 2000, press: true },
  { at: 2300, confirm: true, step: 2 },
  { at: 3300, step: 3 },
  { at: 4100, step: 4 },
];

/**
 * The example chat (AiApps.tsx). The server rendered its final state. When the observer first
 * reports its band below the viewport, it is armed (`data-live`: every step hidden in its own box, the
 * button on "Confirm"); when it comes on screen it plays once: the ask, the preview, a press on
 * Confirm, "Confirmed" with the scheduled line, the second question and its summary. A scene already
 * on screen when the script arrives is never touched, so nothing blinks. Not called with
 * `prefers-reduced-motion: reduce`: the final state simply stands.
 */
export function aiApps(root: ParentNode): Cleanup {
  const scene = root.querySelector<HTMLElement>("[data-mh]");
  if (!scene) return () => {};
  const stage = scene;
  const steps = [...stage.querySelectorAll<HTMLElement>(".mh-step")];
  const button = stage.querySelector<HTMLElement>("[data-mh-btn]");
  const timers = new Set<number>();
  let state: "idle" | "armed" | "played" = "idle";

  const arm = () => {
    state = "armed";
    stage.dataset.live = "";
    delete stage.dataset.mhOk;
    steps.forEach((el) => el.classList.remove("on"));
  };
  const play = () => {
    state = "played";
    for (const { at, step, press, confirm } of AI_APPS_TIMELINE) {
      const id = window.setTimeout(() => {
        timers.delete(id);
        if (press) button?.classList.add("press");
        if (confirm) {
          button?.classList.remove("press");
          stage.dataset.mhOk = "";
        }
        if (step !== undefined) steps.filter((el) => el.dataset.s === String(step)).forEach((el) => el.classList.add("on"));
      }, at);
      timers.add(id);
    }
  };

  // Two observers. The band's own box decides whether to arm: its content is skipped until it nears
  // the viewport (site.css, content-visibility), so the scene inside has no geometry of its own yet.
  // The scene's box then starts the play once a third of it is on screen.
  const band = stage.closest<HTMLElement>("section") ?? stage;
  const player = new IntersectionObserver(
    (entries) => {
      if (state !== "armed" || !entries.some((entry) => entry.isIntersecting)) return;
      player.disconnect();
      play();
    },
    { threshold: 0.35 },
  );
  const observer = new IntersectionObserver((entries) => {
    const entry = entries[entries.length - 1];
    observer.disconnect();
    // Only a band still below the viewport plays; one on screen or scrolled past stays as rendered.
    if (state !== "idle" || entry.isIntersecting || entry.boundingClientRect.top <= 0) {
      state = "played";
      return;
    }
    arm();
    player.observe(stage);
  });
  observer.observe(band);

  return () => {
    observer.disconnect();
    player.disconnect();
    timers.forEach((id) => window.clearTimeout(id));
    delete stage.dataset.live;
    delete stage.dataset.mhOk;
    button?.classList.remove("press");
    steps.forEach((el) => el.classList.remove("on"));
  };
}

// ---------------------------------------------------------------- a day in your inbox (C-175)

type DemoState = { strip?: string; acct?: string; tab?: string; view?: string };

/**
 * One moment of the story, ms from its start: the caption it lights, the parts it turns on and off,
 * the rows in the list (in order), the controls' state, where the pointer goes, and a click there.
 */
type DemoBeat = { at: number; step?: number; on?: string[]; off?: string[]; list?: string[]; state?: DemoState; to?: string; click?: true };

const DEMO_ALL = ["maya", "theo", "nina", "ria", "lena", "leo", "visitor"];
const open = (id: string) => [`sel-${id}`, `conv-${id}`, `det-${id}`];

/** The story (ProductDemo.tsx), about 21.5 s, then a rest; the first beat is the scene's start. */
export const PRODUCT_DEMO_TIMELINE: DemoBeat[] = [
  { at: 0, step: 0, on: ["pick", "theo-dot", "nina-dot"], list: DEMO_ALL.slice(1), state: { strip: "all", acct: "all", tab: "chats", view: "list" } },
  // 1. A DM arrives, and the row opens.
  { at: 400, on: ["maya-row-q", "maya-dot"], list: DEMO_ALL },
  { at: 1000, to: "row-maya" },
  { at: 1350, click: true, on: [...open("maya"), "maya-ph", "det-maya-wait"], off: ["pick", "maya-dot"], state: { view: "thread" } },
  // 2. The AI reads it and drafts.
  { at: 1700, step: 1, on: ["maya-tags", "maya-lead", "det-maya-lead", "det-maya-analysis", "det-maya-add"], off: ["det-maya-wait"] },
  { at: 2200, on: ["maya-bar", "maya-drafting"] },
  { at: 2900, on: ["maya-words", "maya-source"], off: ["maya-drafting"] },
  // 3. You press Send.
  { at: 4000, step: 2, to: "send-draft" },
  { at: 4400, click: true, on: ["maya-out", "maya-sending", "maya-row-you"], off: ["maya-bar", "maya-row-q"] },
  { at: 4900, on: ["maya-sent"], off: ["maya-sending"] },
  // 4. Schedule a message: written, the clock, a time inside the window, then the chip and the tab.
  { at: 5400, step: 3, on: ["maya-typed", "maya-ready"], off: ["maya-ph"] },
  { at: 5800, to: "clock" },
  { at: 6100, click: true, on: ["pop"] },
  { at: 7000, to: "schedule" },
  { at: 7350, click: true, on: ["toast", "maya-chip", "tab-count", "maya-ph"], off: ["pop", "maya-typed", "maya-ready"] },
  { at: 8200, to: "back-maya", off: ["toast"] },
  { at: 8400, click: true, state: { view: "list" } },
  { at: 8600, to: "tab-scheduled" },
  { at: 8900, click: true, state: { tab: "scheduled" } },
  { at: 9800, to: "tab-chats" },
  { at: 10050, click: true, state: { tab: "chats" } },
  // 5. Switch platform and account: the Select shows on a platform with two accounts, and each new
  // list opens its top conversation, so the thread and the panel always match the list.
  { at: 10400, step: 4, to: "seg-instagram" },
  { at: 10700, click: true, list: ["maya", "theo", "ria", "lena"], state: { strip: "instagram" } },
  { at: 11300, to: "acct" },
  { at: 11550, click: true, on: ["menu"] },
  { at: 11850, to: "opt-mumbai" },
  { at: 12100, click: true, off: ["menu"], list: ["maya", "ria"], state: { acct: "mumbai" } },
  { at: 12700, to: "acct" },
  { at: 12900, click: true, on: ["menu"] },
  { at: 13150, to: "opt-pune" },
  { at: 13400, click: true, on: [...open("theo"), "det-theo-analysis", "det-theo-add"], off: ["menu", ...open("maya"), "theo-dot"], list: ["theo", "lena"], state: { acct: "pune" } },
  { at: 14000, to: "seg-whatsapp" },
  { at: 14250, click: true, on: [...open("nina"), "det-nina-analysis", "det-nina-add"], off: [...open("theo"), "nina-dot"], list: ["nina", "leo"], state: { strip: "whatsapp", acct: "all" } },
  { at: 14800, to: "seg-all" },
  { at: 15050, click: true, on: open("maya"), off: open("nina"), list: DEMO_ALL, state: { strip: "all" } },
  // 6. A comment becomes a DM: the opening with its button, their tap, then the link.
  { at: 15600, step: 5, on: ["ana-row-open"], list: ["ana", ...DEMO_ALL] },
  { at: 16000, to: "row-ana" },
  { at: 16300, click: true, on: [...open("ana"), "ana-comment", "det-ana-wait"], off: open("maya"), state: { view: "thread" } },
  { at: 16800, on: ["ana-open"] },
  { at: 17700, on: ["ana-tap", "ana-window", "det-ana-analysis", "det-ana-add"], off: ["det-ana-wait"] },
  { at: 18300, on: ["ana-link", "ana-row-link"], off: ["ana-row-open"] },
  // 7. The tricky one comes to you.
  { at: 18900, step: 6, to: "back-ana" },
  { at: 19100, click: true, state: { view: "list" } },
  { at: 19200, on: ["sam-row-auto", "sam-dot"], list: ["sam", "ana", ...DEMO_ALL] },
  { at: 19500, to: "row-sam" },
  { at: 19750, click: true, on: [...open("sam"), "det-sam-wait", "sam-assign-none", "det-sam-nobody"], off: [...open("ana"), "sam-dot"], state: { view: "thread" } },
  { at: 20200, on: ["sam-banner", "sam-need", "sam-row-need", "need-count", "det-sam-need", "det-sam-analysis", "det-sam-add"], off: ["det-sam-wait"] },
  // 8. Assign it to a teammate.
  { at: 20700, step: 7, to: "assign" },
  { at: 20950, click: true, on: ["assign-menu"] },
  { at: 21200, to: "opt-priya" },
  { at: 21450, click: true, on: ["assign-toast", "sam-assign-who", "sam-row-who", "det-sam-who"], off: ["assign-menu", "sam-assign-none", "det-sam-nobody"] },
  // The rest, before it loops.
  { at: 23000 },
];

/**
 * The inbox story (ProductDemo.tsx). The server drew its finished state; `data-live` (site.css) hides
 * every named part in its own box, and the timeline turns them on, so nothing moves the layout. It
 * runs while the scene is on screen, the tab is visible and the pause control isn't pressed, and picks
 * up where it stopped. The captions become buttons here: a jump replays the timeline from its start
 * (`seek`), so a step looks the same however it was reached. Paused, or with reduced motion (which
 * starts paused, on the story's end, with nothing moving), a jump shows the step's finished state.
 */
export function productDemo(root: ParentNode, reduce = false): Cleanup {
  const scene = root.querySelector<HTMLElement>("[data-demo]");
  const scope = scene?.closest<HTMLElement>("[data-motion-scope]");
  const win = scene?.querySelector<HTMLElement>(".pd-win");
  const cursor = scene?.querySelector<HTMLElement>("[data-cursor]");
  if (!scene || !scope || !win || !cursor) return () => {};
  const stage = scene;
  const frame = win;
  const pointer = cursor;
  const ring = pointer.querySelector<HTMLElement>("[data-ring]");
  const parts = [...stage.querySelectorAll<HTMLElement>("[data-p]")];
  const rows = [...stage.querySelectorAll<HTMLElement>("[data-row]")];
  const homes = rows.map((row) => row.style.getPropertyValue("--y"));
  const home: DemoState = { strip: stage.dataset.strip, acct: stage.dataset.acct, tab: stage.dataset.tab, view: stage.dataset.view };
  const steps = [...scope.querySelectorAll<HTMLElement>("[data-demo-steps] li")];
  const captions = steps.map((li) => li.firstElementChild as HTMLElement);
  const control = bindMotionControl(scope);
  const LAST = PRODUCT_DEMO_TIMELINE.length - 2;
  const startOf = (step: number) => PRODUCT_DEMO_TIMELINE.findIndex((beat) => beat.step === step);
  const endOf = (step: number) => (step === steps.length - 1 ? LAST : startOf(step + 1) - 1);
  let index = 0;
  let clock = 0;
  let resumedAt = 0;
  let timer: number | undefined;
  let settle: number | undefined;
  let armed = false;
  let onScreen = false;
  let aimed = false;

  const toggle = (names: string[] | undefined, on: boolean) => {
    for (const el of parts) if (names?.includes(el.dataset.p ?? "")) el.classList.toggle("on", on);
  };
  const showList = (ids: string[]) => {
    let y = 0;
    for (const id of ids) {
      const row = rows.find((el) => el.dataset.row === id);
      if (!row) continue;
      row.style.setProperty("--y", `${y}px`);
      y += parseInt(row.style.getPropertyValue("--h"), 10) || 0;
    }
    for (const row of rows) row.classList.toggle("on", ids.includes(row.dataset.row ?? ""));
  };
  const light = (step: number) =>
    steps.forEach((el, i) => {
      el.classList.toggle("on", i === step);
      if (i === step) el.firstElementChild?.setAttribute("aria-current", "step");
      else el.firstElementChild?.removeAttribute("aria-current");
    });
  /** A target with no box (the back arrow on a wide screen, where the list is always there) is skipped. */
  const aim = (name: string) => {
    const box = stage.querySelector(`[data-at="${name}"]`)?.getBoundingClientRect();
    aimed = Boolean(box?.width);
    if (!box || !aimed) return;
    const origin = frame.getBoundingClientRect();
    pointer.classList.add("on");
    pointer.style.transform = `translate(${box.left + box.width / 2 - origin.left}px, ${box.top + box.height / 2 - origin.top}px)`;
  };
  /** The state a beat changes: everything but the pointer. */
  const change = ({ step, on, off, list, state }: DemoBeat) => {
    toggle(off, false);
    toggle(on, true);
    if (list) showList(list);
    if (state) Object.assign(stage.dataset, state);
    if (step !== undefined) light(step);
  };
  const apply = (beat: DemoBeat) => {
    if (beat.to) aim(beat.to);
    if (beat.click && aimed) ring?.animate?.([{ opacity: 0.7, transform: "scale(0.4)" }, { opacity: 0, transform: "scale(1)" }], { duration: 350 });
    change(beat);
  };
  const begin = () => {
    parts.forEach((el) => el.classList.remove("on"));
    // A row not yet in the story waits at the top, ready to slide in.
    rows.forEach((row) => row.style.setProperty("--y", "0px"));
    pointer.classList.remove("on");
    change(PRODUCT_DEMO_TIMELINE[0]);
    index = 1;
    clock = 0;
  };
  const arm = () => {
    if (armed) return;
    armed = true;
    stage.dataset.live = "";
  };
  /** Every beat up to `last`, from the start, at once; the pointer waits where the last of them sent it. */
  const seek = (last: number) => {
    arm();
    stage.dataset.seek = "";
    begin();
    let aimAt: string | undefined;
    for (let i = 1; i <= last; i += 1) {
      const beat = PRODUCT_DEMO_TIMELINE[i];
      change(beat);
      aimAt = beat.to ?? aimAt;
    }
    if (aimAt && !reduce) aim(aimAt);
    index = last + 1;
    clock = PRODUCT_DEMO_TIMELINE[last].at;
    window.clearTimeout(settle);
    settle = window.setTimeout(() => delete stage.dataset.seek, 50);
  };
  const run = () => {
    if (timer !== undefined || !armed || !onScreen || document.hidden || control.paused) return;
    resumedAt = performance.now();
    timer = window.setTimeout(fire, Math.max(0, PRODUCT_DEMO_TIMELINE[index].at - clock));
  };
  const fire = () => {
    timer = undefined;
    const beat = PRODUCT_DEMO_TIMELINE[index];
    clock = beat.at;
    apply(beat);
    index += 1;
    if (index === PRODUCT_DEMO_TIMELINE.length) begin();
    run();
  };
  const halt = () => {
    if (timer === undefined) return;
    window.clearTimeout(timer);
    timer = undefined;
    clock += performance.now() - resumedAt;
  };
  const jump = (step: number) => {
    halt();
    seek(control.paused ? endOf(step) : startOf(step));
    run();
  };

  // The captions become controls now; each keeps the plain caption's box, so nothing shifts.
  steps.forEach((li, step) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "pd-step";
    button.textContent = li.textContent;
    button.addEventListener("click", () => jump(step));
    li.replaceChildren(button);
  });

  const unsubscribe = control.subscribe((paused) => (paused ? halt() : run()));
  const onVisibility = () => (document.hidden ? halt() : run());
  document.addEventListener("visibilitychange", onVisibility);
  const observer = reduce
    ? null
    : new IntersectionObserver(
        (entries) => {
          onScreen = entries[entries.length - 1].isIntersecting;
          if (!armed) {
            arm();
            begin();
          }
          if (onScreen) run();
          else halt();
        },
        { threshold: 0.25 },
      );
  observer?.observe(stage);
  if (reduce) seek(LAST);

  return () => {
    observer?.disconnect();
    document.removeEventListener("visibilitychange", onVisibility);
    halt();
    window.clearTimeout(settle);
    unsubscribe();
    control.destroy();
    delete stage.dataset.live;
    delete stage.dataset.seek;
    Object.assign(stage.dataset, home);
    parts.forEach((el) => el.classList.remove("on"));
    steps.forEach((el, i) => {
      el.classList.remove("on");
      el.replaceChildren(captions[i]);
    });
    rows.forEach((row, i) => row.style.setProperty("--y", homes[i]));
    pointer.classList.remove("on");
    pointer.style.transform = "";
  };
}

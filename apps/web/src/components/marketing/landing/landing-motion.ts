/**
 * The landing page's scenes in motion (C-155, C-157), loaded by LandingMotion once the page has
 * settled. Plain DOM over the server-rendered markup: nothing here re-renders React, and every move
 * is a transform, an opacity or a class, so no layout box moves (CLS stays 0). Layout is read once
 * (on start, on a debounced resize, when fonts arrive) and frames only write.
 *
 * - Hero: one short sort once the page is idle (about a second): the newest message lands on top,
 *   then moves to its place in the sorted inbox the server rendered, and the scene holds.
 * - How it works: where its CSS pins the frame (wide screens), the scroll plays it: a scan over the
 *   knowledge, wires to the cited words, the draft writing itself, the hand-off and the gap. Where it
 *   doesn't pin (phones, tablets), it plays once when on screen, with a pause control.
 * - Automations: one round of comments arrives while the scene is on screen (pause control), then
 *   it holds; the keyword field changes what the automation listens for.
 * - Modes: the Off, Suggest and Auto switch.
 *
 * With `prefers-reduced-motion: reduce` only the two controls work and the scenes stay as rendered.
 */
import { bindMotionControl, type MotionControl } from "@/components/site/motion-control";

import { COMMENT_STREAM, DEFAULT_KEYWORD, DM_SCRIPT, MODES, type ModeKey } from "./data";

const clamp = (v: number, a: number, b: number) => Math.max(a, Math.min(b, v));
const seg = (p: number, a: number, b: number) => clamp((p - a) / (b - a), 0, 1);

/** The site's motion tokens (globals.css): the one-shot ceiling and the smooth-out curve. */
const ENTRANCE_MS = 1200;
const EASE_OUT = "cubic-bezier(0.22, 1, 0.36, 1)";
/** How long How it works plays by itself where it doesn't pin. */
const DECIDE_PLAY_MS = 9000;

type Cleanup = () => void;

/** Starts every scene under `root`; returns a function that stops them all. */
export function startLandingMotion(root: ParentNode = document): Cleanup {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const cleanups: Cleanup[] = [];
  cleanups.push(modes(root, reduce));
  cleanups.push(comments(root, reduce));
  if (!reduce) {
    cleanups.push(heroSort(root));
    cleanups.push(decide(root));
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

/**
 * The hero's one sort (at most 1.2 s, the entrance token). The server rendered the sorted inbox; the
 * newest message (`data-arrives`) fades out of its slot and lands on top while the rows above make
 * room, then it moves back down to its place as they close up. The end state is the server's.
 */
function heroSort(root: ParentNode): Cleanup {
  const list = root.querySelector<HTMLElement>("[data-notes]");
  const arriving = list?.querySelector<HTMLElement>("[data-arrives]");
  if (!list || !arriving) return () => {};
  const rows = [...list.children] as HTMLElement[];
  const index = rows.indexOf(arriving);
  if (index <= 0) return () => {};
  const above = rows.slice(0, index);
  const tag = arriving.querySelector<HTMLElement>(".tag");
  const animations: Animation[] = [];

  const play = () => {
    // One read: the row pitch.
    const pitch = arriving.offsetTop - rows[index - 1].offsetTop;
    const top = -index * pitch;
    const options: KeyframeAnimationOptions = { duration: ENTRANCE_MS, easing: "linear" };
    arriving.style.zIndex = "1";
    animations.push(
      arriving.animate(
        [
          { offset: 0, transform: "translateY(0)", opacity: 1 },
          { offset: 0.12, transform: "translateY(0)", opacity: 0, easing: "steps(1, end)" },
          { offset: 0.13, transform: `translateY(${top - 8}px)`, opacity: 0, easing: EASE_OUT },
          { offset: 0.36, transform: `translateY(${top}px)`, opacity: 1 },
          { offset: 0.44, transform: `translateY(${top}px)`, opacity: 1, easing: EASE_OUT },
          { offset: 1, transform: "translateY(0)", opacity: 1 },
        ],
        options,
      ),
    );
    if (tag)
      animations.push(
        tag.animate(
          [
            { offset: 0, opacity: 1, transform: "scale(1)" },
            { offset: 0.12, opacity: 0, transform: "scale(0.96)" },
            { offset: 0.8, opacity: 0, transform: "scale(0.96)", easing: EASE_OUT },
            { offset: 1, opacity: 1, transform: "scale(1)" },
          ],
          options,
        ),
      );
    for (const row of above)
      animations.push(
        row.animate(
          [
            { offset: 0, transform: "translateY(0)" },
            { offset: 0.12, transform: "translateY(0)", easing: EASE_OUT },
            { offset: 0.36, transform: `translateY(${pitch}px)` },
            { offset: 0.44, transform: `translateY(${pitch}px)`, easing: EASE_OUT },
            { offset: 1, transform: "translateY(0)" },
          ],
          options,
        ),
      );
    animations[0].finished.then(() => arriving.style.removeProperty("z-index")).catch(() => {});
  };

  // Once, and only while the hero is on screen (a reload further down the page skips it).
  let observer: IntersectionObserver | null = new IntersectionObserver(
    (entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      observer?.disconnect();
      observer = null;
      play();
    },
    { threshold: 0.5 },
  );
  observer.observe(list);

  return () => {
    observer?.disconnect();
    animations.forEach((animation) => animation.cancel());
    arriving.style.removeProperty("z-index");
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
  const relayout = perFrame(() => {
    setMode();
    scene.layout();
    if (!pinned) scene.render(auto.progress, true);
    tick();
  });

  const observer = new IntersectionObserver(
    (entries) => {
      visible = entries.some((entry) => entry.isIntersecting);
      auto.last = 0;
      if (visible) tick();
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
  scene.layout();

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

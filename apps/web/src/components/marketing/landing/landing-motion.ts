/**
 * The landing page's scenes in motion (C-155), loaded by LandingMotion once the page has settled.
 * Plain DOM over the server-rendered markup: nothing here re-renders React, and every change is a
 * transform, an opacity or a class, so nothing on screen moves its layout box (CLS stays 0).
 *
 * - Hero: on a wide screen the scroll scrubs a pile of messages into the sorted inbox the server
 *   rendered; on a phone it plays by itself while on screen.
 * - How it works: the scroll (or, on a phone, time) scans the knowledge, draws wires to the cited
 *   words, writes the draft and hands the last question over.
 * - Automations: comments keep arriving while the scene is on screen; the keyword field changes
 *   what the automation listens for.
 * - Modes: the Off, Suggest and Auto switch.
 *
 * With `prefers-reduced-motion: reduce` only the two controls work and the scenes stay as rendered.
 */
import { COMMENT_STREAM, DEFAULT_KEYWORD, DM_SCRIPT, MODES, type ModeKey } from "./data";

const clamp = (v: number, a: number, b: number) => Math.max(a, Math.min(b, v));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const seg = (p: number, a: number, b: number) => clamp((p - a) / (b - a), 0, 1);

type Cleanup = () => void;

/** Starts every scene under `root`; returns a function that stops them all. */
export function startLandingMotion(root: ParentNode = document): Cleanup {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const cleanups: Cleanup[] = [];
  cleanups.push(modes(root, reduce));
  cleanups.push(comments(root, reduce));
  if (!reduce) cleanups.push(scrubScenes(root));
  return () => cleanups.forEach((stop) => stop());
}

// ---------------------------------------------------------------- hero and how it works

function scrubScenes(root: ParentNode): Cleanup {
  const wideQuery = window.matchMedia("(min-width: 901px)");
  const navHeight = () => parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--nav-h")) || 64;
  const scrubProgress = (el: HTMLElement) => {
    const r = el.getBoundingClientRect();
    const nav = navHeight();
    const total = r.height - (window.innerHeight - nav);
    return total <= 0 ? 0 : clamp((nav - r.top) / total, 0, 1);
  };

  const hero = heroScene(root);
  const decide = decideScene(root);
  const visible = { hero: true, decide: false };
  const auto = { hero: { on: false, t0: 0 }, decide: { on: false, t0: 0 } };

  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) visible[(entry.target as HTMLElement).dataset.scene as "hero" | "decide"] = entry.isIntersecting;
      tick();
    },
    { rootMargin: "100px" },
  );
  if (hero) {
    hero.scrub.dataset.scene = "hero";
    observer.observe(hero.scrub);
  }
  if (decide) {
    decide.scrub.dataset.scene = "decide";
    observer.observe(decide.scrub);
  }

  // On a phone: the hero sorts, holds, unsorts (9 s); the decide scene plays over 16 s.
  const heroAuto = (e: number) => {
    const t = e % 9000;
    if (t < 1200) return 0;
    if (t < 4000) return (t - 1200) / 2800;
    if (t < 7600) return 1;
    return 1 - (t - 7600) / 1400;
  };
  const decideAuto = (e: number) => Math.min(1, (e % 16000) / 14500);

  let frame = 0;
  let disposed = false;
  function draw(now: number) {
    frame = 0;
    if (disposed) return;
    if (wideQuery.matches) {
      hero?.render(scrubProgress(hero.scrub));
      decide?.render(scrubProgress(decide.scrub));
      return;
    }
    let again = false;
    if (hero) {
      if (visible.hero) {
        // Start in the sorted hold, which is what the server rendered: no jump when the script arrives.
        if (!auto.hero.on) auto.hero = { on: true, t0: now - 4000 };
        hero.render(heroAuto(now - auto.hero.t0));
        again = true;
      } else auto.hero.on = false;
    }
    if (decide) {
      if (visible.decide) {
        if (!auto.decide.on) auto.decide = { on: true, t0: now };
        decide.render(decideAuto(now - auto.decide.t0));
        again = true;
      } else auto.decide.on = false;
    }
    if (again) tick();
  }
  function tick() {
    if (!frame) frame = requestAnimationFrame(draw);
  }
  const relayout = () => {
    hero?.layout();
    decide?.layout();
    tick();
  };
  const onScroll = () => {
    if (wideQuery.matches) tick();
  };
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", relayout);
  wideQuery.addEventListener("change", relayout);
  void document.fonts?.ready.then(() => !disposed && relayout());
  relayout();

  return () => {
    disposed = true;
    if (frame) cancelAnimationFrame(frame);
    observer.disconnect();
    window.removeEventListener("scroll", onScroll);
    window.removeEventListener("resize", relayout);
    wideQuery.removeEventListener("change", relayout);
    hero?.dispose();
    decide?.dispose();
  };
}

/** Where each note starts, as fractions of the stage and a tilt: [x, y, degrees]. */
const SCATTER: [number, number, number][] = [
  [0.04, 0.03, -7], [0.62, 0.05, 5], [0.3, 0.16, -3], [0.78, 0.27, 8], [0, 0.37, 4],
  [0.46, 0.45, -6], [0.7, 0.58, -4], [0.1, 0.7, 7], [0.52, 0.81, 2],
];
const MIX = [6, 2, 0, 4, 8, 1, 7, 3, 5];

function heroScene(root: ParentNode) {
  const scrub = root.querySelector<HTMLElement>("[data-hero-scrub]");
  const stage = scrub?.querySelector<HTMLElement>("[data-stage]");
  if (!scrub || !stage) return null;
  const panel = stage.querySelector<HTMLElement>("[data-panel]")!;
  const panelHead = stage.querySelector<HTMLElement>("[data-panel-h]")!;
  const notes = [...stage.querySelectorAll<HTMLElement>(".note")];
  const capA = stage.querySelector<HTMLElement>("[data-cap-a]")!;
  const capB = stage.querySelector<HTMLElement>("[data-cap-b]")!;
  const hint = scrub.querySelector<HTMLElement>("[data-hint]");
  const hintText = hint?.querySelector<HTMLElement>("[data-hint-text]");
  let geo: { dx: number; dy: number; r: number }[] = [];
  let last = 1;

  notes.forEach((note, i) => {
    const inner = note.firstElementChild as HTMLElement;
    inner.style.setProperty("--dur", `${4.2 + (i % 4) * 0.7}s`);
    inner.style.setProperty("--del", `${-i * 0.6}s`);
  });
  scrub.dataset.live = "";

  function layout() {
    const saved = notes.map((note) => note.style.transform);
    notes.forEach((note) => (note.style.transform = ""));
    const box = stage!.getBoundingClientRect();
    const W = stage!.clientWidth;
    const H = stage!.clientHeight - 36;
    geo = notes.map((note, i) => {
      const r = note.getBoundingClientRect();
      const [fx, fy, tilt] = SCATTER[MIX[i % MIX.length]];
      return { dx: fx * (W - r.width) - (r.left - box.left), dy: fy * (H - r.height) - (r.top - box.top), r: tilt };
    });
    notes.forEach((note, i) => (note.style.transform = saved[i]));
    render(last);
  }

  function render(p: number) {
    last = p;
    notes.forEach((note, i) => {
      const g = geo[i];
      if (!g) return;
      const d = 0.06 + i * 0.035;
      const t = ease(seg(p, d, d + 0.36));
      note.style.transform = `translate3d(${lerp(g.dx, 0, t).toFixed(1)}px,${lerp(g.dy, 0, t).toFixed(1)}px,0) rotate(${lerp(g.r, 0, t).toFixed(2)}deg)`;
      note.style.zIndex = t > 0.5 ? "2" : "3";
      const inner = note.firstElementChild as HTMLElement;
      inner.style.setProperty("--amp", ((1 - t) * 5).toFixed(2));
      inner.style.setProperty("--sh", (1 - t).toFixed(3));
      const tg = seg(p, 0.66 + i * 0.022, 0.74 + i * 0.022);
      inner.style.setProperty("--tg", tg.toFixed(3));
      inner.style.setProperty("--tm", (1 - tg).toFixed(3));
    });
    const po = seg(p, 0.1, 0.36);
    panel.style.opacity = po.toFixed(3);
    panel.style.transform = `scale(${(0.97 + 0.03 * po).toFixed(4)})`;
    panelHead.style.opacity = po.toFixed(3);
    panelHead.style.setProperty("--ch", seg(p, 0.84, 0.92).toFixed(3));
    const after = p > 0.6;
    capA.style.opacity = after ? "0" : "1";
    capB.style.opacity = after ? "1" : "0";
    if (hint) {
      hint.style.opacity = p > 0.92 ? "0" : "1";
      hint.querySelector<HTMLElement>(".track")?.style.setProperty("--hp", `${Math.round(p * 100)}%`);
      if (hintText) hintText.textContent = after ? "Sorted. Keep scrolling" : "Scroll to sort the inbox";
    }
  }

  return { scrub, layout, render, dispose: () => delete scrub.dataset.live };
}

function decideScene(root: ParentNode) {
  const section = root.querySelector<HTMLElement>("[data-decide]");
  const scrub = section?.querySelector<HTMLElement>("[data-decide-scrub]");
  if (!section || !scrub) return null;
  const q = <T extends Element = HTMLElement>(selector: string) => section.querySelector(selector) as T;
  const kb = q("[data-kb]");
  const scan = q("[data-scan]");
  const wires = q<SVGSVGElement>("[data-wires]");
  const grid = q("[data-dgrid]");
  const lines = [...kb.querySelectorAll<HTMLElement>(".line")];
  const text = q("[data-dtext]");
  const draft = q("[data-draft]");
  const parts = { q1: q("[data-q1]"), cites: q("[data-cites]"), q2: q("[data-q2]"), hand: q("[data-hand]"), gap: q("[data-gap]") };
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
  text.classList.add("typing");
  section.dataset.live = "";

  type Wire = { path: SVGPathElement; len: number; c1: SVGCircleElement; c2: SVGCircleElement };
  let wireDefs: Wire[] = [];
  let last = 0;
  const NS = "http://www.w3.org/2000/svg";

  function layout() {
    wires.replaceChildren();
    wireDefs = [];
    if (getComputedStyle(wires).display === "none") return render(last);
    const wasOff = draft.classList.contains("off");
    draft.style.transition = "none";
    draft.classList.remove("off");
    const gr = grid.getBoundingClientRect();
    const dr = draft.getBoundingClientRect();
    wires.setAttribute("viewBox", `0 0 ${gr.width} ${gr.height}`);
    for (const key of ["a", "b", "c"]) {
      const line = kb.querySelector(`.line[data-m="${key}"]`)?.getBoundingClientRect();
      const word = text.querySelector(`.src[data-m="${key}"] .w`)?.getBoundingClientRect();
      if (!line || !word) continue;
      const x1 = line.right - gr.left + 6;
      const y1 = line.top + line.height / 2 - gr.top;
      const x2 = dr.left - gr.left - 1;
      const y2 = word.top + word.height / 2 - gr.top;
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
      const len = path.getTotalLength();
      path.style.strokeDasharray = String(len);
      path.style.strokeDashoffset = String(len);
      wireDefs.push({ path, len, c1, c2 });
    }
    if (wasOff) draft.classList.add("off");
    void draft.offsetWidth;
    draft.style.transition = "";
    render(last);
  }

  const show = (el: HTMLElement, on: boolean) => el.classList.toggle("off", !on);

  function render(p: number) {
    last = p;
    const height = kb.getBoundingClientRect().height;
    const scanning = (p > 0.06 && p < 0.26) || (p > 0.7 && p < 0.84);
    const sp = p < 0.5 ? seg(p, 0.06, 0.26) : seg(p, 0.7, 0.84);
    const scanTop = 24 + sp * (height - 24);
    scan.style.opacity = scanning ? "1" : "0";
    scan.style.top = `${scanTop.toFixed(1)}px`;
    kb.classList.toggle("scanning", scanning);
    const hit = p >= 0.27 && p < 0.7;
    for (const line of lines) {
      // No offsetParent while the scene isn't laid out (a breakpoint change, a frame after leaving
      // the page): leave the line as it is until it's back.
      const parent = line.offsetParent as HTMLElement | null;
      if (!parent) continue;
      const top = line.offsetTop + parent.offsetTop;
      line.classList.toggle("seen", scanning && scanTop > top);
      line.classList.toggle("hit", hit && !!line.dataset.m);
    }
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
    show(parts.q1, true);
    show(draft, p >= 0.28);
    const shown = Math.floor(seg(p, 0.32, 0.56) * words.length + (p >= 0.56 ? 1 : 0));
    words.forEach((word, i) => word.classList.toggle("on", i < shown));
    show(parts.cites, p >= 0.56);
    state.textContent = p < 0.56 ? "Writing" : p < 0.64 ? "Ready to send" : "Sent by you";
    show(parts.q2, p >= 0.66);
    show(parts.hand, p >= 0.86);
    show(parts.gap, p >= 0.92);
    const marks = [0, 0.06, 0.27, 0.66, 1];
    steps.forEach((step, i) => {
      step.style.setProperty("--f", `${(seg(p, marks[i], marks[i + 1]) * 100).toFixed(1)}%`);
      step.classList.toggle("on", p >= marks[i] && (i === steps.length - 1 || p < marks[i + 1]));
    });
  }

  return {
    scrub,
    layout,
    render,
    dispose: () => {
      delete section.dataset.live;
      text.classList.remove("typing");
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
      typing = el("div", "typing");
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

  let observer: IntersectionObserver | null = null;
  if (!reduce) {
    observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting && timer === undefined) {
            addComment();
            timer = window.setInterval(addComment, 1900);
          } else if (!entry.isIntersecting && timer !== undefined) {
            window.clearInterval(timer);
            timer = undefined;
          }
        }
      },
      { threshold: 0.2 },
    );
    observer.observe(machine);
  }

  return () => {
    input.removeEventListener("input", onInput);
    observer?.disconnect();
    if (timer !== undefined) window.clearInterval(timer);
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
        out.style.animationDelay = `${i * 60}ms`;
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

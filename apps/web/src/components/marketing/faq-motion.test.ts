import { afterEach, describe, expect, it, vi } from "vitest";

import { bindFaqMotion } from "./faq-motion";

/** A stand-in for the Web Animations API (jsdom has none): finishes when told to. */
function fakeAnimate() {
  const made: { keyframes: Keyframe[]; animation: Animation & { finish(): void } }[] = [];
  const animate = vi.fn(function (this: HTMLElement, keyframes: Keyframe[]) {
    type Handler = ((ev: AnimationPlaybackEvent) => unknown) | null;
    const fake: { onfinish: Handler; oncancel: Handler; cancel(): void; finish(): void } = {
      onfinish: null,
      oncancel: null,
      cancel() {
        fake.oncancel?.({} as AnimationPlaybackEvent);
      },
      finish() {
        fake.onfinish?.({} as AnimationPlaybackEvent);
      },
    };
    const animation = fake as unknown as Animation & { finish(): void };
    made.push({ keyframes, animation });
    return animation;
  });
  return { animate, made };
}

function setup() {
  document.body.innerHTML = `
    <details class="qa"><summary><h3>Question one</h3></summary><p>Answer one.</p></details>
    <details class="qa" open><summary><h3>Question two</h3></summary><p>Answer two.</p></details>`;
  const [first, second] = [...document.querySelectorAll("details")] as HTMLDetailsElement[];
  return { first, second };
}

const originalAnimate = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "animate");

describe("bindFaqMotion (the FAQ's height animation where CSS can't do it)", () => {
  afterEach(() => {
    document.body.innerHTML = "";
    if (originalAnimate) Object.defineProperty(HTMLElement.prototype, "animate", originalAnimate);
    else delete (HTMLElement.prototype as Partial<HTMLElement>).animate;
  });

  it("opens at once (the answer is readable straight away) and animates the height", () => {
    const { animate, made } = fakeAnimate();
    HTMLElement.prototype.animate = animate as unknown as HTMLElement["animate"];
    const { first } = setup();
    const stop = bindFaqMotion(document);

    first.querySelector("summary")!.click();
    expect(first.open).toBe(true);
    expect(animate).toHaveBeenCalledOnce();
    expect(Object.keys(made[0].keyframes[0])).toEqual(["height"]);
    expect(first.style.overflow).toBe("hidden");
    made[0].animation.finish();
    expect(first.style.overflow).toBe("");
    stop();
  });

  it("closes only when the move ends, marking the item as closing meanwhile, and can reverse mid-move", () => {
    const { animate, made } = fakeAnimate();
    HTMLElement.prototype.animate = animate as unknown as HTMLElement["animate"];
    const { second } = setup();
    const stop = bindFaqMotion(document);

    const summary = second.querySelector("summary")!;
    summary.click();
    expect(second.open).toBe(true);
    expect(second).toHaveAttribute("data-closing");
    // A second click before it ends reopens it from where it is.
    summary.click();
    expect(second).not.toHaveAttribute("data-closing");
    expect(second.open).toBe(true);
    // Close again and let it finish.
    summary.click();
    made.at(-1)!.animation.finish();
    expect(second.open).toBe(false);
    expect(second).not.toHaveAttribute("data-closing");
    stop();
  });

  it("lets go of the summaries when stopped", () => {
    const { animate } = fakeAnimate();
    HTMLElement.prototype.animate = animate as unknown as HTMLElement["animate"];
    const { first } = setup();
    bindFaqMotion(document)();
    first.querySelector("summary")!.click();
    expect(animate).not.toHaveBeenCalled();
  });
});

"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";

import type { ScheduledPostSummary } from "@/lib/api/types";
import { canMove } from "@/lib/schedule/format";
import { cn } from "@/lib/utils";

/**
 * Drag to reschedule and drag drafts onto the calendar (FR-PUB-08), with pointer events as the
 * P4 automations list does, no library. A drag starts after the pointer travels a few pixels, so
 * a click still opens the post. Drop surfaces (the week and month grids) register a hit test; the
 * pointer is followed on window so a draft can travel from the rail to the grid. Esc cancels.
 * Touch never drags: phones and touch screens use "Move to…" (FR-PUB-08).
 */

/** Where a drop lands: a day, and minutes since midnight, or null to keep the post's time. */
export type DropTarget = { day: string; minutes: number | null };

export type DragSource = { post: ScheduledPostSummary; from: "calendar" | "rail" };

export type DropSurface = {
  hitTest: (x: number, y: number) => DropTarget | null;
  /** Scroll the surface when the pointer nears its edge. */
  edgeScroll?: (x: number, y: number) => void;
};

export type DragState = { source: DragSource; x: number; y: number; target: DropTarget | null };

const THRESHOLD_PX = 5;

type Store = {
  get: () => DragState | null;
  set: (next: DragState | null) => void;
  subscribe: (listener: () => void) => () => void;
};

function makeStore(): Store {
  let state: DragState | null = null;
  const listeners = new Set<() => void>();
  return {
    get: () => state,
    set: (next) => {
      state = next;
      for (const listener of listeners) listener();
    },
    subscribe: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}

type Actions = {
  store: Store;
  /** The card's or draft's onPointerDown. */
  pointerDown: (event: ReactPointerEvent<HTMLElement>, source: DragSource) => void;
  register: (surface: { current: DropSurface }) => () => void;
  /** True once right after a drag ended, so the link under the pointer does not open. */
  consumeClick: () => boolean;
  enabled: boolean;
};

const DndContext = createContext<Actions | null>(null);

type ProviderProps = {
  enabled: boolean;
  onDrop: (source: DragSource, target: DropTarget) => void;
  /** Someone tried to drag a post that can't move (published, publishing, failed). */
  onLocked: (post: ScheduledPostSummary) => void;
  /** What the floating label says while dragging, and whether that drop would be accepted. */
  describe: (source: DragSource, target: DropTarget | null) => { text: string; ok: boolean };
  children: ReactNode;
};

export function CalendarDndProvider({ enabled, onDrop, onLocked, describe, children }: ProviderProps) {
  const [store] = useState(makeStore);
  const surfaces = useRef(new Set<{ current: DropSurface }>());
  const suppress = useRef(false);
  const cleanup = useRef<(() => void) | null>(null);
  const callbacks = useRef({ onDrop, onLocked });
  useEffect(() => {
    callbacks.current = { onDrop, onLocked };
  });
  useEffect(() => () => cleanup.current?.(), []);

  const hitTest = useCallback((x: number, y: number): DropTarget | null => {
    for (const surface of surfaces.current) {
      const target = surface.current.hitTest(x, y);
      if (target) return target;
    }
    return null;
  }, []);

  const pointerDown = useCallback(
    (event: ReactPointerEvent<HTMLElement>, source: DragSource) => {
      if (!enabled || event.button !== 0 || event.pointerType === "touch") return;
      cleanup.current?.();
      const pointerId = event.pointerId;
      const startX = event.clientX;
      const startY = event.clientY;
      let started = false;

      const finish = () => {
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", up);
        window.removeEventListener("pointercancel", cancel);
        window.removeEventListener("keydown", key, true);
        cleanup.current = null;
        if (store.get()) store.set(null);
      };
      const endDrag = () => {
        suppress.current = true;
        window.setTimeout(() => {
          suppress.current = false;
        }, 0);
      };
      function move(e: PointerEvent) {
        if (e.pointerId !== pointerId) return;
        if (!started) {
          if (Math.hypot(e.clientX - startX, e.clientY - startY) < THRESHOLD_PX) return;
          if (!canMove(source.post)) {
            finish();
            endDrag();
            callbacks.current.onLocked(source.post);
            return;
          }
          started = true;
        }
        e.preventDefault();
        for (const surface of surfaces.current) surface.current.edgeScroll?.(e.clientX, e.clientY);
        store.set({ source, x: e.clientX, y: e.clientY, target: hitTest(e.clientX, e.clientY) });
      }
      function up(e: PointerEvent) {
        if (e.pointerId !== pointerId) return;
        const target = started ? (hitTest(e.clientX, e.clientY) ?? store.get()?.target ?? null) : null;
        finish();
        if (!started) return;
        endDrag();
        if (target) callbacks.current.onDrop(source, target);
      }
      function cancel(e: PointerEvent) {
        if (e.pointerId === pointerId) finish();
      }
      function key(e: KeyboardEvent) {
        if (e.key !== "Escape") return;
        e.stopPropagation();
        finish();
        if (started) endDrag();
      }
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", up);
      window.addEventListener("pointercancel", cancel);
      window.addEventListener("keydown", key, true);
      cleanup.current = finish;
    },
    [enabled, hitTest, store],
  );

  const register = useCallback((surface: { current: DropSurface }) => {
    surfaces.current.add(surface);
    return () => {
      surfaces.current.delete(surface);
    };
  }, []);

  const consumeClick = useCallback(() => {
    if (!suppress.current) return false;
    suppress.current = false;
    return true;
  }, []);

  const actions = useMemo<Actions>(
    () => ({ store, pointerDown, register, consumeClick, enabled }),
    [store, pointerDown, register, consumeClick, enabled],
  );

  return (
    <DndContext.Provider value={actions}>
      {children}
      <DragLabel store={store} describe={describe} />
    </DndContext.Provider>
  );
}

export function useCalendarDnd(): Actions {
  const actions = useContext(DndContext);
  if (!actions) throw new Error("useCalendarDnd must be used inside CalendarDndProvider");
  return actions;
}

/** A slice of the drag state; the component re-renders only when the slice changes. */
export function useDragSelector<T>(select: (state: DragState | null) => T): T {
  const { store } = useCalendarDnd();
  return useSyncExternalStore(
    store.subscribe,
    () => select(store.get()),
    () => select(null),
  );
}

/** Registers a drop surface for as long as the component is mounted. */
export function useDropSurface(surface: DropSurface): void {
  const { register } = useCalendarDnd();
  const ref = useRef(surface);
  useEffect(() => {
    ref.current = surface;
  });
  useEffect(() => register(ref), [register]);
}

/** "Wed 30 Sep 18:15" beside the pointer while dragging (UX-SCR-04: shows the new time). */
function DragLabel({
  store,
  describe,
}: {
  store: Store;
  describe: ProviderProps["describe"];
}) {
  const state = useSyncExternalStore(store.subscribe, store.get, () => null);
  if (!state) return null;
  const { text, ok } = describe(state.source, state.target);
  return (
    <div
      aria-hidden
      data-testid="drag-label"
      className={cn(
        "pointer-events-none fixed z-50 max-w-64 rounded-lg border px-2.5 py-1.5 text-xs font-medium tabular-nums shadow-xl",
        ok ? "border-brand-line bg-panel text-fg" : "border-danger bg-panel text-danger-fg",
      )}
      style={{ left: state.x + 14, top: state.y + 14 }}
    >
      {text}
    </div>
  );
}

"use client";

import type { Route } from "next";
import { useId, useRef, useState, type PointerEvent as ReactPointerEvent, type KeyboardEvent } from "react";

import type { Automation } from "@/lib/api/types";

import { AutomationRow, type RowReorder } from "./AutomationRow";

/** Move one id within the order (FR-AUT-15). */
export function moveId(ids: string[], from: number, to: number): string[] {
  const next = [...ids];
  const [id] = next.splice(from, 1);
  next.splice(Math.max(0, Math.min(to, next.length)), 0, id);
  return next;
}

type Drag = { id: string; from: number; pointerId: number; drop: number };

export type GroupActions = {
  href: (automation: Automation) => Route;
  selected: Set<string>;
  onSelectedChange: (id: string, selected: boolean) => void;
  onActiveChange: (automation: Automation, active: boolean) => void;
  pendingStatusId: string | null;
  onDuplicate: (automation: Automation) => void;
  onDelete: (automation: Automation) => void;
};

/**
 * One account's automations (UX-SCR-02 groups rows by account). In priority order the rows can
 * be dragged by their handle, or moved with the arrow keys on the handle or Move up / Move down
 * in the row menu (FR-AUT-15); either way the new order is saved for the account.
 */
export function AccountGroup({
  title,
  automations,
  timeZone,
  now,
  actions,
  onReorder,
}: {
  title: string;
  automations: Automation[];
  timeZone: string;
  now: Date;
  actions: GroupActions;
  /** Present when the rows show in priority order and can be reordered. */
  onReorder?: (orderedIds: string[]) => void;
}) {
  const hintId = useId();
  const headingId = useId();
  const rows = useRef(new Map<string, HTMLLIElement>());
  const [drag, setDrag] = useState<Drag | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const ids = automations.map((automation) => automation.id);
  const selecting = actions.selected.size > 0;

  const commit = (from: number, to: number) => {
    if (!onReorder || to === from || to < 0 || to >= ids.length) return;
    const moved = automations[from];
    onReorder(moveId(ids, from, to));
    setAnnouncement(`Moved ${moved.name} to position ${to + 1} of ${ids.length}.`);
  };

  /** The gap the pointer is over: 0 is above the first row, n below the last. */
  const dropIndexAt = (clientY: number): number => {
    for (let index = 0; index < ids.length; index += 1) {
      const rect = rows.current.get(ids[index])?.getBoundingClientRect();
      if (rect && clientY < rect.top + rect.height / 2) return index;
    }
    return ids.length;
  };

  const reorderFor = (automation: Automation, index: number): RowReorder | undefined => {
    if (!onReorder) return undefined;
    const dragging = drag?.id === automation.id;
    // The drop gap translated into this row's marker, hiding markers that would not move anything.
    const gap = drag ? drag.drop : -1;
    const noMove = drag ? gap === drag.from || gap === drag.from + 1 : true;
    const marker = !drag || noMove ? null : gap === index ? "before" : gap === ids.length && index === ids.length - 1 ? "after" : null;
    return {
      hintId,
      dragging,
      dropMarker: marker,
      canMoveUp: index > 0,
      canMoveDown: index < ids.length - 1,
      onMove: (direction) => commit(index, index + direction),
      handleProps: {
        onKeyDown: (event: KeyboardEvent<HTMLButtonElement>) => {
          if (event.key === "ArrowUp" || event.key === "ArrowDown") {
            event.preventDefault();
            commit(index, index + (event.key === "ArrowUp" ? -1 : 1));
          }
        },
        onPointerDown: (event: ReactPointerEvent<HTMLButtonElement>) => {
          if (event.button !== 0) return;
          event.currentTarget.setPointerCapture?.(event.pointerId);
          setDrag({ id: automation.id, from: index, pointerId: event.pointerId, drop: index });
        },
        onPointerMove: (event: ReactPointerEvent<HTMLButtonElement>) => {
          if (!drag || drag.pointerId !== event.pointerId) return;
          const drop = dropIndexAt(event.clientY);
          if (drop !== drag.drop) setDrag({ ...drag, drop });
        },
        onPointerUp: (event: ReactPointerEvent<HTMLButtonElement>) => {
          if (!drag || drag.pointerId !== event.pointerId) return;
          const to = drag.drop > drag.from ? drag.drop - 1 : drag.drop;
          setDrag(null);
          commit(drag.from, to);
        },
        onPointerCancel: () => setDrag(null),
      },
    };
  };

  return (
    <section aria-labelledby={headingId} className="space-y-2">
      <h2 id={headingId} className="flex items-center gap-2 text-sm font-semibold">
        {title}
        <span className="text-xs font-normal text-fg-secondary tabular-nums">{automations.length}</span>
      </h2>
      {onReorder ? (
        <p id={hintId} className="sr-only">
          Drag, or press the up and down arrow keys, to change which automation runs first.
        </p>
      ) : null}
      <ul className="space-y-2">
        {automations.map((automation, index) => (
          <AutomationRow
            key={automation.id}
            rowRef={(node) => {
              if (node) rows.current.set(automation.id, node);
              else rows.current.delete(automation.id);
            }}
            automation={automation}
            href={actions.href(automation)}
            timeZone={timeZone}
            now={now}
            selected={actions.selected.has(automation.id)}
            selecting={selecting}
            onSelectedChange={(value) => actions.onSelectedChange(automation.id, value)}
            onActiveChange={(value) => actions.onActiveChange(automation, value)}
            statusPending={actions.pendingStatusId === automation.id}
            onDuplicate={() => actions.onDuplicate(automation)}
            onDelete={() => actions.onDelete(automation)}
            reorder={reorderFor(automation, index)}
          />
        ))}
      </ul>
      <p role="status" aria-live="polite" className="sr-only">
        {announcement}
      </p>
    </section>
  );
}

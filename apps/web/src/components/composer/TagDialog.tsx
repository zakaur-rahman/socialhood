"use client";

import { Trash2 } from "lucide-react";
import { useRef, useState, type KeyboardEvent, type PointerEvent as ReactPointerEvent } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { normalizeUsername, USER_TAGS_MAX_PER_IMAGE, type AssetInfo } from "@/lib/publishing/rules";

export type TagPoint = { username: string; x: number; y: number };

const KEY_STEP = 0.02;
const clamp = (value: number) => Math.min(1, Math.max(0, value));

/** Where a pointer is on an element, as fractions of its width and height from the top left. */
export function fractionAt(rect: Pick<DOMRect, "left" | "top" | "width" | "height">, clientX: number, clientY: number) {
  if (rect.width <= 0 || rect.height <= 0) return { x: 0.5, y: 0.5 };
  return { x: clamp((clientX - rect.left) / rect.width), y: clamp((clientY - rect.top) / rect.height) };
}

/**
 * FR-PUB-07 user tags: tap the photo to place a tag, type the account's username, drag the
 * marker (or press the arrow keys on it) to move it, remove it with the bin. Positions are
 * fractions of the photo's width and height, as Instagram takes them. A tag without a valid
 * username can't be saved.
 */
export function TagDialog({
  open,
  onOpenChange,
  asset,
  label,
  tags,
  onSave,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  asset: AssetInfo;
  /** "Photo 2" */
  label: string;
  tags: TagPoint[];
  onSave: (tags: TagPoint[]) => void;
}) {
  const [items, setItems] = useState<TagPoint[]>(tags);
  const [selected, setSelected] = useState<number | null>(null);
  const stage = useRef<HTMLDivElement>(null);
  const drag = useRef<{ pointerId: number; index: number; moved: boolean } | null>(null);

  const invalid = items.some((item) => normalizeUsername(item.username) === null);
  const full = items.length >= USER_TAGS_MAX_PER_IMAGE;

  const place = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (drag.current || full || !stage.current) return;
    const point = fractionAt(stage.current.getBoundingClientRect(), event.clientX, event.clientY);
    setItems((current) => [...current, { username: "", ...point }]);
    setSelected(items.length);
  };

  const move = (index: number, x: number, y: number) =>
    setItems((current) => current.map((item, position) => (position === index ? { ...item, x: clamp(x), y: clamp(y) } : item)));

  const onMarkerDown = (event: ReactPointerEvent<HTMLButtonElement>, index: number) => {
    event.stopPropagation();
    event.currentTarget.setPointerCapture?.(event.pointerId);
    drag.current = { pointerId: event.pointerId, index, moved: false };
    setSelected(index);
  };

  const onMarkerMove = (event: ReactPointerEvent<HTMLButtonElement>) => {
    const current = drag.current;
    if (!current || current.pointerId !== event.pointerId || !stage.current) return;
    current.moved = true;
    const point = fractionAt(stage.current.getBoundingClientRect(), event.clientX, event.clientY);
    move(current.index, point.x, point.y);
  };

  const onMarkerUp = (event: ReactPointerEvent<HTMLButtonElement>) => {
    if (drag.current?.pointerId === event.pointerId) drag.current = null;
  };

  const onMarkerKey = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const moves: Record<string, [number, number]> = {
      ArrowLeft: [-KEY_STEP, 0],
      ArrowRight: [KEY_STEP, 0],
      ArrowUp: [0, -KEY_STEP],
      ArrowDown: [0, KEY_STEP],
    };
    const step = moves[event.key];
    if (!step) return;
    event.preventDefault();
    move(index, items[index].x + step[0], items[index].y + step[1]);
  };

  const remove = (index: number) => {
    setItems((current) => current.filter((_, position) => position !== index));
    setSelected(null);
  };

  const save = () => {
    onSave(items.map((item) => ({ ...item, username: normalizeUsername(item.username) ?? item.username })));
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Tag people in {label}</DialogTitle>
          <DialogDescription>
            Tap the photo where someone appears, then type their Instagram username. Drag a tag to move it. Up to{" "}
            {USER_TAGS_MAX_PER_IMAGE} tags.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_220px]">
          <div
            ref={stage}
            data-testid="tag-stage"
            role="group"
            aria-label={`${label}. Tap to place a tag.`}
            className="relative cursor-crosshair touch-none select-none overflow-hidden rounded-lg bg-pressed"
            onPointerDown={place}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={asset.thumbnail_url ?? asset.url} alt="" draggable={false} className="block w-full" />
            {items.map((item, index) => (
              <button
                key={index}
                type="button"
                aria-label={`Tag ${index + 1}${item.username ? `: @${item.username}` : ""}. Arrow keys move it.`}
                data-testid={`tag-marker-${index}`}
                data-x={item.x.toFixed(3)}
                data-y={item.y.toFixed(3)}
                className={
                  "absolute size-6 -translate-x-1/2 -translate-y-1/2 touch-none cursor-grab rounded-full border-2 border-on-brand bg-brand text-2xs font-medium text-on-brand " +
                  (selected === index ? "ring-2 ring-brand" : "")
                }
                style={{ left: `${item.x * 100}%`, top: `${item.y * 100}%` }}
                onPointerDown={(event) => onMarkerDown(event, index)}
                onPointerMove={onMarkerMove}
                onPointerUp={onMarkerUp}
                onPointerCancel={onMarkerUp}
                onKeyDown={(event) => onMarkerKey(event, index)}
                onFocus={() => setSelected(index)}
              >
                {index + 1}
              </button>
            ))}
          </div>
          <ul aria-label="Tags" className="space-y-2">
            {items.length === 0 ? <li className="text-sm text-fg-secondary">No tags yet.</li> : null}
            {items.map((item, index) => {
              const bad = item.username !== "" && normalizeUsername(item.username) === null;
              return (
                <li key={index} className="flex items-center gap-1">
                  <span className="w-5 text-xs text-fg-secondary tabular-nums">{index + 1}</span>
                  <Input
                    value={item.username}
                    aria-label={`Username for tag ${index + 1}`}
                    aria-invalid={bad || undefined}
                    placeholder="username"
                    maxLength={31}
                    autoFocus={selected === index && item.username === ""}
                    onFocus={() => setSelected(index)}
                    onChange={(event) =>
                      setItems((current) => current.map((tag, position) => (position === index ? { ...tag, username: event.target.value.replace(/^@+/, "") } : tag)))
                    }
                  />
                  <Button type="button" variant="ghost" size="icon-sm" aria-label={`Remove tag ${index + 1}`} onClick={() => remove(index)}>
                    <Trash2 className="size-3.5" aria-hidden />
                  </Button>
                </li>
              );
            })}
          </ul>
        </div>
        {invalid ? (
          <p role="alert" className="text-sm text-danger-fg">
            Every tag needs an Instagram username: letters, numbers, periods and underscores.
          </p>
        ) : null}
        <DialogFooter>
          <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="button" disabled={invalid} onClick={save}>
            Save tags
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

"use client";

import { AlertCircle } from "lucide-react";
import { useRef, useState, type KeyboardEvent, type PointerEvent as ReactPointerEvent } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { CROP_RATIOS, CropError, cropRect, focusOf, moveFocus, suggestedRatio, type Cropper, type CropRatio, type CropSource } from "@/lib/publishing/crop";
import type { AssetInfo } from "@/lib/publishing/rules";

const KEY_STEP = 0.02;

/**
 * The crop tool (TR-MED-02): choose 1:1, 4:5 or 1.91:1 and move the frame by dragging or with
 * the arrow keys. The cropped copy uploads as a new file and takes the photo's place.
 */
export function CropDialog({
  open,
  onOpenChange,
  asset,
  label,
  source,
  cropper,
  onCropped,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  asset: AssetInfo;
  /** "Photo 2" */
  label: string;
  source: CropSource;
  cropper: Cropper;
  onCropped: (file: File) => void;
}) {
  const [size, setSize] = useState<{ width: number; height: number } | null>(
    asset.width && asset.height ? { width: asset.width, height: asset.height } : null,
  );
  const [ratio, setRatio] = useState<CropRatio>(() => (size ? suggestedRatio(size.width, size.height) : CROP_RATIOS[0]));
  const [focus, setFocus] = useState({ x: 0.5, y: 0.5 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const stage = useRef<HTMLDivElement>(null);
  const dragStart = useRef<{ pointerId: number; x: number; y: number; focus: { x: number; y: number } } | null>(null);

  const rect = size ? cropRect(size.width, size.height, ratio.value, focus) : null;

  const changeRatio = (key: string) => {
    const next = CROP_RATIOS.find((option) => option.key === key);
    if (!next) return;
    // Keep the frame centred where it was.
    if (size && rect) setFocus(focusOf(rect, size.width, size.height));
    setRatio(next);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const moves: Record<string, [number, number]> = {
      ArrowLeft: [-KEY_STEP, 0],
      ArrowRight: [KEY_STEP, 0],
      ArrowUp: [0, -KEY_STEP],
      ArrowDown: [0, KEY_STEP],
    };
    const move = moves[event.key];
    if (!move || !size || !rect) return;
    event.preventDefault();
    // Start from where the frame is, so a move against an edge takes effect at once.
    setFocus(moveFocus(focusOf(rect, size.width, size.height), move[0], move[1]));
  };

  const onPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 || !size || !rect) return;
    event.currentTarget.setPointerCapture?.(event.pointerId);
    dragStart.current = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, focus: focusOf(rect, size.width, size.height) };
  };

  const onPointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const start = dragStart.current;
    const box = stage.current?.getBoundingClientRect();
    if (!start || start.pointerId !== event.pointerId || !box?.width || !box.height) return;
    setFocus(moveFocus(start.focus, (event.clientX - start.x) / box.width, (event.clientY - start.y) / box.height));
  };

  const apply = async () => {
    if (!rect) return;
    setBusy(true);
    setError(null);
    try {
      const file = await cropper(source, rect, ratio);
      onCropped(file);
      onOpenChange(false);
    } catch (caught) {
      setError(caught instanceof CropError ? caught.message : "This image can't be cropped here. Crop it on your device and upload it again.");
    } finally {
      setBusy(false);
    }
  };

  const aspect = size ? size.width / size.height : 1;

  return (
    <Dialog open={open} onOpenChange={(next) => !busy && onOpenChange(next)}>
      <DialogContent size="lg">
        <DialogHeader>
          <DialogTitle>Crop {label}</DialogTitle>
          <DialogDescription>
            Instagram shows photos from 4:5 to 1.91:1. Choose a shape, then drag the frame or use the arrow keys.
          </DialogDescription>
        </DialogHeader>
        <ToggleGroup value={ratio.key} onValueChange={changeRatio} aria-label="Shape">
          {CROP_RATIOS.map((option) => (
            <ToggleGroupItem key={option.key} value={option.key}>
              {option.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        <div
          ref={stage}
          className="relative mx-auto w-full overflow-hidden rounded-lg bg-field"
          style={{ aspectRatio: `${aspect}`, maxWidth: `min(100%, calc(360px * ${aspect}))` }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element -- the photo being cropped */}
          <img
            src={source.url}
            alt=""
            className="size-full object-cover select-none"
            draggable={false}
            onLoad={(event) => {
              const { naturalWidth, naturalHeight } = event.currentTarget;
              if (naturalWidth && naturalHeight && (!size || size.width !== naturalWidth || size.height !== naturalHeight)) {
                setSize({ width: naturalWidth, height: naturalHeight });
              }
            }}
          />
          {rect && size ? (
            <div
              role="group"
              tabIndex={0}
              aria-label={`Crop frame, ${ratio.label}. Use the arrow keys to move it.`}
              data-testid="crop-frame"
              data-rect={`${rect.x},${rect.y},${rect.width},${rect.height}`}
              onKeyDown={onKeyDown}
              onPointerDown={onPointerDown}
              onPointerMove={onPointerMove}
              onPointerUp={() => {
                dragStart.current = null;
              }}
              onPointerCancel={() => {
                dragStart.current = null;
              }}
              // The stage clips, so the focus outline is drawn inset, over the frame's own edge.
              className="absolute cursor-move touch-none rounded-sm border-2 border-fg shadow-crop-mask focus-visible:-outline-offset-2"
              style={{
                left: `${(rect.x / size.width) * 100}%`,
                top: `${(rect.y / size.height) * 100}%`,
                width: `${(rect.width / size.width) * 100}%`,
                height: `${(rect.height / size.height) * 100}%`,
              }}
            />
          ) : null}
        </div>
        {error ? (
          <p role="alert" className="flex items-start gap-1.5 text-sm text-danger-fg">
            <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden /> {error}
          </p>
        ) : null}
        <DialogFooter>
          <Button type="button" variant="ghost" onClick={() => onOpenChange(false)} disabled={busy}>
            Cancel
          </Button>
          <Button type="button" onClick={() => void apply()} disabled={!rect || busy}>
            {busy ? <Spinner /> : null}
            Crop and upload
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

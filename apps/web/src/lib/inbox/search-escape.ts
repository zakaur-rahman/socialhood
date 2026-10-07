/**
 * Esc in a search field inside a Radix popover (the composer's emoji picker). SearchInput clears
 * a field that has text on Esc, but Radix listens for Esc on the document in the capture phase, so
 * the popover would close before the field saw the key. Pass this as the popover content's
 * `onEscapeKeyDown`: while the focused search field has text, Esc empties it (through the field's
 * own `input` event, so React's onChange sees "") and the popover stays open; the next Esc closes it.
 */
export function clearSearchOnEscape(event: KeyboardEvent): void {
  const field = event.target;
  if (!(field instanceof HTMLInputElement) || field.type !== "search" || field.value === "") return;
  event.preventDefault();
  const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  setValue?.call(field, "");
  field.dispatchEvent(new Event("input", { bubbles: true }));
}

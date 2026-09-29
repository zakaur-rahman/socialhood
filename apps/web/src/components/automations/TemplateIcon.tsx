import { createElement } from "react";
import {
  BookOpen,
  CalendarCheck,
  CircleHelp,
  Gift,
  Link,
  MessageCircle,
  Send,
  ShoppingBag,
  Sparkles,
  Tag,
  Zap,
  type LucideIcon,
} from "lucide-react";

// Templates name a lucide icon (FR-AUT-12); only these are bundled, anything else shows the zap.
const ICONS: Record<string, LucideIcon> = {
  bookopen: BookOpen,
  calendar: CalendarCheck,
  calendarcheck: CalendarCheck,
  circlehelp: CircleHelp,
  helpcircle: CircleHelp,
  messagecirclequestion: CircleHelp,
  gift: Gift,
  link: Link,
  link2: Link,
  messagecircle: MessageCircle,
  send: Send,
  shoppingbag: ShoppingBag,
  sparkles: Sparkles,
  tag: Tag,
  zap: Zap,
};

export function templateIcon(name: string): LucideIcon {
  return ICONS[name.toLowerCase().replace(/[^a-z0-9]/g, "")] ?? Zap;
}

export function TemplateIcon({ name, className }: { name: string; className?: string }) {
  // A lookup, not a new component: createElement keeps the static-components rule satisfied.
  return createElement(templateIcon(name), { "aria-hidden": true, className });
}

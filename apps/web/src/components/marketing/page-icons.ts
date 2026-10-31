import {
  BellRing,
  BookOpenText,
  CalendarClock,
  CalendarDays,
  ChartLine,
  Clock,
  Compass,
  Code,
  FileText,
  EyeOff,
  Hash,
  Images,
  Inbox,
  Layers,
  LayoutGrid,
  LifeBuoy,
  ListFilter,
  type LucideIcon,
  Megaphone,
  MessageCircleQuestionMark,
  MessageSquareReply,
  MessageSquareText,
  Plug,
  QrCode,
  Radio,
  Receipt,
  Repeat2,
  Scale,
  SearchX,
  ShieldAlert,
  ShieldCheck,
  ShoppingBag,
  SlidersHorizontal,
  Smartphone,
  Sparkles,
  SpellCheck,
  SplitSquareVertical,
  Tags,
  TrendingUp,
  UserRoundPlus,
  UsersRound,
  Workflow,
} from "lucide-react";

import { SITE_NAME } from "@/lib/marketing/site";

/**
 * The icons on the inner pages' cards (C-159), by the card's title, in the landing's icon language
 * (C-157 motion: lucide, 20 px, stroke 1.75, in an `.ico` tile). Kept out of the content files
 * (gtm-pages.ts, solutions.ts, faq.ts) so the words stay where they are checked. A title without an
 * entry falls back to its block's icon, then to a neutral mark; the unit test lists every title so a
 * new card can't ship without one.
 */
export const CARD_ICONS: Record<string, LucideIcon> = {
  // Switch from Manychat
  "Comment-to-DM automations": MessageSquareReply,
  "DM keywords and story replies": MessageSquareText,
  "Flows with questions and branches": Workflow,
  "Contacts, tags and fields": Tags,
  "Ways in beyond comments": QrCode,
  "Team inbox": UsersRound,
  "Connect your other tools": Plug,
  "AI that answers from your knowledge": BookOpenText,
  "Comment analysis for every post": ChartLine,
  "Publishing in the same app": CalendarClock,
  "Flat plans": Layers,
  "No free-form canvas": SplitSquareVertical,
  "Instagram and WhatsApp first": Smartphone,
  "Triggers we don't have": EyeOff,
  "WhatsApp broadcasts are coming soon": Megaphone,
  // Comment intelligence
  "Reads every comment": MessageSquareText,
  "Summarises each post": ListFilter,
  "Sorts posts by what needs you": LayoutGrid,
  "Acts from one page": MessageSquareReply,
  "Filters that find the work": SlidersHorizontal,
  "You stay in charge": ShieldCheck,
  // The AI inbox
  "One list for every channel": Inbox,
  "Every message read and tagged": Tags,
  "Summaries and AI polish": SpellCheck,
  "You choose how much the AI does": Sparkles,
  "Only your knowledge": BookOpenText,
  "Escalation you can rely on": ShieldAlert,
  "Questions it couldn't answer": MessageCircleQuestionMark,
  "Assign, save replies, set hours": UsersRound,
  [`Ask ${SITE_NAME}`]: MessageCircleQuestionMark,
  // Publishing
  "Images, carousels, Reels and Stories": Images,
  "A calendar and a queue": CalendarDays,
  "AI captions and hashtags": Hash,
  "A media library": Layers,
  "Best posting times": Clock,
  "Hashtag groups": Tags,
  "Collaborators, tags and a first comment": UserRoundPlus,
  // For creators
  "Comment-to-DM for link drops": MessageSquareReply,
  "Tap first, and a follow invite after": UsersRound,
  "Story replies and mentions": MessageSquareText,
  "Scheduling, Reels and Stories": CalendarClock,
  "AI replies from your own notes": BookOpenText,
  "Comment analysis": ChartLine,
  "Live comments": Radio,
  // For businesses
  "One inbox, with your team": Inbox,
  "AI from your knowledge, with hand-off": BookOpenText,
  "Lead scoring": TrendingUp,
  "Catalogue, orders and payment links": ShoppingBag,
  "Automations and follow-ups": Repeat2,
  Reports: ChartLine,
};

/** The titles whose card is an AI moment: their tile takes iris (C-157: iris only for AI). */
export const AI_TITLES = new Set([`Ask ${SITE_NAME}`, "You choose how much the AI does"]);

/** The verdict cards on a comparison ("Which fits you"): the competitor's, then ours. */
export const VERDICT_ICONS = { theirs: Compass, ours: Scale } as const;

/** The /faq groups (lib/marketing/faq.ts FAQ_GROUPS ids). */
export const FAQ_GROUP_ICONS: Record<string, LucideIcon> = {
  "the-ai": Sparkles,
  "instagram-and-whatsapp": MessageSquareText,
  plans: Receipt,
  "the-app": LifeBuoy,
};

/** The pricing page's limit groups (lib/marketing/plan-matrix.ts MATRIX ids). */
export const MATRIX_GROUP_ICONS: Record<string, LucideIcon> = {
  accounts: UsersRound,
  ai: Sparkles,
  automation: Workflow,
  whatsapp: ShoppingBag,
  publishing: CalendarClock,
  developers: Plug,
};

/** The "how we compare" rules on the /compare hub, in order. */
export const HOW_WE_COMPARE_ICONS: LucideIcon[] = [FileText, CalendarDays, Code, SearchX];

/** A card's icon: its own, else the fallback. */
export function cardIcon(title: string, fallback: LucideIcon = BellRing): LucideIcon {
  return CARD_ICONS[title] ?? fallback;
}

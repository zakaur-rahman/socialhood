import {
  AlertTriangle,
  ArrowLeft,
  Calendar,
  CalendarClock,
  Check,
  ChevronDown,
  CircleCheck,
  Clock,
  CornerDownLeft,
  EllipsisVertical,
  Keyboard,
  Layers,
  LifeBuoy,
  LoaderCircle,
  Menu,
  PanelRight,
  Paperclip,
  Pencil,
  RefreshCw,
  Search,
  SendHorizontal,
  Smile,
  Sparkles,
  Sticker,
  UserPlus,
  X,
  Zap,
} from "lucide-react";
import type { CSSProperties, ReactNode } from "react";

import { PLATFORM_LOGO_BG, PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { NAV_GROUPS, SETTINGS_NAV } from "@/components/shell/nav";
import { MotionToggle } from "@/components/site/MotionToggle";
import type { Platform } from "@/lib/api/types";
import { PLATFORM_LABEL } from "@/lib/inbox/format";

import { DEFAULT_KEYWORD, DM_SCRIPT, SOURCES } from "./data";

/*
 * C-175: a replica of the signed-in inbox, playing one story. Recreated as markup with the app's own
 * labels, sizes and colours (no app component on the marketing page): AppSidebar and nav.ts,
 * PlatformStrip (All and each connected platform), ListHeader (Chats | Scheduled, search, the account
 * Select, the view chips), ConversationRow and rowBadges, ThreadHeader, MessageBubble, AnalysisChips,
 * SuggestionCard, Composer and SchedulePanel, ThreadView's ScheduledChip, ScheduledCard, the toast, and
 * services/automations/actions.py (tap first). docs/CONFLICTS.md C-175 lists where it still differs.
 */

export const PRODUCT_DEMO_ID = "product-demo";
export const PRODUCT_DEMO_TITLE = "See a day in your inbox";
export const PRODUCT_DEMO_NOTE = "Example, with made-up data";
/** plans.py accounts_per_platform: Free and Creator 1, Business 3. */
export const PRODUCT_DEMO_PLAN_NOTE = "Two accounts on one platform need the Business plan.";

export const PRODUCT_DEMO_STEPS = [
  "A DM arrives",
  "The AI reads it and drafts",
  "You stay in control",
  "Schedule a message",
  "Switch platform and account",
  "A comment becomes a DM",
  "The tricky one comes to you",
];

/** What the scene shows, for screen readers (the scene itself is a picture, and it moves). */
export const PRODUCT_DEMO_LABEL = `Example: a new Instagram message arrives in an inbox that also holds WhatsApp and website chat. The AI tags its intent and lead score, then drafts a reply from the cafe's menu. You press Send, and the conversation shows your reply. You write another message and schedule it for later today, inside the reply window, and it waits on the Scheduled tab. You filter the list to Instagram, switch between two Instagram accounts, then go to WhatsApp and back to all. Next, someone comments ${DEFAULT_KEYWORD} on a Reel: an automation opens a DM with a button, and sends the link once they tap it. Then a customer on WhatsApp asks to talk to a person: the AI doesn't reply, and the conversation is marked Needs you.`;

const MUMBAI = "@cafe_mumbai";
const PUNE = "@cafe_pune";
const QUESTION = "Do you have oat milk?";
const DRAFT = "Yes, oat milk is available on every coffee, for $1 extra. Shall I send you the menu?";
const LATER = "We're open until 9 tonight. See you soon!";
const WHEN = "Today 18:30";
const LINK_LINE = "Here's the new menu.";
const AUTOMATION = "New menu Reel";
const PERSON = "Can I talk to a person?";

/** The app's list chips (ListHeader CHIP_VIEWS), in its order. */
export const PRODUCT_DEMO_CHIPS = ["All", "Unread", "Needs reply", "Needs you", "Assigned to me", "Leads", "Handled by AI", "Archived"];
/** The strip shows connected platforms only (InboxShell), so no Facebook here. */
const STRIP: { key: "all" | Platform; label: string }[] = [
  { key: "all", label: "All" },
  { key: "instagram", label: PLATFORM_LABEL.instagram },
  { key: "whatsapp", label: PLATFORM_LABEL.whatsapp },
  { key: "web", label: PLATFORM_LABEL.web },
];

/** Row heights, as ConversationRow's: two lines, or three with badges. */
const ROW_SHORT = 68;
const ROW_TALL = 90;

/** Each moving part has a name (`data-p`), which landing-motion.ts's timeline turns on and off. */
const part = (name: string) => ({ "data-p": name });
/** Something the pointer goes to (`data-at`). */
const at = (name: string) => ({ "data-at": name });

function Avatar({ name, shade, platform, size = 40 }: { name: string; shade: number; platform?: Platform; size?: 24 | 32 | 40 }) {
  return (
    <span className={`pd-av pd-av-${size}`} style={{ "--bg": `var(--av-${shade})` } as CSSProperties}>
      {name.charAt(0).toUpperCase()}
      {platform ? (
        <span className={`pd-mark ${PLATFORM_LOGO_BG[platform]}`}>
          <PlatformGlyph platform={platform} />
        </span>
      ) : null}
    </span>
  );
}

type RowData = { id: string; name: string; shade: number; platform: Platform; ago: string; tall?: boolean; unread?: boolean; text: ReactNode; badges?: ReactNode };

const ROWS: RowData[] = [
  {
    id: "sam",
    name: "Sam K.",
    shade: 4,
    platform: "whatsapp",
    ago: "now",
    tall: true,
    unread: true,
    text: <span>{PERSON}</span>,
    badges: (
      <>
        <span className="pd-b pd-b-danger" {...part("sam-row-need")}>Needs you</span>
        <span className="pd-b" {...part("sam-row-auto")}>Auto replies</span>
      </>
    ),
  },
  {
    id: "ana",
    name: "ana.wears",
    shade: 5,
    platform: "instagram",
    ago: "now",
    text: (
      <>
        <span className="pd-before" {...part("ana-row-open")}>Automation: {DM_SCRIPT.opener}</span>
        <span {...part("ana-row-link")}>Automation: {LINK_LINE}</span>
      </>
    ),
  },
  {
    id: "maya",
    name: "Maya R.",
    shade: 2,
    platform: "instagram",
    ago: "now",
    tall: true,
    text: (
      <>
        <span className="pd-before" {...part("maya-row-q")}>{QUESTION}</span>
        <span {...part("maya-row-you")}>You: {DRAFT}</span>
      </>
    ),
    badges: <span className="pd-b pd-b-brand" {...part("maya-lead")}>Lead 72/100</span>,
  },
  { id: "theo", name: "Theo", shade: 6, platform: "instagram", ago: "12m", unread: true, text: <span>Are you open late on Friday?</span> },
  { id: "nina", name: "Nina", shade: 3, platform: "whatsapp", ago: "26m", unread: true, text: <span>What time do you open on Sunday?</span> },
  { id: "ria", name: "Ria", shade: 1, platform: "instagram", ago: "34m", text: <span>You: See you on Saturday!</span> },
  { id: "lena", name: "Lena", shade: 5, platform: "instagram", ago: "38m", text: <span>Can I book a table for six?</span> },
  { id: "leo", name: "Leo M.", shade: 4, platform: "whatsapp", ago: "41m", text: <span>You: Your pickup is ready.</span> },
  { id: "visitor", name: "Visitor", shade: 1, platform: "web", ago: "52m", text: <span>Do you take bulk orders?</span> },
];

function Row({ row, y }: { row: RowData; y: number }) {
  return (
    <li
      className={row.unread ? "pd-row pd-unread" : "pd-row"}
      data-row={row.id}
      {...part(`row-${row.id}`)}
      {...at(`row-${row.id}`)}
      style={{ "--y": `${y}px`, "--h": `${row.tall ? ROW_TALL : ROW_SHORT}px` } as CSSProperties}
    >
      <span className="pd-sel pd-before" {...part(`sel-${row.id}`)} />
      <Avatar name={row.name} shade={row.shade} platform={row.platform} />
      <span className="pd-row-main">
        <span className="pd-row-top">
          <b>{row.name}</b>
          <time className="num">{row.ago}</time>
        </span>
        <span className="pd-row-line">
          <span className="pd-swap pd-row-text">{row.text}</span>
          {row.id === "maya" ? <i className="pd-unread-dot pd-before" {...part("maya-dot")} /> : row.unread ? <i className="pd-unread-dot" /> : null}
        </span>
        {row.badges ? <span className="pd-badges">{row.badges}</span> : null}
      </span>
    </li>
  );
}

const rowHeight = (row: RowData) => (row.tall ? ROW_TALL : ROW_SHORT);

function RowList() {
  return (
    <ol className="pd-rows">
      {ROWS.map((row, i) => (
        <Row key={row.id} row={row} y={ROWS.slice(0, i).reduce((sum, above) => sum + rowHeight(above), 0)} />
      ))}
    </ol>
  );
}

/** AppSidebar: the floating card, expanded where the app expands it in the inbox (from 1280 px), else icons. */
function Sidebar() {
  return (
    <div className="pd-side">
      <div className="pd-side-top">
        <span className="pd-logo bg-shell-gradient" />
        <span className="pd-side-text pd-side-brand">
          <b>Amplychat</b>
          <small>Cafe</small>
        </span>
      </div>
      <div className="pd-ask">
        <span className="pd-ask-ico">
          <Sparkles className="size-4" />
        </span>
        <span className="pd-side-text">
          <b>Ask Amplychat</b>
          <small>Your AI assistant</small>
        </span>
      </div>
      <div className="pd-side-nav">
        {NAV_GROUPS.map((group) => (
          <div key={group.key}>
            {group.label ? <p className="pd-side-label">{group.label}</p> : null}
            {group.items.map(({ key, label, icon: Icon }) => (
              <span key={key} className={key === "inbox" ? "pd-side-row pd-side-on" : "pd-side-row"}>
                <Icon className="size-4.5" />
                <span className="pd-side-text">{label}</span>
              </span>
            ))}
          </div>
        ))}
      </div>
      <div className="pd-side-foot">
        <span className="pd-side-row">
          <SETTINGS_NAV.icon className="size-4.5" />
          <span className="pd-side-text">{SETTINGS_NAV.label}</span>
        </span>
        <span className="pd-side-row">
          <LifeBuoy className="size-4.5" />
          <span className="pd-side-text">Help</span>
        </span>
      </div>
    </div>
  );
}

/** ListHeader's account Select: it shows only on a platform with more than one account (InboxShell). */
function AccountSelect() {
  return (
    <span className="pd-acct">
      <span className="pd-field pd-acct-trigger" {...at("acct")}>
        <span className="pd-swap">
          <span data-acct-show="all">All accounts</span>
          <span data-acct-show="mumbai">{MUMBAI}</span>
          <span data-acct-show="pune">{PUNE}</span>
        </span>
        <ChevronDown className="size-4" />
      </span>
      <span className="pd-pop pd-menu pd-float" {...part("menu")}>
        <span className="pd-opt" data-opt="all">All accounts<Check className="size-4" /></span>
        <span className="pd-opt" data-opt="mumbai" {...at("opt-mumbai")}>{MUMBAI}<Check className="size-4" /></span>
        <span className="pd-opt" data-opt="pune" {...at("opt-pune")}>{PUNE}<Check className="size-4" /></span>
      </span>
    </span>
  );
}

function ListPane() {
  return (
    <div className="pd-list">
      <div className="pd-strip">
        <div className="pd-track">
          {STRIP.map(({ key, label }) => (
            <span key={key} className="pd-seg" data-seg={key} {...at(`seg-${key}`)}>
              {key === "all" ? <Layers className="size-3.5" /> : <i className={PLATFORM_LOGO_BG[key]} />}
              <span className="pd-seg-t">{label}</span>
            </span>
          ))}
        </div>
      </div>
      <div className="pd-list-h">
        <div className="pd-list-title">
          <b>Inbox</b>
          <span className="pd-list-tools">
            <Keyboard className="size-4 pd-tool" />
            <span className="pd-track pd-tabs">
              <span className="pd-seg" data-tab-seg="chats" {...at("tab-chats")}>Chats</span>
              <span className="pd-seg" data-tab-seg="scheduled" {...at("tab-scheduled")}>
                Scheduled
                <i className="pd-count" {...part("tab-count")}>1</i>
              </span>
            </span>
          </span>
        </div>
      </div>
      <div className="pd-panel-stack">
        <div className="pd-panel pd-panel-chats">
          <div className="pd-list-filters">
            <div className="pd-search">
              <span className="pd-field pd-search-f">
                <Search className="size-4" />
                Search
              </span>
              <AccountSelect />
            </div>
            <div className="pd-chips-row">
              {PRODUCT_DEMO_CHIPS.map((chip) => (
                <span key={chip} className={chip === "All" ? "pd-chip pd-chip-on" : "pd-chip"}>
                  {chip}
                  {chip === "Needs you" ? <i className="pd-count" {...part("need-count")}>1</i> : null}
                </span>
              ))}
            </div>
          </div>
          <RowList />
        </div>
        <div className="pd-panel pd-panel-sched">
          <article className="pd-card">
            <span className="pd-card-top">
              <Avatar name="Maya R." shade={2} size={32} />
              <span>
                <b>
                  Maya R.
                  <PlatformGlyph platform="instagram" className="size-3.5" />
                </b>
                <span className="pd-card-text">{LATER}</span>
              </span>
            </span>
            <span className="pd-card-foot">
              <span className="pd-b pd-b-md num">{WHEN}</span>
              <span className="pd-b pd-b-md pd-b-brand">Scheduled</span>
              <span className="pd-card-acts">
                <span className="pd-btn pd-btn-sm">Edit</span>
                <span className="pd-btn pd-btn-sm pd-btn-danger">Cancel</span>
              </span>
            </span>
          </article>
        </div>
      </div>
    </div>
  );
}

function Header({ id, name, handle, account, shade, platform, ai, needsYou, windowPart }: { id: string; name: string; handle?: string; account?: string; shade: number; platform: Platform; ai: string; needsYou?: boolean; windowPart?: string }) {
  const need = needsYou ? part(`${id}-need`) : {};
  const win = windowPart ? part(windowPart) : {};
  return (
    <div className="pd-head">
      <ArrowLeft className="size-5 pd-back" {...at(`back-${id}`)} />
      <Avatar name={name} shade={shade} platform={platform} />
      <span className="pd-who">
        <span className="pd-who-top">
          <b>{name}</b>
          <span className="pd-b num pd-wide-576" {...win}>Window: 23h left</span>
          {needsYou ? <span className="pd-b pd-b-md pd-b-danger pd-wide-672" {...need}>Needs you: asked for a person</span> : null}
        </span>
        <span className="pd-id">
          {needsYou ? <span className="pd-b pd-b-md pd-b-danger pd-narrow-672" {...need}>Needs you</span> : null}
          <span className="pd-b num pd-narrow-576" {...win}>23h left</span>
          <span className="pd-id-t">
            {handle ? `${handle} · ` : ""}
            <PlatformGlyph platform={platform} className={`pd-glyph pd-c-${platform}`} />
            {PLATFORM_LABEL[platform]}
            {account ? ` · ${account}` : ""}
          </span>
        </span>
      </span>
      <span className="pd-head-acts">
        <span className="pd-btn pd-btn-sm pd-btn-ghost">
          <UserPlus className="size-3.5" />
          <ChevronDown className="size-3.5" />
        </span>
        <span className="pd-btn pd-btn-sm pd-btn-soft">
          <Sparkles className="size-3.5" />
          <span className="pd-wide-576">{ai}</span>
          <ChevronDown className="size-3.5" />
        </span>
        <PanelRight className="size-4 pd-tool pd-wide-352" />
        <EllipsisVertical className="size-4 pd-tool" />
      </span>
    </div>
  );
}

function Composer({ name, sticker, typed, children }: { name: string; sticker?: boolean; typed?: string; children?: ReactNode }) {
  return (
    <div className="pd-composer">
      {children}
      <div className="pd-comp-card">
        <p className="pd-comp-text">
          <span className="pd-swap">
            <span className="pd-comp-ph" {...(typed ? part("maya-ph") : {})}>Reply to {name}…</span>
            {typed ? <span className="pd-comp-typed pd-before" {...part("maya-typed")}>{typed}</span> : null}
          </span>
        </p>
        <div className="pd-comp-tools">
          <Paperclip className="size-4 pd-tool" />
          <Smile className="size-4 pd-tool" />
          {sticker ? <Sticker className="size-4 pd-tool" /> : null}
          <span className="pd-btn pd-btn-soft pd-btn-off">
            <Sparkles className="size-4" />
            AI polish
          </span>
          <Clock className="size-4 pd-tool" {...(typed ? at("clock") : {})} />
          <span className="pd-swap pd-comp-send">
            <span className="pd-btn pd-btn-empty">
              <span className="pd-send-t">Send</span>
              <SendHorizontal className="size-4" />
            </span>
            {typed ? (
              <span className="pd-btn pd-btn-main pd-before" {...part("maya-ready")}>
                <span className="pd-send-t">Send</span>
                <SendHorizontal className="size-4" />
              </span>
            ) : null}
          </span>
        </div>
      </div>
    </div>
  );
}

function Inbound({ text, name, shade, time, children, ...rest }: { text: string; name: string; shade: number; time?: string; children?: ReactNode }) {
  return (
    <div className="pd-msg pd-in" {...rest}>
      <Avatar name={name} shade={shade} size={24} />
      <div>
        <p className="pd-bub">{text}</p>
        <p className="pd-meta num">{time ?? "17:26"}</p>
        {children}
      </div>
    </div>
  );
}

function MayaThread() {
  return (
    <div className="pd-conv pd-first" {...part("conv-maya")}>
      <Header id="maya" name="Maya R." handle="@maya.r" account={MUMBAI} shade={2} platform="instagram" ai="AI: Suggest" />
      <div className="pd-log">
        <p className="pd-day">Today</p>
        <Inbound text={QUESTION} name="Maya R." shade={2}>
          <p className="pd-chips" {...part("maya-tags")}>
            <span className="pd-b pd-b-brand">Product question</span>
            <span className="pd-b">
              <i className="pd-dot" />
              Neutral
            </span>
            <span className="pd-b">Medium priority</span>
            <Pencil className="size-3 pd-tool" />
          </p>
        </Inbound>
        <div className="pd-cell">
          <div className="pd-bar" {...part("maya-bar")}>
            <div className="pd-bar-top">
              <Sparkles className="pd-spark size-3.5" />
              <div className="pd-swap pd-draft">
                <p className="pd-drafting pd-before" {...part("maya-drafting")}>
                  <b>AI draft:</b> Drafting a reply…
                </p>
                <p {...part("maya-words")}>
                  <b>AI draft: </b>
                  {DRAFT}
                </p>
              </div>
              <X className="pd-x size-3.5" />
            </div>
            <div className="pd-bar-foot" {...part("maya-source")}>
              <span className="pd-b">From: Menu</span>
              <span className="pd-acts">
                <span className="pd-left">5 drafts left</span>
                <span className="pd-btn pd-btn-sm pd-btn-ghost pd-act-far">
                  <RefreshCw className="size-3.5" /> Draft again
                </span>
                <span className="pd-btn pd-btn-sm pd-btn-line">
                  <CornerDownLeft className="size-3.5" /> Insert
                </span>
                <span className="pd-btn pd-btn-sm pd-btn-main" {...at("send-draft")}>
                  <SendHorizontal className="size-3.5" /> Send
                </span>
              </span>
            </div>
          </div>
          <div className="pd-msg pd-out" {...part("maya-out")}>
            <p className="pd-bub">{DRAFT}</p>
            <p className="pd-meta num">
              17:27
              <span className="pd-swap pd-status">
                <LoaderCircle className="size-3.5 pd-before" {...part("maya-sending")} />
                <Check className="size-3.5" {...part("maya-sent")} />
              </span>
            </p>
          </div>
          <span className="pd-btn pd-btn-sm pd-btn-soft pd-sched-chip" {...part("maya-chip")}>
            <CalendarClock className="size-3.5" />1 scheduled · {WHEN}
          </span>
        </div>
      </div>
      <Composer name="Maya" typed={LATER}>
        {/* SchedulePanel, in the popover the composer's clock opens. */}
        <div className="pd-pop pd-sched pd-float" {...part("pop")}>
          <p className="pd-sched-h">Schedule message</p>
          <p className="pd-sched-w">Window closes Tomorrow 17:26</p>
          <div className="pd-sched-f">
            <span>
              <small>Date</small>
              <span className="pd-field">
                <Calendar className="size-4" />
                Fri 6 Nov 2026
              </span>
            </span>
            <span>
              <small>Time</small>
              <span className="pd-field num">
                18:30
                <Clock className="size-4" />
              </span>
            </span>
          </div>
          <p className="pd-sched-w">Times are in Asia/Kolkata.</p>
          <span className="pd-btn pd-btn-main pd-sched-go" {...at("schedule")}>Schedule</span>
        </div>
      </Composer>
      <div className="pd-toast pd-before" {...part("toast")}>
        <CircleCheck className="size-4" />
        Scheduled for {WHEN}
      </div>
    </div>
  );
}

function AnaThread() {
  const by = (
    <span className="pd-by">
      <Zap className="size-3" />
      Automation · {AUTOMATION}
    </span>
  );
  return (
    <div className="pd-conv" {...part("conv-ana")}>
      <Header id="ana" name="ana.wears" handle="@ana.wears" account={PUNE} shade={5} platform="instagram" ai="AI: Suggest" windowPart="ana-window" />
      <div className="pd-log">
        <p className="pd-comment" {...part("ana-comment")}>
          <PlatformGlyph platform="instagram" className="pd-glyph pd-c-instagram" />
          <span>{SOURCES.comment.label}</span>
          <b>ana.wears</b>
          <mark>{DEFAULT_KEYWORD}</mark>
        </p>
        <div className="pd-msg pd-out" {...part("ana-open")}>
          <div className="pd-bub">
            {DM_SCRIPT.opener}
            <span className="pd-quick">{DM_SCRIPT.button}</span>
          </div>
          <p className="pd-meta num">17:40<Check className="size-3.5" />{by}</p>
        </div>
        <Inbound text={DM_SCRIPT.button} name="ana.wears" shade={5} time="17:40" {...part("ana-tap")} />
        <div className="pd-msg pd-out" {...part("ana-link")}>
          <div className="pd-bub">
            {LINK_LINE}
            <span className="pd-url">cafe.example/menu</span>
          </div>
          <p className="pd-meta num">17:40<Check className="size-3.5" />{by}</p>
        </div>
      </div>
      <Composer name="ana" />
    </div>
  );
}

function SamThread() {
  return (
    <div className="pd-conv" {...part("conv-sam")}>
      <Header id="sam" name="Sam K." shade={4} platform="whatsapp" ai="AI: Auto" needsYou />
      <div className="pd-log">
        <p className="pd-day">Today</p>
        <Inbound text={PERSON} name="Sam K." shade={4} time="17:42" />
        <p className="pd-banner" {...part("sam-banner")}>
          <AlertTriangle className="size-4" />
          AI didn&apos;t reply: customer asked for a person
        </p>
      </div>
      <Composer name="Sam" sticker />
    </div>
  );
}

/**
 * "See a day in your inbox" (C-175), between the hero and How it works: the inbox as the app lays it
 * out, playing one story of about 20 s, then a short rest before it loops (landing-motion.ts,
 * productDemo; only opacity and transform move, and every box keeps its size). Under the frame, the
 * story's steps as plain captions, and its pause control (MotionToggle). With no script, or
 * `prefers-reduced-motion`, site.css lays everything out one under the other, finished, and nothing
 * moves. The scene is one labelled picture for assistive tech.
 */
export function ProductDemo() {
  return (
    <section className="sec sec-tight pd" id={PRODUCT_DEMO_ID} aria-labelledby="product-demo-title" data-motion-scope="">
      <div className="wrap">
        <div className="split-head">
          <h2 id="product-demo-title" className="h2">
            {PRODUCT_DEMO_TITLE}
          </h2>
          <p className="lede">
            Messages from each channel land in one list. The AI reads them, drafts from your knowledge and hands you the ones it
            shouldn&apos;t answer.
          </p>
        </div>
        <figure className="pd-stage" data-demo="" data-strip="all" data-acct="all" data-tab="chats" data-view="list">
          <div className="pd-win" data-ui="" role="img" aria-label={PRODUCT_DEMO_LABEL}>
            <div className="pd-topbar" aria-hidden>
              <span className="pd-logo bg-shell-gradient" />
              <b>Inbox</b>
              <Menu className="size-5" />
            </div>
            <div className="pd-body" aria-hidden>
              <Sidebar />
              <div className="pd-inbox">
                <ListPane />
                <div className="pd-panes">
                  <div className="pd-pick pd-before" {...part("pick")}>
                    <b>Pick a conversation</b>
                    <span>Choose someone on the left to start replying.</span>
                  </div>
                  <MayaThread />
                  <AnaThread />
                  <SamThread />
                </div>
              </div>
            </div>
            <span className="pd-cursor" aria-hidden data-cursor="">
              <i className="pd-ring" data-ring="" />
              <svg viewBox="0 0 24 24" width="20" height="20">
                <path d="M5 3l14 8-6.5 1.5L10 19z" />
              </svg>
            </span>
          </div>
          <figcaption className="stage-cap pd-cap">
            <span>
              {PRODUCT_DEMO_NOTE}. {PRODUCT_DEMO_PLAN_NOTE}
            </span>
            <MotionToggle label="Pause the example" />
          </figcaption>
        </figure>
        <ol className="pd-steps" data-demo-steps="">
          {PRODUCT_DEMO_STEPS.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </div>
    </section>
  );
}

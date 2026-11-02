import { ArrowRight, BookOpen, Check, CircleCheck, type LucideIcon, MessageSquareOff, MessagesSquare, Sparkles } from "lucide-react";

import { CONFIRM_LINE, MCP_PAGE_PATH, MCP_SETUP_PATH } from "@/lib/marketing/mcp-page";
import { SITE_NAME } from "@/lib/marketing/site";

import { CtaLink } from "../primitives";

/*
 * C-168: the MCP highlight. Every line is true of the server today (docs/architecture/mcp
 * 03-phase-a.md, 04-phase-b.md, 05-phase-c.md; lib/marketing/connect-ai.ts PLAN_ROWS and SAFETY):
 * the preview and the yes before anything is scheduled (CONFIRM_LINE), posts at least 5 minutes out
 * with owners and admins told, no DMs or comment replies from an AI app, reading and drafts on every
 * plan. C-169: keyword automations can be set up from an AI app (Creator and Business); the automation sends,
 * after the member confirms and it is on. Not claimed: the AI sending messages, TikTok, a listing in
 * Anthropic's or OpenAI's directories, or that we are the only or first tool with an MCP server
 * (C-168: four of the nine competitors we compare have one).
 */

export const AI_APPS_ID = "ai-apps";
export const AI_APPS_TITLE = "Your AI assistant, connected to your Instagram";

/** The three apps we've tested, as plain names (brand rules: no logos). */
export const AI_APPS_CLIENTS = ["Claude", "ChatGPT", "Codex"] as const;

export const AI_APPS_POINTS: { title: string; body: string; icon: LucideIcon }[] = [
  {
    title: "Works with Claude, ChatGPT and Codex",
    icon: Sparkles,
    body: `Add ${SITE_NAME} as a connector, sign in and pick the workspace. Other MCP apps should work too, but we haven't tested them yet.`,
  },
  {
    title: "You confirm first",
    icon: CircleCheck,
    body: `${CONFIRM_LINE} A post goes out at least 5 minutes later, and owners and admins are told. Keep approvals on in your AI app for changes: set to always allow, it can confirm without asking you.`,
  },
  {
    title: "It doesn't message your customers itself",
    icon: MessageSquareOff,
    body: `AI apps read conversations and draft replies. Sending a DM or a comment reply stays in ${SITE_NAME}, with a person. An automation set up from your AI app does nothing until you confirm it and it's on.`,
  },
  {
    title: "Reading and drafts on every plan",
    icon: BookOpen,
    body: "Free included. Scheduling posts, adding knowledge and creating or pausing automations are on Creator and Business.",
  },
];

/** The example chat (made-up accounts and counts, labelled "Example" under the scene). */
export const AI_APPS_SCENE = {
  ask: "Schedule this Reel for Friday 6 pm on @cafe_mumbai and @cafe_pune.",
  file: "new-menu.mp4",
  reply: `Here's the preview from ${SITE_NAME}. Nothing is scheduled until you confirm.`,
  preview: [
    { label: "Post", value: "Reel · new-menu.mp4" },
    { label: "Accounts", value: "@cafe_mumbai, @cafe_pune" },
    { label: "When", value: "Fri, 6:00 pm" },
  ],
  checks: "Composer checks passed",
  done: "Scheduled. Owners and admins are notified.",
  ask2: "What did people ask about in DMs this week?",
  summaryLead: "From this week's conversations:",
  summary: [
    { topic: "The new menu and prices", count: 14 },
    { topic: "Table bookings for the weekend", count: 9 },
    { topic: "Opening hours on Sunday", count: 6 },
  ],
  summaryNote: "Nothing was sent or changed.",
} as const;

/** What the scene shows, for screen readers (the scene itself is a picture). */
export const AI_APPS_SCENE_LABEL = `Example: in an AI app, someone asks to schedule a Reel on two Instagram accounts. ${SITE_NAME} shows a preview with the accounts, the time and its checks; they confirm and it is scheduled. Then they ask what people asked about in DMs this week and get a short summary.`;


/**
 * "Your AI assistant, connected to your Instagram" (C-168), between Modes and Security: the copy
 * and four points on the left, an example chat on the right. Server-rendered in its final state
 * (scheduled, then the DM summary), so it reads complete without script and under reduced motion.
 * landing-motion.ts (aiApps) plays it once when it scrolls into view from below: the ask, the
 * preview, the press on Confirm, "Scheduled", then the second question, in under 5 seconds. Every
 * part keeps its box throughout (opacity, translate and a label swap in one grid cell), so nothing
 * moves the layout.
 */
export function AiApps() {
  return (
    <section className="sec mh-sec" id={AI_APPS_ID} aria-labelledby="ai-apps-title">
      <div className="wrap mh">
        <div className="mh-copy">
          <h2 id="ai-apps-title" className="h2">
            {AI_APPS_TITLE}
          </h2>
          <p className="lede">
            Ask Claude, ChatGPT or Codex to schedule a Reel, sum up this week&apos;s DMs or check how your posts did. It works
            through {SITE_NAME}&apos;s MCP server, with your workspace&apos;s rules.
          </p>
          <ul className="mh-points">
            {AI_APPS_POINTS.map(({ title, body, icon: Icon }) => (
              <li key={title} className="mh-pt">
                <Icon className="mh-pt-ico" size={20} strokeWidth={1.75} aria-hidden focusable="false" />
                <h3>{title}</h3>
                <p>{body}</p>
              </li>
            ))}
          </ul>
          <div className="ctas mh-ctas">
            <CtaLink href={MCP_PAGE_PATH}>
              See how it works <ArrowRight className="size-4" aria-hidden />
            </CtaLink>
            <CtaLink href={MCP_SETUP_PATH} variant="secondary">
              Set it up
            </CtaLink>
          </div>
        </div>
        <AiAppsScene />
      </div>
    </section>
  );
}

/** The example chat: one picture for assistive tech, labelled Example, with the apps as plain names. */
export function AiAppsScene() {
  const s = AI_APPS_SCENE;
  return (
    <figure className="mh-stage" data-mh="">
      <div className="mh-win" data-ui="" role="img" aria-label={AI_APPS_SCENE_LABEL}>
        <div className="mh-bar" aria-hidden>
          <span className="mh-dots">
            <i />
            <i />
            <i />
          </span>
          <b>Your AI app</b>
          <span className="mh-conn">
            <i />
            {SITE_NAME} connected
          </span>
        </div>
        <div className="mh-chat" aria-hidden>
          <div className="mh-step mh-me" data-s="0">
            <span className="mh-file">{s.file}</span>
            <p>{s.ask}</p>
          </div>
          <div className="mh-step mh-ai" data-s="1">
            <p>{s.reply}</p>
            <div className="mh-card">
              <div className="mh-card-h">
                <b>{SITE_NAME}</b>
                <span>Preview</span>
              </div>
              <dl>
                {s.preview.map((row) => (
                  <div key={row.label}>
                    <dt>{row.label}</dt>
                    <dd>{row.value}</dd>
                  </div>
                ))}
              </dl>
              <p className="mh-checks">
                <Check size={14} strokeWidth={2.4} aria-hidden focusable="false" />
                {s.checks}
              </p>
              <div className="mh-act">
                <span className="mh-btn" data-mh-btn="">
                  <span className="mh-btn-a">Confirm</span>
                  <span className="mh-btn-b">
                    <Check size={14} strokeWidth={2.4} aria-hidden focusable="false" />
                    Confirmed
                  </span>
                </span>
                <span className="mh-done mh-step" data-s="2">
                  {s.done}
                </span>
              </div>
            </div>
          </div>
          <div className="mh-step mh-me" data-s="3">
            <p>{s.ask2}</p>
          </div>
          <div className="mh-step mh-ai" data-s="4">
            <p>{s.summaryLead}</p>
            <ol className="mh-sum">
              {s.summary.map((item) => (
                <li key={item.topic}>
                  <span>{item.topic}</span>
                  <b className="num">{item.count}</b>
                </li>
              ))}
            </ol>
            <p className="mh-note">
              <MessagesSquare size={14} strokeWidth={2} aria-hidden focusable="false" />
              {s.summaryNote}
            </p>
          </div>
        </div>
      </div>
      <figcaption className="stage-cap mh-cap">
        Example. Works in Claude, ChatGPT and Codex.
      </figcaption>
    </figure>
  );
}

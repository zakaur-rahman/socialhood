# 02 · OpenUI research

What OpenUI is and what integrating it would mean for us. Researched on 2026-10-23 from official sources only: openui.com, github.com/thesysdev/openui and the npm registry.

**Labels:** **Verified** means read in an official source (linked). **Assumption** is our inference. **Unresolved** means not found. Pages were read through a summarising fetch, so links point to pages and files rather than lines.

## Which "OpenUI"

- **Verified:** openui.com and github.com/thesysdev/openui are the same project, maintained by Thesys Inc. It's "an open standard for Generative UI": a compact language the model writes (OpenUI Lang), a parser and renderers (React, Vue, Svelte, Angular), a prompt generator, optional component libraries, and optional hosted services. MIT licence. ([docs](https://www.openui.com/docs), [repo](https://github.com/thesysdev/openui), [LICENSE](https://raw.githubusercontent.com/thesysdev/openui/main/LICENSE))
- **Assumption:** the older "openui" screenshot-to-HTML tool by Weights & Biases is a different project. Don't confuse the two.

## Answers to the twelve questions

### 1. What OpenUI provides
- **The language:** OpenUI Lang is line-based, one statement per line, `id = Component(positional args)`. The entry statement is `root` ([spec](https://www.openui.com/docs/openui-lang/specification)). Version 1.0 adds actions (`@Name(...)`), reactive `$variables`, `Query()` and `Mutation()` bound to a tool provider, and pure synchronous functions. **Verified.**
- **The renderer:** `<Renderer library response isStreaming onAction onStateUpdate initialState onError toolProvider .../>` turns Lang text into your registered React components ([renderer](https://www.openui.com/docs/openui-lang/renderer)). **Verified.**
- **The prompt generator:** a CLI (`npx @openuidev/cli generate ./lib.tsx --out system-prompt.txt`) or `generateSystemPrompt()` describes your components to the model ([system prompts](https://www.openui.com/docs/openui-lang/system-prompts)). **Verified.**
- **Optional extras:**
  - prebuilt component libraries and a chat UI (`@openuidev/react-ui`);
  - hosted Gateway (an OpenAI-compatible endpoint with repair), Autofix and monitoring ([gateway](https://www.openui.com/docs/gateway), [pricing](https://www.openui.com/pricing)).
  - **Verified.**

### 2. Packages (verified on npm and in the repo's package.json files)

| Package | Version | Status | Use for us |
|---|---|---|---|
| `@openuidev/react-lang` | 1.0.1 (2026-10-15; first published 2026-03-10) | Stable | The only package we'd need: `Renderer`, `defineComponent`, `createLibrary`, hooks. Peer dependencies: `react` `*`, `zod` ^3.25 or ^4 |
| `@openuidev/lang-core` | 1.0.1 | Stable | Parser, `generateSystemPrompt`, `jsonToOpenUI`. Has install-time telemetry |
| `@openuidev/react-ui` | 0.18.1 | Pre-1.0 | Prebuilt components plus its own CSS and many dependencies (radix, d3, tanstack-table, react-markdown). **Avoid** |
| `@openuidev/react-headless` | 0.18.1 | Pre-1.0 | Chat state and stream adapters. Not needed |
| `@openuidev/server` | 0.3.0 | Pre-1.0 | TypeScript server helpers. Not usable from Python |
| `@openuidev/cli` | 0.6.0 | Pre-1.0 | Scaffold and prompt generation (build time only) |

Maturity: about 13.4k stars and 66 open issues, all packages released 2026-10-15, active daily. The language reached 1.0 about seven months after first publish, building on v0.5, so the API has recently changed.

### 3. Its own language, and whether we can generate it deterministically
- **Verified:** yes, the format is OpenUI Lang, and the model is meant to write it in place of Markdown.
- **Verified:** `jsonToOpenUI` in `lang-core` serialises a JSON node tree to Lang text. It isn't documented for server-side use, and issue [#1463](https://github.com/thesysdev/openui/issues/1463) reports a precedence bug (fix pending).
- **Assumption:** a Python backend could template Lang text itself. It would have to match the spec exactly (argument order, required props) or the parser reports `missing-required` or `type-mismatch`. There's no official Python helper.

### 4. What the backend must produce
- **Verified:** plain text, a stream of OpenUI Lang (the example route returns `text/plain`), with the generated component prompt appended to the system prompt. The docs say to keep your agent framework, tools and transport and change only the output format ([backend setup](https://www.openui.com/docs/build-agents/backend-setup), [UI generation](https://www.openui.com/docs/build-agents/ui-generation)).
- **Verified:** every example and server SDK is TypeScript or Node. **Unresolved:** there is no Python or FastAPI example. A non-JS backend can load the CLI's `system-prompt.txt` (assumption; options such as tool bindings need the TypeScript function).
- **Unresolved:** how to mix prose and UI in one message. The docs don't cover it.

### 5. Registering components
- **Verified:** `defineComponent({ name, description, props: z.object(...), component })`, then `createLibrary({ root, components })`, then `library.prompt(...)` or the CLI ([defining components](https://www.openui.com/docs/openui-lang/defining-components)). The built-in libraries are optional, so we can register **only our own** shadcn-based components. The prompt must be regenerated whenever the library changes.

### 6. Streaming
- **Verified:** the parser re-runs on every chunk. A complete line renders at once, forward references resolve when they arrive, and invalid nodes are dropped. `isStreaming` must stay true until the stream ends ([renderer](https://www.openui.com/docs/openui-lang/renderer)).
- **Verified:** adapters exist for OpenAI, the Vercel AI SDK (SSE), AG-UI, LangChain, Mastra and Google ADK.
- **Assumption:** it can coexist with our own event protocol, because `Renderer` just takes a string. But our agent doesn't stream text (doc 01, section 4), so streaming Lang would first need a streaming model call.
- **Verified, open issues:**
  - core rendering: [#767](https://github.com/thesysdev/openui/issues/767) (streamed `$binding` defaults stick) and #990 ("Maximum update depth exceeded" with charts);
  - adapters: #1312 and #1413.

### 7. Models and providers
- **Verified:** it "works with any model provider". Gateway is optional, and the prompt can be generated locally.
- **Unresolved, and the main risk:** our agent uses **Google Gemini** (`gemini-3.5-flash-lite` by default) through Pydantic AI. Nothing official measures how reliably Gemini Flash-Lite writes OpenUI Lang. The vendor benchmark uses a single OpenAI model. We would have to run our own evaluation.
- **No separate hosted model call is required** on the open-source path.

### 8. Latency, tokens and cost
- **Verified, vendor-authored:** a benchmark (one model, temperature 0, one run per scenario) puts OpenUI Lang at about 47-53% fewer output tokens than equivalent JSON or YAML UI formats ([benchmarks](https://www.openui.com/docs/openui-lang/benchmarks)). The latency figures are estimates at an assumed 60 tokens a second.
- **Estimate (ours):** a library of 8 to 10 components adds roughly a few hundred to a couple of thousand prompt tokens to every agent turn. It's undocumented, so we'd measure it.
- **Assumption:** server-side generation from tool data costs no model tokens at all.

### 9. Licensing, hosting, telemetry
- **Verified:** MIT (react-lang, lang-core, react-ui and server checked). The framework is free to self-host with no usage limits.
- **Hosted Gateway pricing:**

  | Tier | Price | Calls | Notes |
  |---|---|---|---|
  | Free | $0 | 3K a month | |
  | Build | $49 a month | 25K | $0.002 overage |
  | Grow | $499 a month | 500K | |
  | Scale | Custom | | |

  - LLM tokens at the provider's price.
  - Autofix is hosted ([pricing](https://www.openui.com/pricing)).
- **Verified, telemetry:** `lang-core` runs telemetry at install time via a postinstall script. It's turned off by `OPENUI_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1`, which we'd set in CI and dev ([postinstall.ts](https://github.com/thesysdev/openui/blob/main/packages/lang-core/src/postinstall.ts)). Runtime telemetry is opt-in and server-side only.

### 10. Our design system and charts
- **Verified:** the renderer draws **our** React components, so our tokens, Tailwind and shadcn apply unchanged. `react-ui`'s own CSS is optional, and we should not import it.
- **Implication:** OpenUI gives us no charts. We'd still build the chart components ourselves (we have no chart library; doc 01, section 6).

### 11. Invalid, unsupported or interrupted output
- **Verified:**
  - Unknown components are dropped.
  - `onError` receives structured codes: `unknown-component`, `missing-required`, `type-mismatch`, `no-root`, `parse-failed`, `tool-error`, `render-error`, and others.
  - The production page admits that none of the frameworks they tested was free of errors ([production](https://www.openui.com/docs/production)).
  - Hosted Gateway or Autofix repair output; self-hosted, the fallback is ours.
- **Unresolved:** a formal security statement (eval or HTML injection), and whether the renderer has its own React error boundary. **Recommendation:** wrap it in ours.
- **Verified, actions:**
  - `@ToAssistant(...)` goes back to the conversation through `onAction`, and `@OpenUrl` opens a link.
  - Custom actions reach `onAction` with their name.
  - The renderer handles `@Run`, `@Set` and `@Reset` itself.
  - `Mutation()` calls a client-side tool provider ([interactivity](https://www.openui.com/docs/openui-lang/interactivity)).
  - **For us:** never expose `Mutation` tools, and route every action to our own authenticated API with a server-issued id.

### 12. What we'd build ourselves anyway
The component library, the backend agent and tools, authentication, permission checks, action handling, error boundaries and fallbacks, persistence of state, prompt tuning, and reliability monitoring (unless we pay for Gateway). This is the docs' own scope ([getting started](https://www.openui.com/docs/getting-started)).

## What this means for Social Hood

| OpenUI assumes | We have |
|---|---|
| A TypeScript or Node backend | A Python (FastAPI, Pydantic AI) backend |
| A streaming model response | A non-streaming `agent.run` with a 2,048-token answer cap |
| A capable model writing the UI | Gemini Flash-Lite, with an eval that checks every number |
| The model composes layouts | A rule that the model never computes numbers |
| Prebuilt chart components (in react-ui) | No chart library, and a palette locked to one series colour |

OpenUI's value is letting the model **compose layouts freely**. For our answers (comparisons, rankings, sentiment splits, lead lists), the layout follows from which tool ran. So the deterministic path (doc 03) captures most of the value without these risks.

## Sources
- Docs: https://www.openui.com/docs and these pages under it: `/getting-started`, `/openui-lang`, `/openui-lang/specification`, `/openui-lang/defining-components`, `/openui-lang/renderer`, `/openui-lang/interactivity`, `/openui-lang/system-prompts` and `/openui-lang/benchmarks`.
- Building agents: https://www.openui.com/docs/build-agents/backend-setup and https://www.openui.com/docs/build-agents/ui-generation.
- Production: https://www.openui.com/docs/production, plus `/docs/gateway` and `/docs/autofix`.
- Pricing: https://www.openui.com/pricing.
- Repository: https://github.com/thesysdev/openui (README, `packages/*/package.json`, LICENSE, `lang-core/src/postinstall.ts`, issues).
- Releases: https://api.github.com/repos/thesysdev/openui/releases, and the npm page https://registry.npmjs.org/@openuidev/react-lang.

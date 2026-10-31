import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse, type NextFetchEvent, type NextRequest } from "next/server";

import { APP_ROBOTS_TXT, hostRoute } from "@/lib/hosts";
import { appOrigin, siteUrl } from "@/lib/marketing/site";

// TR-FE-01: every app route needs a signed-in user. Signed-out visits go to /sign-in and come
// back to the same page afterwards (F-02). Marketing, legal and auth pages stay public.
// C-165: /connect/authorize, the AI app consent page, signs in the same way.
const isAppRoute = createRouteMatcher(["/app(.*)", "/w/(.*)", "/connect/(.*)"]);

// C-146: with NEXT_PUBLIC_APP_URL set, the site and the app are two origins on the same Clerk
// production instance (sessions are shared across its subdomains). Clerk checks each session
// token's `azp` against these, so a token minted on any other subdomain is refused.
const app = appOrigin();
const authorizedParties = app ? [siteUrl(), app] : undefined;

const clerk = clerkMiddleware(
  async (auth, request) => {
    if (isAppRoute(request)) await auth.protect();

    if (app) {
      // Nothing on the app host is a search result (its layouts say noindex too).
      const response = NextResponse.next();
      response.headers.set("X-Robots-Tag", "noindex, nofollow");
      return response;
    }
  },
  { authorizedParties },
);

export default function proxy(request: NextRequest, event: NextFetchEvent) {
  // C-146: send each page to the host that serves it before anything else runs.
  const route = hostRoute(request.headers.get("host"), request.nextUrl.pathname, request.nextUrl.search);
  if (route.kind === "redirect") return NextResponse.redirect(route.location, route.status);
  if (route.kind === "robots") {
    return new NextResponse(APP_ROBOTS_TXT, { headers: { "Content-Type": "text/plain; charset=utf-8" } });
  }
  if (route.kind === "not-found") return new NextResponse("Not found", { status: 404 });

  // C-152: the public site never asks who is signed in (its pages load no Clerk, C-148; the header
  // reads the cookie hint), so Clerk doesn't run there. That saves its work on every page and the
  // handshake redirect a signed-in visitor's stale session would otherwise cost the first byte.
  if (route.host === "site") return NextResponse.next();

  return clerk(request, event);
}

export const config = {
  matcher: [
    // Everything except Next internals and static files.
    "/((?!_next|[^?]*\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};

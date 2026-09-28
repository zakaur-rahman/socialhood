import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

// TR-FE-01: every app route needs a signed-in user. Signed-out visits go to /sign-in and come
// back to the same page afterwards (F-02). Marketing, legal and auth pages stay public.
const isAppRoute = createRouteMatcher(["/app(.*)", "/w/(.*)"]);

export default clerkMiddleware(async (auth, request) => {
  if (isAppRoute(request)) await auth.protect();
});

export const config = {
  matcher: [
    // Everything except Next internals and static files.
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};

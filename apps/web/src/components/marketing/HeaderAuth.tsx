import { APP_PATH, SIGN_IN_PATH, SIGN_UP_PATH, appUrl } from "@/lib/marketing/site";
import { cn } from "@/lib/utils";

import { CtaLink } from "./primitives";
import { SignedInSwitch } from "./SignedInSwitch";

/**
 * The header's account actions. The page is static, so it renders the signed-out actions; once the
 * browser knows the visitor is signed in (Clerk, or the session cookie hint when the app has its
 * own host: C-148), they see "Open app" instead.
 *
 * Both sets are rendered here, on the server, and SignedInSwitch picks one in the browser, so the
 * links' class merging (`cn`) never ships to the public pages (C-152).
 *
 * `bar`: the header row (Sign in hides on phones, where the menu has it). `menu`: the phone menu.
 */
export function HeaderAuth({ variant = "bar" }: { variant?: "bar" | "menu" }) {
  const signedIn = (
    <CtaLink href={appUrl(APP_PATH)} prefetch={false} className={cn("px-3 sm:px-4", variant === "menu" && "w-full")}>
      Open app
    </CtaLink>
  );

  const signedOut =
    variant === "menu" ? (
      <div className="grid gap-2">
        <CtaLink href={appUrl(SIGN_IN_PATH)} variant="secondary" prefetch={false} className="w-full">
          Sign in
        </CtaLink>
        <CtaLink href={appUrl(SIGN_UP_PATH)} prefetch={false} className="w-full">
          Start free
        </CtaLink>
      </div>
    ) : (
      <div className="flex items-center gap-1 sm:gap-2">
        <CtaLink href={appUrl(SIGN_IN_PATH)} variant="ghost" prefetch={false} className="hidden sm:inline-flex">
          Sign in
        </CtaLink>
        <CtaLink href={appUrl(SIGN_UP_PATH)} prefetch={false} className="px-3 sm:px-4">
          Start free
        </CtaLink>
      </div>
    );

  return <SignedInSwitch signedIn={signedIn} signedOut={signedOut} />;
}

import { APP_PATH, SIGN_IN_PATH, SIGN_UP_PATH, appUrl } from "@/lib/marketing/site";

import { CtaLink } from "./primitives";
import { SignedInSwitch } from "./SignedInSwitch";

/**
 * The header's account actions. The page is static, so it renders the signed-out actions; once the
 * browser knows the visitor is signed in (Clerk, or the session cookie hint when the app has its
 * own host: C-148), they see "Open app" instead. Both sets are rendered here, on the server, and
 * SignedInSwitch picks one in the browser (C-152).
 *
 * `bar`: the header row (Sign in hides on phones, where the menu has it). `menu`: the phone menu,
 * which adds only what the bar hides: Sign in. "Start free" (or "Open app") stays in the bar, so
 * the open menu shows one of each (C-157, LP-1.4).
 */
export function HeaderAuth({ variant = "bar" }: { variant?: "bar" | "menu" }) {
  if (variant === "menu") {
    return (
      <SignedInSwitch
        signedIn={null}
        signedOut={
          <CtaLink href={appUrl(SIGN_IN_PATH)} variant="secondary" prefetch={false}>
            Sign in
          </CtaLink>
        }
      />
    );
  }

  const signedIn = (
    <CtaLink href={appUrl(APP_PATH)} prefetch={false}>
      Open app
    </CtaLink>
  );

  const signedOut = (
    <>
      <CtaLink href={appUrl(SIGN_IN_PATH)} variant="ghost" prefetch={false} className="si">
        Sign in
      </CtaLink>
      <CtaLink href={appUrl(SIGN_UP_PATH)} prefetch={false}>
        Start free
      </CtaLink>
    </>
  );

  return <SignedInSwitch signedIn={signedIn} signedOut={signedOut} />;
}

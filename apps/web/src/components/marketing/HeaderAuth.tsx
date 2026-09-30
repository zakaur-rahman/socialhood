"use client";

import { useAuth } from "@clerk/nextjs";

import { APP_PATH, SIGN_IN_PATH, SIGN_UP_PATH } from "@/lib/marketing/site";
import { cn } from "@/lib/utils";

import { CtaLink } from "./primitives";

/**
 * The header's account actions. The page is static, so it renders the signed-out actions; once
 * Clerk has loaded in the browser, a signed-in visitor sees "Open app" instead.
 *
 * `bar`: the header row (Sign in hides on phones, where the menu has it). `menu`: the phone menu.
 */
export function HeaderAuth({ variant = "bar", onNavigate }: { variant?: "bar" | "menu"; onNavigate?: () => void }) {
  const { isLoaded, isSignedIn } = useAuth();
  const signedIn = isLoaded && isSignedIn === true;

  if (signedIn) {
    return (
      <CtaLink href={APP_PATH} prefetch={false} onClick={onNavigate} className={cn("px-3 sm:px-4", variant === "menu" && "w-full")}>
        Open app
      </CtaLink>
    );
  }

  if (variant === "menu") {
    return (
      <div className="grid gap-2">
        <CtaLink href={SIGN_IN_PATH} variant="secondary" prefetch={false} onClick={onNavigate} className="w-full">
          Sign in
        </CtaLink>
        <CtaLink href={SIGN_UP_PATH} prefetch={false} onClick={onNavigate} className="w-full">
          Start free
        </CtaLink>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1 sm:gap-2">
      <CtaLink href={SIGN_IN_PATH} variant="ghost" prefetch={false} className="hidden sm:inline-flex">
        Sign in
      </CtaLink>
      <CtaLink href={SIGN_UP_PATH} prefetch={false} className="px-3 sm:px-4">
        Start free
      </CtaLink>
    </div>
  );
}

"use client";

import { SignIn, SignUp, UserButton } from "@clerk/nextjs";

import { authAppearance } from "@/components/auth/AuthShell";
import { clerkAppearanceFor } from "@/lib/clerk-appearance";
import { useTheme } from "@/lib/use-theme";
import type { Theme } from "@/styles/tokens";

/** What changes with the theme: the base theme (Dark only) and the variables. The rest merges from the provider. */
function withBase(theme: Theme) {
  const { variables, ...rest } = clerkAppearanceFor(theme);
  return { variables, theme: "theme" in rest ? rest.theme : undefined };
}

/**
 * Clerk's components with the appearance for the theme on screen (C-129). Clerk takes its colours
 * as literals, so the root layout's provider carries the dark ones and each Clerk component passes
 * the set for Light when the page is light; the element styles are CSS variables and follow by
 * themselves. These three are the only places Clerk's UI is rendered.
 */
export function ThemedSignIn() {
  const { resolved } = useTheme();
  const { theme, variables } = withBase(resolved);
  return <SignIn signUpUrl="/sign-up" fallbackRedirectUrl="/app" appearance={{ ...authAppearance, theme, variables }} />;
}

export function ThemedSignUp() {
  const { resolved } = useTheme();
  const { theme, variables } = withBase(resolved);
  return <SignUp signInUrl="/sign-in" fallbackRedirectUrl="/app" appearance={{ ...authAppearance, theme, variables }} />;
}

export function ThemedUserButton() {
  const { resolved } = useTheme();
  const appearance = clerkAppearanceFor(resolved);
  // The account dialog ("Manage account") is Clerk's UserProfile in a modal: it doesn't inherit the
  // button's appearance, so without its own it took the provider's dark text on a light dialog.
  return <UserButton appearance={appearance} userProfileProps={{ appearance }} />;
}

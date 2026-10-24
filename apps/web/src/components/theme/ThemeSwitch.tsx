"use client";

import { Monitor, Moon, Sun } from "lucide-react";

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { THEME_CHOICES, THEME_LABEL, parseTheme } from "@/lib/theme";
import { useTheme } from "@/lib/use-theme";

export const THEME_ICON = { dark: Moon, light: Sun, system: Monitor } as const;

/**
 * The Dark / Light / System switch as a segmented control (Settings → Appearance). It writes the
 * `sh_theme` cookie and the attribute on <html> at once (lib/use-theme), so nothing reloads.
 */
export function ThemeSwitch() {
  const { choice, setChoice } = useTheme();
  return (
    <ToggleGroup type="single" size="xl" aria-label="Theme" value={choice} onValueChange={(next) => setChoice(parseTheme(next))}>
      {THEME_CHOICES.map((value) => {
        const Icon = THEME_ICON[value];
        return (
          <ToggleGroupItem key={value} value={value}>
            <Icon aria-hidden />
            {THEME_LABEL[value]}
          </ToggleGroupItem>
        );
      })}
    </ToggleGroup>
  );
}

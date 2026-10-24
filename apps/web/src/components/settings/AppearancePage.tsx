"use client";

import { SettingsCard } from "@/components/settings/SettingsCard";
import { SettingsFrame, SettingsPageHeader } from "@/components/settings/SettingsPageHeader";
import { ThemeSwitch } from "@/components/theme/ThemeSwitch";

/**
 * Settings → Appearance (C-129): Dark, Light or System. The choice is the member's own, kept in a
 * cookie on this browser (lib/theme.ts), so it is not a workspace setting and has no Save bar.
 */
export function AppearancePage() {
  return (
    <SettingsFrame
      header={
        <SettingsPageHeader
          title="Appearance"
          description="Choose how Social Hood looks on this device. The public website stays dark."
        />
      }
    >
      <SettingsCard
        id="theme"
        title="Theme"
        description="Dark is the default. System follows your device's setting and changes with it."
      >
        <div className="max-w-md">
          <ThemeSwitch />
        </div>
      </SettingsCard>
    </SettingsFrame>
  );
}

import type { Metadata } from "next";
import { Suspense } from "react";

import { ConsentPage } from "@/components/ai-connections/ConsentPage";
import { PageSkeleton } from "@/components/states/PageSkeleton";

export const metadata: Metadata = { title: "Connect an AI app" };

/** C-165 phase C: the consent page an AI app's sign-in lands on (/oauth/authorize sends it here). */
export default function ConnectAuthorizeRoute() {
  return (
    <Suspense fallback={<PageSkeleton fullPage />}>
      <ConsentPage />
    </Suspense>
  );
}

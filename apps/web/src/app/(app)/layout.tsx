import { PageSkeleton } from "@/components/states/PageSkeleton";
import { ApiProvider } from "@/lib/api/provider";

/** Everything signed in shares one API client and query cache (TR-FE-02). */
export default function SignedInLayout({ children }: LayoutProps<"/">) {
  return <ApiProvider fallback={<PageSkeleton fullPage />}>{children}</ApiProvider>;
}

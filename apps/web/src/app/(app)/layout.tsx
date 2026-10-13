import { ShellSkeleton } from "@/components/shell/ShellFrame";
import { ApiProvider } from "@/lib/api/provider";

/**
 * Everything signed in shares one API client and query cache (TR-FE-02). While it loads, the shell
 * frame is already there (the workspace layout shows the same skeleton next), so a hard load
 * doesn't paint a bare page first.
 */
export default function SignedInLayout({ children }: LayoutProps<"/">) {
  return <ApiProvider fallback={<ShellSkeleton />}>{children}</ApiProvider>;
}

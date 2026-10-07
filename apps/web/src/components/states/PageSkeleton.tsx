import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/** Loading placeholder shaped like a page: title bar and rows (never a centred spinner, §4.7). */
export function PageSkeleton({ fullPage = false, rows = 4 }: { fullPage?: boolean; rows?: number }) {
  return (
    <div
      aria-busy="true"
      aria-label="Loading"
      className={cn("mx-auto w-full max-w-[1200px] space-y-4 p-4 md:p-6", fullPage && "min-h-dvh")}
    >
      <Skeleton className="h-8 w-48" />
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex items-center gap-3 rounded-xl border border-line bg-panel p-4">
          <Skeleton className="size-10 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3 w-1/3" />
            <Skeleton className="h-3 w-2/3" />
          </div>
        </div>
      ))}
    </div>
  );
}

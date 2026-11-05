import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/** Loading placeholder shaped like a page: title bar and rows (never a centred spinner, §4.7). */
export function PageSkeleton({ fullPage = false, rows = 4 }: { fullPage?: boolean; rows?: number }) {
  return (
    <div
      role="status"
      aria-busy="true"
      aria-label="Loading"
      className={cn("w-full space-y-4 p-4 pt-0 md:p-6 md:pt-0", fullPage && "min-h-dvh")}
    >
      {/* The page header's band (PageFrame), so nothing jumps when the page arrives. */}
      <div className="-mx-4 mb-6 border-b border-line bg-panel px-4 pt-4 pb-3 md:-mr-6 md:-ml-2 md:pr-6 md:pl-2 md:pt-6">
        <Skeleton className="h-8 w-48" />
      </div>
      {Array.from({ length: rows }, (_, i) => (
        <Card key={i} className="flex items-center gap-3">
          <Skeleton className="size-10 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3 w-1/3" />
            <Skeleton className="h-3 w-2/3" />
          </div>
        </Card>
      ))}
    </div>
  );
}

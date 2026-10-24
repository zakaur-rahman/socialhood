import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { assigneeInitials } from "@/lib/inbox/assignee";
import { cn } from "@/lib/utils";

/** A member's picture, or their initials. Decorative: the name is always written beside it. */
export function AssigneeAvatar({
  name,
  pictureUrl,
  className,
}: {
  name: string | null;
  pictureUrl?: string | null;
  className?: string;
}) {
  return (
    <Avatar size="sm" className={cn("shrink-0", className)} aria-hidden>
      {pictureUrl ? <AvatarImage src={pictureUrl} alt="" /> : null}
      <AvatarFallback className="text-[10px] font-semibold">{assigneeInitials(name)}</AvatarFallback>
    </Avatar>
  );
}

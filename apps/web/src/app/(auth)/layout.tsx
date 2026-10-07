import { LogoMark } from "@/components/marketing/primitives";

export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-6 p-4">
      <div className="flex items-center gap-2.5">
        <LogoMark className="size-9" />
        <span className="text-base font-semibold">Social Hood</span>
      </div>
      {children}
    </main>
  );
}

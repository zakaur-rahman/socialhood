export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-6 p-4">
      <div className="flex items-center gap-2.5">
        <span className="bg-shell-gradient size-9 rounded-xl" aria-hidden />
        <span className="text-base font-semibold">Social Hood</span>
      </div>
      {children}
    </main>
  );
}

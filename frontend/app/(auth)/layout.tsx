import Link from "next/link";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-1 flex-col">
      <header className="px-6 py-6">
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-sm font-semibold tracking-tight"
        >
          <span className="inline-block size-5 rounded-md bg-primary" />
          PayFast Billing
        </Link>
      </header>
      <main className="flex flex-1 items-center justify-center px-6 py-8">
        <div className="w-full max-w-sm rounded-xl border border-border/60 bg-card p-8 shadow-sm">
          {children}
        </div>
      </main>
    </div>
  );
}

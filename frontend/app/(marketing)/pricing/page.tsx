import { SiteNav } from "@/components/site-nav";
import { PlanCard } from "@/components/plan-card";
import { env } from "@/lib/env";
import { PlanSchema, type Plan } from "@/lib/types";

export const metadata = { title: "Pricing" };

// Always fetch fresh — plan changes should show up without a redeploy.
export const dynamic = "force-dynamic";

type PlansResult =
  | { ok: true; plans: Plan[] }
  | { ok: false; reason: "unreachable" | "shape" | "http"; message?: string };

async function loadPlans(): Promise<PlansResult> {
  let res: Response;
  try {
    res = await fetch(`${env.API_URL.replace(/\/+$/, "")}/plans`, {
      // Server-side fetch; keep it cacheless since plans can change anytime.
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
  } catch {
    return { ok: false, reason: "unreachable" };
  }

  if (!res.ok) {
    return {
      ok: false,
      reason: "http",
      message: `Backend returned ${res.status}`,
    };
  }

  let body: unknown;
  try {
    body = await res.json();
  } catch {
    return { ok: false, reason: "shape", message: "Invalid JSON body" };
  }

  const parsed = PlanSchema.array().safeParse(body);
  if (!parsed.success) {
    return {
      ok: false,
      reason: "shape",
      message: "Unexpected plan shape from API",
    };
  }
  return { ok: true, plans: parsed.data };
}

export default async function PricingPage() {
  const result = await loadPlans();

  return (
    <>
      <SiteNav />
      <main className="flex-1">
        <section className="mx-auto w-full max-w-6xl px-6 py-20">
          <div className="mx-auto mb-14 max-w-2xl text-center">
            <h1 className="text-balance text-4xl font-semibold tracking-tight sm:text-5xl">
              Simple pricing. Start billing today.
            </h1>
            <p className="mt-4 text-muted-foreground">
              Pick a plan that scales with your customers. Switch or cancel
              anytime.
            </p>
          </div>

          {result.ok ? (
            result.plans.length === 0 ? (
              <EmptyState />
            ) : (
              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {result.plans.map((plan, idx) => (
                  <PlanCard
                    key={plan.id}
                    plan={plan}
                    featured={idx === Math.floor(result.plans.length / 2)}
                  />
                ))}
              </div>
            )
          ) : (
            <ErrorState reason={result.reason} message={result.message} />
          )}
        </section>
      </main>
    </>
  );
}

function EmptyState() {
  return (
    <div className="rounded-lg border border-dashed border-border/60 bg-muted/20 p-12 text-center text-sm text-muted-foreground">
      No plans have been published yet. Check back soon.
    </div>
  );
}

function ErrorState({
  reason,
  message,
}: {
  reason: "unreachable" | "shape" | "http";
  message?: string;
}) {
  const headline =
    reason === "unreachable"
      ? "API unreachable"
      : reason === "shape"
        ? "Unexpected response"
        : "Couldn't load plans";

  const body =
    reason === "unreachable"
      ? "We couldn't reach the billing API. If you're running the backend locally, make sure it's started and NEXT_PUBLIC_API_URL points at it."
      : (message ?? "Please try again in a moment.");

  return (
    <div className="rounded-lg border border-border/60 bg-card p-8 text-center">
      <h2 className="text-lg font-semibold">{headline}</h2>
      <p className="mt-2 text-sm text-muted-foreground">{body}</p>
    </div>
  );
}

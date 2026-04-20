"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";

import { AuthField, AuthFormShell } from "@/components/auth-form";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";
import { ApiError, isNetworkError } from "@/lib/api-client";
import { SignupPayloadSchema, type SignupPayload } from "@/lib/types";

export default function SignupPage() {
  // useSearchParams needs a Suspense boundary during prerender in Next 16.
  return (
    <Suspense fallback={null}>
      <SignupForm />
    </Suspense>
  );
}

function SignupForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { signup } = useAuth();
  const [submitting, setSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SignupPayload>({
    resolver: zodResolver(SignupPayloadSchema),
    defaultValues: { email: "", password: "", name: "", phone: "" },
  });

  const onSubmit = async (values: SignupPayload) => {
    setSubmitting(true);
    try {
      await signup(values);
      // Honour `returnTo` (used by the pricing Subscribe CTA) over the generic
      // `plan` fallback so we can drop the user straight into /checkout/initiate.
      const returnTo = searchParams.get("returnTo");
      const plan = searchParams.get("plan");
      const redirect = returnTo
        ? returnTo
        : plan
          ? `/dashboard?plan=${encodeURIComponent(plan)}`
          : "/dashboard";
      router.push(redirect);
    } catch (err) {
      if (isNetworkError(err)) {
        toast.error("Can't reach the server", {
          description:
            "The billing API isn't responding. Check your connection or try again shortly.",
        });
      } else if (err instanceof ApiError) {
        const detail =
          typeof err.body === "object" && err.body && "detail" in err.body
            ? String((err.body as { detail: unknown }).detail)
            : undefined;
        toast.error("Couldn't create account", {
          description:
            detail ??
            (err.status === 409
              ? "An account with this email already exists."
              : `Something went wrong (${err.status}).`),
        });
      } else {
        toast.error("Unexpected error", {
          description:
            err instanceof Error ? err.message : "Please try again.",
        });
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthFormShell
      title="Create your account"
      description="Start billing your customers with PayFast in minutes."
    >
      <form
        className="space-y-4"
        onSubmit={handleSubmit(onSubmit)}
        noValidate
      >
        <AuthField
          id="name"
          label="Full name"
          autoComplete="name"
          placeholder="Ayesha Khan"
          registration={register("name")}
          error={errors.name}
          disabled={submitting}
        />
        <AuthField
          id="email"
          label="Email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          registration={register("email")}
          error={errors.email}
          disabled={submitting}
        />
        <AuthField
          id="phone"
          label="Phone"
          type="tel"
          autoComplete="tel"
          placeholder="+92 300 1234567"
          registration={register("phone")}
          error={errors.phone}
          disabled={submitting}
        />
        <AuthField
          id="password"
          label="Password"
          type="password"
          autoComplete="new-password"
          placeholder="At least 8 characters"
          registration={register("password")}
          error={errors.password}
          disabled={submitting}
        />
        <Button type="submit" className="w-full" disabled={submitting}>
          {submitting ? "Creating account..." : "Create account"}
        </Button>
      </form>
      <p className="text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link
          href="/login"
          className="font-medium text-foreground underline-offset-4 hover:underline"
        >
          Sign in
        </Link>
      </p>
    </AuthFormShell>
  );
}

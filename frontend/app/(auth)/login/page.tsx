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
import { LoginPayloadSchema, type LoginPayload } from "@/lib/types";

export default function LoginPage() {
  // useSearchParams needs a Suspense boundary during prerender in Next 16.
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login } = useAuth();
  const [submitting, setSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginPayload>({
    resolver: zodResolver(LoginPayloadSchema),
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = async (values: LoginPayload) => {
    setSubmitting(true);
    try {
      await login(values);
      // Accept either `redirect` (from the edge proxy) or `returnTo` (from
      // deep links like pricing -> signup -> checkout). Prefer `returnTo`
      // because it's the more intentional signal.
      const redirect =
        searchParams.get("returnTo") ??
        searchParams.get("redirect") ??
        "/dashboard";
      router.push(redirect);
    } catch (err) {
      if (isNetworkError(err)) {
        toast.error("Can't reach the server", {
          description:
            "The billing API isn't responding. Check your connection or try again shortly.",
        });
      } else if (err instanceof ApiError) {
        toast.error("Login failed", {
          description:
            err.status === 400 || err.status === 401
              ? "That email and password don't match."
              : `Something went wrong (${err.status}).`,
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
      title="Welcome back"
      description="Sign in to manage your subscriptions and invoices."
    >
      <form
        className="space-y-4"
        onSubmit={handleSubmit(onSubmit)}
        noValidate
      >
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
          id="password"
          label="Password"
          type="password"
          autoComplete="current-password"
          placeholder="Your password"
          registration={register("password")}
          error={errors.password}
          disabled={submitting}
        />
        <Button type="submit" className="w-full" disabled={submitting}>
          {submitting ? "Signing in..." : "Sign in"}
        </Button>
      </form>
      <p className="text-center text-sm text-muted-foreground">
        Don&apos;t have an account?{" "}
        <Link href="/signup" className="font-medium text-foreground underline-offset-4 hover:underline">
          Create one
        </Link>
      </p>
    </AuthFormShell>
  );
}

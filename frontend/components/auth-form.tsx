"use client";

/**
 * Shared primitives for the login and signup forms.
 *
 * We don't use shadcn's `form.tsx` wrapper (it ships via a registry entry
 * that isn't in the current `base-nova` preset), so we wire
 * react-hook-form + zod directly against shadcn's Input/Label/Button.
 */

import type { FieldError, UseFormRegisterReturn } from "react-hook-form";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

type FieldProps = {
  id: string;
  label: string;
  type?: React.HTMLInputTypeAttribute;
  placeholder?: string;
  autoComplete?: string;
  error?: FieldError;
  /** The spread from react-hook-form's `register(...)`. */
  registration: UseFormRegisterReturn;
  disabled?: boolean;
};

export function AuthField({
  id,
  label,
  type = "text",
  placeholder,
  autoComplete,
  error,
  registration,
  disabled,
}: FieldProps) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        type={type}
        placeholder={placeholder}
        autoComplete={autoComplete}
        disabled={disabled}
        aria-invalid={error ? true : undefined}
        className={cn(error && "border-destructive focus-visible:ring-destructive/30")}
        {...registration}
      />
      {error ? (
        <p className="text-xs text-destructive" role="alert">
          {error.message}
        </p>
      ) : null}
    </div>
  );
}

export function AuthFormShell({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="w-full max-w-sm space-y-6">
      <div className="space-y-2 text-center">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      {children}
    </div>
  );
}

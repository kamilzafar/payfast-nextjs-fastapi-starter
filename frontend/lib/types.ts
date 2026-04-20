/**
 * Zod schemas that mirror the FastAPI backend response shapes.
 *
 * Keep this list intentionally small for phase 1 — add more as each backend
 * endpoint comes online. Using Zod here means we catch shape drift at the
 * API-client boundary instead of at some downstream render crash.
 */
import { z } from "zod";

export const UserSchema = z.object({
  id: z.string(),
  email: z.string().email(),
  is_active: z.boolean().default(true),
  is_verified: z.boolean().default(false),
  // fastapi-users exposes is_superuser; optional here because some deployments
  // disable it.
  is_superuser: z.boolean().default(false).optional(),
  name: z.string().nullable().optional(),
  phone: z.string().nullable().optional(),
});
export type User = z.infer<typeof UserSchema>;

export const PlanSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().nullable().optional(),
  // Backend sends amounts as integer minor units (paisa). We keep the name
  // explicit so UI code can't accidentally treat it as rupees.
  amount_minor: z.number().int(),
  currency: z.string().default("PKR"),
  interval: z.enum(["month", "year"]).default("month"),
  interval_count: z.number().int().positive().default(1),
  // Features are a simple string list for now; richer shape comes in phase 2.
  features: z.array(z.string()).default([]),
});
export type Plan = z.infer<typeof PlanSchema>;

export const SubscriptionStatusSchema = z.enum([
  "trialing",
  "active",
  "past_due",
  "canceled",
]);
export type SubscriptionStatus = z.infer<typeof SubscriptionStatusSchema>;

export const InvoiceStatusSchema = z.enum(["open", "paid", "void"]);
export type InvoiceStatus = z.infer<typeof InvoiceStatusSchema>;

export const SubscriptionSchema = z.object({
  id: z.number().int(),
  user_id: z.string(),
  plan_id: z.number().int(),
  status: SubscriptionStatusSchema,
  current_period_end: z.string().nullable().optional(),
  next_billing_at: z.string().nullable().optional(),
});
export type Subscription = z.infer<typeof SubscriptionSchema>;

/**
 * GET /me/subscription — the current (non-canceled) subscription for the
 * signed-in user, with the plan embedded so the dashboard doesn't need a
 * second round-trip to /plans to render the card.
 *
 * Backend normalizes the plan.interval enum value as a raw string
 * ("monthly" | "yearly"); we're permissive here to avoid schema drift
 * forcing a UI crash.
 */
export const SubscriptionPlanEmbeddedSchema = z.object({
  id: z.number().int(),
  name: z.string(),
  amount_minor: z.number().int(),
  currency: z.string().default("PKR"),
  interval: z.string(),
  trial_days: z.number().int(),
});
export type SubscriptionPlanEmbedded = z.infer<
  typeof SubscriptionPlanEmbeddedSchema
>;

export const SubscriptionOutSchema = z.object({
  id: z.number().int(),
  status: SubscriptionStatusSchema,
  current_period_start: z.string().nullable().optional(),
  current_period_end: z.string().nullable().optional(),
  next_billing_at: z.string().nullable().optional(),
  canceled_at: z.string().nullable().optional(),
  cancel_at_period_end: z.boolean(),
  plan: SubscriptionPlanEmbeddedSchema,
});
export type SubscriptionOut = z.infer<typeof SubscriptionOutSchema>;

export const CancelSubscriptionRequestSchema = z.object({
  at_period_end: z.boolean().default(true),
});
export type CancelSubscriptionRequest = z.infer<
  typeof CancelSubscriptionRequestSchema
>;

export const InvoiceSchema = z.object({
  id: z.number().int(),
  subscription_id: z.number().int(),
  basket_id: z.string().uuid(),
  amount_minor: z.number().int(),
  currency: z.string().default("PKR"),
  status: InvoiceStatusSchema,
  due_at: z.string().nullable().optional(),
  paid_at: z.string().nullable().optional(),
});
export type Invoice = z.infer<typeof InvoiceSchema>;

/** GET /invoices — list response shape. */
export const InvoiceOutSchema = z.object({
  id: z.number().int(),
  basket_id: z.string().uuid(),
  subscription_id: z.number().int(),
  amount_minor: z.number().int(),
  currency: z.string().default("PKR"),
  status: InvoiceStatusSchema,
  due_at: z.string().nullable().optional(),
  paid_at: z.string().nullable().optional(),
  created_at: z.string(),
  payfast_txn_id: z.string().nullable().optional(),
});
export type InvoiceOut = z.infer<typeof InvoiceOutSchema>;

export const InvoiceListSchema = z.object({
  items: z.array(InvoiceOutSchema),
  total: z.number().int().nonnegative(),
});
export type InvoiceList = z.infer<typeof InvoiceListSchema>;

/**
 * POST /subscriptions — creates a subscription and its first open invoice.
 * Backend returns identifiers only; the signed PayFast checkout fields are
 * fetched separately via POST /invoices/{invoice_id}/checkout so that the
 * signature stays short-lived.
 */
export const CreateSubscriptionRequestSchema = z.object({
  plan_id: z.number().int(),
});
export type CreateSubscriptionRequest = z.infer<
  typeof CreateSubscriptionRequestSchema
>;

export const CreateSubscriptionResponseSchema = z.object({
  subscription_id: z.number().int(),
  invoice_id: z.number().int(),
  basket_id: z.string().uuid(),
  // Always null on creation — populated when the user hits /checkout/{id}.
  checkout_url: z.string().url().nullable().optional(),
});
export type CreateSubscriptionResponse = z.infer<
  typeof CreateSubscriptionResponseSchema
>;

/**
 * POST /invoices/{id}/checkout — returns the PayFast auto-post form spec.
 * Front-end builds a hidden <form> with this action and fields and submits
 * it on mount. Signed server-side with the merchant secret.
 */
export const InvoiceCheckoutResponseSchema = z.object({
  action_url: z.string().url(),
  fields: z.record(z.string(), z.string()),
});
export type InvoiceCheckoutResponse = z.infer<
  typeof InvoiceCheckoutResponseSchema
>;

/** fastapi-users login response. */
export const AuthTokenSchema = z.object({
  access_token: z.string(),
  token_type: z.string(),
});
export type AuthToken = z.infer<typeof AuthTokenSchema>;

export const SignupPayloadSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8, "Password must be at least 8 characters"),
  name: z.string().min(1, "Name is required").max(100),
  phone: z
    .string()
    .min(7, "Enter a valid phone number")
    .max(20, "Enter a valid phone number"),
});
export type SignupPayload = z.infer<typeof SignupPayloadSchema>;

export const LoginPayloadSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1, "Password is required"),
});
export type LoginPayload = z.infer<typeof LoginPayloadSchema>;

/** Helper: format minor units as a display string (e.g. 149900 -> "PKR 1,499"). */
export function formatAmount(
  amountMinor: number,
  currency = "PKR",
): string {
  const major = amountMinor / 100;
  const formatted = new Intl.NumberFormat("en-PK", {
    maximumFractionDigits: 0,
  }).format(major);
  return `${currency} ${formatted}`;
}

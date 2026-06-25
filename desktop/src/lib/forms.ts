/**
 * Zod schemas for the modal forms. Centralised so the same rules apply
 * to the "save" path and to inline validation as the user types.
 *
 * Each schema returns either a typed object (on success) or a flat
 * `Record<fieldName, errorMessage>` so the modal can map errors to
 * <FormField error="…">.
 */
import { z } from "zod";

export type FieldErrors<T> = Partial<Record<keyof T, string>>;

/** Run a Zod schema and return a `{ success, data, errors }` triple. */
export function validate<T>(
  schema: z.ZodType<T>,
  raw: unknown,
): { success: true; data: T } | { success: false; errors: FieldErrors<T> } {
  const result = schema.safeParse(raw);
  if (result.success) {
    return { success: true, data: result.data };
  }
  const errors: FieldErrors<T> = {};
  for (const issue of result.error.issues) {
    const key = issue.path[0] as keyof T | undefined;
    if (key && !errors[key]) {
      errors[key] = issue.message;
    }
  }
  return { success: false, errors };
}

// ── Database ──────────────────────────────────────────────────────────────

export const databaseSchema = z.object({
  name: z
    .string()
    .min(1, "Name is required")
    .max(64, "Name must be ≤ 64 chars")
    .regex(/^[a-zA-Z0-9_-]+$/, "Only letters, digits, _ and - are allowed"),
  bastion: z.string().min(1, "Bastion instance is required"),
  host: z
    .string()
    .min(1, "Host is required")
    .max(253, "Host is too long")
    .regex(/^[a-zA-Z0-9._-]+$/, "Invalid hostname or IP"),
  port: z.coerce.number().int("Port must be an integer").min(1).max(65535, "Port out of range"),
  region: z.string().min(1, "Region is required"),
  profile: z.string().optional(),
  local_port: z.coerce.number().int().min(1).max(65535).optional(),
  local_address: z
    .string()
    .regex(/^127\.0\.0\.1$|^localhost$/, "Local address must be 127.0.0.1 or localhost")
    .optional(),
});

export type DatabaseForm = z.infer<typeof databaseSchema>;

// ── Instance ──────────────────────────────────────────────────────────────

export const instanceSchema = z.object({
  name: z
    .string()
    .min(1, "Name is required")
    .max(64, "Name must be ≤ 64 chars")
    .regex(/^[a-zA-Z0-9_-]+$/, "Only letters, digits, _ and - are allowed"),
  instance_id: z
    .string()
    .min(1, "Instance ID is required")
    .regex(/^i-[0-9a-f]{8,17}$/i, "Must look like i-0abc123def456"),
  region: z.string().min(1, "Region is required"),
  profile: z.string().optional(),
});

export type InstanceForm = z.infer<typeof instanceSchema>;

// ── CodeArtifact domain ───────────────────────────────────────────────────

export const codeartifactDomainSchema = z.object({
  domain: z.string().min(1, "Domain is required").max(64),
  repository: z.string().min(1, "Repository is required").max(64),
  namespace: z.string().optional(),
  account_id: z
    .string()
    .regex(/^\d{12}$/, "AWS account ID must be 12 digits")
    .optional()
    .or(z.literal("")),
  profile: z.string().optional(),
  region: z.string().min(1, "Region is required"),
});

export type CodeArtifactDomainForm = z.infer<typeof codeartifactDomainSchema>;

// ── Host ──────────────────────────────────────────────────────────────────

export const hostSchema = z.object({
  ip: z
    .string()
    .min(1, "IP is required")
    .regex(
      /^(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d?\d)$/,
      "Must be a valid IPv4 address",
    ),
  hostname: z
    .string()
    .min(1, "Hostname is required")
    .max(253, "Hostname too long")
    .regex(/^[a-zA-Z0-9._-]+$/, "Invalid hostname"),
});

export type HostForm = z.infer<typeof hostSchema>;

// ── AWS SSO session ──────────────────────────────────────────────────────

export const ssoSessionSchema = z.object({
  name: z
    .string()
    .min(1, "Session name is required")
    .max(64)
    .regex(/^[a-zA-Z0-9_=,.@+-]+$/, "Invalid session name"),
  sso_start_url: z
    .string()
    .min(1, "SSO start URL is required")
    .url("Must be a valid URL (https://…)"),
  sso_region: z
    .string()
    .min(1, "SSO region is required")
    .regex(/^[a-z]{2}-[a-z]+-\d+$/, "Region must look like us-east-1"),
});

export type SsoSessionForm = z.infer<typeof ssoSessionSchema>;

// ── AWS Profile ───────────────────────────────────────────────────────────

export const profileSchema = z.object({
  name: z
    .string()
    .min(1, "Name is required")
    .max(64, "Name must be ≤ 64 chars")
    .regex(/^[a-zA-Z0-9_=,.@+-]+$/, "Only letters, digits and _ - = , . @ + are allowed"),
  sso_session: z.string().optional(),
  sso_account_id: z.string().regex(/^\d{12}$/, "Account ID must be exactly 12 digits"),
  sso_role_name: z
    .string()
    .min(1, "Role name is required")
    .max(64)
    .regex(/^[a-zA-Z0-9_=,.@+-]+$/, "Invalid role name"),
  region: z
    .string()
    .min(1, "Region is required")
    .regex(/^[a-z]{2}-[a-z]+-\d+$/, "Region must look like us-east-1"),
  output: z.string().optional(),
});

export type ProfileForm = z.infer<typeof profileSchema>;

import { z } from "zod";

const envSchema = z.object({
  FLASK_BASE_URL: z.string().url(),
});

const parsed = envSchema.safeParse({
  FLASK_BASE_URL: process.env.FLASK_BASE_URL,
});

if (!parsed.success) {
  const details = parsed.error.flatten().fieldErrors;
  console.error("Invalid environment variables:", details);
  throw new Error("Missing or invalid FLASK_BASE_URL. Set it in next_app/.env.local.");
}

export const env = parsed.data;

export function resolveApiOrigin(configured: string | undefined, mode: string): string {
  const origin = configured?.trim();
  if (origin) return origin.replace(/\/$/, "");
  return mode === "development" ? "http://localhost:8000" : "";
}

export const API_ORIGIN = resolveApiOrigin(
  process.env.NEXT_PUBLIC_API_URL,
  process.env.NODE_ENV,
);

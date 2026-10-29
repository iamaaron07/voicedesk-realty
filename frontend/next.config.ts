import type { NextConfig } from "next";

const apiUrl = process.env.NEXT_PUBLIC_API_URL?.trim();
if (process.env.NODE_ENV === "production" && !apiUrl) {
  throw new Error("NEXT_PUBLIC_API_URL must point to the deployed VoiceDesk backend for production builds.");
}
if (process.env.NODE_ENV === "production" && apiUrl) {
  let parsedApiUrl: URL;
  try { parsedApiUrl = new URL(apiUrl); }
  catch { throw new Error("NEXT_PUBLIC_API_URL must be an absolute HTTPS origin."); }
  if (parsedApiUrl.protocol !== "https:" || parsedApiUrl.pathname !== "/" || parsedApiUrl.search || parsedApiUrl.hash || parsedApiUrl.username || parsedApiUrl.password) {
    throw new Error("NEXT_PUBLIC_API_URL must be the backend's HTTPS origin without credentials, path, query, or fragment.");
  }
}

const config: NextConfig = {};
export default config;

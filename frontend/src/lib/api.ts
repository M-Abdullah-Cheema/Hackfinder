import { Opportunity } from "@/types/opportunity";

/**
 * Always call same-origin Next.js routes.
 * On Vercel these read Supabase directly — works even when your PC is offline.
 * Local FastAPI (:8002) is optional (scraping only).
 */
function apiBase(): string {
  if (typeof window !== "undefined") return "";
  // SSR / server components
  return process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, "") || "http://127.0.0.1:3000";
}

async function timedFetch(url: string, timeoutMs = 12000): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { cache: "no-store", signal: controller.signal });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("API timed out — Supabase/network may be blocked");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export async function fetchOpportunities(params: {
  category?: string;
  organization_name?: string;
  city?: string;
  country?: string;
  domain?: string;
  subcategory?: string;
  lat?: number;
  lng?: number;
  radius_km?: number;
}): Promise<Opportunity[]> {
  const url = new URL(`${apiBase()}/api/opportunities`);
  if (params.category) url.searchParams.set("category", params.category);
  if (params.organization_name)
    url.searchParams.set("organization_name", params.organization_name);
  if (params.city) url.searchParams.set("city", params.city);
  if (params.country) url.searchParams.set("country", params.country);
  if (params.domain) url.searchParams.set("domain", params.domain);
  if (params.subcategory) url.searchParams.set("subcategory", params.subcategory);
  if (params.lat != null) url.searchParams.set("lat", String(params.lat));
  if (params.lng != null) url.searchParams.set("lng", String(params.lng));
  if (params.radius_km != null)
    url.searchParams.set("radius_km", String(params.radius_km));
  url.searchParams.set("upcoming_only", "true");
  url.searchParams.set("limit", "200");

  const res = await timedFetch(url.toString());
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = body?.detail || "";
    } catch {
      /* ignore */
    }
    throw new Error(
      detail ||
        `API error ${res.status} — check Supabase env vars on Vercel / .env.local`
    );
  }
  return res.json();
}

export async function fetchCategories(): Promise<string[]> {
  try {
    const res = await timedFetch(`${apiBase()}/api/opportunities/categories`);
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export async function fetchOrganizations(): Promise<string[]> {
  try {
    const res = await timedFetch(`${apiBase()}/api/opportunities/organizations`);
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

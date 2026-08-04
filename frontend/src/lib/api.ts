import { Opportunity } from "@/types/opportunity";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8002";

async function timedFetch(url: string, timeoutMs = 8000): Promise<Response> {
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
  const url = new URL(`${API_BASE}/api/opportunities`);
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
  url.searchParams.set("limit", "200");

  const res = await timedFetch(url.toString());
  if (!res.ok) {
    throw new Error(
      `API error ${res.status} — database may be unreachable on this network`
    );
  }
  return res.json();
}

export async function fetchCategories(): Promise<string[]> {
  try {
    const res = await timedFetch(`${API_BASE}/api/opportunities/categories`);
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export async function fetchOrganizations(): Promise<string[]> {
  try {
    const res = await timedFetch(`${API_BASE}/api/opportunities/organizations`);
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

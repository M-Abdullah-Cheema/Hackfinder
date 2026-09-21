import { Opportunity } from "@/types/opportunity";

/** Same-origin Next.js routes (Supabase-backed on Vercel). */
async function timedFetch(path: string, timeoutMs = 15000): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(path, { cache: "no-store", signal: controller.signal });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("Request timed out. Please refresh and try again.");
    }
    throw new Error("Could not reach QuestHub. Please refresh.");
  } finally {
    clearTimeout(timer);
  }
}

function buildQuery(params: Record<string, string | number | undefined>): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") qs.set(k, String(v));
  }
  return qs.toString();
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
  const query = buildQuery({
    category: params.category,
    organization_name: params.organization_name,
    city: params.city,
    country: params.country,
    domain: params.domain,
    subcategory: params.subcategory,
    lat: params.lat,
    lng: params.lng,
    radius_km: params.radius_km,
    upcoming_only: "true",
    limit: 200,
  });

  const res = await timedFetch(`/api/opportunities?${query}`);
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = body?.detail || "";
    } catch {
      /* ignore */
    }
    throw new Error(detail || "Unable to load opportunities right now.");
  }

  const data = await res.json();
  if (!Array.isArray(data)) {
    throw new Error("Unexpected response from QuestHub API.");
  }
  return data;
}

export async function fetchCategories(): Promise<string[]> {
  try {
    const res = await timedFetch("/api/opportunities/categories");
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

export async function fetchOrganizations(): Promise<string[]> {
  try {
    const res = await timedFetch("/api/opportunities/organizations");
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

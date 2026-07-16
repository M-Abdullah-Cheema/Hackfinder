import { Opportunity } from "@/types/opportunity";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

export async function fetchOpportunities(params: {
  category?: string;
  organization_name?: string;
}): Promise<Opportunity[]> {
  const url = new URL(`${API_BASE}/api/opportunities`);
  if (params.category) url.searchParams.set("category", params.category);
  if (params.organization_name)
    url.searchParams.set("organization_name", params.organization_name);
  url.searchParams.set("limit", "200");

  const res = await fetch(url.toString(), { cache: "no-store" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function fetchCategories(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/api/opportunities/categories`, {
    cache: "no-store",
  });
  if (!res.ok) return [];
  return res.json();
}

export async function fetchOrganizations(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/api/opportunities/organizations`, {
    cache: "no-store",
  });
  if (!res.ok) return [];
  return res.json();
}

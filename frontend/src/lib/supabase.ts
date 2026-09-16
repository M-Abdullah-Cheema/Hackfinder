import { createClient, SupabaseClient } from "@supabase/supabase-js";
import type { Opportunity } from "@/types/opportunity";

let _client: SupabaseClient | null = null;

export function getSupabaseAdmin(): SupabaseClient {
  if (_client) return _client;

  const url = (
    process.env.SUPABASE_URL ||
    process.env.NEXT_PUBLIC_SUPABASE_URL ||
    ""
  ).trim();
  const key = (
    process.env.SUPABASE_SERVICE_ROLE_KEY ||
    process.env.SUPABASE_ANON_KEY ||
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
    ""
  ).trim();

  if (!url || !key) {
    throw new Error(
      "Missing SUPABASE_URL / NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or anon key)"
    );
  }

  _client = createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  return _client;
}

const OPP_COLUMNS =
  "id,title,organization_name,category,registration_url,platform_post_id,latitude,longitude,city,country,start_datetime_utc,end_datetime_utc,local_timezone,domain,subcategory,format";

export async function fetchOpportunitiesFromDb(params: {
  category?: string | null;
  organization_name?: string | null;
  city?: string | null;
  country?: string | null;
  domain?: string | null;
  subcategory?: string | null;
  limit?: number;
}): Promise<Opportunity[]> {
  const sb = getSupabaseAdmin();
  let q = sb
    .from("final_opportunities")
    .select(OPP_COLUMNS)
    .order("id", { ascending: false })
    .limit(params.limit ?? 200);

  if (params.category) q = q.eq("category", params.category);
  if (params.organization_name)
    q = q.ilike("organization_name", `%${params.organization_name}%`);
  if (params.city) q = q.ilike("city", `%${params.city}%`);
  if (params.country) q = q.ilike("country", `%${params.country}%`);
  if (params.domain) q = q.ilike("domain", params.domain);
  if (params.subcategory)
    q = q.ilike("subcategory", `%${params.subcategory}%`);

  const { data, error } = await q;
  if (error) throw new Error(error.message);
  return (data || []) as Opportunity[];
}

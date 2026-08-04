export interface Opportunity {
  id: number;
  title: string;
  organization_name: string;
  category: string;
  registration_url: string | null;
  platform_post_id: string;
  latitude?: number | null;
  longitude?: number | null;
  city?: string | null;
  country?: string | null;
  start_datetime_utc?: string | null;
  end_datetime_utc?: string | null;
  local_timezone?: string | null;
  domain?: string | null;
  subcategory?: string | null;
  format?: string | null;
}

export type Category =
  | "Hackathon"
  | "Internship"
  | "Workshop"
  | "Job"
  | "Scholarship"
  | "Other";

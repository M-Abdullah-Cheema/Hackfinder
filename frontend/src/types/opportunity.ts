export interface Opportunity {
  id: number;
  title: string;
  organization_name: string;
  category: string;
  registration_url: string | null;
  platform_post_id: string;
}

export type Category =
  | "Hackathon"
  | "Internship"
  | "Workshop"
  | "Job"
  | "Scholarship"
  | "Other";

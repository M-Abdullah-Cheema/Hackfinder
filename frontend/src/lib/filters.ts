/** Upcoming/ongoing filter — mirrors core/event_time.py */
export function isUpcomingOpportunity(
  opp: {
    start_datetime_utc?: string | null;
    end_datetime_utc?: string | null;
  },
  includeUndated = true
): boolean {
  const now = Date.now();
  const startOfToday = new Date();
  startOfToday.setUTCHours(0, 0, 0, 0);
  const todayMs = startOfToday.getTime();

  const start = opp.start_datetime_utc
    ? new Date(opp.start_datetime_utc).getTime()
    : null;
  const end = opp.end_datetime_utc
    ? new Date(opp.end_datetime_utc).getTime()
    : null;

  if (end != null && !Number.isNaN(end) && end >= now) return true;
  if (start != null && !Number.isNaN(start) && start >= todayMs) return true;
  if (start != null && end == null && !Number.isNaN(start) && start < todayMs)
    return false;
  if (end != null && !Number.isNaN(end) && end < now) return false;
  if (start == null && end == null) return includeUndated;
  return false;
}

export function haversineKm(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  const r = 6371;
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dphi = ((lat2 - lat1) * Math.PI) / 180;
  const dlmb = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dphi / 2) ** 2 +
    Math.cos(p1) * Math.cos(p2) * Math.sin(dlmb / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(a));
}

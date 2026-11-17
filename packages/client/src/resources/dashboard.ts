import type {
  DailyUsage,
  DashboardSummary,
  HourlyUsage,
} from "../types.js";

type FetchFn = (path: string, init?: RequestInit) => Promise<Response>;

export class DashboardResource {
  constructor(private readonly request: FetchFn) {}

  /**
   * Get workspace overview, credit balance, and 30-day totals.
   */
  async getSummary(): Promise<DashboardSummary> {
    const response = await this.request("/v1/dashboard/summary", {
      method: "GET",
    });
    return (await response.json()) as DashboardSummary;
  }

  /**
   * Get per-day aggregated usage metrics.
   */
  async getDailyUsage(options?: { days?: number; keyId?: string }): Promise<DailyUsage[]> {
    const params = new URLSearchParams();
    if (options?.days) params.set("days", String(options.days));
    if (options?.keyId) params.set("key_id", options.keyId);

    const qs = params.toString() ? `?${params.toString()}` : "";
    const response = await this.request(`/v1/dashboard/usage/daily${qs}`, {
      method: "GET",
    });
    const data = (await response.json()) as { days: DailyUsage[] };
    return data.days;
  }

  /**
   * Get per-hour aggregated usage metrics for recent operations.
   */
  async getHourlyUsage(options?: { hours?: number; keyId?: string }): Promise<HourlyUsage[]> {
    const params = new URLSearchParams();
    if (options?.hours) params.set("hours", String(options.hours));
    if (options?.keyId) params.set("key_id", options.keyId);

    const qs = params.toString() ? `?${params.toString()}` : "";
    const response = await this.request(`/v1/dashboard/usage/hourly${qs}`, {
      method: "GET",
    });
    const data = (await response.json()) as { hours: HourlyUsage[] };
    return data.hours;
  }
}

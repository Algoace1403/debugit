import type { HealResponse, RunStatus, Results } from "../types";

const BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json();
}

export function startHeal(
  repo_url: string,
  team_name: string,
  leader_name: string
): Promise<HealResponse> {
  return request("/api/v1/heal", {
    method: "POST",
    body: JSON.stringify({ repo_url, team_name, leader_name }),
  });
}

export function getRun(runId: string): Promise<RunStatus> {
  return request(`/api/v1/runs/${runId}`);
}

export function getResults(runId: string): Promise<Results> {
  return request(`/api/v1/runs/${runId}/results`);
}

export function listRuns(): Promise<{ runs: Array<Record<string, unknown>> }> {
  return request("/api/v1/runs");
}

export function getWsUrl(runId: string): string {
  const base = import.meta.env.VITE_WS_URL
    || BASE_URL.replace(/^http/, "ws");
  return `${base}/ws/${runId}`;
}

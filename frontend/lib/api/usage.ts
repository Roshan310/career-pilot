import { api } from "./client";
import type { Usage } from "../types";

export function getUsage(): Promise<Usage> {
  return api.get<Usage>("/api/usage");
}

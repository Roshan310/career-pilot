import { api, tokenStore } from "./client";
import type { AccessTokenResponse, TokenResponse, User } from "../types";

export async function login(email: string, password: string): Promise<User> {
  const tokens = await api.postPublic<TokenResponse>("/api/auth/login", { email, password });
  tokenStore.set(tokens.access_token, tokens.refresh_token);
  return getMe();
}

export async function register(
  email: string,
  password: string,
  name?: string,
): Promise<User> {
  await api.postPublic<User>("/api/auth/register", { email, password, name: name || null });
  // Registration doesn't return tokens — log in immediately after.
  return login(email, password);
}

export function getMe(): Promise<User> {
  return api.get<User>("/api/auth/me");
}

export function refresh(refresh_token: string): Promise<AccessTokenResponse> {
  return api.postPublic<AccessTokenResponse>("/api/auth/refresh", { refresh_token });
}

export function logout(): void {
  tokenStore.clear();
}

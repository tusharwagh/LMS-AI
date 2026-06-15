import { api, setToken } from "./client";
import type { TokenResponse, User } from "./types";

const USER_KEY = "lms_staff_user";

export function getStoredUser(): User | null {
  const raw = sessionStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

export function storeUser(user: User): void {
  sessionStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearStoredUser(): void {
  sessionStorage.removeItem(USER_KEY);
}

export async function login(username: string, password: string): Promise<User> {
  const form = new FormData();
  form.append("username", username);
  form.append("password", password);
  const tokenRes = await fetch("/api/v1/auth/token", { method: "POST", body: form });
  const tokenBody = (await tokenRes.json()) as TokenResponse & { message?: string };
  if (!tokenRes.ok) {
    throw new Error(tokenBody.message ?? "Sign in failed");
  }
  setToken(tokenBody.access_token);
  const me = await api<User>("/api/v1/auth/me");
  storeUser(me);
  return me;
}

export async function fetchCurrentUser(): Promise<User> {
  const me = await api<User>("/api/v1/auth/me");
  storeUser(me);
  return me;
}

export function logout(): void {
  clearStoredUser();
}

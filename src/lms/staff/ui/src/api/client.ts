import type { ApiErrorBody } from "./types";

const TOKEN_KEY = "lms_staff_token";

export class ApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
}

function parseError(body: ApiErrorBody | string | null): string {
  if (!body) return "Request failed";
  if (typeof body === "string") return body;
  if (body.message) return body.message;
  if (typeof body.detail === "object" && body.detail?.message) return body.detail.message;
  if (typeof body.detail === "string") return body.detail;
  if (body.details?.violations?.length) {
    return body.details.violations.map((v) => v.message).join("; ");
  }
  if (
    typeof body.detail === "object" &&
    body.detail.details?.violations?.length
  ) {
    return body.detail.details.violations.map((v) => v.message).join("; ");
  }
  return JSON.stringify(body);
}

export type UnauthorizedHandler = () => void;

let onUnauthorized: UnauthorizedHandler | null = null;

export function setUnauthorizedHandler(handler: UnauthorizedHandler): void {
  onUnauthorized = handler;
}

export type ApiRequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
};

export async function api<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> | undefined),
  };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let body = options.body as BodyInit | undefined;
  if (options.body !== undefined && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  const { body: _ignored, ...rest } = options;
  const res = await fetch(path, { ...rest, headers, body });

  let data: ApiErrorBody | string | null = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text) as ApiErrorBody;
    } catch {
      data = text;
    }
  }

  if (!res.ok) {
    if (res.status === 401) {
      clearToken();
      onUnauthorized?.();
    }
    throw new ApiError(parseError(data));
  }

  return data as T;
}

export async function apiWithIdempotency<T>(
  path: string,
  body: unknown,
  idempotencyKey: string,
): Promise<T> {
  return api<T>(path, {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body,
  });
}

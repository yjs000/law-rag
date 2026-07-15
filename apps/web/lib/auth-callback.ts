const DEFAULT_AUTH_SUCCESS_PATH = "/?auth=success";

export function safeAuthNextPath(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) {
    return DEFAULT_AUTH_SUCCESS_PATH;
  }
  return value;
}

export function callbackBaseUrl(requestOrigin: string, configuredSiteUrl?: string): string {
  if (!configuredSiteUrl) return requestOrigin;
  try {
    const request = new URL(requestOrigin);
    const configured = new URL(configuredSiteUrl);
    const isLocalDevelopment = request.hostname === "localhost"
      && configured.hostname === "localhost"
      && configured.protocol === "http:";
    if (configured.protocol !== "https:" && !isLocalDevelopment) {
      return requestOrigin;
    }
    return configured.origin;
  } catch {
    return requestOrigin;
  }
}

export function authErrorPath(error: string | null): string {
  return error === "access_denied"
    ? "/?auth=error&error=access_denied"
    : "/?auth=error";
}

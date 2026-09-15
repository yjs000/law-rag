export function backendDisplayMessage(payload: unknown): string | null {
  if (typeof payload === "string") return payload;
  if (!isRecord(payload)) return null;
  if (typeof payload.message === "string") return payload.message;
  const detail = payload.detail;
  if (isRecord(detail) && typeof detail.message === "string") return detail.message;
  if (typeof detail === "string") return detail;
  if (isRecord(detail) && typeof detail.code === "string") return detail.code;
  if (typeof payload.reason_code === "string") return payload.reason_code;
  return typeof payload.code === "string" ? payload.code : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

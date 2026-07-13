export const LOGIN_PROMPT_KEY = "law-rag-anonymous-login-prompted";

type SessionStorage = Pick<Storage, "getItem" | "setItem">;

export function claimAnonymousLoginPrompt(storage: SessionStorage): boolean {
  if (storage.getItem(LOGIN_PROMPT_KEY) === "true") return false;
  storage.setItem(LOGIN_PROMPT_KEY, "true");
  return true;
}

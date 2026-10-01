export type DevIdentity = { subject: string; email: string; displayName: string };
const KEY = "automation-platform-dev-identity";
const fallback: DevIdentity = { subject: "dev-user-001", email: "qa.engineer@example.invalid", displayName: "QA Engineer" };
export function getIdentity(): DevIdentity {
  if (typeof window === "undefined") return fallback;
  const raw = window.localStorage.getItem(KEY);
  if (!raw) return fallback;
  try { return { ...fallback, ...JSON.parse(raw) }; } catch { return fallback; }
}
export function setIdentity(identity: DevIdentity) { window.localStorage.setItem(KEY, JSON.stringify(identity)); }
export function devHeaders(): Record<string,string> {
  const i=getIdentity();
  return { "X-Dev-User-Sub":i.subject, "X-Dev-User-Email":i.email, "X-Dev-User-Name":i.displayName };
}

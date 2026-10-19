import { devHeaders } from "./auth";

// The API lives on the same machine as this page, port 8080. With NEXT_PUBLIC_CONTROL_PLANE_URL unset or "auto" the address is taken from the
// address the page was opened with, so the same build works as localhost, on the office network, over a VPN or on a hotspot.
export function apiBase(): string {
  const configured = process.env.NEXT_PUBLIC_CONTROL_PLANE_URL;
  if (configured && configured !== "auto") return configured;
  if (typeof window !== "undefined") return `${window.location.protocol}//${window.location.hostname}:8080`;
  return "http://localhost:8080";
}

function headers(init?: RequestInit): Record<string,string> {
  return {"Content-Type":"application/json", ...devHeaders(), ...(init?.headers as Record<string,string>|undefined)};
}

function errorMessage(body:any, fallback:string):string {
  if(typeof body?.message==="string") return body.message;
  if(typeof body?.detail==="string") return body.detail;
  if(body?.detail && typeof body.detail.message==="string") {
    const code=typeof body.detail.code==="string" ? `${body.detail.code}: ` : "";
    return code + body.detail.message;
  }
  if(typeof body?.error==="string") return body.error;
  return fallback;
}

export async function api<T>(path:string, init:RequestInit={}):Promise<T>{
  const res=await fetch(`${apiBase()}${path}`,{...init,headers:headers(init),cache:"no-store"});
  if(!res.ok){ const fallback=`Request failed (${res.status})`; const body=await res.json().catch(()=>null); throw new Error(errorMessage(body,fallback)); }
  if(res.status===204) return undefined as T;
  return res.json() as Promise<T>;
}

export async function apiBlob(path:string, init:RequestInit={}):Promise<Blob>{
  const res=await fetch(`${apiBase()}${path}`,{...init,headers:headers(init),cache:"no-store"});
  if(!res.ok){ const fallback=`Request failed (${res.status})`; const body=await res.json().catch(()=>null); throw new Error(errorMessage(body,fallback)); }
  return res.blob();
}

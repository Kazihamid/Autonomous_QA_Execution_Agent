"use client";
import Link from "next/link";
import { getIdentity } from "@/lib/auth";
export default function AppShell({children}:{children:React.ReactNode}){
  const identity=typeof window==="undefined"?null:getIdentity();
  return <div className="shell"><header className="topbar"><Link href="/workspaces" className="brand">Autonomous QA Execution Agent</Link><div className="identity">{identity?.displayName ?? "QA Engineer"} · <Link href="/login"><u>change dev identity</u></Link></div></header><main>{children}</main></div>;
}


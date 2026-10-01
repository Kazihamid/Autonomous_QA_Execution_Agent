"use client";
import { FormEvent, useEffect, useState } from "react";
import { getIdentity, setIdentity } from "@/lib/auth";
import { useRouter } from "next/navigation";
export default function LoginPage(){
 const router=useRouter(); const [subject,setSubject]=useState(""); const [email,setEmail]=useState(""); const [name,setName]=useState("");
 useEffect(()=>{const i=getIdentity();setSubject(i.subject);setEmail(i.email);setName(i.displayName)},[]);
 function submit(e:FormEvent){e.preventDefault();setIdentity({subject,email,displayName:name});router.push("/workspaces")}
 return <div className="login"><form className="card stack" onSubmit={submit}><div><h1>Local Development Sign-In</h1><p className="muted">This screen exists only for the isolated Spring <code>dev</code> profile. Production uses OIDC/JWT.</p></div><label>Identity subject<input value={subject} onChange={e=>setSubject(e.target.value)} required/></label><label>Email<input type="email" value={email} onChange={e=>setEmail(e.target.value)} required/></label><label>Display name<input value={name} onChange={e=>setName(e.target.value)} required/></label><button type="submit">Continue to workspaces</button></form></div>;
}

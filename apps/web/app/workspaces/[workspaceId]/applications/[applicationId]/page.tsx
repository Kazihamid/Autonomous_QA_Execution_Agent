"use client";

import AppShell from "@/components/AppShell";
import { api } from "@/lib/api";
import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

type A={id:string;name:string;description?:string;status:string};
type E={id:string;name:string;baseUrl:string;defaultBrowser:string;headlessDefault:boolean;allowRecording:boolean;allowExecution:boolean;validationStatus:string;status:string};

export default function ApplicationPage(){
  const {workspaceId,applicationId}=useParams<{workspaceId:string;applicationId:string}>();
  const [app,setApp]=useState<A|null>(null);
  const [envs,setEnvs]=useState<E[]>([]);
  const [name,setName]=useState("QA");
  const [baseUrl,setBaseUrl]=useState("https://qa.example.invalid");
  const [browser,setBrowser]=useState("CHROMIUM");
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");

  async function load(){
    try{
      const [a,e]=await Promise.all([
        api<A>(`/api/v1/workspaces/${workspaceId}/applications/${applicationId}`),
        api<E[]>(`/api/v1/workspaces/${workspaceId}/applications/${applicationId}/environments`)
      ]);
      setApp(a);setEnvs(e);
    }catch(err){setError((err as Error).message)}
  }
  useEffect(()=>{load()},[workspaceId,applicationId]);
  async function validate(){
    try{
      setError("");
      const r=await api<{dnsResolved:boolean;warnings:string[]}>(`/api/v1/workspaces/${workspaceId}/applications/${applicationId}/target-validation`,{method:"POST",body:JSON.stringify({url:baseUrl})});
      setMessage(r.dnsResolved?"Target passed policy and DNS resolution.":`Target passed configuration policy but DNS is unverified. ${r.warnings.join(" ")}`);
    }catch(e){setMessage("");setError((e as Error).message)}
  }

  async function create(e:FormEvent){
    e.preventDefault();
    try{
      setError("");
      await api(`/api/v1/workspaces/${workspaceId}/applications/${applicationId}/environments`,{
        method:"POST",body:JSON.stringify({name,baseUrl,defaultBrowser:browser,headlessDefault:true,allowRecording:true,allowExecution:true})
      });
      setMessage("Environment created.");await load();
    }catch(e){setError((e as Error).message)}
  }

  async function updateEnvironment(env:E, changes:Partial<E>){
    const next={...env,...changes};
    await api(`/api/v1/workspaces/${workspaceId}/applications/${applicationId}/environments/${env.id}`,{
      method:"PUT",
      body:JSON.stringify({
        name:next.name,baseUrl:next.baseUrl,defaultBrowser:next.defaultBrowser,
        headlessDefault:next.headlessDefault,allowRecording:next.allowRecording,
        allowExecution:next.allowExecution,status:next.status
      })
    });
  }

  async function editEnvironment(env:E){
    const newName=window.prompt("Environment name",env.name);
    if(newName===null||!newName.trim())return;
    const newBaseUrl=window.prompt("Base URL",env.baseUrl);
    if(newBaseUrl===null||!newBaseUrl.trim())return;
    try{
      setError("");setMessage("");
      await updateEnvironment(env,{name:newName.trim(),baseUrl:newBaseUrl.trim()});
      setMessage("Environment updated.");await load();
    }catch(e){setError((e as Error).message)}
  }

  async function toggleEnvironment(env:E){
    const nextStatus=env.status==="ACTIVE"?"INACTIVE":"ACTIVE";
    const verb=nextStatus==="ACTIVE"?"enable":"disable";
    if(!window.confirm(`Do you want to ${verb} environment "${env.name}"?`))return;
    try{
      setError("");setMessage("");
      await updateEnvironment(env,{status:nextStatus});
      setMessage(`Environment ${nextStatus==="ACTIVE"?"enabled":"disabled"}.`);await load();
    }catch(e){setError((e as Error).message)}
  }

  async function deleteEnvironment(env:E){
    if(!window.confirm(`Delete environment "${env.name}" permanently? Environments with recording history cannot be deleted.`))return;
    try{
      setError("");setMessage("");
      await api(`/api/v1/workspaces/${workspaceId}/applications/${applicationId}/environments/${env.id}`,{method:"DELETE"});
      setMessage("Environment deleted.");await load();
    }catch(e){setError((e as Error).message)}
  }
  return <AppShell>
    <div className="breadcrumb"><Link href="/workspaces">Workspaces</Link><span>/</span><Link href={`/workspaces/${workspaceId}`}>Workspace</Link><span>/</span><span>{app?.name??"Application"}</span></div>
    <div className="hero"><div><h1>{app?.name??"Application"}</h1><p className="muted">Configure target environments, record manual tests and manage framework-neutral scenarios.</p></div><div className="actions"><Link className="button secondary" href={`/workspaces/${workspaceId}/applications/${applicationId}/scenarios`}>Scenario repository</Link><span className="badge">{app?.status}</span></div></div>
    {error&&<div className="error">{error}</div>}
    {message&&<div className="success" style={{marginTop:10}}>{message}</div>}
    <div className="grid environment-layout" style={{marginTop:16}}>
      <section className="card"><h2>Add environment</h2><form className="stack" onSubmit={create}>
        <label>Name<input value={name} onChange={e=>setName(e.target.value)} required/></label>
        <label>Base URL<input value={baseUrl} onChange={e=>setBaseUrl(e.target.value)} required/></label>
        <label>Default browser<select value={browser} onChange={e=>setBrowser(e.target.value)}><option>CHROMIUM</option><option>FIREFOX</option><option>WEBKIT</option></select></label>
        <div className="actions"><button type="button" className="secondary" onClick={validate}>Validate target</button><button type="submit">Create environment</button></div>
      </form></section>
      <section className="card"><h2>Environments</h2>
        {envs.length===0?<div className="empty">No environments configured.</div>:<table className="table"><thead><tr><th>Name</th><th>URL</th><th>Browser</th><th>Validation</th><th>Actions</th></tr></thead>
        <tbody>{envs.map(e=><tr key={e.id}>
          <td><strong>{e.name}</strong><div className="muted">{e.status}</div></td>
          <td className="url-cell">{e.baseUrl}</td><td>{e.defaultBrowser}</td>
          <td><span className={`badge ${e.validationStatus==="VALIDATED"?"ok":"warn"}`}>{e.validationStatus}</span></td>
          <td className="environment-actions-cell"><div className="actions environment-actions">{e.allowRecording&&e.status==="ACTIVE"?<Link className="button compact" href={`/workspaces/${workspaceId}/applications/${applicationId}/environments/${e.id}/record`}>Record Test</Link>:null}<button className="secondary compact" onClick={()=>editEnvironment(e)}>Edit</button><button className="secondary compact" onClick={()=>toggleEnvironment(e)}>{e.status==="ACTIVE"?"Disable":"Enable"}</button><button className="secondary compact" onClick={()=>deleteEnvironment(e)}>Delete</button></div></td>
        </tr>)}</tbody></table>}
      </section>
    </div>
    <section className="card" style={{marginTop:16}}><h2>v0.1.2 Stability</h2><p className="muted">Environment management now supports editing and safe enable/disable controls. Scenario Run and Export use recorder locator validation and environment-based configuration.</p></section>
  </AppShell>
}

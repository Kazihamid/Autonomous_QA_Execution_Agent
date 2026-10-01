"use client";
import AppShell from "@/components/AppShell";
import { api } from "@/lib/api";
import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent,useEffect,useState } from "react";

type W={id:string;key:string;name:string;description?:string;role:string};
type A={id:string;name:string;description?:string;status:string};

export default function WorkspacePage(){
  const {workspaceId}=useParams<{workspaceId:string}>();
  const [w,setW]=useState<W|null>(null);
  const [apps,setApps]=useState<A[]>([]);
  const [name,setName]=useState("");
  const [description,setDescription]=useState("");
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");

  async function load(){
    try{
      const [wr,ar]=await Promise.all([
        api<W>(`/api/v1/workspaces/${workspaceId}`),
        api<A[]>(`/api/v1/workspaces/${workspaceId}/applications`)
      ]);
      setW(wr);setApps(ar);
    }catch(e){setError((e as Error).message)}
  }
  useEffect(()=>{load()},[workspaceId]);

  async function create(e:FormEvent){
    e.preventDefault();
    try{
      setError("");setMessage("");
      await api(`/api/v1/workspaces/${workspaceId}/applications`,{method:"POST",body:JSON.stringify({name,description})});
      setName("");setDescription("");setMessage("Application created.");await load();
    }catch(e){setError((e as Error).message)}
  }

  async function editApplication(a:A){
    const newName=window.prompt("Application name",a.name);
    if(newName===null||!newName.trim())return;
    const newDescription=window.prompt("Description",a.description??"");
    if(newDescription===null)return;
    try{
      setError("");setMessage("");
      await api(`/api/v1/workspaces/${workspaceId}/applications/${a.id}`,{
        method:"PUT",body:JSON.stringify({name:newName.trim(),description:newDescription,status:a.status})
      });
      setMessage("Application updated.");await load();
    }catch(e){setError((e as Error).message)}
  }

  async function archiveApplication(a:A){
    if(!window.confirm(`Archive application "${a.name}"? Existing scenarios and history will be preserved.`))return;
    try{
      setError("");setMessage("");
      await api(`/api/v1/workspaces/${workspaceId}/applications/${a.id}`,{
        method:"PUT",body:JSON.stringify({name:a.name,description:a.description??"",status:"ARCHIVED"})
      });
      setMessage("Application archived.");await load();
    }catch(e){setError((e as Error).message)}
  }

  async function deleteApplication(a:A){
    if(!window.confirm(`Delete application "${a.name}" permanently? This is allowed only when it has no dependent environments, scenarios, or recording history.`))return;
    try{
      setError("");setMessage("");
      await api(`/api/v1/workspaces/${workspaceId}/applications/${a.id}`,{method:"DELETE"});
      setMessage("Application deleted.");await load();
    }catch(e){setError((e as Error).message)}
  }
  return <AppShell>
    <div className="breadcrumb"><Link href="/workspaces">Workspaces</Link><span>/</span><span>{w?.name??"Loading"}</span></div>
    <div className="hero"><div><h1>{w?.name??"Workspace"}</h1><p className="muted">{w?.key} · Your role: {w?.role}</p></div></div>
    {error&&<div className="error">{error}</div>}
    {message&&<div className="success" style={{marginTop:10}}>{message}</div>}
    <div className="grid" style={{marginTop:16}}>
      <section className="card"><h2>Create application</h2><form className="stack" onSubmit={create}>
        <label>Application name<input value={name} onChange={e=>setName(e.target.value)} required/></label>
        <label>Description<textarea value={description} onChange={e=>setDescription(e.target.value)}/></label>
        <button>Create application</button>
      </form></section>
      <section className="card"><h2>Applications</h2>
        {apps.length===0?<div className="empty">No applications yet.</div>:<div className="stack">{apps.map(a=>
          <div key={a.id} className="card">
            <div className="actions" style={{justifyContent:"space-between"}}><Link className="table-link" href={`/workspaces/${workspaceId}/applications/${a.id}`}><strong>{a.name}</strong></Link><span className="badge">{a.status}</span></div>
            {a.description&&<p className="muted">{a.description}</p>}
            <div className="actions"><Link className="button secondary compact" href={`/workspaces/${workspaceId}/applications/${a.id}`}>Open</Link><button className="secondary compact" onClick={()=>editApplication(a)}>Edit</button>{a.status!=="ARCHIVED"&&<button className="secondary compact" onClick={()=>archiveApplication(a)}>Archive</button>}<button className="secondary compact" onClick={()=>deleteApplication(a)}>Delete</button></div>
          </div>)}</div>}
      </section>
    </div>
  </AppShell>
}

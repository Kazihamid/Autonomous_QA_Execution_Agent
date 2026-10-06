"use client";
import AppShell from "@/components/AppShell";
import {api} from "@/lib/api";
import Link from "next/link";
import {useParams,useRouter} from "next/navigation";
import {useEffect,useMemo,useState} from "react";

type Param={type?:string;default?:unknown};
type Step={id:string;action:string;element?:string;value?:{source?:string;reference?:string}};
type Ir={parameters?:Record<string,Param>;steps?:Step[]};
type Detail={scenario:{id:string;moduleName?:string;featureName?:string;name:string;currentVersion:number};versionNo:number;automationIr:Ir};
type Created={id:string};

export default function EditScenario(){
  const {workspaceId,applicationId,scenarioId}=useParams<{workspaceId:string;applicationId:string;scenarioId:string}>();
  const router=useRouter();
  const base=`/api/v1/workspaces/${workspaceId}/applications/${applicationId}`;
  const [d,setD]=useState<Detail|null>(null);
  const [name,setName]=useState("");const [moduleName,setModuleName]=useState("");const [featureName,setFeatureName]=useState("");
  const [params,setParams]=useState<Record<string,string>>({});
  const [secrets,setSecrets]=useState<Record<string,string>>({});
  const [error,setError]=useState("");const [busy,setBusy]=useState(false);

  useEffect(()=>{(async()=>{
    try{
      const detail=await api<Detail>(`${base}/scenarios/${scenarioId}`);
      setD(detail);
      setName(`${detail.scenario.name} (copy)`);
      setModuleName(detail.scenario.moduleName||"");setFeatureName(detail.scenario.featureName||"");
      const p:Record<string,string>={};
      Object.entries(detail.automationIr.parameters||{}).forEach(([k,v])=>{p[k]=v.default==null?"":String(v.default)});
      setParams(p);
      const s:Record<string,string>={};
      (detail.automationIr.steps||[]).forEach(st=>{if(st.value?.source==="secret"&&st.value.reference)s[st.value.reference]=st.value.reference});
      setSecrets(s);
    }catch(e){setError((e as Error).message)}
  })()},[base,scenarioId]);

  const usage=useMemo(()=>{
    const u:Record<string,string[]>={};
    (d?.automationIr.steps||[]).forEach(st=>{
      const ref=st.value?.reference;if(!ref)return;
      (u[ref]=u[ref]||[]).push(`${st.id} ${st.action}${st.element?` on “${st.element}”`:""}`);
    });
    return u;
  },[d]);

  const originalParams=d?Object.fromEntries(Object.entries(d.automationIr.parameters||{}).map(([k,v])=>[k,v.default==null?"":String(v.default)])):{};
  const changedParams=Object.fromEntries(Object.entries(params).filter(([k,v])=>v!==originalParams[k]));
  const changedSecrets=Object.fromEntries(Object.entries(secrets).filter(([k,v])=>v.trim()!==k).map(([k,v])=>[k,v.trim()]));

  async function save(){
    try{
      setBusy(true);setError("");
      const created=await api<Created>(`${base}/scenarios/${scenarioId}/clone`,{method:"POST",body:JSON.stringify({name:name.trim(),moduleName:moduleName.trim()||null,featureName:featureName.trim()||null,parameters:changedParams,secretReferences:changedSecrets})});
      router.push(`/workspaces/${workspaceId}/applications/${applicationId}/scenarios/${created.id}`);
    }catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }

  const back=`/workspaces/${workspaceId}/applications/${applicationId}/scenarios`;
  return <AppShell>
    <div className="breadcrumb"><Link href={back}>Scenario repository</Link><span>/</span><span>{d?.scenario.name??"Scenario"}</span><span>/</span><span>Edit</span></div>
    {error&&<div className="error" style={{marginBottom:12}}>{error}</div>}
    {d&&<>
      <div className="hero"><div><h1>Edit and save as new scenario</h1><p className="muted">The original scenario (v{d.versionNo}) is not changed. Your edits are saved as a new scenario with its own automation code, generated from the edited values.</p></div></div>

      <section className="card">
        <h2>Scenario details</h2>
        <div className="form-grid">
          <label>New scenario name<input value={name} onChange={e=>setName(e.target.value)}/></label>
          <label>Module<input value={moduleName} onChange={e=>setModuleName(e.target.value)}/></label>
          <label>Feature<input value={featureName} onChange={e=>setFeatureName(e.target.value)}/></label>
        </div>
      </section>

      <section className="card" style={{marginTop:16}}>
        <h2>Test data (parameters)</h2>
        <p className="muted">Values typed into the application during the test, such as the user name. Change them to run the same flow with different data.</p>
        {Object.keys(params).length===0?<div className="empty">This scenario has no editable parameters.</div>:
        <table className="table form-table"><thead><tr><th>Parameter</th><th>Value</th><th>Used by</th></tr></thead><tbody>
          {Object.keys(params).map(k=><tr key={k}><td><code>{k}</code></td><td><input value={params[k]} onChange={e=>setParams({...params,[k]:e.target.value})}/></td><td className="muted small-note">{(usage[k]||[]).join(", ")||"—"}</td></tr>)}
        </tbody></table>}
      </section>

      <section className="card" style={{marginTop:16}}>
        <h2>Secrets (passwords and tokens)</h2>
        <p className="muted">Passwords are never stored in a scenario. Each one is a <b>secret name</b>; its value is read from the runner&apos;s <code>.env.runtime</code> file when the test runs. To use a different password (for example on another environment), enter a new secret name here, add <code>NEW_NAME=the-password</code> to <code>.env.runtime</code>, and restart the runner.</p>
        {Object.keys(secrets).length===0?<div className="empty">This scenario uses no secrets.</div>:
        <table className="table form-table"><thead><tr><th>Current secret name</th><th>New secret name</th><th>Used by</th></tr></thead><tbody>
          {Object.keys(secrets).map(k=><tr key={k}><td><code>{k}</code></td><td><input value={secrets[k]} onChange={e=>setSecrets({...secrets,[k]:e.target.value})} placeholder="e.g. SECRET_PASSWORD_ENV27"/><div className="field-hint">Letters, digits and underscores only.</div></td><td className="muted small-note">{(usage[k]||[]).join(", ")||"—"}</td></tr>)}
        </tbody></table>}
      </section>

      <div className="actions" style={{marginTop:16}}>
        <button onClick={save} disabled={busy||!name.trim()}>{busy?"Saving…":"Save as new scenario"}</button>
        <Link className="button secondary" href={back}>Cancel</Link>
        <span className="muted small-note" style={{margin:0}}>{Object.keys(changedParams).length} parameter change(s), {Object.keys(changedSecrets).length} secret rename(s)</span>
      </div>
    </>}
  </AppShell>;
}

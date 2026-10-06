"use client";
import AppShell from "@/components/AppShell";
import RunPanel,{RunJob} from "@/components/RunPanel";
import {api,apiBlob} from "@/lib/api";
import Link from "next/link";
import {useParams} from "next/navigation";
import {useCallback,useEffect,useMemo,useRef,useState} from "react";

type Scenario={id:string;moduleName?:string;featureName?:string;name:string;status:string;currentVersion:number;executionOrder?:number;createdAt:string};
type Environment={id:string;name:string;baseUrl:string;allowExecution:boolean;status:string};

export default function ScenarioRepository(){
  const {workspaceId,applicationId}=useParams<{workspaceId:string;applicationId:string}>();
  const base=`/api/v1/workspaces/${workspaceId}/applications/${applicationId}`;
  const [items,setItems]=useState<Scenario[]>([]);
  const [selected,setSelected]=useState<Set<string>>(new Set());
  const [target,setTarget]=useState("PLAYWRIGHT_PYTEST");
  const [envs,setEnvs]=useState<Environment[]>([]);
  const [envId,setEnvId]=useState("");
  const [stopOnFailure,setStopOnFailure]=useState(true);
  const [job,setJob]=useState<RunJob|null>(null);
  const [lastStatus,setLastStatus]=useState<Record<string,{status:string;text:string}>>({});
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  const [busy,setBusy]=useState("");
  const pollRef=useRef<ReturnType<typeof setTimeout>|null>(null);
  const running=!!job&&job.status!=="COMPLETED";

  const load=useCallback(async()=>{
    try{setError("");setItems(await api<Scenario[]>(`${base}/scenarios`))}catch(e){setError((e as Error).message)}
  },[base]);
  useEffect(()=>{load()},[load]);
  useEffect(()=>{
    (async()=>{
      try{
        const list=await api<Environment[]>(`${base}/environments`);
        const usable=list.filter(x=>x.status==="ACTIVE"&&x.allowExecution);
        setEnvs(usable);
        setEnvId(prev=>prev||usable[0]?.id||"");
      }catch(e){setError((e as Error).message)}
    })();
  },[base]);
  useEffect(()=>()=>{if(pollRef.current)clearTimeout(pollRef.current)},[]);

  const allSelected=items.length>0&&items.every(x=>selected.has(x.id));
  const selectedIds=useMemo(()=>items.filter(x=>selected.has(x.id)).map(x=>x.id),[items,selected]);
  const locatorError=error.includes("UNSUPPORTED_LOCATOR")||error.includes("LOCATOR_REQUIRED");
  const envName=envs.find(x=>x.id===envId)?.name;
  const norm=(v?:string)=>(v||"").trim().replace(/\s+/g," ").toLowerCase();
  const dupKeys=useMemo(()=>{const c:Record<string,number>={};items.forEach(x=>{const k=`${norm(x.moduleName)}|${norm(x.featureName)}|${norm(x.name)}`;c[k]=(c[k]||0)+1});return c},[items]);
  const isDup=(x:Scenario)=>dupKeys[`${norm(x.moduleName)}|${norm(x.featureName)}|${norm(x.name)}`]>1;

  function toggle(id:string){setSelected(prev=>{const n=new Set(prev);n.has(id)?n.delete(id):n.add(id);return n})}
  function toggleAll(){setSelected(allSelected?new Set():new Set(items.map(x=>x.id)))}

  async function move(id:string,delta:number){
    const i=items.findIndex(x=>x.id===id);const j=i+delta;
    if(i<0||j<0||j>=items.length)return;
    const next=[...items];[next[i],next[j]]=[next[j],next[i]];setItems(next);
    try{setBusy("reorder");setError("");setItems(await api<Scenario[]>(`${base}/scenarios/order`,{method:"PUT",body:JSON.stringify({scenarioIds:next.map(x=>x.id)})}))}
    catch(e){setError((e as Error).message);await load()}finally{setBusy("")}
  }

  async function exportSelected(){
    if(!selectedIds.length)return;
    try{
      setBusy("export");setError("");setMessage("");
      const blob=await apiBlob(`${base}/scenario-actions/export`,{method:"POST",body:JSON.stringify({scenarioIds:selectedIds,target})});
      const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download=`combined-automation-project-${target.toLowerCase()}.zip`;document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);
      setMessage(`Combined automation project created for ${selectedIds.length} selected scenario(s). Check bulk-manifest.json inside the ZIP for export status.`);
    }catch(e){setError((e as Error).message)}finally{setBusy("")}
  }

  function remember(j:RunJob){
    setLastStatus(prev=>{const n={...prev};j.items.forEach(it=>{n[it.scenarioId]={status:it.status,text:(it.message||it.output||"").slice(-500)}});return n});
  }

  async function poll(jobId:string){
    try{
      const j=await api<RunJob>(`${base}/scenario-actions/run-jobs/${jobId}`);
      setJob(j);remember(j);
      if(j.status!=="COMPLETED"){pollRef.current=setTimeout(()=>poll(jobId),1000);return}
      setBusy("");
      if(j.failed===0&&j.skipped===0)setMessage(`Run complete on ${j.environmentName||"the recorded environment"}: all ${j.passed} passed.`);
    }catch(e){setBusy("");setError((e as Error).message)}
  }

  async function run(ids:string[],label:string){
    if(!ids.length||running)return;
    if(!envId){setError("Choose the environment to run on first. If none is listed, create an environment that allows execution.");return}
    try{
      setBusy(label);setError("");setMessage("");setJob(null);
      const j=await api<RunJob>(`${base}/scenario-actions/run-jobs`,{method:"POST",body:JSON.stringify({scenarioIds:ids,stopOnFailure,environmentId:envId})});
      setJob(j);remember(j);
      pollRef.current=setTimeout(()=>poll(j.jobId),600);
    }catch(e){setBusy("");setError((e as Error).message)}
  }

  async function deleteScenario(s:Scenario){
    if(!window.confirm(`Delete scenario "${s.name}" permanently? This will also remove its generated implementations.`))return;
    try{
      setBusy(`delete-${s.id}`);setError("");setMessage("");
      await api(`${base}/scenarios/${s.id}`,{method:"DELETE"});
      setSelected(prev=>{const n=new Set(prev);n.delete(s.id);return n});
      setMessage(`Scenario "${s.name}" deleted.`);await load();
    }catch(e){setError((e as Error).message)}finally{setBusy("")}
  }

  const scenarioHref=(id:string)=>`/workspaces/${workspaceId}/applications/${applicationId}/scenarios/${id}`;
  const failedItem=job?.items.find(x=>["FAILED","ERROR","TIMED_OUT"].includes(x.status));

  return <AppShell>
    <div className="breadcrumb"><Link href="/workspaces">Workspaces</Link><span>/</span><Link href={`/workspaces/${workspaceId}/applications/${applicationId}`}>Application</Link><span>/</span><span>Scenario repository</span></div>
    <div className="hero"><div><h1>Scenario Repository</h1><p className="muted">Select, order, edit, export and run scenarios against any environment.</p></div><span className="badge">{items.length} scenarios</span></div>
    {error&&<div className="error">{locatorError?<><strong>Scenario cannot be generated or executed.</strong><div style={{marginTop:6}}>One or more recorded steps has no supported locator. Re-record the affected step and save the scenario again.</div><details style={{marginTop:8}}><summary>Technical details</summary><code>{error}</code></details></>:error}</div>}
    {message&&<div className="success" style={{marginBottom:12}}>{message}</div>}
    {failedItem&&!running&&<div className="error" style={{marginBottom:12}}><strong>{failedItem.scenarioName}: {failedItem.status}</strong> — see the test output below.</div>}

    <section className="card scenario-toolbar">
      <div className="toolbar-row">
        <div className="toolbar-group">
          <button className="secondary" onClick={toggleAll}>{allSelected?"Clear selection":"Select all"}</button>
          <span className="badge">{selectedIds.length} selected</span>
        </div>
        <div className="toolbar-group run">
          <label className="muted toolbar-label">Run on
            <select value={envId} onChange={e=>setEnvId(e.target.value)} aria-label="Environment to run on" disabled={running}>
              {envs.length===0&&<option value="">No runnable environment</option>}
              {envs.map(x=><option key={x.id} value={x.id}>{x.name} — {x.baseUrl}</option>)}
            </select>
          </label>
          <button onClick={()=>run(selectedIds,"run-bulk")} disabled={!selectedIds.length||running||!envId}>{busy==="run-bulk"?"Running…":`Run selected (in order)${envName?` on ${envName}`:""}`}</button>
          <label className="muted small-note toolbar-check"><input type="checkbox" checked={stopOnFailure} onChange={e=>setStopOnFailure(e.target.checked)} disabled={running}/>Stop on first failure</label>
        </div>
        <div className="toolbar-group export">
          <label className="muted toolbar-label">Export as
            <select value={target} onChange={e=>setTarget(e.target.value)} aria-label="Export framework"><option value="PLAYWRIGHT_PYTEST">Python + Playwright + Pytest</option><option value="SELENIUM_TESTNG">Java + Selenium + TestNG</option></select>
          </label>
          <button className="export-btn" onClick={exportSelected} disabled={!selectedIds.length||busy==="export"}>{busy==="export"?"Exporting…":"Export selected"}</button>
        </div>
      </div>
      <p className="muted small-note">Scenarios run one after another in the # order shown below (▲▼ to change). The test is generated fresh from the saved Automation IR and its login URL is pointed at the environment you choose, so the same scenario can be run on any environment.</p>
    </section>

    {job&&<RunPanel job={job}/>}

    {items.length===0?<div className="empty">No recorded scenarios yet. Return to an environment and click Record Test.</div>:
    <section className="card" style={{marginTop:14,overflowX:"auto"}}>
      <table className="table scenario-table">
        <thead><tr><th><input type="checkbox" checked={allSelected} onChange={toggleAll} aria-label="Select all scenarios"/></th><th>#</th><th>Module</th><th>Feature</th><th>Scenario</th><th>Status</th><th>Version</th><th>Last run</th><th>Actions</th></tr></thead>
        <tbody>{items.map((s,idx)=>{
          const rr=lastStatus[s.id];
          const live=job?.items.find(x=>x.scenarioId===s.id);
          return <tr key={s.id}>
            <td><input type="checkbox" checked={selected.has(s.id)} onChange={()=>toggle(s.id)} aria-label={`Select ${s.name}`}/></td>
            <td style={{whiteSpace:"nowrap"}}>{idx+1} <button className="secondary compact" onClick={()=>move(s.id,-1)} disabled={idx===0||busy==="reorder"||running} aria-label="Move up">▲</button> <button className="secondary compact" onClick={()=>move(s.id,1)} disabled={idx===items.length-1||busy==="reorder"||running} aria-label="Move down">▼</button></td>
            <td>{s.moduleName||"—"}</td><td>{s.featureName||"—"}</td>
            <td><Link className="table-link" href={scenarioHref(s.id)}>{s.name}</Link>{isDup(s)&&<span className="badge warn" style={{marginLeft:8}} title="Another scenario has the same module, feature and name. Delete the extra one.">Duplicate</span>}</td>
            <td><span className="badge ok">{s.status}</span></td>
            <td>v{s.currentVersion}</td>
            <td>{rr?<span className={`badge ${rr.status==="PASSED"?"ok":["QUEUED","SKIPPED"].includes(rr.status)?"":["GENERATING","RUNNING"].includes(rr.status)?"warn":"bad"}`} title={rr.text}>{live&&["GENERATING","RUNNING"].includes(live.status)?<><span className="spin"/> </>:null}{rr.status}</span>:"—"}</td>
            <td><div className="actions scenario-row-actions">
              <Link className="button secondary compact" href={scenarioHref(s.id)}>View</Link>
              <Link className="button secondary compact" href={`${scenarioHref(s.id)}/edit`} title="Change parameters and save as a new scenario">Edit</Link>
              <button className="compact" onClick={()=>run([s.id],`run-${s.id}`)} disabled={running||!envId} title={envName?`Run on ${envName}`:"Choose an environment first"}>{busy===`run-${s.id}`?"Running…":"Run"}</button>
              <button className="danger compact" onClick={()=>deleteScenario(s)} disabled={busy===`delete-${s.id}`||running}>{busy===`delete-${s.id}`?"Deleting…":"Delete"}</button>
            </div></td>
          </tr>})}</tbody>
      </table>
    </section>}
  </AppShell>;
}

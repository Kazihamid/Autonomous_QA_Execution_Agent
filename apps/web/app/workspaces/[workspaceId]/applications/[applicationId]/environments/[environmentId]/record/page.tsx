"use client";

import AppShell from "@/components/AppShell";
import { api } from "@/lib/api";
import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";

type Env={id:string;name:string;baseUrl:string;defaultBrowser:string;validationStatus:string;status:string;allowRecording:boolean};
type Session={id:string;environmentId:string;workerSessionId:string;scenarioName:string;moduleName?:string;featureName?:string;status:string;startUrl:string;browser:string;rawEventCount:number;semanticActionCount:number;error?:string;ir?:unknown};
const VIEW=process.env.NEXT_PUBLIC_RECORDER_VIEW_URL ?? "http://localhost:6080/vnc.html?autoconnect=1&resize=scale";

export default function RecorderPage(){
  const {workspaceId,applicationId,environmentId}=useParams<{workspaceId:string;applicationId:string;environmentId:string}>();
  const [env,setEnv]=useState<Env|null>(null); const [session,setSession]=useState<Session|null>(null);
  const [scenarioName,setScenarioName]=useState("User Login"); const [moduleName,setModuleName]=useState("Authentication"); const [featureName,setFeatureName]=useState("Login");
  const [selector,setSelector]=useState(""); const [assertionType,setAssertionType]=useState("visible"); const [expected,setExpected]=useState(""); const [checkpoint,setCheckpoint]=useState("");
  const [error,setError]=useState(""); const [message,setMessage]=useState(""); const [busy,setBusy]=useState(false);
  const base=`/api/v1/workspaces/${workspaceId}/applications/${applicationId}`;
  useEffect(()=>{api<Env[]>(`${base}/environments`).then(es=>setEnv(es.find(e=>e.id===environmentId)??null)).catch(e=>setError((e as Error).message))},[base,environmentId]);
  const canStart=session?.status==="READY"; const canPause=session?.status==="RECORDING"; const canResume=session?.status==="PAUSED"; const canFinish=canPause||canResume; const completed=session?.status==="COMPLETED";
  const irText=useMemo(()=>session?.ir?JSON.stringify(session.ir,null,2):"",[session]);

  async function create(e:FormEvent){e.preventDefault();setBusy(true);setError("");setMessage("");try{const s=await api<Session>(`${base}/environments/${environmentId}/recording-sessions`,{method:"POST",body:JSON.stringify({scenarioName,moduleName,featureName})});setSession(s);setMessage("Managed Chromium is ready. Click Start Recording before interacting with the browser.")}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  async function command(cmd:string){if(!session)return;setBusy(true);setError("");try{const s=await api<Session>(`${base}/recording-sessions/${session.id}/${cmd}`,{method:"POST"});setSession(s);setMessage(cmd==="start"||cmd==="resume"?"Recording is active.":cmd==="pause"?"Recording paused.":"Session updated.")}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  async function finish(){if(!session)return;setBusy(true);setError("");try{const s=await api<Session>(`${base}/recording-sessions/${session.id}/finish`,{method:"POST"});setSession(s);setMessage(s.status==="COMPLETED"?"Recording normalized and Automation IR validated.":"Recorder finished with validation errors.")}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  async function addAssertion(){if(!session||!selector.trim())return;setBusy(true);setError("");try{await api(`${base}/recording-sessions/${session.id}/assertions`,{method:"POST",body:JSON.stringify({selector,assertionType,expected:expected||null})});setMessage("Assertion added to the recording.");setSelector("");setExpected("")}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  async function addCheckpoint(){if(!session||!checkpoint.trim())return;setBusy(true);setError("");try{await api(`${base}/recording-sessions/${session.id}/checkpoints`,{method:"POST",body:JSON.stringify({description:checkpoint})});setMessage("Checkpoint added.");setCheckpoint("")}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  async function saveScenario(){if(!session)return;if(!window.confirm(`Save scenario "${session.scenarioName}" to the Scenario Repository?`))return;setBusy(true);setError("");setMessage("");try{await api(`${base}/recording-sessions/${session.id}/scenarios`,{method:"POST"});setMessage(`Scenario "${session.scenarioName}" saved successfully to the repository.`)}catch(e){setError((e as Error).message)}finally{setBusy(false)}}

  return <AppShell>
    <div className="breadcrumb"><Link href="/workspaces">Workspaces</Link><span>/</span><Link href={`/workspaces/${workspaceId}/applications/${applicationId}`}>Application</Link><span>/</span><span>Record Test</span></div>
    <div className="hero"><div><h1>Record Test</h1><p className="muted">{env?`${env.name} · ${env.baseUrl}`:"Loading environment..."}</p></div>{session&&<span className={`badge ${completed?"ok":session.status==="FAILED"?"warn":""}`}>{session.status}</span>}</div>
    {error&&<div className="error">{error}</div>}{message&&<div className="success" style={{marginTop:10}}>{message}</div>}

    {!session&&<section className="card" style={{marginTop:16}}><h2>1. Prepare recording session</h2><form className="form-grid" onSubmit={create}><label className="full">Scenario name<input value={scenarioName} onChange={e=>setScenarioName(e.target.value)} required maxLength={200}/></label><label>Module<input value={moduleName} onChange={e=>setModuleName(e.target.value)} maxLength={120}/></label><label>Feature<input value={featureName} onChange={e=>setFeatureName(e.target.value)} maxLength={120}/></label><div className="full actions"><button disabled={busy||!env}>{busy?"Launching...":"Launch managed browser"}</button></div></form><p className="muted" style={{marginBottom:0}}>The managed browser runs inside the Recorder Worker. Password values are marked sensitive and are converted to secret references instead of plaintext Automation IR values.</p></section>}

    {session&&<>
      <section className="card" style={{marginTop:16}}><div className="recorder-toolbar"><div><h2>2. Managed browser</h2><p className="muted">Interact with the application inside this browser. Recording only captures business events while status is RECORDING.</p></div><div className="actions"><button disabled={!canStart||busy} onClick={()=>command("start")}>Start Recording</button><button className="secondary" disabled={!canPause||busy} onClick={()=>command("pause")}>Pause</button><button className="secondary" disabled={!canResume||busy} onClick={()=>command("resume")}>Resume</button><button disabled={!canFinish||busy} onClick={finish}>Finish</button><button className="secondary" disabled={completed||session.status==="CANCELLED"||busy} onClick={()=>command("cancel")}>Cancel</button></div></div><iframe className="recorder-frame" src={VIEW} title="Managed Chromium via noVNC" /></section>

      {(canPause||canResume)&&<div className="grid" style={{marginTop:16}}><section className="card"><h2>Add assertion</h2><p className="muted">MVP technical control: enter a CSS selector for the element you want to verify.</p><div className="stack"><label>CSS selector<input value={selector} onChange={e=>setSelector(e.target.value)} placeholder="#success-message"/></label><label>Assertion<select value={assertionType} onChange={e=>setAssertionType(e.target.value)}><option value="visible">visible</option><option value="text">text</option><option value="value">value</option><option value="checked">checked</option></select></label><label>Expected (optional)<input value={expected} onChange={e=>setExpected(e.target.value)}/></label><button disabled={busy||!selector.trim()} onClick={addAssertion}>Add assertion</button></div></section><section className="card"><h2>Add checkpoint</h2><p className="muted">Checkpoints annotate important points without adding framework-specific code.</p><div className="stack"><label>Description<textarea value={checkpoint} onChange={e=>setCheckpoint(e.target.value)} placeholder="User dashboard loaded"/></label><button disabled={busy||!checkpoint.trim()} onClick={addCheckpoint}>Add checkpoint</button></div></section></div>}

      {completed&&<section className="card" style={{marginTop:16}}><div className="hero"><div><h2>3. Automation IR</h2><p className="muted">{session.rawEventCount} raw events → {session.semanticActionCount} semantic actions → validated canonical IR.</p></div><div className="actions"><button disabled={busy} onClick={saveScenario}>Save Scenario</button><Link className="button secondary" href={`/workspaces/${workspaceId}/applications/${applicationId}/scenarios`}>Open repository</Link></div></div><pre className="code-panel">{irText}</pre></section>}
      {session.error&&<div className="error" style={{marginTop:16}}>{session.error}</div>}
    </>}
  </AppShell>
}

"use client";
import {api,apiBlob} from "@/lib/api";
import {useCallback,useEffect,useState} from "react";

type Scenario={id:string;moduleName?:string;featureName?:string;name:string;currentVersion:number};
type Deleted={id:string;moduleName?:string;featureName?:string;name:string;currentVersion:number;deletedAt?:string};
type Version={versionNo:number;createdAt?:string;sourceRecordingSessionId?:string;current:boolean};
type Recording={sessionId:string;scenarioName:string;moduleName?:string;featureName?:string;recordedAt?:string};
type ImportResult={restored:number;created:number;copied:number;versionsAdded:number;skipped:number};

const when=(v?:string)=>{if(!v)return "";const d=new Date(v);return isNaN(d.getTime())?v:d.toLocaleString()};
const where=(m?:string,f?:string)=>[m,f].filter(Boolean).join(" › ")||"No module";

export default function ScenarioRecovery({base,scenarios,onChanged}:{base:string;scenarios:Scenario[];onChanged:()=>void|Promise<void>}){
  const [deleted,setDeleted]=useState<Deleted[]>([]);
  const [recordings,setRecordings]=useState<Recording[]>([]);
  const [pick,setPick]=useState("");
  const [versions,setVersions]=useState<Version[]>([]);
  const [busy,setBusy]=useState("");
  const [note,setNote]=useState("");
  const [problem,setProblem]=useState("");

  const refresh=useCallback(async()=>{
    try{
      setDeleted(await api<Deleted[]>(`${base}/scenarios/deleted`));
      setRecordings(await api<Recording[]>(`${base}/scenarios/recoverable-recordings`));
    }catch(e){setProblem((e as Error).message)}
  },[base]);
  useEffect(()=>{refresh()},[refresh,scenarios.length]);

  useEffect(()=>{
    if(!pick){setVersions([]);return}
    (async()=>{try{setVersions(await api<Version[]>(`${base}/scenarios/${pick}/versions`))}catch(e){setProblem((e as Error).message)}})();
  },[base,pick,scenarios]);

  async function act(key:string,okText:string,fn:()=>Promise<unknown>){
    try{setBusy(key);setProblem("");setNote("");await fn();setNote(okText);await onChanged();await refresh()}
    catch(e){setProblem((e as Error).message)}finally{setBusy("")}
  }

  const restore=(d:Deleted)=>act(`restore-${d.id}`,`Scenario "${d.name}" is back in the repository.`,()=>api(`${base}/scenarios/${d.id}/restore`,{method:"POST"}));
  const purge=(d:Deleted)=>{
    if(!window.confirm(`Delete "${d.name}" permanently? It cannot be restored afterwards.`))return;
    return act(`purge-${d.id}`,`Scenario "${d.name}" was deleted permanently.`,()=>api(`${base}/scenarios/${d.id}/permanent`,{method:"DELETE"}));
  };
  const purgeAll=()=>{
    if(!deleted.length||!window.confirm(`Delete all ${deleted.length} scenario(s) in Recently deleted permanently? They cannot be restored afterwards.`))return;
    return act("purge-all","Recently deleted was emptied.",()=>api(`${base}/scenarios/deleted`,{method:"DELETE"}));
  };
  const dismiss=(r:Recording)=>act(`dismiss-${r.sessionId}`,`The recording "${r.scenarioName}" was removed from this list.`,()=>api(`${base}/recording-sessions/${r.sessionId}/dismiss`,{method:"POST"}));
  const restoreVersion=(v:Version)=>act(`version-${v.versionNo}`,`Version ${v.versionNo} was saved again as the newest version.`,()=>api(`${base}/scenarios/${pick}/versions/${v.versionNo}/restore`,{method:"POST"}));
  const recover=(r:Recording)=>act(`recover-${r.sessionId}`,`The recording "${r.scenarioName}" is saved as a scenario again.`,()=>api(`${base}/recording-sessions/${r.sessionId}/recover`,{method:"POST"}));

  async function download(){
    try{
      setBusy("backup");setProblem("");setNote("");
      const blob=await apiBlob(`${base}/scenarios/backup`);
      const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;
      a.download=`scenarios-backup-${new Date().toISOString().slice(0,10)}.json`;document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);
      setNote("Backup file downloaded. Keep it somewhere safe; it holds every scenario with all of its versions.");
    }catch(e){setProblem((e as Error).message)}finally{setBusy("")}
  }

  async function upload(file?:File){
    if(!file)return;
    try{
      setBusy("import");setProblem("");setNote("");
      const doc=JSON.parse(await file.text());
      const r=await api<ImportResult>(`${base}/scenarios/backup/import`,{method:"POST",body:JSON.stringify(doc)});
      setNote(`Backup loaded: ${r.copied} scenario(s) copied in, ${r.restored} restored, ${r.created} brought back, ${r.versionsAdded} version(s) added, ${r.skipped} skipped (already here). Nothing existing was overwritten.`);
      await onChanged();await refresh();
    }catch(e){setProblem(e instanceof SyntaxError?"That file is not a valid backup file.":(e as Error).message)}finally{setBusy("")}
  }

  const count=deleted.length+recordings.length;
  const withHistory=scenarios.filter(s=>s.currentVersion>1);

  return <section className="card recovery-panel" style={{marginTop:14}}>
    <details open={deleted.length>0}>
      <summary className="group-head"><h2>Recovery &amp; Backup</h2>
        <span className="badge">{deleted.length} recently deleted</span>
        <span className="badge">{recordings.length} unsaved recording{recordings.length===1?"":"s"}</span>
        {count===0&&<span className="muted small-note">Nothing to recover right now.</span>}
      </summary>
      {problem&&<div className="error" style={{marginTop:10}}>{problem}</div>}
      {note&&<div className="success" style={{marginTop:10}}>{note}</div>}

      <h3 style={{marginTop:14}}>Recently deleted</h3>
      <p className="muted small-note">Deleting a scenario only moves it here. Restore puts it back with all of its versions. If the name is already used, it comes back as “name (restored)”. Delete permanently removes it for good, so the list does not keep growing.</p>
      {deleted.length===0?<p className="muted small-note">No deleted scenarios.</p>:
      <div className="recovery-list deleted" style={{overflowX:"auto"}}><table className="table"><thead><tr><th>Scenario</th><th>Module › Feature</th><th>Versions</th><th>Deleted</th><th></th></tr></thead>
        <tbody>{deleted.map(d=><tr key={d.id}><td>{d.name}</td><td>{where(d.moduleName,d.featureName)}</td><td>v{d.currentVersion}</td><td>{when(d.deletedAt)}</td>
          <td><div className="actions"><button className="tint-blue compact" onClick={()=>restore(d)} disabled={!!busy}>{busy===`restore-${d.id}`?"Restoring…":"Restore"}</button><button className="danger compact" onClick={()=>purge(d)} disabled={!!busy}>{busy===`purge-${d.id}`?"Deleting…":"Delete permanently"}</button></div></td></tr>)}</tbody></table></div>}
      {deleted.length>1&&<div className="actions" style={{marginTop:8}}><button className="danger compact" onClick={purgeAll} disabled={!!busy}>{busy==="purge-all"?"Deleting…":`Delete all ${deleted.length} permanently`}</button></div>}

      <h3 style={{marginTop:18}}>Go back to an earlier version</h3>
      <p className="muted small-note">Pick a scenario that was edited or re-recorded, then restore an older version. It is saved again as the newest version, so nothing is lost.</p>
      {withHistory.length===0?<p className="muted small-note">No scenario has more than one version yet.</p>:<>
        <select value={pick} onChange={e=>setPick(e.target.value)} aria-label="Scenario to roll back">
          <option value="">Choose a scenario…</option>
          {withHistory.map(s=><option key={s.id} value={s.id}>{where(s.moduleName,s.featureName)} › {s.name} (v{s.currentVersion})</option>)}
        </select>
        {pick&&<div className="recovery-list versions" style={{marginTop:8}}><table className="table"><thead><tr><th>Version</th><th>Saved</th><th></th></tr></thead>
          <tbody>{versions.map(v=><tr key={v.versionNo}><td>v{v.versionNo}{v.current&&<span className="badge ok" style={{marginLeft:8}}>current</span>}</td><td>{when(v.createdAt)}</td>
            <td>{!v.current&&<button className="secondary compact" onClick={()=>restoreVersion(v)} disabled={!!busy}>{busy===`version-${v.versionNo}`?"Restoring…":"Restore this version"}</button>}</td></tr>)}</tbody></table></div>}
      </>}

      <h3 style={{marginTop:18}}>Recordings that are not saved as a scenario</h3>
      <p className="muted small-note">Every finished recording is kept. If a scenario disappeared (or was never saved), recover it from its recording here. Dismiss removes a recording from this list. A scenario you delete permanently never comes back here.</p>
      {recordings.length===0?<p className="muted small-note">Every finished recording is already a scenario.</p>:
      <div className="recovery-list recoverable" style={{overflowX:"auto"}}><table className="table"><thead><tr><th>Recording</th><th>Module › Feature</th><th>Recorded</th><th></th></tr></thead>
        <tbody>{recordings.map(r=><tr key={r.sessionId}><td>{r.scenarioName}</td><td>{where(r.moduleName,r.featureName)}</td><td>{when(r.recordedAt)}</td>
          <td><div className="actions"><button className="compact" onClick={()=>recover(r)} disabled={!!busy}>{busy===`recover-${r.sessionId}`?"Recovering…":"Recover as scenario"}</button><button className="secondary compact" onClick={()=>dismiss(r)} disabled={!!busy} title="Remove this recording from the list without recovering it">{busy===`dismiss-${r.sessionId}`?"Removing…":"Dismiss"}</button></div></td></tr>)}</tbody></table></div>}

      <h3 style={{marginTop:18}}>Backup file</h3>
      <p className="muted small-note">A copy of every scenario and version. Use it to bring scenarios back after a crash or a lost database. The file can be shared: anybody with write access to an application can load it there, and the scenarios are copied in. Loading only adds what is missing; it never overwrites. If the platform was started with the scenario-backups folder, a fresh copy is also saved there automatically after every change.</p>
      <div className="actions">
        <button className="secondary" onClick={download} disabled={!!busy}>{busy==="backup"?"Preparing…":"Download backup"}</button>
        <label className="button secondary" style={{cursor:"pointer"}}>{busy==="import"?"Loading…":"Load backup file"}
          <input type="file" accept="application/json,.json" style={{display:"none"}} disabled={!!busy} onChange={e=>{upload(e.target.files?.[0]);e.target.value=""}}/>
        </label>
      </div>
    </details>
  </section>;
}

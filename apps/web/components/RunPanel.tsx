"use client";
import {useEffect,useRef,useState} from "react";

export type RunItem={scenarioId:string;scenarioName:string;status:string;currentStep:number;totalSteps:number;currentAction:string;startedAt?:string;durationMs:number;output:string;message:string};
export type RunJob={jobId:string;status:string;environmentId?:string;environmentName?:string;baseUrl?:string;stopOnFailure:boolean;startedAt?:string;finishedAt?:string;total:number;completed:number;passed:number;failed:number;skipped:number;items:RunItem[]};

const ACTIVE=new Set(["GENERATING","RUNNING"]);
function badgeClass(s:string){return s==="PASSED"?"badge ok":s==="QUEUED"||s==="SKIPPED"?"badge":s==="GENERATING"||s==="RUNNING"?"badge warn":"badge bad"}
function icon(s:string){if(ACTIVE.has(s))return <span className="spin" aria-label="running"/>;if(s==="PASSED")return <span aria-label="passed">✅</span>;if(s==="QUEUED")return <span aria-label="queued">⏳</span>;if(s==="SKIPPED")return <span aria-label="skipped">⏭</span>;return <span aria-label="failed">❌</span>}
function label(s:string){return s==="GENERATING"?"Generating code":s==="RUNNING"?"Running in browser":s}
function fmt(ms:number){const s=Math.max(0,Math.round(ms/1000));return s<60?`${s}s`:`${Math.floor(s/60)}m ${s%60}s`}

function Terminal({text,follow}:{text:string;follow:boolean}){
  const ref=useRef<HTMLPreElement>(null);
  useEffect(()=>{if(follow&&ref.current)ref.current.scrollTop=ref.current.scrollHeight},[text,follow]);
  return <pre className="terminal" ref={ref}>{text||"Waiting for output…"}</pre>;
}

export default function RunPanel({job}:{job:RunJob}){
  const [now,setNow]=useState(Date.now());
  const live=job.status!=="COMPLETED";
  useEffect(()=>{if(!live)return;const t=setInterval(()=>setNow(Date.now()),500);return()=>clearInterval(t)},[live]);
  const started=job.startedAt?Date.parse(job.startedAt):now;
  const ended=job.finishedAt?Date.parse(job.finishedAt):now;
  const pct=job.total?Math.round((job.completed/job.total)*100):0;
  const allGood=!live&&job.failed===0&&job.skipped===0;
  return <section className="card run-panel" aria-live="polite">
    <div className="run-head">
      <div>
        <strong>{live?"Run in progress":allGood?"Run finished — all passed":"Run finished"}</strong>
        <div className="muted small-note" style={{margin:0}}>
          Environment: <b>{job.environmentName||"recorded environment"}</b>{job.baseUrl?` · ${job.baseUrl}`:""} · {job.stopOnFailure?"stops on first failure":"runs all selected"}
        </div>
      </div>
      <div className="actions">
        {live&&<span className="spin"/>}
        <span className="badge">{job.completed}/{job.total} done</span>
        <span className="badge ok">{job.passed} passed</span>
        {job.failed>0&&<span className="badge bad">{job.failed} failed</span>}
        {job.skipped>0&&<span className="badge">{job.skipped} skipped</span>}
        <span className="badge">⏱ {fmt(ended-started)}</span>
      </div>
    </div>
    <div className={`progress ${live?"live":""}`} role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}><div style={{width:`${pct}%`}}/></div>
    {job.items.map((it,idx)=>{
      const running=ACTIVE.has(it.status);
      const stepPct=it.totalSteps?Math.round((it.currentStep/it.totalSteps)*100):0;
      const elapsed=running&&it.startedAt?now-Date.parse(it.startedAt):it.durationMs;
      return <div key={it.scenarioId} className={`run-item ${running?"running":""}`}>
        <div className="run-item-row">
          <div>{icon(it.status)} <strong>{idx+1}. {it.scenarioName}</strong></div>
          <div className="actions">
            {running&&it.totalSteps>0&&<span className="muted small-note" style={{margin:0}}>step {it.currentStep} of {it.totalSteps} · {it.currentAction}</span>}
            {it.status!=="QUEUED"&&it.status!=="SKIPPED"&&<span className="muted small-note" style={{margin:0}}>{fmt(elapsed)}</span>}
            <span className={badgeClass(it.status)}>{label(it.status)}</span>
          </div>
        </div>
        {running&&it.totalSteps>0&&<div className="progress step-bar"><div style={{width:`${stepPct}%`}}/></div>}
        {it.message&&it.status!=="PASSED"&&<div className="muted small-note">{it.message}</div>}
        {(it.output||running)&&<details open={running||it.status==="FAILED"||it.status==="ERROR"||it.status==="TIMED_OUT"}>
          <summary className="muted small-note" style={{cursor:"pointer"}}>{running?"Live test output":"Test output"}</summary>
          <Terminal text={it.output} follow={running}/>
        </details>}
      </div>;
    })}
  </section>;
}

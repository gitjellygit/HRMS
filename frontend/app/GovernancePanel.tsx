"use client";
import {explainError} from "./formErrors";
import {useEffect,useState} from "react";
type Row=Record<string,any>;
export default function GovernancePanel({api,user}:{api:string;user:{id:number;role:string}}){
 const admin=["super_admin","admin"].includes(user.role);
 const [rows,setRows]=useState<Row[]>([]);
 const [notes,setNotes]=useState<Record<number,string>>({});
 const [message,setMessage]=useState("");
 const [error,setError]=useState("");
 async function load(){
  const r=await fetch(api+"/governance/requests",{credentials:"include"});
  if(!r.ok)throw Error("Could not load approval queue");
  setRows(await r.json());
 }
 useEffect(()=>{void load().catch(e=>setError((e as Error).message))},[api,user.id]);
 async function review(id:number,approve:boolean){
  setError("");setMessage("");
  try{
   const r=await fetch(api+"/governance/requests/"+id+"/review",{
    method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({approve,reason:notes[id]||""})});
   const j=await r.json().catch(()=>({}));
   if(!r.ok)throw Error(explainError(j,r.status));
   setMessage("Change #"+id+" "+(approve?"approved and applied":"rejected")+".");
   await load();
  }catch(e){setError((e as Error).message)}
 }
 return <section className="panel">
  <h2>{admin?"Admin approval inbox":"My policy and leave approval requests"}</h2>
  <p className="muted">Major policy or manual leave allocation changes require a reason and independent admin approval. Password and profile-photo updates remain self-service.</p>
  {error&&<p className="error" role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
  {rows.map(r=><div className="card" key={r.id}>
    <strong>#{r.id}: {String(r.kind).replace(/_/g," ")} — {r.status}</strong>
    <p>{r.reason}</p><details><summary>Proposed changes</summary>
     <pre style={{whiteSpace:"pre-wrap",overflowWrap:"anywhere"}}>{JSON.stringify(r.payload,null,2)}</pre>
    </details>
    <p className="muted">Submitted by employee #{r.submitted_by}</p>
    {admin&&r.status==="pending"&&<div className="form">
      <label>Approval or rejection reason<textarea minLength={10} required
       value={notes[r.id]||""} onChange={e=>setNotes(v=>({...v,[r.id]:e.target.value}))}/></label>
      <button className="primary" disabled={(notes[r.id]||"").trim().length<10} onClick={()=>void review(r.id,true)}>Approve and apply</button>
      <button className="secondary" disabled={(notes[r.id]||"").trim().length<10} onClick={()=>void review(r.id,false)}>Reject</button>
    </div>}
  </div>)}
  {rows.length===0&&<p>No approval requests.</p>}
 </section>;
}

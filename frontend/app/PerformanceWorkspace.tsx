"use client";
import {useEffect,useState} from "react";

type Person={id:number;role:string;name:string};
type RecordRow=Record<string,any>;
type Area="goals"|"reviews"|"development";
const today=()=>new Date().toISOString().slice(0,10);
export default function PerformanceWorkspace({api,user}:{api:string;user:Person}){
 const hr=["hr","admin","super_admin"].includes(user.role);
 const [area,setArea]=useState<Area>("goals");
 const [team,setTeam]=useState<RecordRow[]>([]);
 const [goals,setGoals]=useState<RecordRow[]>([]);
 const [reviews,setReviews]=useState<RecordRow[]>([]);
 const [cycles,setCycles]=useState<RecordRow[]>([]);
 const [plans,setPlans]=useState<RecordRow[]>([]);
 const [employee,setEmployee]=useState(String(user.id));
 const [title,setTitle]=useState("");
 const [detail,setDetail]=useState("");
 const [target,setTarget]=useState(today());
 const [cycle,setCycle]=useState("");
 const [rating,setRating]=useState(3);
 const [message,setMessage]=useState("");
 const [error,setError]=useState("");
 const [busy,setBusy]=useState(false);
 const canAssign=hr||user.role==="manager";
 async function call(path:string,method="GET",body?:unknown){
  const response=await fetch(api+"/performance"+path,{
   method,credentials:"include",headers:{"Content-Type":"application/json"},
   body:body===undefined?undefined:JSON.stringify(body)
  });
  const data=await response.json().catch(()=>null);
  if(!response.ok)throw Error(typeof data?.detail==="string"?data.detail:"Unable to save. Please review the details.");
  return data;
 }
 async function refresh(){
  const [g,r,c,p]=await Promise.all([call("/goals"),call("/reviews"),call("/cycles"),call("/plans")]);
  setGoals(g);setReviews(r);setCycles(c);setPlans(p);
 }
 useEffect(()=>{
  void refresh().catch(e=>setError((e as Error).message));
  if(canAssign)void fetch(api+"/employees",{credentials:"include"}).then(r=>r.ok?r.json():[])
   .then(setTeam).catch(()=>setTeam([]));
 },[api,user.id]);
 async function save(action:()=>Promise<unknown>,success:string){
  setError("");setMessage("");setBusy(true);
  try{await action();await refresh();setTitle("");setDetail("");setMessage(success)}
  catch(e){setError((e as Error).message)}
  finally{setBusy(false)}
 }
 const editable=canAssign?employee:user.id;
 return <section className="panel">
  <h2>Performance & growth</h2>
  <p className="muted">Track individual goals, self and manager reviews, and development plans.</p>
  <div className="time-tabs" role="tablist">{([["goals","Goals & KRAs"],["reviews","Appraisal cycles"],["development","Development plans"]] as const).map(([key,label])=>
   <button key={key} type="button" role="tab" aria-selected={area===key} onClick={()=>setArea(key)}>{label}</button>)}</div>
  {error&&<p role="alert" className="error">{error}</p>}{message&&<p role="status">{message}</p>}
  {canAssign&&<label>Assign to employee <select value={employee} onChange={e=>setEmployee(e.target.value)}>
    <option value={user.id}>Myself</option>{team.filter(e=>e.id!==user.id).map(e=><option key={e.id} value={e.id}>{e.name}</option>)}
   </select></label>}
  {area==="goals"&&<>
   <form className="form" onSubmit={e=>{e.preventDefault();void save(
    ()=>call("/goals","POST",{employee_id:Number(editable),title,description:detail,target_date:target}),"Goal added.")}}>
    <label>Goal title<input required minLength={3} maxLength={180} value={title} onChange={e=>setTitle(e.target.value)}/></label>
    <label>Target date<input type="date" required value={target} onChange={e=>setTarget(e.target.value)}/></label>
    <label className="wide">Description<textarea value={detail} onChange={e=>setDetail(e.target.value)}/></label>
    <button disabled={busy} className="primary">Add goal</button>
   </form>
   <div className="table-wrap"><table><thead><tr><th>Goal</th><th>Employee</th><th>Target</th><th>Progress</th></tr></thead><tbody>
    {goals.map(g=><tr key={g.id}><td><strong>{g.title}</strong><div className="muted">{g.description}</div></td>
    <td>#{g.employee_id}</td><td>{g.target_date}</td><td>
    <label>Completion % <input aria-label={"Completion percentage for "+g.title} type="number" min={0} max={100} defaultValue={g.progress}
      key={g.id+":"+g.progress} onBlur={e=>{const value=Number(e.target.value);if(value!==g.progress&&value>=0&&value<=100)
      void save(()=>call("/goals/"+g.id+"/progress","PATCH",{progress:value}),"Progress updated.")}}/></label>
    </td></tr>)}</tbody></table></div>
  </>}
  {area==="reviews"&&<>
   {hr&&<form className="form" onSubmit={e=>{e.preventDefault();void save(
    ()=>call("/cycles","POST",{name:title,start_date:today(),end_date:target}),"Review cycle created.")}}>
    <label>Cycle name<input minLength={3} required value={title} onChange={e=>setTitle(e.target.value)}/></label>
    <label>End date<input type="date" required value={target} onChange={e=>setTarget(e.target.value)}/></label>
    <button className="primary" disabled={busy}>Create cycle</button>
   </form>}
   <form className="form" onSubmit={e=>{e.preventDefault();void save(
    ()=>call("/reviews","POST",{cycle_id:Number(cycle),employee_id:user.id,self_notes:detail}),"Self-review submitted.")}}>
    <label>Review cycle<select value={cycle} required onChange={e=>setCycle(e.target.value)}><option value="">Choose cycle</option>
    {cycles.filter(c=>c.status==="open").map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
    <label className="wide">Self assessment<textarea minLength={10} required value={detail} onChange={e=>setDetail(e.target.value)}/></label>
    <button className="primary" disabled={busy}>Submit self-review</button>
   </form>
   {reviews.map(r=><article key={r.id} className="card">
    <strong>Cycle #{r.cycle_id} · Employee #{r.employee_id}</strong>
    <p>{r.self_notes}</p><p>Manager rating: {r.manager_rating??"Pending"} · {r.status}</p>
    {r.manager_notes&&<p>{r.manager_notes}</p>}
    {canAssign&&r.employee_id!==user.id&&r.status==="self_submitted"&&
     <form className="form" onSubmit={e=>{e.preventDefault();void save(
      ()=>call("/reviews/"+r.id+"/manager","POST",{rating,feedback:detail}),"Manager review completed.")}}>
      <label>Rating <select value={rating} onChange={e=>setRating(Number(e.target.value))}>{[1,2,3,4,5].map(v=><option key={v} value={v}>{v}/5</option>)}</select></label>
      <label>Feedback<textarea minLength={10} required value={detail} onChange={e=>setDetail(e.target.value)}/></label>
      <button disabled={busy} className="primary">Complete review</button>
     </form>}
   </article>)}
  </>}
  {area==="development"&&<>
   <form className="form" onSubmit={e=>{e.preventDefault();void save(
    ()=>call("/plans","POST",{employee_id:Number(editable),skill:title,action:detail,target_date:target}),"Development plan added.")}}>
    <label>Skill or growth area<input required minLength={2} value={title} onChange={e=>setTitle(e.target.value)}/></label>
    <label>Target date<input type="date" value={target} onChange={e=>setTarget(e.target.value)} required/></label>
    <label className="wide">Development action<textarea required minLength={5} value={detail} onChange={e=>setDetail(e.target.value)}/></label>
    <button disabled={busy} className="primary">Add development plan</button>
   </form>
   {plans.map(p=><div className="card" key={p.id}><strong>{p.skill} · Employee #{p.employee_id}</strong>
    <p>{p.action}</p><p className="muted">Target: {p.target_date}</p>
    <label>Status <select value={p.status} onChange={e=>void save(
     ()=>call("/plans/"+p.id,"PATCH",{status:e.target.value}),"Development status updated.")}>
     <option value="planned">Planned</option><option value="in_progress">In progress</option><option value="completed">Completed</option>
    </select></label></div>)}
  </>}
 </section>;
}

"use client";
import {useEffect,useState} from "react";

type Row=Record<string,any>;
export default function GrowthExtensions({api,user}:{api:string;user:{id:number;role:string;name:string}}){
 const hr=["hr","admin","super_admin"].includes(user.role);
 const manage=hr||user.role==="manager";
 const [tab,setTab]=useState<"learning"|"career"|"feedback">("learning");
 const [items,setItems]=useState<Row[]>([]);
 const [careers,setCareers]=useState<Row[]>([]);
 const [assignments,setAssignments]=useState<Row[]>([]);
 const [people,setPeople]=useState<Row[]>([]);
 const [cycles,setCycles]=useState<Row[]>([]);
 const [employee,setEmployee]=useState(String(user.id));
 const [title,setTitle]=useState("");
 const [description,setDescription]=useState("");
 const [date,setDate]=useState(new Date().toISOString().slice(0,10));
 const [reviewer,setReviewer]=useState("");
 const [cycle,setCycle]=useState("");
 const [score,setScore]=useState(3);
 const [message,setMessage]=useState("");
 const [error,setError]=useState("");
 async function call(path:string,method="GET",body?:unknown){
  const r=await fetch(api+path,{method,credentials:"include",headers:{"Content-Type":"application/json"},
    body:body===undefined?undefined:JSON.stringify(body)});
  const j=await r.json().catch(()=>null);
  if(!r.ok)throw Error(typeof j?.detail==="string"?j.detail:"Request failed");
  return j;
 }
 async function refresh(){
  const [a,b,c,d]=await Promise.all([call("/growth/learning"),call("/growth/career"),
   call("/growth/feedback-assignments"),call("/performance/cycles")]);
  setItems(a);setCareers(b);setAssignments(c);setCycles(d);
 }
 useEffect(()=>{void refresh().catch(e=>setError((e as Error).message));
  if(manage)void fetch(api+"/employees",{credentials:"include"}).then(r=>r.ok?r.json():[]).then(setPeople).catch(()=>{});
 },[api,user.id]);
 async function save(fn:()=>Promise<unknown>,messageText:string){
  setError("");setMessage("");
  try{await fn();await refresh();setTitle("");setDescription("");setMessage(messageText)}
  catch(e){setError((e as Error).message)}
 }
 const selected=manage?Number(employee):user.id;
 return <section className="panel">
  <h2>Learning, career & 360 feedback</h2>
  <div className="time-tabs" role="tablist">{([["learning","Learning & training"],["career","Career progression"],["feedback","Peer feedback"]] as const).map(([id,label])=>
    <button key={id} role="tab" aria-selected={tab===id} onClick={()=>setTab(id)}>{label}</button>)}</div>
  {error&&<p role="alert" className="error">{error}</p>}{message&&<p role="status">{message}</p>}
  {manage&&<label>Employee <select value={employee} onChange={e=>setEmployee(e.target.value)}>
   <option value={user.id}>Myself</option>{people.filter(p=>p.id!==user.id).map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
   </select></label>}
  {tab==="learning"&&<>
   <form className="form" onSubmit={e=>{e.preventDefault();void save(
     ()=>call("/growth/learning","POST",{employee_id:selected,title,provider:description,target_date:date}),"Training added.")}}>
    <label>Course/training name<input required minLength={3} value={title} onChange={e=>setTitle(e.target.value)}/></label>
    <label>Provider<input value={description} onChange={e=>setDescription(e.target.value)}/></label>
    <label>Target completion<input type="date" required value={date} onChange={e=>setDate(e.target.value)}/></label>
    <button className="primary">Assign training</button>
   </form>
   {items.map(p=><div key={p.id} className="card"><strong>{p.title} — employee #{p.employee_id}</strong>
     <p>{p.provider||"Internal"} · by {p.target_date}</p>
     <label>Status <select value={p.status} onChange={e=>void save(
      ()=>call("/growth/learning/"+p.id,"PATCH",{status:e.target.value}),"Training updated.")}>
      <option value="assigned">Assigned</option><option value="in_progress">In progress</option><option value="completed">Completed</option>
     </select></label>
   </div>)}
  </>}
  {tab==="career"&&<>
   {manage&&<form className="form" onSubmit={e=>{e.preventDefault();void save(
     ()=>call("/growth/career","POST",{employee_id:selected,target_role:title,requirements:description,target_date:date}),"Career milestone added.")}}>
     <label>Target role<input required minLength={3} value={title} onChange={e=>setTitle(e.target.value)}/></label>
     <label>Target date<input type="date" required value={date} onChange={e=>setDate(e.target.value)}/></label>
     <label className="wide">Readiness requirements<textarea minLength={10} required value={description} onChange={e=>setDescription(e.target.value)}/></label>
     <button className="primary">Add career milestone</button>
   </form>}
   {careers.map(c=><div key={c.id} className="card"><strong>{c.target_role} — employee #{c.employee_id}</strong>
    <p>{c.requirements}</p><p>Target: {c.target_date}</p>
    <p>Status: {c.status}</p>
    {manage&&<label>Update status <select value={c.status} onChange={e=>void save(
     ()=>call("/growth/career/"+c.id,"PATCH",{status:e.target.value}),"Career status updated.")}>
     <option value="planned">Planned</option><option value="in_progress">In progress</option><option value="achieved">Achieved</option>
    </select></label>}
   </div>)}
  </>}
  {tab==="feedback"&&<>
   <p className="muted">Peer reviews are confidential. The subject sees an aggregate only after at least three ratings; HR can audit individual submissions.</p>
   {hr&&<form className="form" onSubmit={e=>{e.preventDefault();void save(
      ()=>call("/growth/feedback-assignments","POST",{employee_id:Number(employee),reviewer_id:Number(reviewer),cycle_id:Number(cycle)}),"Peer review assigned.")}}>
      <label>Reviewer<select value={reviewer} required onChange={e=>setReviewer(e.target.value)}>
       <option value="">Select reviewer</option>{people.filter(p=>String(p.id)!==employee).map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
      </select></label>
      <label>Appraisal cycle<select value={cycle} required onChange={e=>setCycle(e.target.value)}>
       <option value="">Select cycle</option>{cycles.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
      </select></label><button className="primary">Request confidential feedback</button>
     </form>}
   {assignments.map(a=><div className="card" key={a.id}>
    <strong>Feedback for employee #{a.employee_id} — cycle #{a.cycle_id}</strong>
    {a.status==="submitted"?<p>Submitted confidentially</p>:
      <form className="form" onSubmit={e=>{e.preventDefault();void save(
        ()=>call("/growth/feedback-assignments/"+a.id+"/submit","POST",{score,feedback:description}),"Peer feedback submitted.")}}>
       <label>Rating<select value={score} onChange={e=>setScore(Number(e.target.value))}>
        {[1,2,3,4,5].map(n=><option key={n} value={n}>{n}/5</option>)}</select></label>
       <label className="wide">Feedback<textarea minLength={15} required value={description} onChange={e=>setDescription(e.target.value)}/></label>
       <button className="primary">Submit feedback privately</button>
      </form>}
   </div>)}
   {cycles.map(c=><button key={c.id} className="secondary" onClick={()=>void save(async()=>{
     const result=await call("/growth/feedback-summary/"+selected+"/"+c.id);
     setMessage("Responses: "+result.response_count+" · Average: "+(result.average_score??"Hidden until minimum response count"));
    },"")}>View {c.name} feedback summary</button>)}
  </>}
 </section>;
}

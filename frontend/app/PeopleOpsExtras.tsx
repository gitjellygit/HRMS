"use client";
import {explainError} from "./formErrors";
import {useEffect,useState} from "react";
type Row=Record<string,any>;
export default function PeopleOpsExtras({api,user}:{api:string;user:{id:number;role:string}}){
 const hr=["hr","admin","super_admin"].includes(user.role);
 const [tab,setTab]=useState<"assets"|"messages"|"clearances">("assets");
 const [employees,setEmployees]=useState<Row[]>([]);
 const [assets,setAssets]=useState<Row[]>([]);
 const [tickets,setTickets]=useState<Row[]>([]);
 const [exits,setExits]=useState<Row[]>([]);
 const [thread,setThread]=useState<Row[]>([]);
 const [ticketId,setTicketId]=useState("");
 const [employee,setEmployee]=useState(String(user.id));
 const [name,setName]=useState("");
 const [serial,setSerial]=useState("");
 const [note,setNote]=useState("");
 const [exitId,setExitId]=useState("");
 const [kind,setKind]=useState("assets");
 const [message,setMessage]=useState("");
 const [error,setError]=useState("");
 async function call(path:string,method="GET",body?:unknown){
  const r=await fetch(api+"/people"+path,{credentials:"include",method,
   headers:{"Content-Type":"application/json"},body:body===undefined?undefined:JSON.stringify(body)});
  const j=await r.json().catch(()=>null);
  if(!r.ok)throw Error(explainError(j,r.status));
  return j;
 }
 async function reload(){
  const [a,b,c]=await Promise.all([call("/assets"),call("/tickets"+(hr?"?scope=all":"")),
   call("/exits"+(hr?"?scope=all":""))]);
  setAssets(a);setTickets(b);setExits(c);
 }
 useEffect(()=>{void reload().catch(e=>setError((e as Error).message));
  if(hr)void fetch(api+"/employees",{credentials:"include"}).then(r=>r.ok?r.json():[]).then(setEmployees).catch(()=>{});
 },[api,user.id]);
 async function save(fn:()=>Promise<unknown>,success:string){
  setError("");setMessage("");
  try{await fn();await reload();setMessage(success)}catch(e){setError((e as Error).message)}
 }
 async function loadThread(id:string){
  setTicketId(id);
  if(!id){setThread([]);return}
  try{setThread(await call("/tickets/"+id+"/messages"))}catch(e){setError((e as Error).message)}
 }
 return <section className="panel">
  <h2>Asset, ticket and exit clearance records</h2>
  <div className="time-tabs" role="tablist">
   {([["assets","Asset register"],["messages","Helpdesk conversation"],["clearances","Exit clearances"]] as const).map(([id,title])=>
    <button key={id} role="tab" aria-selected={tab===id} onClick={()=>setTab(id)}>{title}</button>)}
  </div>
  {error&&<p className="error" role="alert">{error}</p>}
  {message&&<p role="status">{message}</p>}
  {tab==="assets"&&<>
   {hr&&<form className="form asset-allocation-form" onSubmit={e=>{e.preventDefault();void save(
    ()=>call("/assets","POST",{employee_id:Number(employee),name,serial_number:serial}),"Company asset allocated.")}}>
    <label>Employee<select value={employee} onChange={e=>setEmployee(e.target.value)}>
      {employees.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
    <label>Asset name<input required minLength={3} value={name} onChange={e=>setName(e.target.value)}/></label>
    <label>Serial number<input required minLength={3} value={serial} onChange={e=>setSerial(e.target.value)}/></label>
    <button className="primary">Allocate asset</button>
   </form>}
   <div className="table-wrap asset-register-table"><table><thead><tr><th>Asset</th><th>Serial</th><th>Employee</th><th>Returned</th></tr></thead>
   <tbody>{assets.map(a=><tr key={a.id}><td>{a.name}</td><td>{a.serial_number}</td><td>#{a.employee_id}</td>
    <td>{a.returned_at?"Yes":hr?<button className="secondary" onClick={()=>void save(
     ()=>call("/assets/"+a.id+"/return","POST"),"Asset return recorded.")}>Record return</button>:"No"}</td></tr>)}</tbody></table></div>
  </>}
  {tab==="messages"&&<>
   <label>Helpdesk ticket<select value={ticketId} onChange={e=>void loadThread(e.target.value)}>
    <option value="">Select ticket</option>{tickets.map(t=><option key={t.id} value={t.id}>#{t.id} · {t.subject}</option>)}
   </select></label>
   {thread.map(m=><div className="card" key={m.id}><strong>From employee #{m.author_id}</strong><p>{m.body}</p></div>)}
   {ticketId&&<form className="form" onSubmit={e=>{e.preventDefault();void save(async()=>{
     await call("/tickets/"+ticketId+"/messages","POST",{body:note});await loadThread(ticketId);setNote("");
    },"Reply added.")}}>
    <label className="wide">Reply<textarea minLength={2} required value={note} onChange={e=>setNote(e.target.value)}/></label>
    <button className="primary">Send ticket reply</button>
   </form>}
  </>}
  {tab==="clearances"&&<>
   <label>Exit request<select value={exitId} onChange={e=>setExitId(e.target.value)}>
    <option value="">Select exit case</option>{exits.map(x=><option key={x.id} value={x.id}>#{x.id} · employee #{x.employee_id} · {x.status}</option>)}
   </select></label>
   {exitId&&<><p className="muted">Clearance must be documented before a final-and-full settlement can be recorded.</p>
    <button className="secondary" onClick={()=>void save(async()=>{
      const rows=await call("/exits/"+exitId+"/clearances");
      setMessage(rows.length?rows.map((r:Row)=>r.kind+" cleared").join(", "):"No clearances yet");
    },"")}>View existing clearances</button>
    {(hr||user.role==="accountant")&&<form className="form" onSubmit={e=>{e.preventDefault();void save(
     ()=>call("/exits/"+exitId+"/clearances","POST",{kind,note}),"Clearance approved.")}}>
      <label>Clearance type<select value={kind} onChange={e=>setKind(e.target.value)}>
       {(hr?["assets","it","finance"]:["finance"]).map(k=><option key={k} value={k}>{k}</option>)}</select></label>
      <label>Approval note<textarea required minLength={10} value={note} onChange={e=>setNote(e.target.value)}/></label>
      <button className="primary">Approve clearance</button>
    </form>}
   </>}
  </>}
 </section>;
}

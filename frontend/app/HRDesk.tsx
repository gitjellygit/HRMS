"use client";
import {useEffect,useState} from "react";
import {CalendarDays,CheckCircle2,Clock3,Search,Users} from "lucide-react";

type Balance={leave_type:string;allocated:number;carried:number;used:number;remaining:number};
type Staff={id:number;name:string;department:string;role:string;status:string;joining_date:string;currently_checked_in:boolean;leave_balances:Balance[]};
type Overview={fy:number;fy_label:string;headcount:number;pending_leave_requests:number;currently_checked_in:number;employees:Staff[]};
const currentFY=()=>{const d=new Date();return d.getMonth()<3?d.getFullYear()-1:d.getFullYear()};
export default function HRDesk({api}:{api:string}){
 const [fy,setFY]=useState(currentFY());
 const [overview,setOverview]=useState<Overview|null>(null);
 const [search,setSearch]=useState("");
 const [selected,setSelected]=useState("");
 const [kind,setKind]=useState("");
 const [days,setDays]=useState("");
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");
 const [saving,setSaving]=useState(false);
 async function load(){
  setError("");
  try{
   const response=await fetch(api+"/leave/hr-overview?fy="+fy,{credentials:"include"});
   if(!response.ok)throw Error("Unable to load HR leave overview.");
   setOverview(await response.json());
  }catch(err){setError((err as Error).message)}
 }
 useEffect(()=>{void load()},[api,fy]);
 async function save(event:React.FormEvent){
  event.preventDefault();
  if(!selected||!kind||days==="")return;
  setSaving(true);setError("");setNotice("");
  try{
   const response=await fetch(api+"/leave/allocations",{method:"PUT",credentials:"include",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({employee_id:Number(selected),year:fy,leave_type:kind,allocated_days:Number(days)})});
   const data=await response.json().catch(()=>({}));
   if(!response.ok)throw Error(typeof data.detail==="string"?data.detail:"Could not save the override.");
   setNotice("Leave balance override saved for FY "+fy+"-"+String(fy+1).slice(-2)+".");
   setDays("");await load();
  }catch(err){setError((err as Error).message)}finally{setSaving(false)}
 }
 const filtered=(overview?.employees||[]).filter(e=>[e.name,e.department,e.role].some(v=>(v||"").toLowerCase().includes(search.toLowerCase())));
 const types=[...new Set((overview?.employees||[]).flatMap(e=>e.leave_balances.map(b=>b.leave_type)))];
 return <section className="employee-surface">
  <header className="core-head"><Users size={22}/><div><h2>HR overview</h2><p>Attendance, employee leave balances and April–March financial-year entitlements.</p></div></header>
  {error&&<div className="error" role="alert">{error}</div>}{notice&&<div className="employee-success" role="status"><CheckCircle2 size={17}/>{notice}</div>}
  <div className="employee-metrics"><div className="employee-metric"><Users size={20}/><span>Active employees</span><strong>{overview?.headcount??"—"}</strong></div><div className="employee-metric"><Clock3 size={20}/><span>Currently checked in</span><strong>{overview?.currently_checked_in??"—"}</strong></div><div className="employee-metric"><CalendarDays size={20}/><span>Pending leave requests</span><strong>{overview?.pending_leave_requests??"—"}</strong></div></div>
  <div className="core-hr-controls"><div className="employee-search"><Search size={17}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search employees / department"/></div><label>FY begins <input type="number" min={2020} max={2100} value={fy} onChange={e=>setFY(Number(e.target.value))}/></label></div>
  <p className="field-help">Showing {overview?.fy_label||"financial year"} (1 April {fy}–31 March {fy+1}). Annual entitlements are automatically prorated using the employee's joining date. HR overrides are optional.</p>
  <div className="table-wrap"><table><thead><tr><th>Employee</th><th>Joined</th><th>Department</th><th>Attendance</th><th>Leave balance for FY</th></tr></thead><tbody>{filtered.map(e=><tr key={e.id}><td><strong>{e.name}</strong><div className="muted">{e.role.replace("_"," ")}</div></td><td>{e.joining_date||"—"}</td><td>{e.department||"—"}</td><td><span className={"pill "+(e.currently_checked_in?"active":"pending")}>{e.currently_checked_in?"Checked in":"Not checked in"}</span></td><td>{e.leave_balances.length?e.leave_balances.map(b=><div key={b.leave_type} className="core-balance">{b.leave_type.replace("_"," ")}: <b>{b.remaining}</b> left ({b.allocated} allocated{b.carried?" + "+b.carried+" carried":""}, {b.used} reserved/used)</div>):<span className="muted">Configure a leave policy to generate entitlements</span>}</td></tr>)}</tbody></table>{!filtered.length&&<div className="empty">No employees match this filter.</div>}</div>
  <div className="core-entitlement"><h3>Optional: override an employee's entitlement</h3><p className="muted">Normally no action is needed here. Configure 12 annual days in Leave requests → Policies, and new joiners receive a prorated entitlement automatically. Overrides replace the calculated allocation for the selected FY.</p>
   <form className="core-inline-form" onSubmit={save}><select value={selected} onChange={e=>setSelected(e.target.value)} required><option value="">Choose employee</option>{overview?.employees.map(e=><option key={e.id} value={e.id}>{e.name}</option>)}</select><select value={kind} onChange={e=>setKind(e.target.value)} required><option value="">Leave type</option>{types.map(t=><option key={t} value={t}>{t.replace("_"," ")}</option>)}</select><input value={days} onChange={e=>setDays(e.target.value)} type="number" min={0} max={365} step={0.5} placeholder="Override days" required/><button className="employee-primary" disabled={saving}>Save override</button></form>
  </div>
 </section>;
}

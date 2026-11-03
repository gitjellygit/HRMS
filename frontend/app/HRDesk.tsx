"use client";
import { useEffect, useState } from "react";
import { CalendarDays, CheckCircle2, Clock3, Search, Users } from "lucide-react";

type Balance={leave_type:string;allocated:number;used:number;remaining:number};
type Staff={id:number;name:string;department:string;role:string;status:string;currently_checked_in:boolean;leave_balances:Balance[]};
type Overview={year:number;headcount:number;pending_leave_requests:number;currently_checked_in:number;employees:Staff[]};
export default function HRDesk({api}:{api:string}){
 const [year,setYear]=useState(new Date().getFullYear());
 const [overview,setOverview]=useState<Overview|null>(null);
 const [search,setSearch]=useState("");
 const [selected,setSelected]=useState("");
 const [leaveType,setLeaveType]=useState("Annual");
 const [days,setDays]=useState("");
 const [error,setError]=useState("");
 const [success,setSuccess]=useState("");
 const [saving,setSaving]=useState(false);
 async function fetchDesk(){
  setError("");
  try{
   const res=await fetch(api+"/core/hr-overview?year="+year,{credentials:"include"});
   if(!res.ok)throw Error("Unable to load HR overview");
   setOverview(await res.json());
  }catch(e){setError((e as Error).message)}
 }
 useEffect(()=>{void fetchDesk()},[api,year]);
 async function save(event:React.FormEvent<HTMLFormElement>){
  event.preventDefault();
  if(!selected||!days)return;
  setError("");setSuccess("");setSaving(true);
  try{
   const res=await fetch(api+"/core/leave-entitlements",{method:"PUT",credentials:"include",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({employee_id:Number(selected),year,leave_type:leaveType,allocated_days:Number(days)})});
   const data=await res.json().catch(()=>({}));
   if(!res.ok)throw Error(typeof data.detail==="string"?data.detail:"Could not save leave entitlement.");
   setSuccess("Leave entitlement saved.");setDays("");await fetchDesk();
  }catch(e){setError((e as Error).message)}finally{setSaving(false)}
 }
 const list=(overview?.employees||[]).filter(e=>[e.name,e.department,e.role].some(x=>x.toLowerCase().includes(search.toLowerCase())));
 return <section className="employee-surface"><header className="core-head"><Users size={22}/><div><h2>HR overview</h2><p>Employee directory, live attendance status and configured leave balances in one place.</p></div></header>
  {error&&<div className="error" role="alert">{error}</div>}
  {success&&<div className="employee-success" role="status"><CheckCircle2 size={17}/>{success}</div>}
  <div className="employee-metrics">
   <div className="employee-metric"><Users size={20}/><span>Active employees</span><strong>{overview?.headcount??"—"}</strong></div>
   <div className="employee-metric"><Clock3 size={20}/><span>Currently checked in</span><strong>{overview?.currently_checked_in??"—"}</strong></div>
   <div className="employee-metric"><CalendarDays size={20}/><span>Pending leave requests</span><strong>{overview?.pending_leave_requests??"—"}</strong></div>
  </div>
  <div className="core-hr-controls"><div className="employee-search"><Search size={17}/><input placeholder="Search employees or departments" value={search} onChange={e=>setSearch(e.target.value)}/></div><label>Year <input type="number" min={2020} max={2100} value={year} onChange={e=>setYear(Number(e.target.value))}/></label></div>
  <div className="table-wrap"><table><thead><tr><th>Employee</th><th>Department</th><th>Attendance</th><th>Leave balance</th></tr></thead><tbody>{list.map(row=><tr key={row.id}><td><strong>{row.name}</strong><div className="muted">{row.role.replace("_"," ")}</div></td><td>{row.department||"—"}</td><td><span className={"pill "+(row.currently_checked_in?"active":"pending")}>{row.currently_checked_in?"Checked in":"Not checked in"}</span></td><td>{row.leave_balances.length?row.leave_balances.map(b=><div key={b.leave_type} className="core-balance">{b.leave_type}: <b>{b.remaining}</b> days remaining ({b.used}/{b.allocated} used)</div>):<span className="muted">Not configured</span>}</td></tr>)}</tbody></table>{!list.length&&<div className="empty">No employees found.</div>}</div>
  <div className="core-entitlement"><h3>Set employee leave entitlement</h3><p className="muted">Manual starting balances only. Accrual, carry-forward and leave policies are planned for the Leave Management module.</p><form className="core-inline-form" onSubmit={save}><select value={selected} onChange={e=>setSelected(e.target.value)} required><option value="">Select employee</option>{overview?.employees.map(e=><option key={e.id} value={e.id}>{e.name}</option>)}</select><select value={leaveType} onChange={e=>setLeaveType(e.target.value)}>{["Annual","Casual","Sick","Unpaid"].map(t=><option key={t}>{t}</option>)}</select><input type="number" min={0} max={365} step={0.5} placeholder="Allocated days" value={days} onChange={e=>setDays(e.target.value)} required/><button className="employee-primary" disabled={saving}>Save allocation</button></form></div>
 </section>;
}

"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Bell, CalendarDays, Check, ChevronLeft, ChevronRight, Clock3, Download, FileText, Gift, Plus, RefreshCw, Settings2, ShieldCheck, Users, X } from "lucide-react";

type User={id:number;name:string;role:string;email:string};
type Tab="requests"|"approvals"|"calendar"|"holidays"|"policies"|"delegation"|"reports"|"notifications";
type LeaveRow={id:number;employee_id:number;leave_type:string;start_date:string;end_date:string;day_part:string;days:number;reason:string;status:string;current_stage:string|null;cancellation_requested:boolean;created_at:string};
type Balance={leave_type:string;allocated:number;carried:number;used:number;encashed:number;remaining:number};
type Policy={leave_type:string;annual_days:number;monthly_accrual:number;carry_forward_limit:number;encashment_allowed:boolean;probation_allowed:boolean;approval_chain:string[];active:boolean};
type Holiday={id:number;name:string;date:string;location:string;optional:boolean};
type CalendarRow={employee_id:number;employee_name:string;start_date:string;end_date:string;leave_type:string;day_part:string};
type Notice={id:number;message:string;created_at:string;read:boolean;request_id:number|null};
type Delegation={id:number;manager_id:number;delegate_id:number;start_date:string;end_date:string;active:boolean};
const KINDS=["casual","sick","earned","maternity","paternity","comp_off","loss_of_pay"];
const title=(value:string)=>value.replace(/_/g," ").replace(/\b\w/g,c=>c.toUpperCase());
const today=()=>new Date().toLocaleDateString("en-CA");
function messageFor(data:any):string{
 const detail=data?.detail||data;
 if(typeof detail==="string")return detail;
 if(Array.isArray(detail))return detail.map((e:any)=>e.msg||"Invalid value").join("; ");
 return "Could not complete the request. Please check the details.";
}
function monthLabel(year:number,month:number){return new Date(year,month-1,1).toLocaleString("en-IN",{month:"long",year:"numeric"})}
export default function LeaveWorkspace({api,user}:{api:string;user:User}){
 const canHR=["super_admin","admin","hr"].includes(user.role);
 const canApprove=canHR||user.role==="manager";
 const [tab,setTab]=useState<Tab>("requests");
 const [requests,setRequests]=useState<LeaveRow[]>([]);
 const [approvals,setApprovals]=useState<LeaveRow[]>([]);
 const [balances,setBalances]=useState<Balance[]>([]);
 const [policies,setPolicies]=useState<Policy[]>([]);
 const [teamBalances,setTeamBalances]=useState<Balance[]>([]);
 const [encashments,setEncashments]=useState<{id:number;employee_id:number;leave_type:string;year:number;days:number;status:string}[]>([]);
 const [holidays,setHolidays]=useState<Holiday[]>([]);
 const [calendar,setCalendar]=useState<CalendarRow[]>([]);
 const [notifications,setNotifications]=useState<Notice[]>([]);
 const [delegations,setDelegations]=useState<Delegation[]>([]);
 const [staff,setStaff]=useState<{id:number;name:string}[]>([]);
 const [report,setReport]=useState<any>(null);
 const [year,setYear]=useState(new Date().getFullYear());
 const [month,setMonth]=useState(new Date().getMonth()+1);
 const [location,setLocation]=useState("all");
 const [department,setDepartment]=useState("");
 const [kind,setKind]=useState("casual");
 const [start,setStart]=useState(today());
 const [end,setEnd]=useState(today());
 const [part,setPart]=useState("full");
 const [reason,setReason]=useState("");
 const [newPolicy,setNewPolicy]=useState<Policy>({leave_type:"casual",annual_days:0,monthly_accrual:0,carry_forward_limit:0,encashment_allowed:false,probation_allowed:true,approval_chain:["manager","hr"],active:true});
 const [holidayName,setHolidayName]=useState("");
 const [holidayDate,setHolidayDate]=useState(today());
 const [optional,setOptional]=useState(false);
 const [delegateId,setDelegateId]=useState("");
 const [delegateStart,setDelegateStart]=useState(today());
 const [delegateEnd,setDelegateEnd]=useState(today());
 const [allocationEmployee,setAllocationEmployee]=useState("");
 const [allocationDays,setAllocationDays]=useState("");
 const [encashDays,setEncashDays]=useState("");
 const [error,setError]=useState("");
 const [success,setSuccess]=useState("");
 const [busy,setBusy]=useState(false);
 const [loading,setLoading]=useState(true);
 const call=useCallback(async(path:string,method="GET",body?:unknown)=>{
  const response=await fetch(api+"/leave"+path,{method,credentials:"include",headers:{"Content-Type":"application/json"},body:body===undefined?undefined:JSON.stringify(body)});
  const result=await response.json().catch(()=>({}));
  if(!response.ok)throw Error(messageFor(result));
  return result;
 },[api]);
 const load=useCallback(async()=>{
  setLoading(true);setError("");
  try{
   const scope=canHR?"all":"mine";
   const entries=await Promise.all([
    call("/requests?scope="+scope),call("/requests?scope=approvals"),
    call("/balances?year="+year),call("/policies"),
    call("/holidays?year="+year+"&location="+encodeURIComponent(location)),
    call("/calendar?year="+year+"&month="+month),call("/notifications"),call("/delegations")
   ]);
   setRequests(entries[0]);setApprovals(entries[1]);setBalances(entries[2]);setPolicies(entries[3]);
   setHolidays(entries[4]);setCalendar(entries[5]);setNotifications(entries[6]);setDelegations(entries[7]);
   if(canHR){
    const people=await fetch(api+"/core/employees",{credentials:"include"});
    if(people.ok)setStaff((await people.json()).map((e:any)=>({id:e.id,name:e.name})));
    setReport(await call("/reports?year="+year+(department?"&department="+encodeURIComponent(department):"")));
    setEncashments(await call("/encashment"));
   }
  }catch(err){setError((err as Error).message)}finally{setLoading(false)}
 },[api,call,year,month,location,department,canHR]);
 useEffect(()=>{void load()},[load]);
 useEffect(()=>{
  if(!canHR||!allocationEmployee){setTeamBalances([]);return}
  call("/balances?employee_id="+allocationEmployee+"&year="+year)
    .then(setTeamBalances).catch(err=>setError((err as Error).message));
 },[canHR,allocationEmployee,year,call]);
 async function execute(work:()=>Promise<unknown>,confirmation="Updated successfully"){
  setBusy(true);setError("");setSuccess("");
  try{await work();setSuccess(confirmation);await load()}catch(err){setError((err as Error).message)}finally{setBusy(false)}
 }
 const leaveTypes=policies.filter(p=>p.active).map(p=>p.leave_type);
 async function submit(event:React.FormEvent){
  event.preventDefault();
  await execute(()=>call("/requests","POST",{leave_type:kind,start_date:start,end_date:end,day_part:part,reason}),"Leave request submitted for approval.");
 }
 async function review(id:number,action:string){
  await execute(()=>call("/requests/"+id+"/review","POST",{action,note:""}),"Leave request updated.");
 }
 async function withdraw(id:number){
  if(!window.confirm("Withdraw this request? Approved leave requires HR cancellation approval."))return;
  await execute(()=>call("/requests/"+id+"/withdraw","POST"),"Withdrawal or cancellation requested.");
 }
 function applyPolicy(p:Policy){setNewPolicy({...p,approval_chain:[...p.approval_chain]})}
 async function savePolicy(event:React.FormEvent){
  event.preventDefault();
  await execute(()=>call("/policies","PUT",newPolicy),"Leave policy saved.");
 }
 async function addHoliday(event:React.FormEvent){
  event.preventDefault();
  await execute(()=>call("/holidays","POST",{name:holidayName,holiday_date:holidayDate,location,optional}),"Holiday added.");
  setHolidayName("");
 }
 async function delegate(event:React.FormEvent){
  event.preventDefault();
  await execute(()=>call("/delegations","POST",{delegate_id:Number(delegateId),start_date:delegateStart,end_date:delegateEnd}),"Delegation created.");
 }
 async function allocate(event:React.FormEvent){
  event.preventDefault();
  await execute(()=>call("/allocations","PUT",{employee_id:Number(allocationEmployee),year,leave_type:kind,allocated_days:Number(allocationDays)}),"Employee leave allocation saved.");
 }
 async function reviewEncashment(id:number,approve:boolean){
  await execute(()=>call("/encashment/"+id+"/review?approve="+approve,"POST"),approve?"Encashment approved.":"Encashment rejected.");
 }
 async function encash(event:React.FormEvent){
  event.preventDefault();
  await execute(()=>call("/encashment","POST",{leave_type:kind,year,days:Number(encashDays)}),"Encashment request submitted.");
 }
 async function exportReport(){
  setError("");
  try{
   const query=new URLSearchParams({year:String(year),format:"csv"});
   if(department)query.set("department",department);
   const res=await fetch(api+"/leave/reports?"+query,{credentials:"include"});
   if(!res.ok)throw Error("Report download failed.");
   const uri=URL.createObjectURL(await res.blob());
   const anchor=window.document.createElement("a");anchor.href=uri;anchor.download="leave-report.csv";anchor.click();URL.revokeObjectURL(uri);
  }catch(err){setError((err as Error).message)}
 }
 const tabs: [Tab,string,React.ReactNode][]=[
  ["requests","My leave",<CalendarDays size={16}/>],["approvals","Approvals",<ShieldCheck size={16}/>],
  ["calendar","Team calendar",<Users size={16}/>],["holidays","Holidays",<Gift size={16}/>],
  ["notifications","Notifications",<Bell size={16}/>],["delegation","Delegation",<Clock3 size={16}/>],
  ["policies","Policies & balances",<Settings2 size={16}/>],["reports","Reports",<FileText size={16}/>]
 ];
 const visibleTabs=tabs.filter(([id])=>(!["policies","reports"].includes(id)||canHR)&&(!["delegation"].includes(id)||canApprove));
 const calendarDays=useMemo(()=>{
  const count=new Date(year,month,0).getDate();
  const pad=(new Date(year,month-1,1).getDay()+6)%7;
  return [...Array(pad).fill(null),...Array.from({length:count},(_,i)=>i+1)] as (number|null)[];
 },[year,month]);
 const getForDay=(day:number)=>calendar.filter(c=>c.start_date<=`${year}-${String(month).padStart(2,"0")}-${String(day).padStart(2,"0")}`&&c.end_date>=`${year}-${String(month).padStart(2,"0")}-${String(day).padStart(2,"0")}`);
 const displayRows=(items:LeaveRow[],isReview:boolean)=> <div className="table-wrap"><table className="leave-table"><thead><tr>{isReview&&<th>Employee</th>}<th>Type</th><th>Dates</th><th>Duration</th><th>Status</th><th>Approver</th><th>Action</th></tr></thead><tbody>{items.map(item=><tr key={item.id}>{isReview&&<td>{staff.find(s=>s.id===item.employee_id)?.name||"Employee #"+item.employee_id}</td>}<td><strong>{title(item.leave_type)}</strong><small>{item.reason}</small></td><td>{item.start_date} – {item.end_date}</td><td>{item.days} day(s)<small>{title(item.day_part)}</small></td><td><span className={"pill "+item.status}>{item.status}</span>{item.cancellation_requested&&<small>Cancellation pending</small>}</td><td>{item.current_stage?title(item.current_stage):"—"}</td><td><div className="actions">{isReview?item.cancellation_requested?<><button className="secondary" disabled={busy} onClick={()=>review(item.id,"cancel_approve")}>Accept cancellation</button><button className="secondary" disabled={busy} onClick={()=>review(item.id,"cancel_reject")}>Decline</button></>:<><button className="secondary" disabled={busy} onClick={()=>review(item.id,"approve")}>Approve</button><button className="secondary" disabled={busy} onClick={()=>review(item.id,"reject")}>Reject</button></>:["approved","pending"].includes(item.status)&&!item.cancellation_requested?<button className="employee-link" disabled={busy||item.employee_id!==user.id} onClick={()=>withdraw(item.id)}>{item.status==="approved"?"Request cancellation":"Withdraw"}</button>:"—"}</div></td></tr>)}</tbody></table>{items.length===0&&<div className="empty">No leave requests to show.</div>}</div>;
 return <div className="leave-workspace">
  <div className="leave-intro"><div><h2>Leave & time off</h2><p>Manage your leave, holidays and approval workflow.</p></div><button className="employee-cancel" onClick={load} disabled={busy}><RefreshCw size={15}/> Refresh</button></div>
  <div className="leave-tabs">{visibleTabs.map(([id,label,icon])=><button key={id} className={tab===id?"selected":""} onClick={()=>setTab(id)}>{icon}{label}{id==="approvals"&&approvals.length>0&&<b>{approvals.length}</b>}{id==="notifications"&&notifications.some(n=>!n.read)&&<span className="leave-unread"/>}</button>)}</div>
  {error&&<div className="error" role="alert">{error}</div>}{success&&<div className="employee-success" role="status"><Check size={17}/>{success}</div>}
  {loading&&<p className="muted">Loading leave information…</p>}
  {tab==="requests"&&<><div className="leave-balances">{balances.map(b=><div className="leave-balance" key={b.leave_type}><span>{title(b.leave_type)}</span><strong>{b.remaining}</strong><small>days remaining · {b.used} used</small></div>)}{!balances.length&&<p className="muted">No leave policies configured. Ask HR to set up leave policies.</p>}</div><section className="employee-surface"><div className="core-head"><Plus size={20}/><div><h2>Apply for leave</h2><p>Choose a leave type, dates and reason. Requests follow your assigned manager's approval chain.</p></div></div><form className="leave-form" onSubmit={submit}><label>Leave type<select value={kind} onChange={e=>setKind(e.target.value)}>{(leaveTypes.length?leaveTypes:KINDS).map(x=><option key={x} value={x}>{title(x)}</option>)}</select></label><label>Start date<input type="date" value={start} onChange={e=>setStart(e.target.value)} required/></label><label>End date<input type="date" value={end} onChange={e=>setEnd(e.target.value)} required/></label><label>Duration<select value={part} onChange={e=>setPart(e.target.value)}><option value="full">Full day</option><option value="half">Half day</option><option value="short">Short leave (¼ day)</option></select></label><label className="full">Reason<textarea value={reason} onChange={e=>setReason(e.target.value)} rows={2} required minLength={3} placeholder="Reason for your leave request"/></label><div className="full leave-submit"><button className="employee-primary" disabled={busy||!leaveTypes.length}>Submit request</button></div></form></section><section className="employee-surface"><div className="core-head"><CalendarDays size={20}/><div><h2>Leave history</h2><p>Your submitted and approved leave requests.</p></div></div>{displayRows(requests.filter(r=>r.employee_id===user.id),false)}</section>
   {["earned","comp_off"].includes(kind)&&policies.find(p=>p.leave_type===kind)?.encashment_allowed&&<section className="employee-surface"><h3>Request leave encashment</h3><form className="core-inline-form" onSubmit={encash}><input type="number" step="0.5" min="0.5" value={encashDays} onChange={e=>setEncashDays(e.target.value)} placeholder="Days" required/><button className="employee-primary" disabled={busy}>Request encashment</button></form><small className="muted">HR approval is required. Payment processing is part of the payroll roadmap.</small></section>}
  </>}
  {tab==="approvals"&&<section className="employee-surface"><div className="core-head"><ShieldCheck size={20}/><div><h2>Leave approvals</h2><p>Only pending requests assigned to your current approval stage are shown.</p></div></div>{displayRows(approvals,true)}</section>}
  {tab==="calendar"&&<section className="employee-surface"><div className="core-head"><Users size={20}/><div><h2>Team leave calendar</h2><p>View approved time off for your team and avoid scheduling conflicts.</p></div></div><div className="leave-calendar-nav"><button className="employee-icon-button" onClick={()=>{if(month===1){setMonth(12);setYear(y=>y-1)}else setMonth(x=>x-1)}}><ChevronLeft size={17}/></button><strong>{monthLabel(year,month)}</strong><button className="employee-icon-button" onClick={()=>{if(month===12){setMonth(1);setYear(y=>y+1)}else setMonth(x=>x+1)}}><ChevronRight size={17}/></button></div><div className="leave-calendar">{["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].map(d=><div className="leave-weekday" key={d}>{d}</div>)}{calendarDays.map((day,i)=><div key={i} className={"leave-calendar-day "+(!day?"blank":"")}><strong>{day||""}</strong>{day&&getForDay(day).slice(0,3).map((c,j)=><span className="leave-calendar-event" key={j} title={c.employee_name+" · "+title(c.leave_type)}>{c.employee_name}</span>)}{day&&getForDay(day).length>3&&<small>+{getForDay(day).length-3} more</small>}</div>)}</div></section>}
  {tab==="holidays"&&<section className="employee-surface"><div className="core-head"><Gift size={20}/><div><h2>Holiday calendar</h2><p>Public and optional holidays by employee location.</p></div></div><div className="core-inline-form"><input value={location} onChange={e=>setLocation(e.target.value)} placeholder="Location (e.g. Noida)"/><input type="number" min={2020} max={2100} value={year} onChange={e=>setYear(Number(e.target.value))}/></div>{canHR&&<form className="core-inline-form" onSubmit={addHoliday}><input placeholder="Holiday name" value={holidayName} onChange={e=>setHolidayName(e.target.value)} required minLength={2}/><input type="date" value={holidayDate} onChange={e=>setHolidayDate(e.target.value)} required/><label className="leave-inline-check"><input type="checkbox" checked={optional} onChange={e=>setOptional(e.target.checked)}/> Optional</label><button className="employee-primary" disabled={busy}>Add holiday</button></form>}<div className="table-wrap"><table><thead><tr><th>Date</th><th>Holiday</th><th>Location</th><th>Type</th></tr></thead><tbody>{holidays.map(h=><tr key={h.id}><td>{h.date}</td><td>{h.name}</td><td>{h.location}</td><td>{h.optional?"Optional":"Public"}</td></tr>)}</tbody></table>{!holidays.length&&<div className="empty">No holidays configured for this location/year.</div>}</div></section>}
  {tab==="notifications"&&<section className="employee-surface"><div className="core-head"><Bell size={20}/><div><h2>Notifications</h2><p>Leave submissions, approval decisions and delegation notices.</p></div></div><div className="leave-notifications">{notifications.map(n=><div className={"leave-notice "+(!n.read?"unread":"")} key={n.id}><div><p>{n.message}</p><small>{new Date(n.created_at).toLocaleString()}</small></div>{!n.read&&<button className="employee-link" onClick={()=>execute(()=>call("/notifications/"+n.id+"/read","POST"),"Marked as read.")}>Mark read</button>}</div>)}{!notifications.length&&<div className="empty">No notifications yet.</div>}</div></section>}
  {tab==="delegation"&&<section className="employee-surface"><div className="core-head"><Clock3 size={20}/><div><h2>Approval delegation</h2><p>Assign an alternate approver for up to 90 days while you are away.</p></div></div><form className="leave-form" onSubmit={delegate}><label>Delegate employee ID<input type="number" min={1} value={delegateId} onChange={e=>setDelegateId(e.target.value)} required placeholder="Employee ID (numeric)"/></label><label>From<input type="date" value={delegateStart} onChange={e=>setDelegateStart(e.target.value)} required/></label><label>To<input type="date" value={delegateEnd} onChange={e=>setDelegateEnd(e.target.value)} required/></label><button className="employee-primary" disabled={busy}>Delegate approvals</button></form><div className="table-wrap"><table><thead><tr><th>Manager</th><th>Delegate</th><th>Dates</th><th>Status</th><th>Action</th></tr></thead><tbody>{delegations.map(d=><tr key={d.id}><td>#{d.manager_id}</td><td>#{d.delegate_id}</td><td>{d.start_date} to {d.end_date}</td><td>{d.active?"Active":"Revoked"}</td><td>{d.active&&<button className="employee-link" disabled={busy} onClick={()=>execute(()=>call("/delegations/"+d.id,"DELETE"),"Delegation revoked.")}>Revoke</button>}</td></tr>)}</tbody></table></div></section>}
  {tab==="policies"&&canHR&&<><section className="employee-surface"><div className="core-head"><Settings2 size={20}/><div><h2>Leave policies</h2><p>Configure accrual, carry-forward, encashment and approval sequence.</p></div></div><div className="leave-policy-choices">{KINDS.map(k=><button key={k} className={newPolicy.leave_type===k?"active":""} onClick={()=>applyPolicy(policies.find(p=>p.leave_type===k)||{leave_type:k,annual_days:0,monthly_accrual:0,carry_forward_limit:0,encashment_allowed:false,probation_allowed:true,approval_chain:["manager","hr"],active:true})}>{title(k)}</button>)}</div><form className="leave-form" onSubmit={savePolicy}><label>Annual allocation (days)<input type="number" min={0} max={365} step={0.5} value={newPolicy.annual_days} onChange={e=>setNewPolicy(p=>({...p,annual_days:Number(e.target.value)}))}/></label><label>Monthly accrual (days)<input type="number" min={0} max={31} step={0.25} value={newPolicy.monthly_accrual} onChange={e=>setNewPolicy(p=>({...p,monthly_accrual:Number(e.target.value)}))}/></label><label>Carry-forward limit<input type="number" min={0} max={365} step={0.5} value={newPolicy.carry_forward_limit} onChange={e=>setNewPolicy(p=>({...p,carry_forward_limit:Number(e.target.value)}))}/></label><label>Approval workflow<select value={newPolicy.approval_chain.join(",")} onChange={e=>setNewPolicy(p=>({...p,approval_chain:e.target.value?e.target.value.split(","):[]}))}><option value="manager">Manager</option><option value="manager,hr">Manager → HR</option><option value="manager,hr,admin">Manager → HR → Admin</option><option value="hr">HR</option><option value="hr,admin">HR → Admin</option></select></label><label className="leave-inline-check"><input type="checkbox" checked={newPolicy.probation_allowed} onChange={e=>setNewPolicy(p=>({...p,probation_allowed:e.target.checked}))}/> Available during probation</label><label className="leave-inline-check"><input type="checkbox" checked={newPolicy.encashment_allowed} onChange={e=>setNewPolicy(p=>({...p,encashment_allowed:e.target.checked}))}/> Encashment permitted</label><label className="leave-inline-check"><input type="checkbox" checked={newPolicy.active} onChange={e=>setNewPolicy(p=>({...p,active:e.target.checked}))}/> Policy active</label><button className="employee-primary" disabled={busy}>Save policy</button></form></section><section className="employee-surface"><div className="core-head"><Users size={20}/><div><h2>Individual leave allocations</h2><p>Override policy-generated balances for a given employee/year.</p></div></div><form className="core-inline-form" onSubmit={allocate}><select value={allocationEmployee} onChange={e=>setAllocationEmployee(e.target.value)} required><option value="">Select employee</option>{staff.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select><select value={kind} onChange={e=>setKind(e.target.value)}>{(leaveTypes.length?leaveTypes:KINDS).map(k=><option value={k} key={k}>{title(k)}</option>)}</select><input type="number" min="0" max="365" step="0.5" value={allocationDays} onChange={e=>setAllocationDays(e.target.value)} placeholder="Allocated days" required/><button className="employee-primary" disabled={busy}>Save allocation</button></form>{allocationEmployee&&<div className="leave-balances">{teamBalances.map(b=><div className="leave-balance" key={b.leave_type}><span>{title(b.leave_type)}</span><strong>{b.remaining}</strong><small>Remaining · {b.used} days reserved/used</small></div>)}</div>}</section>
   <section className="employee-surface"><div className="core-head"><Gift size={20}/><div><h2>Leave encashment approvals</h2><p>Approve eligible leave encashment requests. Financial settlement happens in Payroll.</p></div></div><div className="table-wrap"><table><thead><tr><th>Employee</th><th>Type</th><th>Year</th><th>Days</th><th>Status</th><th>Review</th></tr></thead><tbody>{encashments.map(e=><tr key={e.id}><td>{staff.find(p=>p.id===e.employee_id)?.name||"Employee #"+e.employee_id}</td><td>{title(e.leave_type)}</td><td>{e.year}</td><td>{e.days}</td><td><span className={"pill "+e.status}>{e.status}</span></td><td>{e.status==="pending"?<div className="actions"><button className="secondary" disabled={busy} onClick={()=>reviewEncashment(e.id,true)}>Approve</button><button className="secondary" disabled={busy} onClick={()=>reviewEncashment(e.id,false)}>Reject</button></div>:"—"}</td></tr>)}</tbody></table>{!encashments.length&&<div className="empty">No encashment requests.</div>}</div></section></>}
  {tab==="reports"&&canHR&&<section className="employee-surface"><div className="core-head"><FileText size={20}/><div><h2>Leave reports</h2><p>Leave usage and trends, filtered by department and year.</p></div></div><div className="core-inline-form"><input type="number" min={2020} max={2100} value={year} onChange={e=>setYear(Number(e.target.value))}/><input value={department} onChange={e=>setDepartment(e.target.value)} placeholder="Department filter (optional)"/><button className="employee-cancel" onClick={exportReport}><Download size={15}/> Export CSV</button></div>{report&&<div className="leave-report-kpis"><div><span>Requests</span><strong>{report.requests}</strong></div><div><span>Approved days</span><strong>{report.approved_days}</strong></div>{Object.entries(report.by_type||{}).map(([k,v])=><div key={k}><span>{title(k)}</span><strong>{String(v)}</strong></div>)}</div>}<div className="table-wrap"><table><thead><tr><th>Employee</th><th>Department</th><th>Type</th><th>Dates</th><th>Days</th><th>Status</th></tr></thead><tbody>{(report?.rows||[]).map((r:any,i:number)=><tr key={i}><td>{r.employee}</td><td>{r.department}</td><td>{title(r.type)}</td><td>{r.start} – {r.end}</td><td>{r.days}</td><td><span className={"pill "+r.status}>{r.status}</span></td></tr>)}</tbody></table></div></section>}
 </div>;
}

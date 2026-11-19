"use client";
import AppSelect from "./AppSelect";
import {useTransientMessage} from "./useTransientMessage";
import {useEffect,useState} from "react";
import {CalendarDays,CheckCircle2,ChevronDown,Clock3,Mail,RefreshCw,Search,Users} from "lucide-react";

type Balance={leave_type:string;allocated:number;carried:number;used:number;remaining:number};
type Staff={id:number;name:string;department:string;role:string;status:string;joining_date:string;manager_id:number|null;currently_checked_in:boolean;leave_balances:Balance[]};
type Delivery={id:number;recipient_id:number;request_id:number|null;status:string;attempts:number;error:string;created_at:string};
type Overview={fy:number;fy_label:string;headcount:number;pending_leave_requests:number;currently_checked_in:number;unassigned_managers:number;employees:Staff[]};
const currentFY=()=>{const d=new Date();return d.getMonth()<3?d.getFullYear()-1:d.getFullYear()};
export default function HRDesk({api}:{api:string}){
 const [fy,setFY]=useState(currentFY());
 const [overview,setOverview]=useState<Overview|null>(null);
 const [deliveries,setDeliveries]=useState<Delivery[]>([]);
 const [deliveryExpanded,setDeliveryExpanded]=useState(false);
 const [deliveryFilter,setDeliveryFilter]=useState<"all"|"action">("all");
 const [deliveryLimit,setDeliveryLimit]=useState(5);
 const [loadingMail,setLoadingMail]=useState(false);
 const [retrying,setRetrying]=useState<number|null>(null);
 const [search,setSearch]=useState("");
 const [selected,setSelected]=useState("");
 const [kind,setKind]=useState("");
 const [days,setDays]=useState("");
 const [error,setError]=useState("");
 const [notice,setNotice]=useTransientMessage();
 const [saving,setSaving]=useState(false);
 async function load(){
  setError("");
  try{
   const response=await fetch(api+"/leave/hr-overview?fy="+fy,{credentials:"include"});
   if(!response.ok)throw Error("Unable to load HR leave overview.");
   setOverview(await response.json());
   const mail=await fetch(api+"/leave/email-outbox",{credentials:"include"});
   if(mail.ok)setDeliveries(await mail.json());
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
 async function retryEmail(id:number){
  setRetrying(id);setError("");setNotice("");
  try{
   const response=await fetch(api+"/leave/email-outbox/"+id+"/retry",{method:"POST",credentials:"include"});
   const data=await response.json().catch(()=>({}));
   if(!response.ok)throw Error(typeof data.detail==="string"?data.detail:data.detail?.message||"Could not queue the email retry.");
   setNotice("Leave email queued for retry. The mail worker will attempt delivery.");
   await load();
  }catch(err){setError((err as Error).message)}finally{setRetrying(null)}
 }
 const filtered=(overview?.employees||[]).filter(e=>[e.name,e.department,e.role].some(v=>(v||"").toLowerCase().includes(search.toLowerCase())));
 const types=[...new Set((overview?.employees||[]).flatMap(e=>e.leave_balances.map(b=>b.leave_type)))];
 const pendingMail=deliveries.filter(x=>x.status!=="sent");
 const actionMail=pendingMail.filter(x=>x.status==="failed"||x.status==="retry");
 const queuedMail=pendingMail.filter(x=>x.status==="queued");
 const visibleMail=(deliveryFilter==="action"?actionMail:pendingMail).slice(0,deliveryLimit);
 const staffNames=new Map((overview?.employees||[]).map(p=>[p.id,p.name]));
 async function refreshMail(){
  setLoadingMail(true);
  try{
   const response=await fetch(api+"/leave/email-outbox",{credentials:"include"});
   if(!response.ok)throw Error("Could not refresh email delivery status.");
   setDeliveries(await response.json());
  }catch(err){setError((err as Error).message)}finally{setLoadingMail(false)}
 }
 return <section className="employee-surface">
  <header className="core-head"><Users size={22}/><div><h2>HR overview</h2><p>Attendance, employee leave balances and April–March financial-year entitlements.</p></div></header>
  {error&&<div className="error" role="alert">{error}</div>}{notice&&<div className="employee-success" role="status"><CheckCircle2 size={17}/>{notice}</div>}
  <div className="employee-metrics"><div className="employee-metric"><Users size={20}/><span>Active employees</span><strong>{overview?.headcount??"—"}</strong></div><div className="employee-metric"><Clock3 size={20}/><span>Currently checked in</span><strong>{overview?.currently_checked_in??"—"}</strong></div><div className="employee-metric"><CalendarDays size={20}/><span>Pending leave requests</span><strong>{overview?.pending_leave_requests??"—"}</strong></div></div>
  {(overview?.unassigned_managers??0)>0&&<div className="hr-manager-warning"><strong>{overview?.unassigned_managers} active employees have no reporting manager assigned.</strong><p>Open Employees, select a highlighted employee, and assign a reporting manager to enable leave approvals.</p><div>{(overview?.employees||[]).filter(e=>e.status==="active"&&!["admin","super_admin"].includes(e.role)&&!e.manager_id).map(e=><span key={e.id}>{e.name}</span>)}</div></div>}
  <div className="core-hr-controls"><div className="employee-search"><Search size={17}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search employees / department"/></div><label>FY begins <input type="number" min={2020} max={2100} value={fy} onChange={e=>setFY(Number(e.target.value))}/></label></div>
  <p className="field-help">Showing {overview?.fy_label||"financial year"} (1 April {fy}–31 March {fy+1}). Annual entitlements are automatically prorated using the employee's joining date. HR overrides are optional.</p>
  <div className="table-wrap"><table><thead><tr><th>Employee</th><th>Joined</th><th>Department</th><th>Attendance</th><th>Leave balance for FY</th></tr></thead><tbody>{filtered.map(e=><tr key={e.id}><td><strong>{e.name}</strong><div className="muted">{e.role.replace("_"," ")}{!e.manager_id&&!["admin","super_admin"].includes(e.role)?" · Manager needed":""}</div></td><td>{e.joining_date||"—"}</td><td>{e.department||"—"}</td><td><span className={"pill "+(e.currently_checked_in?"active":"pending")}>{e.currently_checked_in?"Checked in":"Not checked in"}</span></td><td>{e.leave_balances.length?e.leave_balances.map(b=><div key={b.leave_type} className="core-balance">{b.leave_type.replace("_"," ")}: <b>{b.remaining}</b> left ({b.allocated} allocated{b.carried?" + "+b.carried+" carried":""}, {b.used} reserved/used)</div>):<span className="muted">Configure a leave policy to generate entitlements</span>}</td></tr>)}</tbody></table>{!filtered.length&&<div className="empty">No employees match this filter.</div>}</div>
  <div className="core-entitlement hr-mail-section">
   <button type="button" className="hr-mail-toggle" aria-expanded={deliveryExpanded} aria-controls="hr-leave-email-details" onClick={()=>setDeliveryExpanded(v=>!v)}>
    <span className="hr-mail-toggle-icon"><Mail size={19}/></span>
    <span className="hr-mail-toggle-copy"><strong>Leave email delivery</strong><small>{pendingMail.length===0?"No undelivered messages":`${pendingMail.length} undelivered · ${queuedMail.length} queued · ${actionMail.length} need attention`}</small></span>
    {actionMail.length>0&&<span className="hr-mail-alert">{actionMail.length} action needed</span>}
    <ChevronDown className={deliveryExpanded?"is-open":""} size={18}/>
   </button>
   {deliveryExpanded&&<div id="hr-leave-email-details" className="hr-mail-details">
    <p className="field-help">Queued messages are awaiting the background email worker. An email marked queued does not need manual retry. Failed messages can be requeued after the delivery issue is resolved.</p>
    <div className="hr-mail-toolbar">
     <div className="hr-mail-filter" role="group" aria-label="Email delivery filter">
      <button type="button" aria-pressed={deliveryFilter==="all"} onClick={()=>{setDeliveryFilter("all");setDeliveryLimit(5)}}>Undelivered ({pendingMail.length})</button>
      <button type="button" aria-pressed={deliveryFilter==="action"} onClick={()=>{setDeliveryFilter("action");setDeliveryLimit(5)}}>Needs attention ({actionMail.length})</button>
     </div>
     <button type="button" className="employee-cancel hr-mail-refresh" onClick={()=>void refreshMail()} disabled={loadingMail}><RefreshCw size={15}/>{loadingMail?"Refreshing…":"Refresh status"}</button>
    </div>
    <div className="hr-mail-scroll"><table className="hr-mail-table"><thead><tr><th>Recipient</th><th>Status</th><th>Attempts</th><th>Delivery detail</th><th>Action</th></tr></thead>
     <tbody>{visibleMail.map(item=><tr key={item.id}>
      <td><strong>{staffNames.get(item.recipient_id)||`Employee #${item.recipient_id}`}</strong></td>
      <td><span className={"hr-mail-state "+item.status}>{item.status==="queued"?"Queued":item.status==="retry"?"Retry scheduled":item.status==="failed"?"Failed":item.status}</span></td>
      <td>{item.attempts}</td>
      <td className="hr-mail-detail">{item.error||"Waiting for background email worker"}</td>
      <td className="hr-mail-action">{item.status==="failed"||item.status==="retry"?<button type="button" className="employee-cancel" disabled={retrying!==null} onClick={()=>void retryEmail(item.id)}>{retrying===item.id?"Queuing…":"Retry"}</button>:<span className="muted">Automatic</span>}</td>
     </tr>)}</tbody>
    </table>{visibleMail.length===0&&<div className="empty">No messages in this category.</div>}</div>
    {visibleMail.length<(deliveryFilter==="action"?actionMail:pendingMail).length&&<button type="button" className="employee-cancel hr-mail-more" onClick={()=>setDeliveryLimit(n=>n+5)}>Show 5 more messages</button>}
    <p className="field-help">Showing the latest {deliveries.length} delivery records. Status updates when you select Refresh status.</p>
   </div>}
  </div>
  <div className="core-entitlement hr-override-section"><h3>Optional: override an employee's entitlement</h3>
   <p className="muted">Only use an override when an employee needs a documented exception to the configured leave policy. This replaces their calculated allocation for the selected financial year.</p>
   <form className="hr-override-form" onSubmit={save}>
    <label>Employee<AppSelect value={selected} aria-label="Override employee" onChange={e=>setSelected(e.target.value)} required><option value="">Choose employee</option>{overview?.employees.map(e=><option key={e.id} value={e.id}>{e.name}</option>)}</AppSelect></label>
    <label>Leave type<AppSelect value={kind} aria-label="Override leave type" onChange={e=>setKind(e.target.value)} required><option value="">Choose leave type</option>{types.map(t=><option key={t} value={t}>{t.replace("_"," ")}</option>)}</AppSelect></label>
    <label>Override days<input aria-label="Override days" value={days} onChange={e=>setDays(e.target.value)} type="number" min={0} max={365} step={0.5} placeholder="e.g. 12" required/></label>
    <button className="employee-primary" disabled={saving}>{saving?"Saving…":"Save override"}</button>
   </form>
  </div>
 </section>;
}

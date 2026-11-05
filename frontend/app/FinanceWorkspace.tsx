"use client";
import {useEffect,useState} from "react";

type Row=Record<string,any>;
type User={id:number;name:string;role:string};
const today=()=>new Date().toISOString().slice(0,10);
const currency=(n:unknown,code="USD")=>new Intl.NumberFormat("en-US",{style:"currency",currency:code}).format(Number(n||0));
export default function FinanceWorkspace({api,user}:{api:string;user:User}){
 const hr=["hr","admin","super_admin"].includes(user.role);
 const [tab,setTab]=useState<"projects"|"invoices"|"schedule">("projects");
 const [projects,setProjects]=useState<Row[]>([]);
 const [invoices,setInvoices]=useState<Row[]>([]);
 const [selected,setSelected]=useState("");
 const [billing,setBilling]=useState<Row>({recipient_type:"client",recipient_name:"",recipient_email:"",recipient_phone:"",billing_address:"",billing_day:"15",payment_terms_days:15,end_date:""});
 const [periodStart,setPeriodStart]=useState(today());
 const [periodEnd,setPeriodEnd]=useState(today());
 const [quantity,setQuantity]=useState("1");
 const [tax,setTax]=useState("0");
 const [endDate,setEndDate]=useState("");
 const [reason,setReason]=useState("");
 const [scheduleDate,setScheduleDate]=useState(today());
 const [message,setMessage]=useState("");
 const [error,setError]=useState("");
 const [busy,setBusy]=useState(false);
 const [result,setResult]=useState<Row|null>(null);
 async function call(path:string,method="GET",body?:unknown){
  const r=await fetch(api+"/finance"+path,{method,credentials:"include",headers:{"Content-Type":"application/json"},
   body:body===undefined?undefined:JSON.stringify(body)});
  const j=await r.json().catch(()=>null);
  if(!r.ok)throw Error(typeof j?.detail==="string"?j.detail:"Please check the finance details.");
  return j;
 }
 async function refresh(){
  const [p,i]=await Promise.all([call("/projects"),call("/invoices")]);setProjects(p);setInvoices(i);
 }
 useEffect(()=>{void refresh().catch(e=>setError((e as Error).message));},[api,user.id]);
 useEffect(()=>{
  const row=projects.find(p=>String(p.id)===selected);
  if(!row)return;
  const p=row.billing||{};
  setBilling({recipient_type:p.recipient_type||"client",recipient_name:p.recipient_name||row.client,
   recipient_email:p.recipient_email||"",recipient_phone:p.recipient_phone||"",billing_address:p.billing_address||"",
   billing_day:p.billing_day??15,payment_terms_days:p.payment_terms_days??15,end_date:p.end_date||""});
  setPeriodStart(row.start_date||today());setPeriodEnd(today());setEndDate(p.end_date||"");
 },[selected,projects]);
 async function save(fn:()=>Promise<any>,messageText:string){
  setError("");setMessage("");setBusy(true);
  try{const r=await fn();setResult(r);setMessage(messageText);await refresh()}
  catch(e){setError((e as Error).message)}
  finally{setBusy(false)}
 }
 const row=projects.find(p=>String(p.id)===selected);
 const field=(key:string,label:string,type="text")=><label key={key}>{label}<input type={type} value={billing[key]??""}
  onChange={e=>setBilling(v=>({...v,[key]:e.target.value}))}/></label>;
 return <div className="ops-area">
  <p className="muted">Accountant workspace: source projects, bill-to details, invoice drafts and payment tracking. Generating a draft does not send a bill.</p>
  <div className="time-tabs" role="tablist">{([["projects","Project billing"],["invoices","Invoice ledger"],["schedule","Invoice schedule"]] as const).map(([id,title])=>
   <button key={id} role="tab" aria-selected={tab===id} className={tab===id?"active":""} onClick={()=>setTab(id)}>{title}</button>)}</div>
  {error&&<p role="alert" className="error">{error}</p>}{message&&<p role="status" className="employee-success">{message}</p>}
  {tab==="projects"&&<>
   <h2>Projects available for finance</h2>
   <div className="table-wrap"><table><thead><tr><th>Project</th><th>Candidate</th><th>Client</th><th>Vendor</th><th>Rate</th><th>Status</th></tr></thead><tbody>
    {projects.map(p=><tr key={p.id}><td><button className="secondary" onClick={()=>setSelected(String(p.id))}>{p.project_number||p.name}</button></td>
    <td>{p.candidate_name||"—"}</td><td>{p.client}</td><td>{p.vendor_name||"—"}</td>
    <td>{currency(p.rate,p.currency||"USD")} / {p.rate_unit}</td><td>{p.status}{p.billing?.end_date?" · ends "+p.billing.end_date:""}</td></tr>)}
   </tbody></table></div>
   {row&&<section className="employee-surface"><h3>Billing details: {row.name}</h3>
    <p>Candidate: {row.candidate_name||"—"} · Sourced by employee #{row.sourced_by_id} · Prime vendor: {row.prime_vendor_name||"—"}</p>
    <form className="form" onSubmit={e=>{e.preventDefault();void save(()=>call("/projects/"+row.id+"/billing","PUT",{
       ...billing,billing_day:billing.billing_day===""?null:Number(billing.billing_day),
       payment_terms_days:Number(billing.payment_terms_days),end_date:billing.end_date||null}),"Billing contact and schedule updated.")}}>
     <label>Invoice recipient<select value={billing.recipient_type} onChange={e=>setBilling(v=>({...v,recipient_type:e.target.value}))}>
       <option value="client">Client</option><option value="vendor">Vendor</option><option value="candidate">Candidate</option>
      </select></label>
     {field("recipient_name","Billing recipient name")}{field("recipient_email","Invoice email","email")}
     {field("recipient_phone","Invoice phone","tel")}{field("billing_address","Billing address")}
     {field("billing_day","Monthly billing day (1–28)","number")}
     {field("payment_terms_days","Payment terms in days","number")}
     {field("end_date","Project contractual end date","date")}
     <button className="primary" disabled={busy}>Save billing configuration</button>
    </form>
    {hr&&<form className="form" onSubmit={e=>{e.preventDefault();void save(
      ()=>call("/projects/"+row.id+"/lifecycle","PUT",{active:row.status!=="active",end_date:endDate||null,reason}),
      "Project lifecycle updated. Schedules respect the end date.")}}>
      <h3>HR-only project lifecycle</h3><label>End date<input type="date" value={endDate} onChange={e=>setEndDate(e.target.value)}/></label>
      <label>Reason (required)<textarea minLength={10} value={reason} onChange={e=>setReason(e.target.value)} required/></label>
      <button className="primary" disabled={busy}>{row.status==="active"?"Schedule end / deactivate":"Reactivate project"}</button>
    </form>}
   </section>}
  </>}
  {tab==="invoices"&&<>
   <h2>Invoice ledger</h2>
   <form className="form" onSubmit={e=>{e.preventDefault();void save(()=>call("/invoices","POST",{
    project_id:Number(selected),period_start:periodStart,period_end:periodEnd,
    quantity:Number(quantity),tax_rate_pct:Number(tax),issue_date:today()}),"Invoice draft created.")}}>
    <label>Project<select value={selected} onChange={e=>setSelected(e.target.value)} required>
     <option value="">Select project</option>{projects.map(p=><option key={p.id} value={p.id}>{p.project_number} · {p.name} ({p.status})</option>)}</select></label>
    <label>Service start<input type="date" required value={periodStart} onChange={e=>setPeriodStart(e.target.value)}/></label>
    <label>Service end<input type="date" required value={periodEnd} onChange={e=>setPeriodEnd(e.target.value)}/></label>
    <label>Units billed<input type="number" min="0.01" step="0.01" required value={quantity} onChange={e=>setQuantity(e.target.value)}/></label>
    <label>Tax %<input type="number" min={0} max={100} step="0.01" value={tax} onChange={e=>setTax(e.target.value)}/></label>
    <button disabled={busy||!selected} className="primary">Create invoice draft</button>
   </form>
   <div className="table-wrap"><table><thead><tr><th>#</th><th>Project</th><th>Recipient</th><th>Period</th><th>Total</th><th>Due</th><th>Status</th><th>Actions</th></tr></thead>
    <tbody>{invoices.map(i=><tr key={i.id}><td>{i.id}</td><td>{projects.find(p=>p.id===i.project_id)?.project_number||i.project_id}</td>
     <td>{i.recipient_name} · {i.recipient_type}</td><td>{i.period_start} – {i.period_end}</td>
     <td>{currency(i.total,i.currency)}</td><td>{i.due_date}</td><td>{i.status}</td>
     <td><a href={api+"/finance/invoices/"+i.id+".pdf"} target="_blank" rel="noreferrer">PDF</a>
     {i.status==="draft"&&<button className="secondary" onClick={()=>void save(
       ()=>call("/invoices/"+i.id+"/status","POST",{status:"sent"}),"Marked sent (no email was sent).")}>Mark sent</button>}
     {["sent","overdue"].includes(i.status)&&<button className="secondary" onClick={()=>void save(
       ()=>call("/invoices/"+i.id+"/status","POST",{status:"paid"}),"Payment recorded.")}>Mark paid</button>}
     </td></tr>)}</tbody></table></div>
  </>}
  {tab==="schedule"&&<>
   <h2>Scheduled draft generation</h2>
   <p>On each configured billing day, generate draft invoices for the unbilled service period. A scheduled project end also triggers its final draft on that end date. Inactive projects never generate new invoices.</p>
   <form className="form" onSubmit={e=>{e.preventDefault();void save(
     ()=>call("/schedules/run","POST",{as_of:scheduleDate}),"Schedule evaluated. Review the generated drafts before sending.")}}>
    <label>Schedule date<input type="date" required value={scheduleDate} onChange={e=>setScheduleDate(e.target.value)}/></label>
    <button disabled={busy}>Run due invoice schedules</button></form>
   {result&&Array.isArray(result.created)&&<p>{result.created.length} draft(s) created; {result.skipped?.length||0} projects skipped.</p>}
  </>}
 </div>;
}

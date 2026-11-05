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
 const [reviews,setReviews]=useState<Row[]>([]);
 const [approvedUnits,setApprovedUnits]=useState<Record<number,string>>({});
 const [pricingMode,setPricingMode]=useState("fixed_rate");
 const [pricingValue,setPricingValue]=useState("");
 const [pricingTax,setPricingTax]=useState("0");
 const [expanded,setExpanded]=useState(false);
 const [scheduleProject,setScheduleProject]=useState("");
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
  const [p,i,r]=await Promise.all([call("/projects"),call("/invoices"),call("/reviews")]);setProjects(p);setInvoices(i);setReviews(r);
 }
 useEffect(()=>{void refresh().catch(e=>setError((e as Error).message));},[api,user.id]);
 useEffect(()=>{
  const row=projects.find(p=>String(p.id)===selected);
  if(!row)return;
  const p=row.billing||{};
  setBilling({recipient_type:p.recipient_type||"client",recipient_name:p.recipient_name||row.client,
   recipient_email:p.recipient_email||"",recipient_phone:p.recipient_phone||"",billing_address:p.billing_address||"",
   billing_day:p.billing_day??15,payment_terms_days:p.payment_terms_days??15,end_date:p.end_date||""});
  const charge=(row.charges||[]).find((x:Row)=>x.recipient_type===(p.recipient_type||"client"));
  setPricingMode(charge?.pricing_mode||"fixed_rate");
  setPricingValue(String(charge?.pricing_value??row.rate??""));
  setPricingTax(String(charge?.tax_rate_pct??0));setTax(String(charge?.tax_rate_pct??0));
  setPeriodStart(row.start_date||today());setPeriodEnd(today());setEndDate(p.end_date||"");
 },[selected,projects]);
 async function save(fn:()=>Promise<any>,messageText:string){
  setError("");setMessage("");setBusy(true);
  try{const r=await fn();setResult(r);setMessage(messageText);await refresh()}
  catch(e){setError((e as Error).message)}
  finally{setBusy(false)}
 }
 const chosen=projects.find(p=>String(p.id)===selected);
 const effectiveRate=pricingMode==="percentage"?Number(chosen?.rate||0)*Number(pricingValue||0)/100:Number(pricingValue||0);
 const estimatedTotal=effectiveRate*Number(quantity||0)*(1+Number(pricingTax||0)/100);
 const field=(key:string,label:string,type="text")=><label key={key}>{label}<input type={type} value={billing[key]??""}
  onChange={e=>setBilling(v=>({...v,[key]:e.target.value}))}/></label>;
 return <div className="ops-area finance-workspace">
  <p className="muted">Accountant workspace: source projects, bill-to details, invoice drafts and payment tracking. Generating a draft does not send a bill.</p>
  <div className="time-tabs" role="tablist">{([["projects","Project billing"],["invoices","Invoice ledger"],["schedule","Invoice schedule"]] as const).map(([id,title])=>
   <button key={id} role="tab" aria-selected={tab===id} className={tab===id?"active":""} onClick={()=>setTab(id)}>{title}</button>)}</div>
  {error&&<p role="alert" className="error">{error}</p>}{message&&<p role="status" className="employee-success">{message}</p>}
  {tab==="projects"&&<>
   <h2>Projects available for finance</h2>
   <div className="table-wrap"><table><thead><tr><th>Project</th><th>Candidate</th><th>Client</th><th>Vendor</th><th>Rate</th><th>Status</th></tr></thead><tbody>
    {projects.map(p=><tr key={p.id}><td><button className="finance-link" aria-expanded={selected===String(p.id)&&expanded} onClick={()=>{if(selected===String(p.id)){setExpanded(!expanded)}else{setSelected(String(p.id));setExpanded(true)}}}>{p.project_number||p.name} <span aria-hidden="true">{selected===String(p.id)&&expanded?"▴":"▾"}</span></button></td>
    <td>{p.candidate_name||"—"}</td><td>{p.client}</td><td>{p.vendor_name||"—"}</td>
    <td>{currency(p.rate,p.currency||"USD")} / {p.rate_unit}</td><td>{p.status}{p.billing?.end_date?" · ends "+p.billing.end_date:""}</td></tr>)}
   </tbody></table></div>
   {chosen&&expanded&&<section className="employee-surface"><div className="finance-header"><h3>Billing details: {chosen.name}</h3><button type="button" className="finance-quiet" onClick={()=>setExpanded(false)}>Collapse details ↑</button></div>
    <p>Candidate: {chosen.candidate_name||"—"} · Sourced by employee #{chosen.sourced_by_id} · Prime vendor: {chosen.prime_vendor_name||"—"}</p>
    <form className="form" onSubmit={e=>{e.preventDefault();void save(()=>call("/projects/"+chosen.id+"/billing","PUT",{
       ...billing,billing_day:billing.billing_day===""?null:Number(billing.billing_day),
       payment_terms_days:Number(billing.payment_terms_days),end_date:billing.end_date||null}),"Billing contact and schedule updated.")}}>
     <label>Invoice recipient<select value={billing.recipient_type} onChange={e=>{const type=e.target.value;setBilling(v=>({...v,recipient_type:type}));const c=(chosen?.charges||[]).find((x:Row)=>x.recipient_type===type);setPricingMode(c?.pricing_mode||"fixed_rate");setPricingValue(String(c?.pricing_value??chosen?.rate??""));setPricingTax(String(c?.tax_rate_pct??0));setTax(String(c?.tax_rate_pct??0))}}>
       <option value="client">Client</option><option value="vendor">Vendor</option><option value="candidate">Candidate</option>
      </select></label>
     {field("recipient_name","Billing recipient name")}{field("recipient_email","Invoice email","email")}
     {field("recipient_phone","Invoice phone","tel")}{field("billing_address","Billing address")}
     {field("billing_day","Monthly billing day (1–28)","number")}
     {field("payment_terms_days","Payment terms in days","number")}
     {hr&&field("end_date","Contractual project end date","date")}
     <div className="finance-actions"><button className="primary" disabled={busy}>Save billing details</button></div>
    </form>
    <section className="finance-pricing"><h4>Invoice pricing for {billing.recipient_type}</h4>
     <p className="muted">Placement rate: {currency(chosen.rate,chosen.currency)}/{chosen.rate_unit}. Billing rates are independent; nothing changes the placement contract.</p>
     <form className="form" onSubmit={e=>{e.preventDefault();void save(()=>call("/projects/"+chosen.id+"/charges","PUT",{
       recipient_type:billing.recipient_type,pricing_mode:pricingMode,pricing_value:Number(pricingValue),tax_rate_pct:Number(pricingTax)
     }),"Invoice pricing saved for "+billing.recipient_type+".")}}>
      <label>How to charge<select value={pricingMode} onChange={e=>setPricingMode(e.target.value)}><option value="fixed_rate">Custom unit rate</option><option value="percentage">Percentage of placement rate</option></select></label>
      <label>{pricingMode==="percentage"?"Percentage to charge (%)":"Invoice unit rate ("+(chosen.currency||"USD")+")"}<input type="number" min="0.01" max={pricingMode==="percentage"?"100":undefined} step="0.01" required value={pricingValue} onChange={e=>setPricingValue(e.target.value)}/></label>
      <label>Default tax (%)<input type="number" min="0" max="100" step="0.01" value={pricingTax} onChange={e=>setPricingTax(e.target.value)}/></label>
      <div className="finance-preview"><span>Effective invoicing rate</span><strong>{currency(effectiveRate,chosen.currency)} / {chosen.rate_unit}</strong></div>
      <div className="finance-actions"><button className="primary" disabled={busy}>Save invoice pricing</button></div>
     </form>
    </section>
    {hr&&<form className="form" onSubmit={e=>{e.preventDefault();void save(
      ()=>call("/projects/"+chosen.id+"/lifecycle","PUT",{active:chosen.status!=="active",end_date:endDate||null,reason}),
      "Project lifecycle updated. Schedules respect the end date.")}}>
      <h3>HR-only project status</h3><p className="muted">A future end date schedules the last billing day; leaving it empty deactivates the project now.</p><label>End date<input type="date" value={endDate} onChange={e=>setEndDate(e.target.value)}/></label>
      <label>Reason (required)<textarea minLength={10} value={reason} onChange={e=>setReason(e.target.value)} required/></label>
      <button className="primary" disabled={busy}>{chosen.status==="active"?(endDate&&endDate>today()?"Set future project end date":"Deactivate project immediately"):"Reactivate inactive project"}</button>
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
    <label>Project start date<input type="date" required value={periodStart} onChange={e=>setPeriodStart(e.target.value)}/></label>
    <label>Project end date<input type="date" required value={periodEnd} onChange={e=>setPeriodEnd(e.target.value)}/></label>
    <label>Billable units (verified hours, days or milestones)<input type="number" min="0.01" step="0.01" required value={quantity} onChange={e=>setQuantity(e.target.value)}/></label>
    <label>Tax % (defaults from saved pricing)<input type="number" min={0} max={100} step="0.01" value={tax} onChange={e=>setTax(e.target.value)}/></label>
    {chosen&&<div className="finance-preview"><span>Estimated total · {chosen.currency}</span><strong>{currency(estimatedTotal,chosen.currency)}</strong><small>Rate {currency(effectiveRate,chosen.currency)} × {quantity||0} units, including tax. Review before saving.</small></div>}
    <div className="finance-actions"><button disabled={busy||!selected} className="primary">Create invoice draft</button></div>
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
     ()=>call("/schedules/run","POST",{as_of:scheduleDate,project_id:scheduleProject?Number(scheduleProject):null}),"Schedule evaluated. Review the generated drafts before sending.")}}>
    <label>Project to process<select value={scheduleProject} onChange={e=>setScheduleProject(e.target.value)}><option value="">All active projects</option>{projects.map(p=><option value={p.id} key={p.id}>{p.project_number} · {p.name}</option>)}</select></label>
    <label>Schedule date<input type="date" required value={scheduleDate} onChange={e=>setScheduleDate(e.target.value)}/></label>
    <div className="finance-actions"><button disabled={busy}>Generate due billing review tasks</button></div></form>
   <div className="table-wrap"><table><thead><tr><th>Project</th><th>Recipient & email</th><th>Invoice rate</th><th>Billing day</th><th>End date</th><th>Status</th></tr></thead><tbody>{projects.filter(p=>!scheduleProject||String(p.id)===scheduleProject).map(p=>{
    const charge=(p.charges||[]).find((c:Row)=>c.recipient_type===p.billing?.recipient_type);
    const rate=charge?.pricing_mode==="percentage"?Number(p.rate)*Number(charge.pricing_value)/100:Number(charge?.pricing_value??p.rate);
    return <tr key={p.id}><td>{p.project_number} · {p.name}</td><td>{p.billing?.recipient_name||"Not configured"}<small>{p.billing?.recipient_email||"No email"}</small></td><td>{currency(rate,p.currency)}/{p.rate_unit}</td><td>{p.billing?.billing_day||"Off"}</td><td>{p.billing?.end_date||"—"}</td><td>{p.status}</td></tr>})}</tbody></table></div>
   {result&&Array.isArray(result.tasks_created)&&<p>{result.tasks_created.length} billing review(s) queued; {result.skipped?.length||0} projects skipped. No invoices sent.</p>}
   <h3>Due billing reviews</h3>
   <div className="ops-table">{reviews.filter(r=>!scheduleProject||String(r.project_id)===scheduleProject).map(r=><div className="ops-row" key={r.id}>
     <strong>Task #{r.id} · Project #{r.project_id} · {r.status}</strong>
     <span>Service period {r.period_start} to {r.period_end}</span>
     {r.status==="needs_units"&&<div className="form">
       <label>Approved billable units<input type="number" min="0.01" step="0.01" placeholder="Enter verified hours, days or milestone quantity"
         aria-label={"Approved billable units for task "+r.id}
         value={approvedUnits[r.id]||""} onChange={e=>setApprovedUnits(v=>({...v,[r.id]:e.target.value}))}/></label>
       <button className="primary" disabled={!approvedUnits[r.id]||Number(approvedUnits[r.id])<=0||busy}
        onClick={()=>void save(()=>call("/reviews/"+r.id+"/invoice","POST",{
          quantity:Number(approvedUnits[r.id]),tax_rate_pct:Number(tax)}),"Verified billing draft prepared for review.")}>Create reviewed invoice draft</button>
     </div>}
   </div>)}</div>
  </>}
 </div>;
}

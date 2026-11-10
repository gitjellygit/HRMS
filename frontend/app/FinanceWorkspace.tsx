"use client";
import {useEffect,useRef,useState} from "react";
import {BadgeCheck,ChevronDown,ChevronUp,X} from "lucide-react";
import {explainError} from "./formErrors";

type Row=Record<string,any>;
type User={id:number;name:string;role:string};
const today=()=>new Date().toISOString().slice(0,10);
const currency=(n:unknown,code="USD")=>new Intl.NumberFormat("en-US",{style:"currency",currency:code}).format(Number(n||0));
const initialBilling={recipient_type:"client",recipient_name:"",recipient_email:"",recipient_phone:"",billing_address:"",
 billing_day:"15",payment_terms_days:"15",billing_frequency:"monthly",rate_unit:"hour",invoice_rate:"",tax_rate_pct:"0"};

export default function FinanceWorkspace({api,user}:{api:string;user:User}){
 const [tab,setTab]=useState<"projects"|"invoices"|"schedule">("projects");
 const [projects,setProjects]=useState<Row[]>([]);
 const [invoices,setInvoices]=useState<Row[]>([]);
 const [reviews,setReviews]=useState<Row[]>([]);
 const [approvedUnits,setApprovedUnits]=useState<Record<number,string>>({});
 const [expandedId,setExpandedId]=useState<number|null>(null);
 const [selected,setSelected]=useState("");
 const [scheduleProject,setScheduleProject]=useState("");
 const [billing,setBilling]=useState<Row>(initialBilling);
 const [periodStart,setPeriodStart]=useState(today());
 const [periodEnd,setPeriodEnd]=useState(today());
 const [quantity,setQuantity]=useState("1");
 const [replacementInvoiceId,setReplacementInvoiceId]=useState<number|null>(null);
 const [tax,setTax]=useState("0");
 const [scheduleDate,setScheduleDate]=useState(today());
 const [notice,setNotice]=useState<{kind:"success"|"error";text:string}|null>(null);
 const [busy,setBusy]=useState(false);
 const [result,setResult]=useState<Row|null>(null);
 const successRef=useRef<HTMLDivElement|null>(null);
 async function call(path:string,method="GET",body?:unknown){
  const response=await fetch(api+"/finance"+path,{method,credentials:"include",
   headers:{"Content-Type":"application/json"},body:body===undefined?undefined:JSON.stringify(body)});
  const data=await response.json().catch(()=>null);
  if(!response.ok)throw Error(explainError(data,response.status));
  return data;
 }
 async function refresh(){
  const [p,i,r]=await Promise.all([call("/projects"),call("/invoices"),call("/reviews")]);
  setProjects(p);setInvoices(i);setReviews(r);
 }
 useEffect(()=>{void refresh().catch(e=>setNotice({kind:"error",text:(e as Error).message}));},[api,user.id]);
 function openProject(p:Row){
  if(expandedId===p.id){setExpandedId(null);return}
  const b=p.billing||{};
  const charge=(p.charges||[]).find((x:Row)=>x.recipient_type===(b.recipient_type||"client"));
  setBilling({
   recipient_type:b.recipient_type||"client",
   recipient_name:b.recipient_name||p.client||"",
   recipient_email:b.recipient_email||"",
   recipient_phone:b.recipient_phone||"",
   billing_address:b.billing_address||"",
   billing_day:String(b.billing_day??15),
   payment_terms_days:String(b.payment_terms_days??15),
   billing_frequency:b.billing_frequency||"monthly",
   rate_unit:charge?.rate_unit||p.rate_unit||"hour",
   invoice_rate:String(charge?.pricing_mode==="percentage"?Number(p.rate||0)*Number(charge.pricing_value)/100:charge?.pricing_value??p.rate??""),
   tax_rate_pct:String(charge?.tax_rate_pct??0)
  });
  setExpandedId(p.id);setSelected(String(p.id));setTax(String(charge?.tax_rate_pct??0));setNotice(null);
 }
 const chosen=projects.find(p=>String(p.id)===selected);
 const effectiveRate=Number(billing.invoice_rate||chosen?.rate||0);
 const estimatedTotal=effectiveRate*Number(quantity||0)*(1+Number(tax||0)/100);
 const update=(key:string,value:string)=>setBilling(x=>({...x,[key]:value}));
 const field=(key:string,label:string,type="text",props:Record<string,any>={})=>
  <label key={key}>{label}<input type={type} value={billing[key]??""} onChange={e=>update(key,e.target.value)} {...props}/></label>;
 async function save(fn:()=>Promise<Row>,message:string){
  if(busy)return;
  setBusy(true);setNotice(null);
  try{
   const updated=await fn();setResult(updated);
   await refresh();
   setNotice({kind:"success",text:message});
   // Unlike an inline success message, the fixed feedback stays visible while
   // the user scrolls through long project and invoice tables.
   requestAnimationFrame(()=>successRef.current?.focus({preventScroll:true}));
  }catch(e){setNotice({kind:"error",text:(e as Error).message})}
  finally{setBusy(false)}
 }
 async function saveConfiguration(project:Row){
  const payload={
   recipient_type:billing.recipient_type||"client",
   recipient_name:String(billing.recipient_name||"").trim(),
   recipient_email:String(billing.recipient_email||"").trim()||null,
   recipient_phone:String(billing.recipient_phone||"").trim(),
   billing_address:String(billing.billing_address||"").trim(),
   billing_day:Number(billing.billing_day),payment_terms_days:Number(billing.payment_terms_days),
   billing_frequency:billing.billing_frequency,rate_unit:billing.rate_unit,
   invoice_rate:Number(billing.invoice_rate),tax_rate_pct:Number(billing.tax_rate_pct)
  };
  if(payload.recipient_name.length<2){setNotice({kind:"error",text:"Enter the billing recipient name."});return}
  await save(()=>call("/projects/"+project.id+"/configuration","PUT",payload),
   "Billing details, invoice amount and schedule saved for "+(project.project_number||project.name)+".");
  setTax(String(billing.tax_rate_pct));
 }
 return <div className="ops-area finance-workspace finance-premium">
  <p className="muted">Configure billing, prepare invoice drafts and track payments. Creating an invoice does not send an email.</p>
  <div className="time-tabs" role="tablist">{([["projects","Project billing"],["invoices","Invoice ledger"],["schedule","Invoice schedule"]] as const).map(([id,title])=>
   <button key={id} role="tab" aria-selected={tab===id} className={tab===id?"active":""} onClick={()=>{setTab(id);setNotice(null);void refresh().catch(e=>setNotice({kind:"error",text:(e as Error).message}))}}>{title}</button>)}</div>
  {notice&&<div ref={successRef} role={notice.kind==="success"?"status":"alert"} tabIndex={-1}
   className={"finance-toast "+(notice.kind==="success"?"is-success":"is-error")}>
    <BadgeCheck size={19}/><span>{notice.text}</span>
    <button type="button" title="Dismiss" aria-label="Dismiss notification" onClick={()=>setNotice(null)}><X size={17}/></button>
   </div>}
  {tab==="projects"&&<>
   <div className="finance-header"><div><h2>Project billing</h2><p className="muted">Choose a project to set its recipient, invoice rate and billing cycle.</p></div></div>
   <div className="table-wrap"><table className="finance-project-table">
    <thead><tr><th>Project</th><th>Candidate</th><th>Client</th><th>Vendor</th><th>Placement rate</th><th>Status</th></tr></thead>
    <tbody>{projects.flatMap(p=>{
     const open=expandedId===p.id;
     const base=<tr key={"project-"+p.id} className={open?"finance-selected-row":""}>
      <td><button className="finance-link" aria-expanded={open} onClick={()=>openProject(p)}>
       {p.project_number||p.name} {open?<ChevronUp size={14}/>:<ChevronDown size={14}/>}</button>
       <small>{p.name}</small></td>
      <td>{p.candidate_name||"—"}</td><td>{p.client}</td><td>{p.vendor_name||"—"}</td>
      <td>{currency(p.rate,p.currency||"USD")} / {p.rate_unit||"hour"}</td>
      <td><span className={"pill "+p.status}>{p.status}</span></td>
     </tr>;
     if(!open)return [base];
     const details=<tr key={"billing-"+p.id} className="finance-expanded-row"><td colSpan={6}>
      <div className="finance-billing-card">
       <div className="finance-header"><div><h3>Billing settings · {p.project_number||p.name}</h3>
        <p className="muted">Change the invoice settings without changing the placement contract.</p></div>
        <button type="button" className="finance-quiet" onClick={()=>setExpandedId(null)}>Collapse <ChevronUp size={14}/></button></div>
       {p.status!=="active"&&<p className="muted">This project is inactive. Reactivate it from the Projects tab to edit billing.</p>}
       <form className="finance-settings-form" onSubmit={e=>{e.preventDefault();void saveConfiguration(p)}}>
        <fieldset disabled={busy||p.status!=="active"}>
         <div className="finance-form-section"><h4>Billing recipient</h4><div className="finance-field-grid">
          {field("recipient_name","Billing recipient name","text",{required:true,minLength:2})}
          {field("recipient_email","Billing email","email")}
          {field("recipient_phone","Phone number","tel")}
          <label className="finance-wide">Billing address<textarea rows={2} value={billing.billing_address||""} onChange={e=>update("billing_address",e.target.value)}/></label>
         </div></div>
         <div className="finance-form-section"><h4>Invoice amount and schedule</h4>
          <p className="muted">Placement contract: {currency(p.rate,p.currency||"USD")} per {p.rate_unit||"hour"}. The invoice rate below is independent.</p>
          <div className="finance-field-grid">
           <label>Bill every<select value={billing.billing_frequency} onChange={e=>{update("billing_frequency",e.target.value);setBilling(v=>({...v,billing_frequency:e.target.value,billing_day:e.target.value==="monthly"?"15":"1"}))}}>
            <option value="weekly">Weekly</option><option value="biweekly">Every two weeks</option><option value="monthly">Monthly</option>
           </select></label>
           <label>{billing.billing_frequency==="monthly"?"Billing day of month (1–28)":"Billing weekday"}
            {billing.billing_frequency==="monthly"?<input type="number" min="1" max="28" required
             value={billing.billing_day} onChange={e=>update("billing_day",e.target.value)}/>:
             <select value={billing.billing_day} onChange={e=>update("billing_day",e.target.value)}>
              {["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"].map((day,i)=>
                <option key={day} value={i+1}>{day}</option>)}
             </select>}</label>
           <label>Invoice currency<input value={p.currency||"USD"} disabled readOnly/></label>
           <label>Invoice rate basis<select value={billing.rate_unit} onChange={e=>update("rate_unit",e.target.value)}>
            <option value="hour">Per hour</option><option value="day">Per day</option><option value="week">Per week</option>
            <option value="month">Per month</option><option value="project">Per project</option></select></label>
           {field("invoice_rate","Invoice rate ("+(p.currency||"USD")+")","number",{required:true,min:"0.01",step:"0.01"})}
           {field("tax_rate_pct","Tax (%)","number",{required:true,min:"0",max:"100",step:"0.01"})}
           {field("payment_terms_days","Net payment terms (days)","number",{required:true,min:"0",max:"180"})}
          </div></div>
         <div className="finance-settings-footer"><span className="finance-rate-summary">Invoice rate: <strong>{currency(billing.invoice_rate,p.currency||"USD")} / {billing.rate_unit}</strong> · Tax {billing.tax_rate_pct||0}%</span>
          <button className="primary" type="submit" disabled={busy}>{busy?"Saving…":"Save billing settings"}</button>
         </div>
        </fieldset>
       </form>
      </div>
     </td></tr>;
     return [base,details];
    })}</tbody>
   </table></div>
  </>}
  {tab==="invoices"&&<>
   <h2>Invoice ledger</h2>
   <form className="form" onSubmit={e=>{e.preventDefault();
     if(!selected){setNotice({kind:"error",text:"Project: choose a project before creating an invoice."});return}
     if(periodEnd<periodStart){setNotice({kind:"error",text:"Billing period ends: choose a date on or after the billing period start."});return}
     if(chosen?.start_date&&periodStart<chosen.start_date){setNotice({kind:"error",text:"Billing period starts: cannot be earlier than the project's start date ("+chosen.start_date+")."});return}
     if(!chosen?.billing?.recipient_name){setNotice({kind:"error",text:"Billing recipient: open Project billing and save the recipient details first."});return}
     if(!Number.isFinite(Number(quantity))||Number(quantity)<=0){setNotice({kind:"error",text:"Verified billable quantity: enter a positive number."});return}
     void save(async()=>{const row=await call("/invoices","POST",{
    project_id:Number(selected),period_start:periodStart,period_end:periodEnd,
    quantity:Number(quantity),tax_rate_pct:Number(tax),issue_date:today(),
    replaces_invoice_id:replacementInvoiceId});setReplacementInvoiceId(null);return row},
    replacementInvoiceId?"Replacement invoice created with an audit link to the voided invoice.":"Invoice draft created successfully.")}}>
    <label>Project<select value={selected} onChange={e=>{setSelected(e.target.value);setReplacementInvoiceId(null);const p=projects.find(x=>String(x.id)===e.target.value);
      setPeriodStart(p?.start_date||today());setPeriodEnd(today());setTax(String(p?.charges?.find((c:Row)=>c.recipient_type===(p.billing?.recipient_type||"client"))?.tax_rate_pct??0))}} required>
     <option value="">Select project</option>{projects.map(p=><option key={p.id} value={p.id}>{p.project_number} · {p.name} ({p.status})</option>)}</select></label>
    {replacementInvoiceId&&<p className="field-help">Replacing voided invoice #{replacementInvoiceId}. The replacement keeps the same project and service period. Verify the quantity and tax before creating it.</p>}
    <label>Billing period starts<input type="date" required value={periodStart} onChange={e=>setPeriodStart(e.target.value)}/></label>
    <label>Billing period ends<input type="date" required min={periodStart} aria-invalid={periodEnd<periodStart} value={periodEnd} onChange={e=>setPeriodEnd(e.target.value)}/></label>
    <label>Verified billable quantity<input type="number" min="0.01" step="0.01" required value={quantity} onChange={e=>setQuantity(e.target.value)}/></label>
    <label>Tax (%)<input type="number" min={0} max={100} step="0.01" value={tax} onChange={e=>setTax(e.target.value)}/></label>
    {chosen&&<div className="finance-preview"><span>Estimated total · {chosen.currency}</span>
      <strong>{currency((Number(chosen.charges?.find((c:Row)=>c.recipient_type===(chosen.billing?.recipient_type||"client"))?.pricing_value??chosen.rate)||0)*Number(quantity||0)*(1+Number(tax||0)/100),chosen.currency||"USD")}</strong>
      <small>The verified quantity must match the invoice rate basis. Review the billable period and hours before creating the draft.</small></div>}
    <div className="finance-actions"><button disabled={busy||!selected} className="primary">{replacementInvoiceId?"Create replacement invoice":"Create invoice draft"}</button>
      {replacementInvoiceId&&<button type="button" className="secondary" onClick={()=>setReplacementInvoiceId(null)}>Cancel replacement</button>}</div>
   </form>
   <div className="table-wrap"><table><thead><tr><th>#</th><th>Project</th><th>Bill to</th><th>Period</th><th>Total</th><th>Due</th><th>Status</th><th>Actions</th></tr></thead>
    <tbody>{invoices.map(i=><tr key={i.id}><td>{i.id}</td><td>{projects.find(p=>p.id===i.project_id)?.project_number||i.project_id}</td>
     <td>{i.recipient_name}</td><td>{i.period_start} – {i.period_end}</td>
     <td>{currency(i.total,i.currency)}</td><td>{i.due_date}</td><td>{i.status}</td>
     <td><a href={api+"/finance/invoices/"+i.id+".pdf"} target="_blank" rel="noreferrer">PDF</a>{" "}
     {i.status==="draft"&&<button className="secondary" disabled={busy} onClick={()=>void save(
       ()=>call("/invoices/"+i.id+"/status","POST",{status:"sent"}),"Invoice marked sent. No email was sent automatically.")}>Mark sent</button>}
     {["sent","overdue"].includes(i.status)&&<button className="secondary" disabled={busy} onClick={()=>void save(
       ()=>call("/invoices/"+i.id+"/status","POST",{status:"paid"}),"Payment recorded.")}>Mark paid</button>}
     {["draft","sent","overdue"].includes(i.status)&&<button className="secondary" disabled={busy}
       onClick={()=>{const reason=window.prompt("Why is this invoice being voided? Provide at least 10 characters.");
        if(reason?.trim()&&reason.trim().length>=10)void save(
         ()=>call("/invoices/"+i.id+"/status","POST",{status:"void",reference:reason.trim()}),
         "Invoice voided. Create a replacement to restore the billing period.");
        else if(reason!==null)setNotice({kind:"error",text:"Explain the reason for voiding the invoice (10+ characters)."});}}>Void invoice</button>}
     {i.stored_status==="void"&&<button className="secondary" disabled={busy}
       onClick={()=>{setSelected(String(i.project_id));setPeriodStart(i.period_start);setPeriodEnd(i.period_end);
        setQuantity(String(i.quantity));setTax(String(i.tax_rate_pct));setReplacementInvoiceId(i.id);
        setNotice({kind:"success",text:"Preparing replacement for invoice #"+i.id+". Verify the quantities and create the new draft."});}}>
       Prepare replacement</button>}
     </td></tr>)}</tbody></table></div>
  </>}
  {tab==="schedule"&&<>
   <h2>Invoice schedule</h2><p className="muted">Generate review tasks on the saved billing day. Weekly and biweekly billing need verified billable units before invoicing. Inactive projects are excluded.</p>
   <form className="form" onSubmit={e=>{e.preventDefault();void save(
    ()=>call("/schedules/run","POST",{as_of:scheduleDate,project_id:scheduleProject?Number(scheduleProject):null}),
    "Schedule checked. Review generated billing tasks; no invoices were sent.")}}>
    <label>Projects<select value={scheduleProject} onChange={e=>setScheduleProject(e.target.value)}>
      <option value="">All active projects</option>{projects.map(p=><option key={p.id} value={p.id}>{p.project_number} · {p.name}</option>)}</select></label>
    <label>Schedule date<input type="date" required value={scheduleDate} onChange={e=>setScheduleDate(e.target.value)}/></label>
    <div className="finance-actions"><button disabled={busy} className="primary">Check due billing tasks</button></div>
   </form>
   <div className="table-wrap"><table><thead><tr><th>Project</th><th>Recipient & email</th><th>Invoice rate</th><th>Billing cycle</th><th>Payment terms</th><th>Status</th></tr></thead>
    <tbody>{projects.filter(p=>!scheduleProject||String(p.id)===scheduleProject).map(p=>{
      const charge=(p.charges||[]).find((c:Row)=>c.recipient_type===(p.billing?.recipient_type||"client"));
      const rate=charge?.pricing_mode==="percentage"?Number(p.rate)*Number(charge.pricing_value)/100:Number(charge?.pricing_value??p.rate);
      return <tr key={p.id}><td>{p.project_number} · {p.name}</td>
       <td>{p.billing?.recipient_name||"Not configured"}<small>{p.billing?.recipient_email||"No email"}</small></td>
       <td>{currency(rate,p.currency)}/{charge?.rate_unit||p.rate_unit}</td>
       <td>{p.billing?.billing_frequency||"Monthly"} · day {p.billing?.billing_day||"—"}</td>
       <td>Net {p.billing?.payment_terms_days??15}</td><td>{p.status}</td></tr>})}</tbody></table></div>
   {result&&Array.isArray(result.tasks_created)&&<p>{result.tasks_created.length} review task(s) created; {result.skipped?.length||0} skipped. No invoices sent.</p>}
   <h3>Due billing reviews</h3><div className="ops-table">
    {reviews.filter(r=>!scheduleProject||String(r.project_id)===scheduleProject).map(r=><div className="ops-row" key={r.id}>
     <strong>Task #{r.id} · Project #{r.project_id} · {r.status}</strong>
     <span>Service period {r.period_start} to {r.period_end}</span>
     {r.status==="needs_units"&&<div className="form">
      <label>Approved billable units<input type="number" min="0.01" step="0.01"
       aria-label={"Approved billable units for task "+r.id} placeholder="Verified quantity"
       value={approvedUnits[r.id]||""} onChange={e=>setApprovedUnits(v=>({...v,[r.id]:e.target.value}))}/></label>
      <button className="primary" disabled={!approvedUnits[r.id]||Number(approvedUnits[r.id])<=0||busy}
       onClick={()=>void save(()=>call("/reviews/"+r.id+"/invoice","POST",{
         quantity:Number(approvedUnits[r.id])}),"Reviewed invoice draft created using the configured project tax rate.")}>Create reviewed invoice draft</button>
     </div>}
    </div>)}
   </div>
  </>}
 </div>;
}

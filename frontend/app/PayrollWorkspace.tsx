"use client";
import {useEffect,useState} from "react";
import {BadgeIndianRupee,ReceiptText,FileDown,ShieldCheck} from "lucide-react";
import FeedbackMotion from "./FeedbackMotion";
type Row=Record<string,any>;
type Tab="salary"|"runs"|"payslips"|"expenses";
const period=()=>new Date().toISOString().slice(0,7);
const today=()=>new Date().toISOString().slice(0,10);
const cash=(n:unknown)=>"₹"+Number(n||0).toLocaleString("en-IN",{minimumFractionDigits:2,maximumFractionDigits:2});
export default function PayrollWorkspace({api,user}:{api:string;user:{id:number;role:string}}){
 const hr=["admin","super_admin","hr"].includes(user.role),finance=hr||user.role==="accountant";
 const [tab,setTab]=useState<Tab>(finance?"salary":"payslips");
 const [employees,setEmployees]=useState<Row[]>([]);
 const [structures,setStructures]=useState<Row[]>([]);
 const [rules,setRules]=useState<Row[]>([]);
 const [runs,setRuns]=useState<Row[]>([]);
 const [slips,setSlips]=useState<Row[]>([]);
 const [expenses,setExpenses]=useState<Row[]>([]);
 const [claims,setClaims]=useState<Row[]>([]);
 const [chosen,setChosen]=useState("");
 const [components,setComponents]=useState<Row[]>([]);
 const [component,setComponent]=useState({code:"",title:"",kind:"earning",amount:"",effective_from:today(),active:true});
 const [salary,setSalary]=useState<Row>({basic:"",hra:"",allowances:"",other_deductions:"",effective_from:today()});
 const [statutory,setStatutory]=useState<Row>({pf_employee_monthly:"",esi_employee_monthly:"",professional_tax_monthly:"",
  tds_monthly:"",gratuity_employer_provision:"",effective_from:today()});
 const [month,setMonth]=useState(period());
 const [runDetail,setRunDetail]=useState<Row|null>(null);
 const [claim,setClaim]=useState({title:"",category:"travel",amount:"",incurred_on:today(),note:""});
 const [receipt,setReceipt]=useState<File|null>(null);
 const [message,setMessage]=useState("");
 const [error,setError]=useState("");const [fieldError,setFieldError]=useState("");
 const [busy,setBusy]=useState(false);
 async function call(path:string,method="GET",body?:unknown){
  const r=await fetch(api+"/payroll"+path,{method,credentials:"include",headers:{"Content-Type":"application/json"},
   body:body===undefined?undefined:JSON.stringify(body)});
  const j=await r.json().catch(()=>({}));
  if(!r.ok){const d=j.detail;throw Object.assign(new Error(typeof d==="string"?d:d?.message||"Request could not be processed."),{field:d?.field,employees:d?.employees})}
  return j;
 }
 async function refresh(){
  const get=(path:string)=>call(path).catch(()=>[]);
  const [a,b,c,d,e,f,g]=await Promise.all([
   finance?fetch(api+"/employees",{credentials:"include"}).then(r=>r.ok?r.json():[]):Promise.resolve([]),
   finance?get("/structures"):Promise.resolve([]),finance?get("/statutory"):Promise.resolve([]),
   finance?get("/runs"):Promise.resolve([]),get("/my-payslips"),get("/expenses"),
   finance?get("/expenses?scope=all"):Promise.resolve([])]);
  setEmployees(a);setStructures(b);setRules(c);setRuns(d);setSlips(e);setExpenses(f);setClaims(g);
 }
 useEffect(()=>{void refresh()},[api,user.id]);
 useEffect(()=>{
  const p=structures.find(s=>String(s.employee_id)===chosen),t=rules.find(s=>String(s.employee_id)===chosen);
  setSalary(p?{...p}:{basic:"",hra:"",allowances:"",other_deductions:"",effective_from:today()});
  setStatutory(t?{...t}:{pf_employee_monthly:"",esi_employee_monthly:"",professional_tax_monthly:"",tds_monthly:"",
    gratuity_employer_provision:"",effective_from:today()});
 },[chosen,structures,rules]);
 useEffect(()=>{
   if(!chosen){setComponents([]);return}
   void call("/components?employee_id="+chosen).then(setComponents).catch(()=>setComponents([]));
 },[chosen,api]);
 function clear(){setError("");setMessage("");setFieldError("")}
 async function submit(fn:()=>Promise<unknown>,success:string){
  clear();setBusy(true);
  try{await fn();setMessage(success);await refresh()}catch(e){
   const err=e as Error&{field?:string;employees?:Row[]};
   setError(err.message+(err.employees?.length?" "+err.employees.slice(0,4).map(x=>x.employee_name+": "+x.message).join("; "):""));
   setFieldError(err.field||"");
  }finally{setBusy(false)}
 }
 const salaryFields=[["basic","Basic salary"],["hra","HRA"],["allowances","Other allowances"],["other_deductions","Other deductions"]] as const;
 const statutoryFields=[["pf_employee_monthly","PF employee"],["esi_employee_monthly","ESI employee"],
  ["professional_tax_monthly","Professional Tax"],["tds_monthly","TDS"],["gratuity_employer_provision","Gratuity (employer provision)"]] as const;
 return <div className="ops-area">
  <p className="ops-intro">Confidential salary and expense workflows. Published payslips are accessible only to the employee and authorized payroll staff.</p>
  <div className="time-tabs" role="tablist" aria-label="Payroll sections">
   {(finance?[["salary","Salary & statutory"],["runs","Payroll runs"],["payslips","My payslips"],["expenses","Expenses"]]:
    [["payslips","My payslips"],["expenses","Expenses"]]).map(([id,title])=><button key={id} role="tab"
    className={tab===id?"active":""} aria-selected={tab===id} onClick={()=>{setTab(id as Tab);clear()}}>{title}</button>)}
  </div>
  {error&&<div className="time-form-error" role="alert">{error}</div>}
  {message&&<FeedbackMotion type="success" compact message={message}/>}
  {busy&&<FeedbackMotion type="loading" compact message="Processing…"/>}
  {tab==="salary"&&finance&&<div className="ops-columns">
   <section className="employee-surface"><h3>Monthly salary structure</h3><p className="field-help">All amounts in INR per month. Effective dates are recorded for HR review.</p>
    <label className="ops-label">Employee<select value={chosen} onChange={e=>setChosen(e.target.value)}><option value="">Select employee</option>{employees.map(e=><option key={e.id} value={e.id}>{e.name} · {e.department}</option>)}</select></label>
    <form className="ops-form" onSubmit={e=>{e.preventDefault();if(!chosen){setError("Select the employee.");setFieldError("employee_id");return}
     void submit(()=>call("/structures","PUT",{...salary,employee_id:Number(chosen)}),"Salary structure saved.")}}>
     {salaryFields.map(([key,title])=><label key={key}>{title}<input type="number" min="0" step=".01" required
      aria-invalid={fieldError===key} value={salary[key]??""} onChange={e=>setSalary(v=>({...v,[key]:e.target.value}))}/></label>)}
     <label>Effective from<input type="date" required value={salary.effective_from||today()} onChange={e=>setSalary(v=>({...v,effective_from:e.target.value}))}/></label>
     <button className="employee-primary" disabled={!chosen||busy}>Save salary</button>
    </form></section>
   <section className="employee-surface"><h3>Reviewed statutory deductions</h3><p className="field-help">Enter employee-specific validated monthly amounts. This system does not choose tax brackets automatically.</p>
    <form className="ops-form" onSubmit={e=>{e.preventDefault();void submit(()=>call("/statutory","PUT",{...statutory,employee_id:Number(chosen)}),"Statutory configuration saved.")}}>
     {statutoryFields.map(([key,title])=><label key={key}>{title}<input type="number" min="0" step=".01" required value={statutory[key]??""}
     onChange={e=>setStatutory(v=>({...v,[key]:e.target.value}))}/></label>)}
     <label>Effective from<input type="date" required value={statutory.effective_from||today()}
      onChange={e=>setStatutory(v=>({...v,effective_from:e.target.value}))}/></label>
     <button className="employee-primary" disabled={!chosen||busy}>Save statutory amounts</button>
    </form></section>
   {hr&&<section className="employee-surface"><h3>Additional earnings and deductions</h3>
    <p className="field-help">Add custom monthly salary components. They appear in payroll calculations, published payslips and new offers using the salary breakdown placeholder.</p>
    <form className="ops-form" onSubmit={e=>{e.preventDefault();if(!chosen){setError("Select an employee first.");return}
      void submit(async()=>{await call("/components","PUT",{...component,employee_id:Number(chosen),amount:Number(component.amount)});
        setComponents(await call("/components?employee_id="+chosen));
      },"Salary component saved.")}}>
     <label>Unique code<input placeholder="shift_bonus" pattern="[a-z][a-z0-9_]{1,34}" required value={component.code} onChange={e=>setComponent(v=>({...v,code:e.target.value}))}/></label>
     <label>Display label<input placeholder="Shift allowance" minLength={2} required value={component.title} onChange={e=>setComponent(v=>({...v,title:e.target.value}))}/></label>
     <label>Item type<select value={component.kind} onChange={e=>setComponent(v=>({...v,kind:e.target.value}))}><option value="earning">Earning / allowance / bonus</option><option value="deduction">Deduction / tax adjustment</option></select></label>
     <label>Monthly amount (INR)<input type="number" min="0" step=".01" required value={component.amount} onChange={e=>setComponent(v=>({...v,amount:e.target.value}))}/></label>
     <label>Effective date<input type="date" required value={component.effective_from} onChange={e=>setComponent(v=>({...v,effective_from:e.target.value}))}/></label>
     <label className="ops-check"><input type="checkbox" checked={component.active} onChange={e=>setComponent(v=>({...v,active:e.target.checked}))}/>Active item</label>
     <button className="employee-primary" disabled={!chosen||busy}>Save salary item</button>
    </form>
    <div className="ops-table">{components.map(c=><div className="ops-row" key={c.code}>
      <strong>{c.title}</strong><span>{c.code} · {c.kind} · {cash(c.amount)} · {c.active?"active":"inactive"}</span>
      <button type="button" className="employee-cancel" onClick={()=>setComponent({code:c.code,title:c.title,kind:c.kind,amount:String(c.amount),effective_from:c.effective_from,active:c.active})}>Edit</button>
    </div>)}{!components.length&&<p className="muted">No additional salary items configured.</p>}</div>
   </section>}
  </div>}
  {tab==="runs"&&finance&&<section className="employee-surface">
   <h3>Monthly payroll processing</h3><p className="field-help">Draft → separate HR approver → publish payslips. No funds or statutory returns are transferred.</p>
   <div className="ops-inline"><label>Payroll period<input type="month" value={month} onChange={e=>setMonth(e.target.value)}/></label>
    <button className="employee-primary" disabled={busy} onClick={()=>void submit(()=>call("/runs","POST",{period:month}),"Payroll draft calculated.")}>Calculate draft</button></div>
   <div className="ops-table">{runs.map(r=><div className="ops-row" key={r.id}><strong>{r.period}</strong><span>{r.status}</span>
    <button className="employee-cancel" onClick={()=>void call("/runs/"+r.id).then(setRunDetail).catch(e=>setError(e.message))}>Review</button>
    {r.status==="draft"&&hr&&<button className="employee-primary" disabled={busy} onClick={()=>void submit(()=>call("/runs/"+r.id+"/approve","POST"),"Payroll approved.")}>Approve</button>}
    {r.status==="approved"&&hr&&<button className="employee-primary" disabled={busy} onClick={()=>void submit(()=>call("/runs/"+r.id+"/publish","POST"),"Payslips published.")}>Publish</button>}
   </div>)}</div>
   {runDetail&&<div className="ops-breakdown"><h4>Run {runDetail.period} · {runDetail.status}</h4><p>Gross {cash(runDetail.gross_total)} · Net {cash(runDetail.net_total)} · {runDetail.exceptions} attendance exceptions</p>
    <div className="table-wrap"><table><thead><tr><th>Employee</th><th>Gross</th><th>LOP days</th><th>LOP</th><th>Net</th><th>Exceptions</th></tr></thead><tbody>{runDetail.lines?.map((line:Row)=><tr key={line.id}><td>#{line.employee_id}</td><td>{cash(line.gross)}</td><td>{line.lop_days}</td><td>{cash(line.lop_amount)}</td><td>{cash(line.net)}</td><td>{line.exceptions||"None"}{line.exceptions&&hr&&<button className="employee-cancel" disabled={busy}
   onClick={()=>{const reason=window.prompt("Explain the verified attendance exception (20+ characters).");
    if(reason)void submit(()=>call("/runs/"+runDetail.id+"/lines/"+line.id+"/resolve-exception","POST",{reason}),"Attendance exception reviewed.");
   }}>Resolve with reason</button>}</td></tr>)}</tbody></table></div></div>}
  </section>}
  {tab==="payslips"&&<section className="employee-surface">
   <h3><FileDown size={19}/> Published payslips</h3><p className="muted">Confidential; only published statements are available for download.</p>
   <div className="ops-table">{slips.length?slips.map(s=><div className="ops-row" key={s.line_id}><strong>{s.period}</strong><span>Gross {cash(s.gross)}</span><span>Net {cash(s.net)}</span>
    <a className="employee-primary" href={api+"/payroll/payslips/"+s.line_id+".pdf"} download>Download PDF</a></div>):<p>No payslips published yet.</p>}</div>
  </section>}
  {tab==="expenses"&&<div className="ops-columns">
   <section className="employee-surface"><h3><ReceiptText size={19}/> New reimbursement claim</h3>
    <form className="ops-form" onSubmit={e=>{e.preventDefault();void submit(async()=>{
      const r=await call("/expenses","POST",{...claim,amount:Number(claim.amount)});
      if(receipt){const f=new FormData();f.append("receipt",receipt);
       const response=await fetch(api+"/payroll/expenses/"+r.id+"/receipt",{method:"POST",credentials:"include",body:f});
       if(!response.ok)throw Error("Claim was created, but receipt upload failed. Please contact HR.");
      }
      setClaim({title:"",category:"travel",amount:"",incurred_on:today(),note:""});setReceipt(null);
     },"Expense claim submitted.")}}>
      <label>Expense title<input required minLength={4} value={claim.title} onChange={e=>setClaim(v=>({...v,title:e.target.value}))}/></label>
      <label>Category<select value={claim.category} onChange={e=>setClaim(v=>({...v,category:e.target.value}))}>{["travel","food","equipment","internet","other"].map(c=><option key={c}>{c}</option>)}</select></label>
      <label>Amount (INR)<input required min=".01" max="1000000" type="number" step=".01" value={claim.amount} onChange={e=>setClaim(v=>({...v,amount:e.target.value}))}/></label>
      <label>Expense date<input required type="date" value={claim.incurred_on} onChange={e=>setClaim(v=>({...v,incurred_on:e.target.value}))}/></label>
      <label className="wide">Explanation<textarea rows={3} value={claim.note} onChange={e=>setClaim(v=>({...v,note:e.target.value}))}/></label>
      <label className="wide">Receipt (PDF/JPEG/PNG, 5 MB)<input type="file" required accept=".pdf,.jpg,.jpeg,.png" onChange={e=>setReceipt(e.target.files?.[0]||null)}/></label>
      <button className="employee-primary" disabled={busy}>Submit expense</button>
    </form></section>
   <section className="employee-surface"><h3>Claims</h3><div className="ops-table">{expenses.map(e=><div className="ops-row" key={e.id}><strong>{e.title}</strong><span>{cash(e.amount)} · {e.status}</span>
    {e.has_receipt&&<a href={api+"/payroll/expenses/"+e.id+"/receipt"} target="_blank" rel="noreferrer">Receipt</a>}</div>)}
    {!expenses.length&&<p>No submitted expenses yet.</p>}</div>
    {finance&&<><h3>Finance review</h3><div className="ops-table">{claims.filter(x=>x.status==="pending").map(x=><div className="ops-row" key={x.id}><strong>{x.title} · #{x.employee_id}</strong><span>{cash(x.amount)}</span>
     {x.has_receipt&&<a href={api+"/payroll/expenses/"+x.id+"/receipt"} target="_blank" rel="noreferrer">View receipt</a>}
     <button className="employee-primary" disabled={busy||x.employee_id===user.id} onClick={()=>void submit(()=>call("/expenses/"+x.id+"/review","POST",{approve:true}),"Claim approved.")}>Approve</button>
     <button className="employee-cancel" disabled={busy||x.employee_id===user.id} onClick={()=>void submit(()=>call("/expenses/"+x.id+"/review","POST",{approve:false}),"Claim rejected.")}>Reject</button>
    </div>)}</div></>}
   </section>
  </div>}
 </div>;
}

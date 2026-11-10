"use client";
import {explainError} from "./formErrors";
import {useEffect,useRef,useState} from "react";
import {BadgeIndianRupee,ReceiptText,FileDown,ShieldCheck,CalendarDays,ChevronDown,ChevronRight,UploadCloud,CheckCircle2,Info,AlertCircle} from "lucide-react";
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
 const [payReason,setPayReason]=useState("");
 const [salarySection,setSalarySection]=useState<"structure"|"statutory"|"components">("structure");
 const [reviewLoading,setReviewLoading]=useState<number|null>(null);
 const reviewRef=useRef<HTMLDivElement>(null);
 const salaryInputRef=useRef<HTMLDivElement>(null);
 const [validation,setValidation]=useState<string[]>([]);
 async function call(path:string,method="GET",body?:unknown){
  const r=await fetch(api+"/payroll"+path,{method,credentials:"include",headers:{"Content-Type":"application/json"},
   body:body===undefined?undefined:JSON.stringify(body)});
  const j=await r.json().catch(()=>({}));
  if(!r.ok){const d=j.detail;throw Object.assign(new Error(explainError(j,r.status)),{field:d?.field,employees:d?.employees})}
  return j;
 }
 async function propose(kind:string,payload:Row){
  if(payReason.trim().length<10)throw Error("Enter a specific reason (at least 10 characters) before submitting.");
  const r=await fetch(api+"/governance/requests",{method:"POST",credentials:"include",
   headers:{"Content-Type":"application/json"},body:JSON.stringify({kind,payload,reason:payReason.trim()})});
  const j=await r.json().catch(()=>({}));
  if(!r.ok)throw Error(explainError(j,r.status));
  setPayReason("");
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
 function clear(){setError("");setMessage("");setFieldError("");setValidation([])}
 function requirements(kind:"structure"|"statutory"|"components"){
  const problems:string[]=[];
  if(!chosen)problems.push("Select the employee whose payroll configuration you want to change.");
  if(payReason.trim().length<10)problems.push("Explain why this change is needed (at least 10 characters).");
  const fields=kind==="structure"?salaryFields:kind==="statutory"?statutoryFields:[["code","Component code"],["title","Display label"],["amount","Monthly amount"]] as const;
  const source:Row=kind==="structure"?salary:kind==="statutory"?statutory:component;
  for(const [key,label] of fields){
   const value=source[key];
   if(value===undefined||value===null||String(value).trim()==="")problems.push(label+" is required.");
   else if((kind!=="components"||key==="amount")&&(!Number.isFinite(Number(value))||Number(value)<0))
    problems.push(label+" must be zero or greater.");
  }
  if(kind==="components"&&component.code&&!/^[a-z][a-z0-9_]{1,34}$/.test(component.code))
   problems.push("Component code must use lowercase letters, numbers or underscores, starting with a letter.");
  if(kind==="structure"&&salaryFields.every(([key])=>salary[key]!==""&&salary[key]!=null)){
   if(Number(salary.other_deductions)>Number(salary.basic)+Number(salary.hra)+Number(salary.allowances))
    problems.push("Other deductions cannot exceed the combined salary and allowances.");
  }
  if(!(source.effective_from))problems.push("Choose the effective date.");
  return problems;
 }
 async function requestApproval(kind:"structure"|"statutory"|"components"){
  const problems=requirements(kind);
  if(problems.length){setValidation(problems);setError("Please correct the following before submitting your "+(kind==="components"?"component":kind==="statutory"?"statutory":"salary")+" request.");return}
  const payload=kind==="structure"?{...salary,employee_id:Number(chosen)}:kind==="statutory"?
   {...statutory,employee_id:Number(chosen)}:{...component,employee_id:Number(chosen),amount:Number(component.amount)};
  await submit(()=>propose(kind==="structure"?"salary_structure":kind==="statutory"?"statutory_settings":"salary_component",payload),
   "Approval request submitted. No payroll values have changed yet; an independent administrator must review it.");
 }
 async function reviewRun(id:number){
  setReviewLoading(id);clear();
  try{
   const detail=await call("/runs/"+id);
   setRunDetail(detail);
   window.requestAnimationFrame(()=>reviewRef.current?.scrollIntoView({behavior:"smooth",block:"start"}));
  }catch(e){setError("Could not open payroll run #"+id+": "+(e as Error).message)}
  finally{setReviewLoading(null)}
 }
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
  {tab==="salary"&&finance&&<div className="payroll-config">
   <div className="payroll-config-banner">
    <div className="payroll-config-icon"><ShieldCheck size={22}/></div>
    <div><h3>Configure employee payroll</h3>
     <p>Select an employee, choose what you want to update, and submit it for independent approval. Changes are not applied immediately.</p></div>
   </div>
   {!hr?<section className="employee-surface"><h3>View-only payroll access</h3><p className="field-help">An HR administrator submits compensation changes for approval. Accountants can review payroll runs and expense claims.</p></section>:<>
    <section className="employee-surface payroll-setup-card">
     <div className="payroll-step-title"><span className="payroll-step-number">1</span>
       <div><h3>Choose an employee</h3><p className="field-help">The selected employee is shared across all payroll settings below.</p></div></div>
     <label className="payroll-field">Employee <span className="payroll-required">Required</span>
      <span className="payroll-select-wrap"><select aria-label="Employee for payroll configuration" value={chosen}
        onChange={e=>{setChosen(e.target.value);setValidation([]);setError("")}}>
        <option value="">Choose an employee to continue</option>
        {employees.filter(e=>e.id!==user.id).map(e=><option key={e.id} value={e.id}>{e.name} · {e.employee_code||e.department||e.email}</option>)}
       </select><ChevronDown size={16}/></span>
     </label>
     {chosen?<p className="payroll-helper success"><CheckCircle2 size={15}/> Editing a proposal for {employees.find(e=>String(e.id)===chosen)?.name||"selected employee"}.</p>:
      <p className="payroll-helper"><Info size={15}/> Choose an employee before sending any salary, deduction, or component request. You cannot modify your own compensation.</p>}
    </section>
    <section className="employee-surface payroll-workflow-card">
     <div className="payroll-step-title"><span className="payroll-step-number">2</span>
      <div><h3>What do you want to update?</h3><p className="field-help">Complete one request at a time. Each request needs its own approval.</p></div></div>
     <div className="payroll-section-switch" role="tablist" aria-label="Payroll configuration type">
      {([["structure","Salary structure"],["statutory","Statutory deductions"],["components","Additional earnings"]] as const).map(([key,label])=>
       <button type="button" key={key} role="tab" aria-selected={salarySection===key}
        className={salarySection===key?"active":""} onClick={()=>{setSalarySection(key);clear()}}>{label}</button>)}
     </div>
     <div className="payroll-edit-form" ref={salaryInputRef}>
      {salarySection==="structure"&&<>
       <div className="payroll-panel-heading"><div><h3>Monthly salary structure</h3><p>Amounts in INR per month. Enter zero where a component does not apply.</p></div><BadgeIndianRupee size={24}/></div>
       <div className="payroll-fields">
        {salaryFields.map(([key,title])=><label className="payroll-field" key={key}>{title}<input type="number" min="0" step="0.01" inputMode="decimal" placeholder="0.00"
         aria-invalid={validation.some(v=>v.startsWith(title+" "))||fieldError===key}
         value={salary[key]??""} onChange={e=>setSalary(v=>({...v,[key]:e.target.value}))}/></label>)}
        <label className="payroll-field">Effective from<input type="date" value={salary.effective_from||""}
         onChange={e=>setSalary(v=>({...v,effective_from:e.target.value}))}/></label>
        <div className="payroll-net-preview"><span>Proposed gross monthly salary</span><strong>{cash(Number(salary.basic)+Number(salary.hra)+Number(salary.allowances))}</strong>
         <small>Before tax, statutory deductions and other salary components.</small></div>
       </div>
      </>}
      {salarySection==="statutory"&&<>
       <div className="payroll-panel-heading"><div><h3>Statutory deduction settings</h3><p>Enter verified amounts for this employee. The app does not determine tax eligibility or tax brackets automatically.</p></div><ShieldCheck size={24}/></div>
       <div className="payroll-fields">
        {statutoryFields.map(([key,title])=><label className="payroll-field" key={key}>{title}<input type="number" min="0" step="0.01" inputMode="decimal" placeholder="0.00"
         value={statutory[key]??""} aria-invalid={validation.some(v=>v.startsWith(title+" "))}
         onChange={e=>setStatutory(v=>({...v,[key]:e.target.value}))}/></label>)}
        <label className="payroll-field">Effective from<input type="date" value={statutory.effective_from||""}
         onChange={e=>setStatutory(v=>({...v,effective_from:e.target.value}))}/></label>
       </div>
      </>}
      {salarySection==="components"&&<>
       <div className="payroll-panel-heading"><div><h3>Additional earnings and deductions</h3><p>Add a separately approved allowance, bonus, or deduction to the monthly calculation.</p></div><BadgeIndianRupee size={24}/></div>
       <div className="payroll-fields">
        <label className="payroll-field">Component code<input value={component.code} placeholder="e.g. shift_bonus"
         onChange={e=>setComponent(v=>({...v,code:e.target.value}))}/></label>
        <label className="payroll-field">Display label<input value={component.title} placeholder="e.g. Shift allowance"
         onChange={e=>setComponent(v=>({...v,title:e.target.value}))}/></label>
        <label className="payroll-field">Type<select value={component.kind}
         onChange={e=>setComponent(v=>({...v,kind:e.target.value}))}><option value="earning">Earning / allowance</option><option value="deduction">Deduction</option></select></label>
        <label className="payroll-field">Monthly amount (INR)<input type="number" min="0" step="0.01" placeholder="0.00"
         value={component.amount} onChange={e=>setComponent(v=>({...v,amount:e.target.value}))}/></label>
        <label className="payroll-field">Effective from<input type="date" value={component.effective_from}
         onChange={e=>setComponent(v=>({...v,effective_from:e.target.value}))}/></label>
        <label className="payroll-active-toggle"><input type="checkbox" checked={component.active}
         onChange={e=>setComponent(v=>({...v,active:e.target.checked}))}/> Active component</label>
       </div>
       <div className="payroll-component-list"><h4>Currently configured</h4>
        {components.map(c=><div className="payroll-component-row" key={c.code}><div><strong>{c.title}</strong><small>{c.code} · {c.kind} · {cash(c.amount)} · {c.active?"Active":"Inactive"}</small></div>
         <button type="button" className="employee-cancel" onClick={()=>setComponent({code:c.code,title:c.title,kind:c.kind,amount:String(c.amount),effective_from:c.effective_from,active:c.active})}>Edit details</button></div>)}
        {!components.length&&<p className="field-help">No additional components have been configured for this employee.</p>}
       </div>
      </>}
      <div className="payroll-request-divider"/>
      <div className="payroll-step-title"><span className="payroll-step-number">3</span><div>
       <h3>Explain and submit for approval</h3><p className="field-help">The reviewer needs to know what is changing and why. At least 10 characters are required.</p>
      </div></div>
      <label className="payroll-field payroll-reason-label">Reason for this request
       <textarea rows={3} minLength={10} maxLength={1000} value={payReason}
        placeholder="Example: Updated compensation effective from the approved offer revision."
        onChange={e=>setPayReason(e.target.value)}/>
       <small>{payReason.trim().length}/10 minimum characters</small></label>
      {validation.length>0&&<div role="alert" className="payroll-validation"><strong><AlertCircle size={17}/> Fix these fields before submitting:</strong>
       <ul>{validation.map((problem,i)=><li key={i}>{problem}</li>)}</ul></div>}
      <div className="payroll-submit-row"><button type="button" className="employee-primary payroll-submit"
       disabled={busy} onClick={()=>void requestApproval(salarySection)}>{busy?"Submitting request…":
         salarySection==="structure"?"Submit salary approval request":salarySection==="statutory"?"Submit statutory approval request":"Submit component approval request"}
       <ChevronRight size={17}/></button>
       <span><ShieldCheck size={16}/> Changes are applied only after another authorized admin approves.</span></div>
     </div>
    </section>
   </>}
  </div>}
  {tab==="runs"&&finance&&<section className="employee-surface">
   <h3>Monthly payroll processing</h3><p className="field-help">Draft → separate HR approver → publish payslips. No funds or statutory returns are transferred.</p>
   <div className="ops-inline"><label>Payroll period<input type="month" value={month} onChange={e=>setMonth(e.target.value)}/></label>
    <button className="employee-primary" disabled={busy} onClick={()=>void submit(()=>call("/runs","POST",{period:month}),"Payroll draft calculated.")}>Calculate draft</button></div>
   <div className="ops-table">{runs.map(r=><div className="ops-row" key={r.id}><strong>{r.period}</strong><span>{r.status}</span>
    <button className="employee-cancel" disabled={reviewLoading!==null} onClick={()=>void reviewRun(r.id)}>{reviewLoading===r.id?"Opening…":"Review details"}</button>
    {r.status==="draft"&&hr&&<button className="employee-primary" disabled={busy} onClick={()=>void submit(()=>call("/runs/"+r.id+"/approve","POST"),"Payroll approved.")}>Approve</button>}
    {r.status==="approved"&&hr&&<button className="employee-primary" disabled={busy} onClick={()=>void submit(()=>call("/runs/"+r.id+"/publish","POST"),"Payslips published.")}>Publish</button>}
   </div>)}</div>
   {runDetail&&<div className="ops-breakdown payroll-run-review" ref={reviewRef} tabIndex={-1}><div className="payroll-review-header"><strong>Payroll review details</strong><button type="button" className="employee-cancel" onClick={()=>setRunDetail(null)}>Close review</button></div><h4>Run {runDetail.period} · {runDetail.status}</h4><p>Gross {cash(runDetail.gross_total)} · Net {cash(runDetail.net_total)} · {runDetail.exceptions} attendance exceptions</p>
    <div className="table-wrap"><table><thead><tr><th>Employee</th><th>Gross</th><th>LOP days</th><th>LOP</th><th>Net</th><th>Exceptions</th></tr></thead><tbody>{runDetail.lines?.map((line:Row)=><tr key={line.id}><td>#{line.employee_id}</td><td>{cash(line.gross)}</td><td>{line.lop_days}</td><td>{cash(line.lop_amount)}</td><td>{cash(line.net)}</td><td>{line.exceptions||"None"}{line.exceptions&&hr&&<button className="employee-cancel" disabled={busy}
   onClick={()=>{const reason=window.prompt("Explain the verified attendance exception (20+ characters).");
    if(reason)void submit(()=>call("/runs/"+runDetail.id+"/lines/"+line.id+"/resolve-exception","POST",{reason}),"Attendance exception reviewed.");
   }}>Resolve with reason</button>}</td></tr>)}</tbody></table></div></div>}
  </section>}
  {tab==="payslips"&&<section className="employee-surface">
   <h3><FileDown size={19}/> Published payslips</h3><p className="muted">Confidential — only published payslips can be downloaded by authorized users.</p>
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
      <label className="wide">Receipt (PDF, JPEG or PNG · up to 5 MB)
       <span className="payroll-upload"><UploadCloud size={21}/><span>{receipt?receipt.name:"Choose a receipt or drag a file here"}</span><small>{receipt?"File selected":"PDF, JPG or PNG · max 5 MB"}</small>
        <input type="file" required accept=".pdf,.jpg,.jpeg,.png" onChange={e=>{const file=e.target.files?.[0]||null;if(file&&file.size>5*1024*1024){setError("The receipt is larger than 5 MB. Choose a smaller file.");setReceipt(null);e.target.value="";return}setReceipt(file)}}/></span></label>
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

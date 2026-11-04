"use client";
import {useCallback,useEffect,useState} from "react";
import {Wallet,FileText,Receipt,ShieldCheck,SlidersHorizontal,Download,CheckCircle2} from "lucide-react";
import FeedbackMotion from "./FeedbackMotion";
type Row=Record<string,any>;
type User={id:number;role:string};
type Tab="payslips"|"expenses"|"structures"|"runs"|"statutory";
const today=()=>new Date().toISOString().slice(0,10);
export default function PayrollWorkspace({api,user}:{api:string;user:User}){
 const finance=["super_admin","admin","hr","accountant"].includes(user.role);
 const hr=["super_admin","admin","hr"].includes(user.role);
 const [tab,setTab]=useState<Tab>("payslips");
 const [staff,setStaff]=useState<Row[]>([]),[structure,setStructure]=useState<Row>({}),[runs,setRuns]=useState<Row[]>([]),
       [payslips,setPayslips]=useState<Row[]>([]),[claims,setClaims]=useState<Row[]>([]),[statutory,setStatutory]=useState<Row[]>([]);
 const [selectedRun,setSelectedRun]=useState<Row|null>(null);
 const [employeeId,setEmployeeId]=useState("");
 const [salary,setSalary]=useState<Row>({basic:"",hra:"",allowances:"0",other_deductions:"0",monthly_pt:"0",
  monthly_tds:"0",effective_from:today(),pf_enabled:true,esi_enabled:false,state:"MP"});
 const [runForm,setRunForm]=useState({year:new Date().getFullYear().toString(),month:String(new Date().getMonth()+1),note:""});
 const [policy,setPolicy]=useState<Row>({effective_from:"2026-09-17",pf_rate:"0.12",pf_wage_ceiling:"25000",
  esi_employee_rate:"0.0075",esi_employer_rate:"0.0325",esi_eligibility_ceiling:"21000",
  verified:false,note:"Review EPFO, ESIC, tax and state requirements before marking verified."});
 const [claim,setClaim]=useState({category:"travel",amount:"",expense_date:today(),description:""});
 const [receipt,setReceipt]=useState<File|null>(null);
 const [busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
 const [badField,setBadField]=useState("");
 const url=api+"/payroll";
 const call=useCallback(async(path:string,method="GET",body?:unknown)=>{
  const r=await fetch(url+path,{method,credentials:"include",headers:{"Content-Type":"application/json"},body:body?JSON.stringify(body):undefined});
  const data=await r.json().catch(()=>({}));
  if(!r.ok){
   const detail=data.detail;const field=detail?.field||(Array.isArray(detail)?detail[0]?.loc?.at(-1):"");
   const message=typeof detail==="string"?detail:detail?.message||(
    Array.isArray(detail)?detail.map((x:Row)=>x.msg).join("; "):"Unable to complete request");
   throw Object.assign(new Error(message),{field});
  }
  return data;
 },[url]);
 const load=useCallback(async()=>{
  const targets=[call("/payslips"),call("/claims"),...(finance?[call("/runs"),call("/statutory")]:[]),
   ...(hr?[fetch(api+"/employees",{credentials:"include"}).then(r=>r.ok?r.json():[])]:[])];
  const results=await Promise.allSettled(targets);
  const value=(i:number)=>results[i]?.status==="fulfilled"?(results[i] as PromiseFulfilledResult<any>).value:[];
  setPayslips(value(0));setClaims(value(1));
  if(finance){setRuns(value(2));setStatutory(value(3));}
  if(hr)setStaff(value(finance?4:2));
 },[api,call,finance,hr]);
 useEffect(()=>{void load()},[load]);
 async function execute(action:()=>Promise<unknown>,message:string){
  setError("");setBadField("");setNotice("");setBusy(true);
  try{await action();setNotice(message);await load()}
  catch(err){const e=err as Error&{field?:string};setError(e.message);setBadField(e.field||"");
   window.requestAnimationFrame(()=>{
    const el=e.field?window.document.querySelector<HTMLElement>(`[name="${e.field}"]`):null;
    el?.scrollIntoView({behavior:"smooth",block:"center"});el?.focus();
   });
  }finally{setBusy(false)}
 }
 async function getFile(path:string,name:string){
  setError("");
  const r=await fetch(path.startsWith(api)?path:url+path,{credentials:"include"});
  if(!r.ok){setError("Cannot download this document. You may not have access.");return}
  const blob=await r.blob(),link=window.document.createElement("a");
  const object=URL.createObjectURL(blob);link.href=object;link.download=name;
  link.click();URL.revokeObjectURL(object);
 }
 async function submitClaim(e:React.FormEvent){
  e.preventDefault();
  await execute(async()=>{
   const saved=await call("/claims","POST",{...claim,amount:Number(claim.amount)});
   if(receipt){
    const body=new FormData();body.append("document",receipt);
    const result=await fetch(url+"/claims/"+saved.id+"/receipt",{method:"POST",credentials:"include",body});
    if(!result.ok)throw Error("Expense saved, but receipt upload failed. Open your claim to attach it.");
   }
   setReceipt(null);setClaim(v=>({...v,amount:"",description:""}));
  },"Expense claim submitted for review.");
 }
 return <div className="ops-workspace">
  <div className="ops-heading"><Wallet size={21}/><div><h2>Payroll & expenses</h2><p>Private salaries, reviewed payroll runs and reimbursement claims.</p></div></div>
  <nav className="ops-tabs">
   {([["payslips","Payslips",FileText],["expenses","Expenses",Receipt],
     ...(hr?[["structures","Salary structures",SlidersHorizontal]]:[]),
     ...(finance?[["runs","Payroll runs",Wallet]]:[]),
     ...(hr?[["statutory","Statutory rules",ShieldCheck]]:[])] as [Tab,string,any][]).map(([key,label,Icon])=>
      <button key={key} className={tab===key?"active":""} onClick={()=>{setTab(key);setError("");setNotice("")}}><Icon size={16}/>{label}</button>)}
  </nav>
  {error&&<div role="alert" className="time-form-error">{error}</div>}
  {notice&&<FeedbackMotion type="success" compact message={notice}/>}
  {busy&&<FeedbackMotion type="loading" compact message="Processing payroll records…"/>}

  {tab==="payslips"&&<section className="employee-surface"><h3>My approved payslips</h3>
   <p className="muted">Only finalized monthly payslips are available here.</p>
   <div className="ops-list">{payslips.map(p=><div key={p.run_id}><strong>{p.month}/{p.year}</strong><span>Net salary: ₹{Number(p.net).toLocaleString("en-IN")}</span>
    <button className="employee-cancel" onClick={()=>void getFile("/payslips/"+p.run_id+"/pdf",`payslip-${p.year}-${p.month}.pdf`)}><Download size={14}/> Download PDF</button></div>)}{!payslips.length&&<p>No finalized payslips yet.</p>}</div>
  </section>}

  {tab==="expenses"&&<div className="ops-columns"><section className="employee-surface"><h3>Submit reimbursement</h3>
   <form className="ops-form" onSubmit={submitClaim}>
    <label>Expense category<select name="category" value={claim.category} onChange={e=>setClaim(v=>({...v,category:e.target.value}))}>{["travel","meals","internet","equipment","medical","other"].map(k=><option key={k}>{k}</option>)}</select></label>
    <label>Amount (INR)<input name="amount" type="number" step=".01" min=".01" required aria-invalid={badField==="amount"} value={claim.amount} onChange={e=>setClaim(v=>({...v,amount:e.target.value}))}/></label>
    <label>Date<input name="expense_date" type="date" required max={today()} value={claim.expense_date} onChange={e=>setClaim(v=>({...v,expense_date:e.target.value}))}/></label>
    <label>Receipt (PDF/JPG/PNG, up to 5 MB)<input type="file" accept="application/pdf,image/png,image/jpeg" onChange={e=>setReceipt(e.target.files?.[0]||null)}/></label>
    <label className="wide">Description<textarea required minLength={10} rows={3} value={claim.description} onChange={e=>setClaim(v=>({...v,description:e.target.value}))}/></label>
    <button className="employee-primary" disabled={busy}>Submit claim</button>
   </form></section>
   <section className="employee-surface"><h3>{finance?"Claims for review":"My expense claims"}</h3>
    {finance&&<button className="employee-cancel" onClick={()=>void call("/claims?scope=all").then(setClaims).catch(e=>setError(e.message))}>Show all employee claims</button>}
    <div className="ops-list">{claims.map(x=><div key={x.id}><strong>{x.category} · ₹{Number(x.amount).toLocaleString("en-IN")}</strong>
     <span>{x.description} · {x.expense_date}</span><small>{x.status}</small>
     {x.receipt_key&&<button className="employee-cancel" onClick={()=>void getFile("/claims/"+x.id+"/receipt","receipt-"+x.id)}>View receipt</button>}
     {finance&&x.status==="pending"&&x.employee_id!==user.id&&<div className="ops-actions">
      <button className="employee-primary" disabled={busy} onClick={()=>void execute(()=>call("/claims/"+x.id+"/review","POST",{approve:true,note:"Receipt and business expense verified"}),"Expense approved.")}>Approve</button>
      <button className="employee-cancel" disabled={busy} onClick={()=>void execute(()=>call("/claims/"+x.id+"/review","POST",{approve:false,note:"Expense not approved; contact HR"}),"Expense rejected.")}>Reject</button>
     </div>}
    </div>)}{!claims.length&&<p>No claims found.</p>}</div>
   </section></div>}

  {tab==="structures"&&hr&&<div className="ops-columns"><section className="employee-surface"><h3>Create effective-dated salary structure</h3>
   <p className="muted">Basic, HRA and allowances are monthly INR figures. TDS and state PT are explicit reviewed withholding amounts.</p>
   <form className="ops-form" onSubmit={e=>{e.preventDefault();void execute(()=>call("/structures","POST",{employee_id:Number(employeeId),...salary,
    basic:Number(salary.basic),hra:Number(salary.hra),allowances:Number(salary.allowances),
    other_deductions:Number(salary.other_deductions),monthly_tds:Number(salary.monthly_tds),
    monthly_pt:Number(salary.monthly_pt)}),"Salary structure saved.")}}>
    <label className="wide">Employee<select required value={employeeId} onChange={e=>{setEmployeeId(e.target.value);
     void call("/structures?employee_id="+e.target.value).then((rows:Row[])=>setStructure(rows[0]||{})).catch(()=>{})}}>
      <option value="">Select employee</option>{staff.filter(x=>x.status==="active").map(x=><option value={x.id} key={x.id}>{x.name}</option>)}</select></label>
    {(["effective_from","basic","hra","allowances","other_deductions","monthly_tds","monthly_pt","state"] as const).map(k=>
     <label key={k}>{k.replace(/_/g," ").toUpperCase()}<input name={k} required type={k==="effective_from"?"date":["state"].includes(k)?"text":"number"}
       min={k==="effective_from"||k==="state"?undefined:"0"} step={k==="effective_from"||k==="state"?undefined:".01"} value={salary[k]??""} onChange={e=>setSalary(v=>({...v,[k]:e.target.value}))}/></label>)}
    <label className="ops-check"><input type="checkbox" checked={salary.pf_enabled} onChange={e=>setSalary(v=>({...v,pf_enabled:e.target.checked}))}/> PF enabled</label>
    <label className="ops-check"><input type="checkbox" checked={salary.esi_enabled} onChange={e=>setSalary(v=>({...v,esi_enabled:e.target.checked}))}/> ESI enabled</label>
    <button className="employee-primary" disabled={busy||!employeeId}>Save structure</button>
   </form></section><section className="employee-surface"><h3>Current structure</h3>
    {Object.keys(structure).length?<div className="ops-list">{Object.entries(structure).filter(([key])=>!["id","employee_id"].includes(key)).map(([key,value])=>
      <div key={key}><strong>{key.replace(/_/g," ")}</strong><span>{String(value)}</span></div>)}</div>:<p>Select an employee to inspect the current structure.</p>}
   </section></div>}

  {tab==="runs"&&finance&&<div className="ops-columns"><section className="employee-surface"><h3>Monthly payroll</h3>
    <p className="muted">Creates an immutable draft from salary, attendance and approved loss-of-pay. HR approval is separate; no bank payments are sent.</p>
    <form className="ops-form" onSubmit={e=>{e.preventDefault();void execute(()=>call("/runs","POST",{
     year:Number(runForm.year),month:Number(runForm.month),note:runForm.note}),"Payroll draft created.")}}>
     <label>Year<input type="number" min="2020" max="2100" value={runForm.year} onChange={e=>setRunForm(v=>({...v,year:e.target.value}))}/></label>
     <label>Month<select value={runForm.month} onChange={e=>setRunForm(v=>({...v,month:e.target.value}))}>{Array.from({length:12},(_,i)=>i+1).map(m=><option key={m} value={m}>{m}</option>)}</select></label>
     <label className="wide">Payroll note<textarea rows={2} value={runForm.note} onChange={e=>setRunForm(v=>({...v,note:e.target.value}))}/></label>
     <button className="employee-primary" disabled={busy}>Generate draft</button>
    </form>
    <div className="ops-list">{runs.map(run=><div key={run.id}>
      <strong>{run.month}/{run.year} · {run.status}</strong>
      <button className="employee-cancel" onClick={()=>void call("/runs/"+run.id).then(setSelectedRun).catch(e=>setError(e.message))}>Review run</button>
      {run.status==="approved"&&<button className="employee-cancel" onClick={()=>void getFile(api+"/platform/accounting/payroll.csv?run_id="+run.id,"payroll-"+run.id+".csv")}>Accounting CSV</button>}
    </div>)}{!runs.length&&<p>No payroll runs yet.</p>}</div>
   </section><section className="employee-surface"><h3>Payroll review</h3>{selectedRun?<div className="ops-review">
    <p>Period {selectedRun.month}/{selectedRun.year} · {selectedRun.status}</p>
    <div className="ops-list">{(selectedRun.lines||[]).map((x:Row)=><div key={x.id}><strong>Employee #{x.employee_id} · Net ₹{Number(x.net).toLocaleString("en-IN")}</strong>
      <span>Gross ₹{x.gross} · LOP {x.lop_days} days / ₹{x.lop_deduction} · PF ₹{x.pf} · ESI ₹{x.esi} · TDS ₹{x.tds}</span>
      {x.review_note&&<small className="ops-warning">{x.review_note}</small>}</div>)}</div>
    {hr&&selectedRun.status==="draft"&&<button className="employee-primary" disabled={busy||selectedRun.has_review_flags} onClick={()=>void execute(()=>call("/runs/"+selectedRun.id+"/approve","POST",{reason:"Payroll verified against approved salary structures and attendance"}),"Payroll approved and payslips released.")}>Approve and release payslips</button>}
    {selectedRun.has_review_flags&&<p className="ops-warning">Review flags block finalization. Resolve them with supporting HR records.</p>}
   </div>:<p>Select a payroll run to inspect employee calculations.</p>}</section></div>}

  {tab==="statutory"&&hr&&<div className="ops-columns"><section className="employee-surface"><h3>Effective-dated statutory settings</h3>
   <p className="ops-warning">Confirm applicability, PF/ESI wage bases, Professional Tax state schedules, tax declarations and current law before marking verified.</p>
   <form className="ops-form" onSubmit={e=>{e.preventDefault();void execute(()=>call("/statutory","PUT",{...policy,
     pf_rate:Number(policy.pf_rate),pf_wage_ceiling:Number(policy.pf_wage_ceiling),
     esi_employee_rate:Number(policy.esi_employee_rate),esi_employer_rate:Number(policy.esi_employer_rate),
     esi_eligibility_ceiling:Number(policy.esi_eligibility_ceiling)}),"Statutory configuration saved.")}}>
    {(["effective_from","pf_rate","pf_wage_ceiling","esi_employee_rate","esi_employer_rate","esi_eligibility_ceiling"] as const).map(key=>
      <label key={key}>{key.replace(/_/g," ")}<input name={key} type={key==="effective_from"?"date":"number"} min={key==="effective_from"?undefined:"0"}
       step={key==="effective_from"?undefined:".0001"} required value={policy[key]} onChange={e=>setPolicy(v=>({...v,[key]:e.target.value}))}/></label>)}
    <label className="wide">Notes<textarea rows={3} value={policy.note} onChange={e=>setPolicy(v=>({...v,note:e.target.value}))}/></label>
    <label className="ops-check wide"><input type="checkbox" checked={Boolean(policy.verified)} onChange={e=>setPolicy(v=>({...v,verified:e.target.checked}))}/> HR has verified this effective-dated schedule with official sources</label>
    <button className="employee-primary" disabled={busy}>Save statutory policy</button>
   </form></section><section className="employee-surface"><h3>Stored schedules</h3><div className="ops-list">{statutory.map((x:Row)=><div key={x.effective_from}>
    <strong>{x.effective_from} {x.verified?<CheckCircle2 size={14}/>:<span>Not verified</span>}</strong>
    <span>PF ceiling ₹{x.pf_wage_ceiling} · PF {Number(x.pf_rate)*100}% · ESI threshold ₹{x.esi_eligibility_ceiling}</span></div>)}{!statutory.length&&<p>No statutory rules configured.</p>}</div></section></div>}
 </div>;
}

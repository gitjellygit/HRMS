"use client";
import {useTransientMessage} from "./useTransientMessage";
import {explainError} from "./formErrors";
import {useEffect,useMemo,useState} from "react";
import {CheckCircle2,ChevronDown,Clock3,FileText,History,ShieldCheck,XCircle} from "lucide-react";

type Row={
 id:number;kind:string;payload:Record<string,unknown>;reason:string;status:string;
 submitted_by:number;submitted_by_name?:string;reviewed_by?:number|null;
 reviewed_by_name?:string|null;review_note?:string;
 created_at?:string;reviewed_at?:string|null;
};
const titles:Record<string,string>={
 company_policy:"Company policy",leave_policy:"Leave policy",leave_allocation:"Leave allocation",
 bonus_policy:"Bonus policy",salary_structure:"Salary structure",
 statutory_settings:"Statutory settings",salary_component:"Salary component"
};
const labels:Record<string,string>={
 title:"Policy title",category:"Category",description:"Description",effective_date:"Effective date",
 leave_type:"Leave type",annual_days:"Annual leave days",monthly_accrual:"Monthly accrual",
 carry_forward_limit:"Carry-forward limit",encashment_allowed:"Encashment allowed",
 probation_allowed:"Allowed during probation",approval_chain:"Approval chain",active:"Active",
 employee_id:"Employee",year:"Year",allocated_days:"Allocated days",
 default_project_bonus_inr:"Default bonus (INR)",audience_ids:"Visible to employee IDs",
 basic:"Basic",hra:"HRA",allowances:"Allowances",other_deductions:"Other deductions"
};
function friendly(value:unknown):string{
 if(typeof value==="boolean")return value?"Yes":"No";
 if(Array.isArray(value))return value.map(friendly).join(", ")||"All employees";
 if(value===null||value===undefined||value==="")return "Not specified";
 if(typeof value==="object")return JSON.stringify(value);
 return String(value);
}
function dateLabel(value?:string|null){
 if(!value)return "—";
 const time=Date.parse(value);
 return Number.isFinite(time)?new Date(time).toLocaleString(undefined,{dateStyle:"medium",timeStyle:"short"}):value;
}
function kindLabel(kind:string){return titles[kind]||kind.replaceAll("_"," ")}
function Summary({payload}:{payload:Record<string,unknown>}){
 const values=Object.entries(payload);
 return <dl className="governance-fields">{values.map(([key,value])=>
  <div key={key} className={key==="description"?"governance-wide":""}>
   <dt>{labels[key]||key.replaceAll("_"," ")}</dt><dd>{friendly(value)}</dd>
  </div>)}</dl>;
}
export default function GovernancePanel({api,user}:{api:string;user:{id:number;role:string}}){
 const admin=["super_admin","admin"].includes(user.role);
 const [rows,setRows]=useState<Row[]>([]);
 const [notes,setNotes]=useState<Record<number,string>>({});
 const [message,setMessage]=useTransientMessage();
 const [error,setError]=useState("");
 const [busy,setBusy]=useState<number|null>(null);
 const [showHistory,setShowHistory]=useState(false);
 async function load(){
  const r=await fetch(api+"/governance/requests",{credentials:"include"});
  if(!r.ok)throw Error("Could not load approvals. Refresh the page or contact HR support.");
  setRows(await r.json());
 }
 useEffect(()=>{void load().catch(e=>setError((e as Error).message))},[api,user.id]);
 const pending=useMemo(()=>rows.filter(r=>r.status==="pending"),[rows]);
 const history=useMemo(()=>rows.filter(r=>r.status!=="pending"),[rows]);
 async function review(id:number,approve:boolean){
  const reason=(notes[id]||"").trim();
  if(reason.length<10){setError("Enter an approval or rejection reason of at least 10 characters.");return}
  setError("");setMessage("");setBusy(id);
  try{
   const r=await fetch(api+"/governance/requests/"+id+"/review",{
    method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({approve,reason})});
   const j=await r.json().catch(()=>({}));
   if(!r.ok)throw Error(explainError(j,r.status));
   await load();
   setNotes(previous=>({...previous,[id]:""}));
   setMessage("Request #"+id+(approve?" approved and applied.":" rejected.")+" It is now in approval history.");
  }catch(e){setError((e as Error).message)}
  finally{setBusy(null)}
 }
 function item(r:Row){
  const pendingItem=r.status==="pending";
  const selfRequest=r.submitted_by===user.id;
  return <article key={r.id} className={"governance-request governance-"+r.status}>
   <div className="governance-item-head">
    <div className="governance-item-title"><span className="governance-kind">{kindLabel(r.kind)}</span>
     <h3>{typeof r.payload?.title==="string"?r.payload.title:typeof r.payload?.leave_type==="string"?String(r.payload.leave_type).replaceAll("_"," ")+" leave":kindLabel(r.kind)} <small>#{r.id}</small></h3>
    </div>
    <span className={"governance-status governance-status-"+r.status}>
     {r.status==="approved"?<CheckCircle2 size={15}/>:r.status==="rejected"?<XCircle size={15}/>:<Clock3 size={15}/>}
     {r.status==="approved"?"Approved":r.status==="rejected"?"Rejected":"Pending review"}
    </span>
   </div>
   <div className="governance-meta">
    <span><strong>Requested by</strong>{r.submitted_by_name||"Employee #"+r.submitted_by}</span>
    <span><strong>Submitted</strong>{dateLabel(r.created_at)}</span>
    {!pendingItem&&<span><strong>Reviewed by</strong>{r.reviewed_by_name||"—"}</span>}
    {!pendingItem&&<span><strong>Decision date</strong>{dateLabel(r.reviewed_at)}</span>}
   </div>
   <div className="governance-reason"><strong>Business reason</strong><p>{r.reason}</p></div>
   <details className="governance-details"><summary><FileText size={16}/> View proposed changes <ChevronDown size={16}/></summary><Summary payload={r.payload||{}}/></details>
   {!pendingItem&&<div className="governance-decision"><strong>Decision reason</strong><p>{r.review_note||"No decision note recorded."}</p></div>}
   {admin&&pendingItem&&(selfRequest?<div className="governance-self-review">Another administrator must review this request. Self-approval is not allowed.</div>:
    <div className="governance-review"><label htmlFor={"gov-reason-"+r.id}>Decision reason <span aria-hidden="true">*</span>
     <textarea id={"gov-reason-"+r.id} rows={2} minLength={10} maxLength={1000}
      value={notes[r.id]||""} placeholder="Explain why you are approving or rejecting this request"
      onChange={e=>setNotes(old=>({...old,[r.id]:e.target.value}))}/></label>
     <div className="governance-buttons"><button type="button" className="governance-approve" disabled={busy!==null||(notes[r.id]||"").trim().length<10} onClick={()=>void review(r.id,true)}><CheckCircle2 size={16}/> {busy===r.id?"Processing…":"Approve & apply"}</button>
      <button type="button" className="governance-reject" disabled={busy!==null||(notes[r.id]||"").trim().length<10} onClick={()=>void review(r.id,false)}><XCircle size={16}/> Reject</button></div>
    </div>)}
  </article>;
 }
 return <section className="panel governance-workspace">
  <div className="governance-heading"><div><h2>{admin?"Admin approval inbox":"My approval requests"}</h2>
   <p>Review proposed policy and HR configuration changes. Every decision requires a reason and is retained in history.</p></div>
   <button type="button" className="governance-refresh" onClick={()=>void load().catch(e=>setError((e as Error).message))}>Refresh approvals</button>
  </div>
  {error&&<p className="error" role="alert">{error}</p>}
  {message&&<p className="governance-success" role="status">{message}</p>}
  <div className="governance-overview"><div><span>Awaiting review</span><strong>{pending.length}</strong></div><div><span>Approved</span><strong>{history.filter(r=>r.status==="approved").length}</strong></div><div><span>Rejected</span><strong>{history.filter(r=>r.status==="rejected").length}</strong></div></div>
  <div className="governance-section-head"><div><h3>{admin?"Pending approvals":"Pending requests"}</h3><p>{admin?"Requests that still need an administrator's decision":"Your requests currently awaiting an administrator's decision"}</p></div></div>
  <div className="governance-list">{pending.length?pending.map(item):<div className="governance-empty"><ShieldCheck size={28}/><strong>No approvals pending</strong><p>You're all caught up. New requests will appear here and trigger a bell notification.</p></div>}</div>
  <div className="governance-history"><button type="button" aria-expanded={showHistory} className="governance-history-toggle" onClick={()=>setShowHistory(v=>!v)}>
   <History size={18}/>{showHistory?"Hide approval history":"View older approvals & rejections"} <span>{history.length}</span><ChevronDown className={showHistory?"expanded":""} size={17}/></button>
   {showHistory&&<div className="governance-list">{history.length?history.map(item):<p className="governance-empty-history">No reviewed requests yet.</p>}</div>}
  </div>
 </section>;
}

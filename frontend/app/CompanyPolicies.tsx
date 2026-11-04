"use client";
import {useEffect,useState} from "react";
import {Settings2, ShieldCheck, CircleDollarSign, Info, CheckCircle2, Plus} from "lucide-react";

type ProjectPolicy={default_project_bonus_inr:number;currency:string;milestone_days:number;award_status:string};
export default function CompanyPolicies({api}:{api:string}){
 const [policy,setPolicy]=useState<ProjectPolicy|null>(null);
 const [amount,setAmount]=useState("");
 const [error,setError]=useState("");
 const [saved,setSaved]=useState("");
 const [saving,setSaving]=useState(false);
 const [records,setRecords]=useState<{id:number;title:string;category:string;description:string;effective_date:string;active:boolean}[]>([]);
 const [adding,setAdding]=useState(false);
 const [policyTitle,setPolicyTitle]=useState("");
 const [policyCategory,setPolicyCategory]=useState("general");
 const [policyDescription,setPolicyDescription]=useState("");
 const [effectiveDate,setEffectiveDate]=useState(new Date().toISOString().slice(0,10));
 const [policyBusy,setPolicyBusy]=useState(false);
 useEffect(()=>{
  fetch(api+"/policies/project-bonus",{credentials:"include"})
  .then(async r=>{if(!r.ok)throw Error("Cannot read company bonus policy.");return r.json()})
  .then((p:ProjectPolicy)=>{setPolicy(p);setAmount(String(p.default_project_bonus_inr))})
  .catch(err=>setError((err as Error).message));
  fetch(api+"/policies/records",{credentials:"include"}).then(r=>r.ok?r.json():[]).then(setRecords).catch(()=>{});
 },[api]);
 async function submit(e:React.FormEvent){
  e.preventDefault();setSaved("");setError("");
  const n=Number(amount);
  if(amount===""||!Number.isFinite(n)||n<0||n>100000000){setError("Enter a valid INR amount from 0 to 100,000,000.");return}
  setSaving(true);
  try{
   const r=await fetch(api+"/policies/project-bonus",{method:"PUT",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({default_project_bonus_inr:n})});
   const result=await r.json().catch(()=>({}));
   if(!r.ok)throw Error(typeof result.detail==="string"?result.detail:"Unable to update policy.");
   setPolicy(result);setSaved("Company default bonus saved.");
  }catch(err){setError((err as Error).message)}finally{setSaving(false)}
 }
 async function createRecord(e:React.FormEvent){
  e.preventDefault();setError("");setSaved("");
  if(policyTitle.trim().length<3||policyDescription.trim().length<20){setError("Add a title and description of at least 20 characters.");return}
  setPolicyBusy(true);
  try{
   const response=await fetch(api+"/policies/records",{method:"POST",credentials:"include",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({title:policyTitle.trim(),category:policyCategory,description:policyDescription.trim(),effective_date:effectiveDate,active:true})});
   const data=await response.json().catch(()=>({}));
   if(!response.ok)throw Error(typeof data.detail==="string"?data.detail:"Unable to create policy.");
   setRecords(previous=>[data,...previous]);setAdding(false);setPolicyTitle("");setPolicyDescription("");setSaved("Company policy created successfully.");
  }catch(err){setError((err as Error).message)}finally{setPolicyBusy(false)}
 }
 return <div className="policy-page">
  <section className="employee-surface"><div className="core-head"><Settings2 size={21}/><div><h2>Company policies</h2><p>Centralized HR settings used across onboarding and project workflows.</p></div></div>
   {error&&<div className="error" role="alert">{error}</div>}
   {saved&&<div className="employee-success" role="status"><CheckCircle2 size={17}/>{saved}</div>}
   <div className="policy-card"><div className="policy-card-head"><CircleDollarSign size={20}/><div><h3>Project sourcing incentive</h3><p>Default milestone bonus for employees who source projects.</p></div></div>
    <form className="policy-form" onSubmit={submit}>
     <div className="employee-field"><label htmlFor="default-bonus">Company default bonus (INR)</label><input id="default-bonus" value={amount} type="number" min="0" max="100000000" step="0.01" onChange={e=>setAmount(e.target.value)} required/><span className="field-help">Applies to newly created projects, unless an employee-specific amount or project override is supplied.</span></div>
     <div className="policy-summary"><span>Milestone</span><strong>{policy?.milestone_days??30} completed calendar days</strong><span>Bonus creation</span><strong>Planned · pending approval</strong></div>
     <div className="policy-actions"><button className="employee-primary" disabled={saving||!policy}>{saving?"Saving…":"Save policy"}</button></div>
    </form>
   </div>
   <section className="policy-records">
    <div className="employee-title-row"><div><h3>Company policy register</h3><p>Publish and maintain HR policy documents and effective dates.</p></div><button type="button" className="employee-primary" onClick={()=>setAdding(v=>!v)}><Plus size={16}/> {adding?"Close":"Add policy"}</button></div>
    {adding&&<form className="policy-record-form" onSubmit={createRecord}>
     <div className="employee-form-grid">
      <label className="employee-field">Policy title<input value={policyTitle} onChange={e=>setPolicyTitle(e.target.value)} minLength={3} maxLength={150} required placeholder="e.g. Remote work policy"/></label>
      <label className="employee-field">Category<select value={policyCategory} onChange={e=>setPolicyCategory(e.target.value)}>{["general","leave","attendance","payroll","security","onboarding"].map(c=><option key={c} value={c}>{c[0].toUpperCase()+c.slice(1)}</option>)}</select></label>
      <label className="employee-field">Effective date<input type="date" required value={effectiveDate} onChange={e=>setEffectiveDate(e.target.value)}/></label>
     </div>
     <label className="employee-field">Policy details<textarea rows={5} minLength={20} maxLength={10000} value={policyDescription} required placeholder="Write the policy and its conditions…" onChange={e=>setPolicyDescription(e.target.value)}/></label>
     <div className="employee-form-footer"><button type="button" className="employee-cancel" onClick={()=>setAdding(false)}>Cancel</button><button className="employee-primary" disabled={policyBusy}>{policyBusy?"Creating…":"Create policy"}</button></div>
    </form>}
    <div className="policy-record-list">{records.length?records.map(r=><details key={r.id} className="policy-record"><summary><strong>{r.title}</strong><span>{r.category} · Effective {r.effective_date}</span></summary><p>{r.description}</p></details>):<p className="muted">No additional company policies have been created yet.</p>}</div>
   </section>
   <div className="policy-guidance"><ShieldCheck size={18}/><p><strong>Priority order:</strong> Project override → Employee bonus → Company policy. For example, set the company default to ₹10,000, optionally set an employee's amount to ₹15,000, and only override an individual project when needed. Existing project bonuses do not change when the policy is updated.</p></div>
   <div className="policy-guidance"><Info size={18}/><p>Leave policies are managed under <strong>Leave requests → Policies & balances</strong>. Use Add policy above for written company policies.</p></div>
  </section>
 </div>;
}

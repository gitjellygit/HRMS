"use client";
import {useEffect,useState} from "react";
import {Settings2, ShieldCheck, CircleDollarSign, Info, CheckCircle2} from "lucide-react";

type ProjectPolicy={default_project_bonus_inr:number;currency:string;milestone_days:number;award_status:string};
export default function CompanyPolicies({api}:{api:string}){
 const [policy,setPolicy]=useState<ProjectPolicy|null>(null);
 const [amount,setAmount]=useState("");
 const [error,setError]=useState("");
 const [saved,setSaved]=useState("");
 const [saving,setSaving]=useState(false);
 useEffect(()=>{
  fetch(api+"/policies/project-bonus",{credentials:"include"})
  .then(async r=>{if(!r.ok)throw Error("Cannot read company bonus policy.");return r.json()})
  .then((p:ProjectPolicy)=>{setPolicy(p);setAmount(String(p.default_project_bonus_inr))})
  .catch(err=>setError((err as Error).message));
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
   <div className="policy-guidance"><ShieldCheck size={18}/><p><strong>Priority order:</strong> Project override → Employee bonus → Company policy. For example, set the company default to ₹10,000, optionally set an employee's amount to ₹15,000, and only override an individual project when needed. Existing project bonuses do not change when the policy is updated.</p></div>
   <div className="policy-guidance"><Info size={18}/><p>Leave policies are managed under <strong>Leave requests → Policies & balances</strong>. This is the first centralized company policy screen; additional company policies can be added here later.</p></div>
  </section>
 </div>;
}

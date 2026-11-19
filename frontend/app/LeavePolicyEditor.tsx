"use client";
import React,{useState} from "react";
import AppSelect from "./AppSelect";
import type {EditablePolicy} from "./LeaveWorkspace";

type Props={policy:EditablePolicy;update:React.Dispatch<React.SetStateAction<EditablePolicy>>;save:(event:React.FormEvent)=>void;busy:boolean;isExisting:boolean};
const MONTHS_FIN=["Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec","Jan","Feb","Mar"];
const MONTHS_CAL=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const amount=(n:number)=>Number.isFinite(n)?n:0;
export default function LeavePolicyEditor({policy,update,save,busy,isExisting}:Props){
 const [annualDraft,setAnnualDraft]=useState("22");
 const [previewDate,setPreviewDate]=useState("");
 const [previewOpen,setPreviewOpen]=useState(false);
 const monthly=policy.monthly_schedule!==null||Number(policy.monthly_accrual)>0;
 const months=policy.monthly_schedule||Array.from({length:12},(_,i)=>i>=8?Number(policy.late_year_monthly_accrual||policy.monthly_accrual):Number(policy.monthly_accrual||0));
 const labels=policy.year_type==="financial"?MONTHS_FIN:MONTHS_CAL;
 const total=monthly?months.reduce((x,y)=>x+amount(Number(y)),0):Number(policy.annual_days||0);
 function setMode(mode:"annual"|"monthly"){
  update(prev=>mode==="monthly"?{
   ...prev,annual_days:0,monthly_accrual:0,late_year_monthly_accrual:0,
   monthly_schedule:prev.monthly_schedule||Array.from({length:12},(_,i)=>
    i>=8?Number(prev.late_year_monthly_accrual||prev.monthly_accrual||1.5):Number(prev.monthly_accrual||1.5))
  }:{...prev,monthly_schedule:null,monthly_accrual:0,late_year_monthly_accrual:0,
   annual_days:Number(prev.annual_days||annualDraft||22)});
 }
 function distribute(){
  const desired=Number(annualDraft);
  if(!Number.isFinite(desired)||desired<0||desired>365||Math.round(desired*4)!==desired*4)return;
  const units=Math.round(desired*4),base=Math.floor(units/12),extra=units%12;
  update(prev=>({...prev,annual_days:0,monthly_accrual:0,late_year_monthly_accrual:0,
   monthly_schedule:Array.from({length:12},(_,i)=>(base+(i<extra?1:0))/4)}));
 }
 // This is a UI-only illustration, not a server-calculated entitlement.
 function preview(){
  const d=new Date(previewDate+"T12:00:00");
  if(Number.isNaN(d.getTime()))return null;
  const m=Number(policy.probation_months||0);
  const e=new Date(d.getFullYear(),d.getMonth()+m,Math.min(d.getDate(),
   new Date(d.getFullYear(),d.getMonth()+m+1,0).getDate()));
  const start=policy.year_type==="financial"?(e.getMonth()<3?new Date(e.getFullYear()-1,3,1):new Date(e.getFullYear(),3,1)):new Date(e.getFullYear(),0,1);
  const end=policy.year_type==="financial"?new Date(start.getFullYear()+1,2,31):new Date(e.getFullYear(),11,31);
  if(!policy.probation_allowed&&e>end)return {eligible:e,days:0};
  const eligible=policy.probation_allowed?d:e;
  if(monthly){
   let amountTotal=0;
   for(let i=0;i<12;i++){
    const offset=policy.year_type==="financial"?3:0;
    const monthDate=new Date(start.getFullYear(),offset+i,1);
    const next=new Date(monthDate.getFullYear(),monthDate.getMonth()+1,1);
    const validFrom=new Date(Math.max(monthDate.getTime(),eligible.getTime()));
    const validDays=Math.max(0,(next.getTime()-validFrom.getTime())/86400000);
    const monthDays=(next.getTime()-monthDate.getTime())/86400000;
    amountTotal+=amount(Number(months[i]))*validDays/monthDays;
   }
   return {eligible:e,days:Math.round(amountTotal*2)/2};
  }
  const activeFrom=new Date(Math.max(start.getTime(),eligible.getTime()));
  const ratio=Math.max(0,(end.getTime()-activeFrom.getTime())/86400000+1)/((end.getTime()-start.getTime())/86400000+1);
  return {eligible:e,days:Math.round(total*ratio*2)/2};
 }
 const example=previewOpen&&previewDate?preview():null;
 return <form className="jg-leave-simple-form" onSubmit={save}>
  <div className="jg-leave-step"><strong>1. Leave year</strong><AppSelect value={policy.year_type} disabled={isExisting} onChange={e=>update(p=>({...p,year_type:e.target.value as "financial"|"calendar"}))}><option value="financial">April–March (Financial year)</option><option value="calendar">January–December (Calendar year)</option></AppSelect>{isExisting&&<small>The leave year cannot be changed for an existing policy without a balance migration.</small>}</div>
  <div className="jg-leave-step"><strong>2. How should leave be given?</strong>
   <div className="jg-leave-methods">
    <button type="button" aria-pressed={!monthly} className="jg-leave-method" onClick={()=>setMode("annual")}><strong>Yearly allowance at once</strong><small>Eligible employees receive their prorated yearly leave when probation ends.</small></button>
    <button type="button" aria-pressed={monthly} className="jg-leave-method" onClick={()=>setMode("monthly")}><strong>Add leave each month</strong><small>Choose how many days to credit in each month of the leave year.</small></button>
   </div>
   {!monthly?<label className="jg-leave-small-field">Full-year leave allowance (days)<input required min={0} max={365} step=".25" type="number" value={policy.annual_days} onChange={e=>update(p=>({...p,annual_days:e.target.value}))}/></label>:
    <div className="jg-leave-monthly"><div className="jg-leave-distribute">
     <label>Full-year total to distribute<input type="number" min={0} max={365} step=".25" value={annualDraft} onChange={e=>setAnnualDraft(e.target.value)}/></label>
     <button type="button" className="employee-cancel" onClick={distribute}>Distribute evenly</button>
    </div><div className="jg-leave-month-grid">{labels.map((label,index)=><label key={label}>{label}<input type="number" min={0} max={31} step=".25" required aria-label={label+" monthly leave days"} value={months[index]} onChange={e=>update(p=>({...p,monthly_schedule:months.map((n,i)=>i===index?Number(e.target.value):n),annual_days:0,monthly_accrual:0,late_year_monthly_accrual:0}))}/></label>)}</div></div>}
   <div className="jg-leave-total"><span>Full-year allowance</span><strong>{total.toFixed(2)} days</strong><small>{monthly?"Credited by the monthly schedule shown above":"Given when the employee becomes eligible"}</small></div>
  </div>
  <div className="jg-leave-step"><strong>3. Probation and new joiners</strong>
   <div className="jg-leave-probation"><label>Probation period<AppSelect value={String(policy.probation_months)} onChange={e=>update(p=>({...p,probation_months:Number(e.target.value)}))}>{Array.from({length:13},(_,i)=><option key={i} value={i}>{i===0?"No probation":i+" month"+(i===1?"":"s")}</option>)}</AppSelect></label>
    <label className="leave-inline-check"><input type="checkbox" checked={policy.probation_allowed} onChange={e=>update(p=>({...p,probation_allowed:e.target.checked}))}/> Allow leave during probation</label></div>
   <p className="field-help">{policy.probation_allowed?"Leave is earned from joining and can be requested during probation.":"Leave begins accumulating only after probation ends. The first eligible month is prorated, as is the remaining policy year."}</p>
   <button type="button" className="employee-cancel" onClick={()=>setPreviewOpen(x=>!x)}>{previewOpen?"Hide":"Preview"} new joiner entitlement</button>
   {previewOpen&&<div className="jg-leave-preview"><label>Sample joining date<input type="date" value={previewDate} onChange={e=>setPreviewDate(e.target.value)}/></label>{example&&<p>Probation completion: <b>{example.eligible.toLocaleDateString("en-IN")}</b>. Illustrative prorated entitlement: <b>{example.days.toFixed(2)} days</b>. Actual leave depends on effective policy versions, holidays, credits and balances.</p>}</div>}
  </div>
  <div className="jg-leave-step"><strong>4. Additional rules</strong><div className="jg-leave-rules">
   <label>Carry forward (max days)<input type="number" min={0} max={365} step=".5" value={policy.carry_forward_limit} onChange={e=>update(p=>({...p,carry_forward_limit:e.target.value}))}/></label>
   <label>Approval process<AppSelect value={policy.approval_chain.join(",")} onChange={e=>update(p=>({...p,approval_chain:e.target.value.split(",")}))}><option value="manager">Manager</option><option value="manager,hr">Manager → HR</option><option value="manager,hr,admin">Manager → HR → Admin</option><option value="hr">HR</option><option value="hr,admin">HR → Admin</option></AppSelect></label>
   <label className="leave-inline-check"><input type="checkbox" checked={policy.encashment_allowed} onChange={e=>update(p=>({...p,encashment_allowed:e.target.checked}))}/> Allow encashment</label>
   <label className="leave-inline-check"><input type="checkbox" checked={policy.active} onChange={e=>update(p=>({...p,active:e.target.checked}))}/> Policy active</label>
  </div></div>
  <div className="jg-leave-step"><strong>5. Review and save</strong><div className="jg-leave-rules">
   <label>Effective from<input type="date" required value={policy.effective_from} onChange={e=>update(p=>({...p,effective_from:e.target.value}))}/></label>
   <label>Reason for policy update<textarea required minLength={10} value={policy.change_reason} onChange={e=>update(p=>({...p,change_reason:e.target.value}))} placeholder="Why is the leave policy changing?"/></label>
  </div><p className="field-help">An approval may be required depending on your role. Previous policy versions remain available in the audit history.</p>
   <button className="employee-primary" type="submit" disabled={busy}>{busy?"Saving…":"Save leave policy"}</button>
  </div>
 </form>;
}

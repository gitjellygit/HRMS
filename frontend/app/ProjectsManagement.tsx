"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, BriefcaseBusiness, BadgeCheck, CircleDollarSign, FileText, Plus, RefreshCw, Search, Users, X } from "lucide-react";

type Project={sourced_by_id:number|null;start_date:string|null;bonus_amount_inr:number|null;bonus_eligible_on:string|null;bonus_status:string;id:number;project_number:string|null;name:string;client:string;candidate_name:string;vendor_name:string;prime_vendor_name:string;engagement_type:string|null;rate:number|null;currency:string|null;rate_unit:string|null;description:string;status:string};
type Draft={sourced_by_id:string;start_date:string;bonus_amount_inr:string;name:string;client:string;candidate_name:string;vendor_name:string;prime_vendor_name:string;engagement_type:string;rate:string;currency:string;rate_unit:string;description:string};
type Field=keyof Draft;
const blank:Draft={sourced_by_id:"",start_date:"",bonus_amount_inr:"",name:"",client:"",candidate_name:"",vendor_name:"",prime_vendor_name:"",engagement_type:"c2c",rate:"",currency:"USD",rate_unit:"hour",description:""};
const types=[["c2c","C2C Contract"],["w2","W2 Contract"],["full_time","Full-time Employment"],["contract_1099","1099 Contract"],["fixed_price","Fixed-price Project"]];
const currencies=["USD","INR","CAD","GBP","EUR","AED","SAR"];
function validate(d:Draft):Partial<Record<Field,string>>{
 const errors:Partial<Record<Field,string>>={};
 if(d.name.trim().length<3)errors.name="Project name must contain at least 3 characters.";
 if(d.client.trim().length<2)errors.client="Enter the client name.";
 if(!types.some(t=>t[0]===d.engagement_type))errors.engagement_type="Choose a valid engagement type.";
 if(!d.rate||!Number.isFinite(Number(d.rate))||Number(d.rate)<=0||Number(d.rate)>100000000)errors.rate="Enter a positive project rate.";
 if(!currencies.includes(d.currency))errors.currency="Choose a valid currency.";
 if(!d.sourced_by_id||Number(d.sourced_by_id)<=0)errors.sourced_by_id="Select the employee who sourced the project.";
 if(!d.start_date)errors.start_date="Select the project start date.";
 if(d.bonus_amount_inr!==""&&(!Number.isFinite(Number(d.bonus_amount_inr))||Number(d.bonus_amount_inr)<0))errors.bonus_amount_inr="Enter a valid non-negative INR bonus.";
 if(d.description.length>3000)errors.description="Description must be under 3000 characters.";
 return errors;
}
function serverError(detail:any):{field?:Field;message:string}{
 if(typeof detail==="string")return {message:detail};
 if(detail?.field&&detail?.message)return detail;
 if(Array.isArray(detail)&&detail.length){
  const e=detail[0];return {field:e.loc?.at(-1) as Field,message:String(e.msg||"Invalid field").replace(/^Value error, /,"")};
 }
 return {message:"Unable to save project. Please review the fields."};
}
const money=(project:Project)=>project.rate===null?"Not configured":new Intl.NumberFormat("en-US",{style:"currency",currency:project.currency||"USD",maximumFractionDigits:2}).format(project.rate)+"/"+(project.rate_unit||"hour");
export default function ProjectsManagement({api,canCreate}:{api:string;canCreate:boolean}){
 const [projects,setProjects]=useState<Project[]>([]);
 const [open,setOpen]=useState(false);
 const [draft,setDraft]=useState<Draft>({...blank});
 const [errors,setErrors]=useState<Partial<Record<Field,string>>>({});
 const [number,setNumber]=useState("—");
 const [busy,setBusy]=useState(false);
 const [loading,setLoading]=useState(true);
 const [search,setSearch]=useState("");
 const [filter,setFilter]=useState("all");
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");
 const [bonusPreview,setBonusPreview]=useState<{bonus_amount_inr:number;source:string}|null>(null);
 const [overrideBonus,setOverrideBonus]=useState(false);
 const [employees,setEmployees]=useState<{id:number;name:string;employee_code:string;status:string}[]>([]);
 const [team,setTeam]=useState<{project:Project;people:{name:string}[]}|null>(null);
 const load=useCallback(async()=>{
  setLoading(true);
  try{
   const res=await fetch(api+"/project-management/projects",{credentials:"include"});
   if(!res.ok)throw Error("Unable to load projects.");
   setProjects(await res.json());
  }catch(e){setError((e as Error).message)}finally{setLoading(false)}
 },[api]);
 useEffect(()=>{void load();fetch(api+"/core/employees",{credentials:"include"}).then(r=>r.ok?r.json():[]).then(setEmployees).catch(()=>{});},[load,api]);
 const shown=useMemo(()=>projects.filter(p=>(filter==="all"||p.engagement_type===filter)&&(!search||[p.project_number,p.name,p.client,p.candidate_name,p.vendor_name,p.prime_vendor_name].some(v=>(v||"").toLowerCase().includes(search.toLowerCase())))),[projects,filter,search]);
 async function refreshNumber(){
  try{
   const res=await fetch(api+"/project-management/next-number",{credentials:"include"});
   if(res.ok){const data=await res.json();setNumber(data.project_number)}
  }catch{/* Project number is allocated on save regardless of preview. */}
 }
 function start(){
  setBonusPreview(null);setOverrideBonus(false);setOpen(true);setError("");setNotice("");setDraft({...blank});setErrors({});setNumber("Generating…");void refreshNumber();
 }
 function edit(field:Field,value:string){setDraft(d=>({...d,[field]:value}));setErrors(e=>({...e,[field]:undefined}))}
 async function save(event:React.FormEvent){
  event.preventDefault();
  const found=validate(draft);
  if(overrideBonus&&draft.bonus_amount_inr==="")found.bonus_amount_inr="Enter a bonus or disable the override.";
  setErrors(found);setError("");
  if(Object.keys(found).length){setError("Please fix the highlighted fields.");return}
  setBusy(true);
  try{
   const res=await fetch(api+"/project-management/projects",{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({...draft,name:draft.name.trim(),client:draft.client.trim(),rate:Number(draft.rate),sourced_by_id:Number(draft.sourced_by_id),bonus_amount_inr:overrideBonus?Number(draft.bonus_amount_inr):null})});
   const data=await res.json().catch(()=>({}));
   if(!res.ok){const detail=serverError(data.detail);if(detail.field)setErrors({[detail.field]:detail.message});throw Error(detail.message)}
   setOpen(false);setNotice("Project "+data.project_number+" created successfully.");await load();
  }catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 function field(key:Field,label:string,options?:{required?:boolean;placeholder?:string;type?:string;wide?:boolean}){
  const id="proj-"+key;
  return <div key={key} className={"employee-field "+(options?.wide?"full":"")}>
   <label htmlFor={id}>{label}{options?.required&&<span className="required"> *</span>}</label>
   <input id={id} type={options?.type||"text"} value={draft[key]} placeholder={options?.placeholder} required={options?.required} aria-invalid={!!errors[key]} onChange={e=>edit(key,e.target.value)}/>
   {errors[key]&&<span className="field-error">{errors[key]}</span>}
  </div>;
 }
 async function selectSourcer(value:string){
  edit("sourced_by_id",value);
  setBonusPreview(null);
  setOverrideBonus(false);
  edit("bonus_amount_inr","");
  if(!value)return;
  try{
   const response=await fetch(api+"/project-management/employees/"+value+"/bonus-default",{credentials:"include"});
   if(!response.ok)throw Error("Could not load the employee bonus policy.");
   setBonusPreview(await response.json());
  }catch(e){setError((e as Error).message)}
 }
 async function awardBonus(project:Project){
  if(!window.confirm("Create a planned 30-day milestone bonus of ₹"+Number(project.bonus_amount_inr||0).toLocaleString("en-IN")+" for the sourcing employee?"))return;
  setBusy(true);setError("");
  try{
   const res=await fetch(api+"/project-management/projects/"+project.id+"/award-bonus",{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"}});
   const body=await res.json().catch(()=>({}));
   if(!res.ok)throw Error(typeof body.detail==="string"?body.detail:"Unable to award bonus");
   setNotice("Bonus of ₹"+Number(body.amount_inr).toLocaleString("en-IN")+" created. Awaiting approval/payment.");
   await load();
  }catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 async function showTeam(project:Project){
  try{
   const res=await fetch(api+"/projects/"+project.id+"/team",{credentials:"include"});
   if(!res.ok)throw Error("Could not load assigned employees.");
   setTeam({project,people:await res.json()});
  }catch(e){setError((e as Error).message)}
 }
 return <div className="project-page">
  {error&&<div className="error" role="alert">{error}</div>}
  {notice&&<div className="employee-success" role="status"><BadgeCheck size={18}/>{notice}</div>}
  {!open?<><div className="employee-metrics">
   <div className="employee-metric"><BriefcaseBusiness size={20}/><span>Total projects</span><strong>{projects.length}</strong></div>
   <div className="employee-metric"><BadgeCheck size={20}/><span>Active projects</span><strong>{projects.filter(p=>p.status==="active").length}</strong></div>
   <div className="employee-metric"><CircleDollarSign size={20}/><span>Contract engagements</span><strong>{projects.filter(p=>["c2c","w2","contract_1099"].includes(p.engagement_type||"")).length}</strong></div>
  </div><section className="employee-surface">
   <div className="employee-title-row"><div><h2>Project directory</h2><p>Client engagements, placement details and commercial terms.</p></div>{canCreate&&<button className="employee-primary" onClick={start}><Plus size={16}/> Add project</button>}</div>
   <div className="employee-filters"><div className="employee-search"><Search size={17}/><input aria-label="Search projects" value={search} onChange={e=>setSearch(e.target.value.toLowerCase())} placeholder="Search project, number, client or vendor…"/></div><select aria-label="Filter projects by type" value={filter} onChange={e=>setFilter(e.target.value)}><option value="all">All engagement types</option>{types.map(([value,label])=><option value={value} key={value}>{label}</option>)}</select><button className="employee-icon-button" aria-label="Refresh" onClick={load}><RefreshCw size={17}/></button></div>
   <div className="table-wrap"><table className="project-table"><thead><tr><th>Project</th><th>Client / Candidate</th><th>Engagement</th><th>Rate</th><th>Vendor / Prime vendor</th><th>Sourced by</th><th>30-day bonus</th><th>Status</th><th>Team</th></tr></thead><tbody>{shown.map(p=><tr key={p.id}><td><div className="project-main"><strong>{p.name}</strong><small>{p.project_number||"Legacy project"}</small></div></td><td><strong>{p.client||"—"}</strong><small>{p.candidate_name||"No candidate assigned"}</small></td><td>{types.find(x=>x[0]===p.engagement_type)?.[1]||"—"}</td><td className="project-rate">{money(p)}</td><td><strong>{p.vendor_name||"—"}</strong><small>{p.prime_vendor_name?"Prime: "+p.prime_vendor_name:"No prime vendor"}</small></td><td>{employees.find(e=>e.id===p.sourced_by_id)?.name||"Not assigned"}</td><td><div className="project-bonus"><strong>{p.bonus_amount_inr?"₹"+Number(p.bonus_amount_inr).toLocaleString("en-IN"):"—"}</strong><small>{p.bonus_eligible_on?"Eligible "+p.bonus_eligible_on:"Not configured"} · {p.bonus_status.replace("_"," ")}</small>{canCreate&&p.bonus_status==="eligible"&&<button className="employee-link" disabled={busy} onClick={()=>awardBonus(p)}>Award bonus</button>}</div></td><td><span className={"pill "+p.status}>{p.status}</span></td><td><button className="employee-link" onClick={()=>showTeam(p)}>View team</button></td></tr>)}</tbody></table>{loading?<div className="empty">Loading projects…</div>:!shown.length?<div className="empty">No matching projects found.</div>:null}</div><div className="employee-count">Showing {shown.length} of {projects.length} projects</div>
  </section></>:<section className="employee-surface employee-editor">
   <div className="employee-editor-top"><div><button className="employee-back" onClick={()=>setOpen(false)}><ArrowLeft size={16}/> Project directory</button><h2>Create a project</h2><p>Complete the client and engagement details. Fields marked * are required.</p></div><button className="employee-icon-button" onClick={()=>setOpen(false)} aria-label="Close"><X size={18}/></button></div>
   <form onSubmit={save} noValidate>
    <div className="employee-group"><div className="employee-group-head"><BriefcaseBusiness size={18}/><div><h3>Project information</h3><p>Identify the project and client</p></div></div><div className="employee-form-grid">
      <div className="employee-field"><label>Project number</label><div className="employee-code-row"><input readOnly value={number}/><button type="button" onClick={refreshNumber}><RefreshCw size={14}/> Generate</button></div><span className="field-help">Unique number assigned when saved; preview may change.</span></div>
      {field("name","Project name",{required:true,placeholder:"e.g. Java Modernization"})}
      {field("client","Client name",{required:true,placeholder:"e.g. Acme Corporation"})}
      {field("candidate_name","Candidate name",{placeholder:"e.g. Employee or consultant name"})}
      <div className="employee-field"><label htmlFor="proj-sourced">Sourced by employee <span className="required">*</span></label><select id="proj-sourced" value={draft.sourced_by_id} aria-invalid={!!errors.sourced_by_id} onChange={e=>void selectSourcer(e.target.value)}><option value="">Select employee</option>{employees.filter(e=>e.status==="active").map(e=><option key={e.id} value={e.id}>{e.name} · {e.employee_code||e.id}</option>)}</select>{errors.sourced_by_id&&<span className="field-error">{errors.sourced_by_id}</span>}</div>
      {field("start_date","Project start date",{type:"date",required:true})}
      <div className="employee-field">
       <label>30-day sourcing bonus (INR)</label>
       <div className="project-auto-bonus"><strong>{bonusPreview?"₹"+bonusPreview.bonus_amount_inr.toLocaleString("en-IN"):"Select a sourcing employee"}</strong><span>{bonusPreview?.source==="employee"?"Employee-specific default":"Company policy default"}</span></div>
       <label className="project-override-check"><input type="checkbox" checked={overrideBonus} onChange={e=>{setOverrideBonus(e.target.checked);edit("bonus_amount_inr","")}}/> Override bonus for this project</label>
       {overrideBonus&&<input aria-label="Override amount in INR" type="number" min="0" step="0.01" value={draft.bonus_amount_inr} onChange={e=>edit("bonus_amount_inr",e.target.value)} placeholder="Override bonus amount in INR"/>}
       {errors.bonus_amount_inr&&<span className="field-error">{errors.bonus_amount_inr}</span>}
       <span className="field-help">Without an override, the API uses the employee default, then company policy.</span>
      </div>
      <div className="employee-field"><label>Bonus milestone</label><p className="field-help">Eligible after 30 calendar days from the start date. HR awards it once eligible; payout follows bonus approval.</p></div>
    </div></div>
    <div className="employee-group"><div className="employee-group-head"><Users size={18}/><div><h3>Vendor information</h3><p>Commercial relationships for this engagement</p></div></div><div className="employee-form-grid">
      {field("vendor_name","Vendor name",{placeholder:"Vendor company"})}
      {field("prime_vendor_name","Prime vendor name",{placeholder:"Prime vendor company"})}
    </div></div>
    <div className="employee-group"><div className="employee-group-head"><CircleDollarSign size={18}/><div><h3>Engagement & billing</h3><p>Contract classification and project rate</p></div></div><div className="employee-form-grid">
      <div className="employee-field"><label htmlFor="proj-type">Engagement type <span className="required">*</span></label><select id="proj-type" value={draft.engagement_type} onChange={e=>{const type=e.target.value;setDraft(d=>({...d,engagement_type:type,rate_unit:type==="full_time"?"year":type==="fixed_price"?"project":"hour"}))}}>{types.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></div>
      {field("rate","Project rate",{required:true,type:"number",placeholder:"e.g. 75.00"})}
      <div className="employee-field"><label>Currency</label><select value={draft.currency} onChange={e=>edit("currency",e.target.value)}>{currencies.map(c=><option key={c}>{c}</option>)}</select></div>
      <div className="employee-field"><label>Rate basis</label><select value={draft.rate_unit} onChange={e=>edit("rate_unit",e.target.value)}>{["hour","day","month","year","project"].map(x=><option key={x} value={x}>Per {x}</option>)}</select></div>
    </div></div>
    <div className="employee-group"><div className="employee-group-head"><FileText size={18}/><div><h3>Description</h3><p>Optional scope and engagement notes</p></div></div><div className="employee-field"><label htmlFor="proj-description">Project description</label><textarea id="proj-description" rows={3} value={draft.description} maxLength={3000} placeholder="Briefly describe the work, project scope and responsibilities…" onChange={e=>edit("description",e.target.value)}/><span className="field-help">{draft.description.length}/3000 characters</span></div></div>
    <div className="employee-form-footer"><button type="button" className="employee-cancel" onClick={()=>setOpen(false)}>Cancel</button><button className="employee-primary" disabled={busy}>{busy?"Saving…":"Save project"}</button></div>
   </form>
  </section>}
  {team&&<div className="employee-modal-backdrop"><div className="employee-modal" role="dialog" aria-modal="true" aria-label={"Assigned team for "+team.project.name}><div className="employee-title-row"><div><h2>{team.project.name}</h2><p>Assigned team members</p></div><button className="employee-icon-button" onClick={()=>setTeam(null)} aria-label="Close"><X size={18}/></button></div>{team.people.length?<div className="project-team-list">{team.people.map((p,i)=><div key={i}>{p.name}</div>)}</div>:<p className="muted">No team members assigned.</p>}</div></div>}
 </div>;
}

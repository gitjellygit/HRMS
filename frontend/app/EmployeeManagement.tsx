"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, BadgeCheck, BriefcaseBusiness, FileUp, IdCard, Plus, RefreshCw, Search, ShieldCheck, Users, X } from "lucide-react";

type Employee = {
 id:number; employee_code:string; name:string; email:string; designation:string; department:string;
 role:string; status:string; joining_date:string; phone:string;
};
type EmployeeDraft = {
 name:string;email:string;password:string;designation:string;department:string;role:string;
 phone:string;joining_date:string;employee_code:string;work_location:string;
 employment_type:string;manager_name:string;emergency_contact:string;
};
type Field = keyof EmployeeDraft;
type Errors=Partial<Record<Field,string>>;
const blank:EmployeeDraft={
 name:"",email:"",password:"",designation:"",department:"",role:"employee",phone:"",
 joining_date:new Date().toLocaleDateString("en-CA"),employee_code:"",work_location:"",
 employment_type:"Full time",manager_name:"",emergency_contact:""
};
const EMAIL=/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const validate=(data:EmployeeDraft):Errors=>{
 const errors:Errors={};
 if(!/^[A-Za-z][A-Za-z .'-]*$/.test(data.name.trim())||data.name.trim().split(/\s+/).length<2)errors.name="Enter both first and last name using letters.";
 if(!EMAIL.test(data.email.trim()))errors.email="Enter a valid work email, e.g. name@jellygit.com.";
 if(data.password.length<12||!/[A-Z]/.test(data.password)||!/[a-z]/.test(data.password)||!/[0-9]/.test(data.password)||!/[^A-Za-z0-9]/.test(data.password))errors.password="Use 12+ characters with uppercase, lowercase, number and special character.";
 if(data.designation.trim().length<2)errors.designation="Designation must contain at least 2 characters.";
 if(data.department.trim().length<2)errors.department="Select or enter a department.";
 if(!data.joining_date)errors.joining_date="Choose the date of joining.";
 if(data.phone&&!/^\+?[0-9 ()-]{7,30}$/.test(data.phone))errors.phone="Enter a valid contact number.";
 return errors;
};
const initials=(name:string)=>name.trim().split(/\s+/).map(n=>n[0]).slice(0,2).join("").toUpperCase();
function ApiError(detail:unknown):{field?:Field;message:string}{
 if(typeof detail==="string")return {message:detail};
 if(detail&&typeof detail==="object"){
  const info=detail as {field?:Field;message?:string;detail?:unknown};
  if(info.message)return {field:info.field,message:info.message};
  if(Array.isArray(detail)){
   const item=detail[0] as {loc?:string[];msg?:string};
   if(item?.loc?.length)return {field:item.loc[item.loc.length-1] as Field,message:(item.msg||"Invalid field").replace(/^Value error, /i,"")};
  }
 }
 return {message:"Unable to save employee. Please check the highlighted fields."};
}
export default function EmployeeManagement({api,canCreate,onOpenEmployee,currentRole}:{api:string;canCreate:boolean;onOpenEmployee?:(id:number)=>void;currentRole?:string}){
 const [employees,setEmployees]=useState<Employee[]>([]);
 const [loading,setLoading]=useState(true);
 const [saving,setSaving]=useState(false);
 const [open,setOpen]=useState(false);
 const [draft,setDraft]=useState<EmployeeDraft>(blank);
 const [errors,setErrors]=useState<Errors>({});
 const [message,setMessage]=useState("");
 const [failure,setFailure]=useState("");
 const [search,setSearch]=useState("");
 const [department,setDepartment]=useState("all");
 const [showPassword,setShowPassword]=useState(false);
 const [document,setDocument]=useState<File|null>(null);
 const [master,setMaster]=useState<Record<string,string>>({});
 const [units,setUnits]=useState<{id:number;kind:string;name:string;code:string}[]>([]);
 const [docsFor,setDocsFor]=useState<Employee|null>(null);
 const [documents,setDocuments]=useState<{id:number;name:string;type:string}[]>([]);
 const [docError,setDocError]=useState("");
 const load=useCallback(async()=>{
  setLoading(true);
  try{
   const response=await fetch(api+"/employees",{credentials:"include"});
   if(!response.ok)throw Error("Could not load employees. Try refreshing.");
   setEmployees(await response.json());
  }catch(err){setFailure((err as Error).message)}finally{setLoading(false)}
 },[api]);
 useEffect(()=>{void load();fetch(api+"/core/units",{credentials:"include"}).then(r=>r.ok?r.json():[]).then(setUnits).catch(()=>{});},[load,api]);
 const departments=useMemo(()=>[...new Set(employees.map(e=>e.department).filter(Boolean))].sort(),[employees]);
 const shown=useMemo(()=>employees.filter(e=>{
  const term=search.toLowerCase().trim();
  return (department==="all"||e.department===department)&&(!term||[e.name,e.email,e.employee_code,e.designation,e.department].some(v=>(v||"").toLowerCase().includes(term)));
 }),[employees,department,search]);
 function edit(field:Field,value:string){
  setDraft(d=>({...d,[field]:value}));
  setErrors(prev=>({...prev,[field]:undefined}));
 }
 async function openForm(){
  setDraft({...blank,joining_date:new Date().toLocaleDateString("en-CA")});
  setErrors({});setFailure("");setMessage("");setDocument(null);setMaster({});setOpen(true);
  try{
   const response=await fetch(api+"/employees/next-code",{credentials:"include"});
   if(response.ok){const data=await response.json();setDraft(d=>({...d,employee_code:data.employee_code}))}
  }catch{/* Preview is optional: the backend allocates the authoritative ID on save. */}
 }
 async function generateCode(){
  try{
   const response=await fetch(api+"/employees/next-code",{credentials:"include"});
   if(!response.ok)throw Error("Unable to preview the next ID");
   const data=await response.json();
   edit("employee_code",data.employee_code);
  }catch(err){setFailure((err as Error).message)}
 }
 async function submit(event:React.FormEvent<HTMLFormElement>){
  event.preventDefault();
  const found=validate(draft);setErrors(found);setFailure("");setMessage("");
  if(Object.keys(found).length){setFailure("Please correct the highlighted fields before saving.");return;}
  setSaving(true);
  try{
   const {employee_code,...payload}=draft;
   const chosen:Record<string,unknown>={};
   for(const [key,value] of Object.entries(master)){if(!value)continue;chosen[key]=key.endsWith("_id")?Number(value):value}
   const response=await fetch(api+"/core/employees",{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({account:{...payload,name:draft.name.trim(),email:draft.email.trim().toLowerCase(),designation:draft.designation.trim(),department:draft.department.trim()},master:chosen})});
   const result=await response.json().catch(()=>({}));
   if(!response.ok){
    const detail=ApiError(result.detail);
    if(detail.field)setErrors({[detail.field]:detail.message});
    throw Error(detail.message);
   }
   let note=`${result.name} added successfully as ${result.employee_code}.`;
   if(document){
    const body=new FormData();body.append("document",document);
    const uploaded=await fetch(api+"/core/employees/"+result.id+"/documents",{method:"POST",credentials:"include",body});
    if(!uploaded.ok)note+=" Employee saved, but document upload failed; upload it separately.";
   }
   setOpen(false);setMessage(note);await load();
  }catch(err){setFailure((err as Error).message)}finally{setSaving(false)}
 }
 async function viewDocuments(employee:Employee){
  setDocsFor(employee);setDocuments([]);setDocError("");
  try{
   const response=await fetch(api+"/employees/"+employee.id+"/documents",{credentials:"include"});
   if(!response.ok)throw Error("Unable to retrieve documents.");
   setDocuments(await response.json());
  }catch(err){setDocError((err as Error).message)}
 }
 async function downloadFile(id:number,name:string){
  try{
   const res=await fetch(api+"/documents/"+id,{credentials:"include"});
   if(!res.ok)throw Error("Download denied or file unavailable.");
   const url=URL.createObjectURL(await res.blob());
   const anchor=window.document.createElement("a");anchor.href=url;anchor.download=name;anchor.click();
   URL.revokeObjectURL(url);
  }catch(err){setDocError((err as Error).message)}
 }
 function field(key:Field,label:string,options?:{required?:boolean;type?:string;hint?:string;placeholder?:string;choices?:string[];wide?:boolean}){
  const id="emp-"+key;
  const invalid=Boolean(errors[key]);
  return <div key={key} className={"employee-field "+(options?.wide?"full":"")}>
   <label htmlFor={id}>{label}{options?.required&&<span className="required"> *</span>}</label>
   {options?.choices?<select id={id} value={draft[key]} onChange={e=>edit(key,e.target.value)} aria-invalid={invalid} aria-describedby={invalid?id+"-error":undefined}>
    {options.choices.map(choice=><option key={choice} value={choice}>{choice==="employee"?"Employee":choice==="hr"?"HR Admin":choice==="accountant"?"Accountant":choice==="admin"?"Admin":choice}</option>)}
   </select>:<input id={id} value={draft[key]} type={options?.type||"text"} maxLength={key==="password"?128:undefined}
    placeholder={options?.placeholder} onChange={e=>edit(key,e.target.value)} aria-invalid={invalid} aria-describedby={invalid?id+"-error":undefined} autoComplete={key==="password"?"new-password":"off"}/>}
   {invalid?<span id={id+"-error"} className="field-error">{errors[key]}</span>:options?.hint?<span className="field-help">{options.hint}</span>:null}
  </div>;
 }
 return <div className="employee-page">
  {failure&&!open&&<div className="error" role="alert">{failure}</div>}
  {message&&<div className="employee-success" role="status"><BadgeCheck size={18}/>{message}</div>}
  {!open?<><div className="employee-metrics">
   <div className="employee-metric"><Users size={20}/><span>Total employees</span><strong>{employees.length}</strong></div>
   <div className="employee-metric"><BadgeCheck size={20}/><span>Active employees</span><strong>{employees.filter(e=>e.status==="active").length}</strong></div>
   <div className="employee-metric"><BriefcaseBusiness size={20}/><span>Departments</span><strong>{departments.length}</strong></div>
  </div>
  <section className="employee-surface">
   <div className="employee-title-row"><div><h2>Employee directory</h2><p>All employee records, in one organized place.</p></div>{canCreate&&<button className="employee-primary" onClick={openForm}><Plus size={17}/> Add employee</button>}</div>
   <div className="employee-filters"><div className="employee-search"><Search size={17}/><input aria-label="Search employees" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search by name, ID, email or role…"/></div><select aria-label="Filter by department" value={department} onChange={e=>setDepartment(e.target.value)}><option value="all">All departments</option>{departments.map(d=><option key={d}>{d}</option>)}</select><button className="employee-icon-button" onClick={load} title="Refresh employees" aria-label="Refresh"><RefreshCw size={17}/></button></div>
   <div className="table-wrap"><table className="employee-table"><thead><tr><th>Employee</th><th>Employee ID</th><th>Designation / Department</th><th>Access</th><th>Joined</th><th>Status</th>{canCreate&&<th>Documents</th>}</tr></thead><tbody>
    {shown.map(e=><tr key={e.id}><td><div className="employee-person"><div className="employee-avatar">{initials(e.name)}</div><div><button type="button" className="employee-name-link" onClick={()=>onOpenEmployee?.(e.id)}>{e.name}</button><small>{e.email}</small></div></div></td><td><span className="employee-id">{e.employee_code||"Legacy"}</span></td><td><strong className="employee-detail">{e.designation||"—"}</strong><small className="employee-secondary">{e.department||"—"}</small></td><td><span className="employee-role">{e.role==="hr"?"HR Admin":e.role}</span></td><td>{e.joining_date||"—"}</td><td><span className={"pill "+e.status}>{e.status}</span></td>{canCreate&&<td><button className="employee-link" onClick={()=>viewDocuments(e)}>View files</button></td>}</tr>)}
   </tbody></table>{loading?<div className="empty">Loading employee directory…</div>:!shown.length?<div className="employee-empty">No employees match your search.</div>:null}</div>
   <div className="employee-count">Showing {shown.length} of {employees.length} employees</div>
  </section></>:<section className="employee-surface employee-editor">
   <div className="employee-editor-top"><div><button className="employee-back" onClick={()=>{setOpen(false);setFailure("")}}><ArrowLeft size={16}/> Employee directory</button><h2>Add a new employee</h2><p>Create a secure account and complete the employee's profile.</p></div><button className="employee-icon-button" aria-label="Cancel" onClick={()=>setOpen(false)}><X size={20}/></button></div>
   {failure&&<div id="employee-first-error" className="error" role="alert">{failure}</div>}
   <form onSubmit={submit} noValidate>
    <div className="employee-group"><div className="employee-group-head"><IdCard size={18}/><div><h3>Personal information</h3><p>Basic employee and contact details</p></div></div>
     <div className="employee-form-grid">
      {field("name","Full name",{required:true,placeholder:"e.g. Aarav Sharma"})}
      {field("email","Work email",{required:true,type:"email",placeholder:"aarav@jellygit.com"})}
      {field("phone","Phone number",{placeholder:"+91 98765 43210"})}
      {field("emergency_contact","Emergency contact",{placeholder:"Name and contact number"})}
     </div>
    </div>
    <div className="employee-group"><div className="employee-group-head"><BriefcaseBusiness size={18}/><div><h3>Employment details</h3><p>Assign employee information, reporting hierarchy and access</p></div></div>
     <div className="employee-form-grid">
      <div className="employee-field"><label htmlFor="employee-code">Employee ID</label><div className="employee-code-row"><input id="employee-code" readOnly value={draft.employee_code||"Generating…"} aria-label="Generated employee ID"/><button type="button" onClick={generateCode}><RefreshCw size={15}/> Generate ID</button></div><span className="field-help">Preview only. The final unique ID is assigned when saved.</span></div>
      {field("joining_date","Date of joining",{required:true,type:"date"})}
      {field("designation","Designation",{required:true,placeholder:"e.g. Software Engineer"})}
      {field("department","Department",{required:true,placeholder:"e.g. Engineering"})}
      {field("employment_type","Employment type",{choices:["Full time","Part time","Contract","Intern"]})}
      {field("role","System access",{choices:currentRole==="admin"||currentRole==="super_admin"?["employee","manager","hr","accountant","super_admin"]:["employee","manager","hr","accountant"]})}
      {field("work_location","Work location",{placeholder:"e.g. Noida · Hybrid"})}
      <div className="employee-field"><label htmlFor="core-manager">Reporting manager</label><select id="core-manager" value={master.manager_id||""} onChange={e=>setMaster(v=>({...v,manager_id:e.target.value}))}><option value="">No reporting manager</option>{employees.filter(e=>e.status==="active").map(e=><option key={e.id} value={e.id}>{e.name} · {e.employee_code||e.id}</option>)}</select><span className="field-help">Used for future approval routing</span></div>
      <div className="employee-field"><label htmlFor="core-hod">Second-level manager / HOD</label><select id="core-hod" value={master.hod_id||""} onChange={e=>setMaster(v=>({...v,hod_id:e.target.value}))}><option value="">Optional HOD</option>{employees.filter(e=>e.status==="active").map(e=><option key={e.id} value={e.id}>{e.name}</option>)}</select></div>
      {(["department","designation","grade","branch","cost_center"] as const).map(kind=><div key={kind} className="employee-field"><label htmlFor={"org-"+kind}>{kind.replace("_"," ").replace(/^./,c=>c.toUpperCase())} unit</label><select id={"org-"+kind} value={master[kind+"_id"]||""} onChange={e=>{const selected=units.find(u=>String(u.id)===e.target.value);setMaster(v=>({...v,[kind+"_id"]:e.target.value}));if(selected&&(kind==="department"||kind==="designation"))edit(kind,selected.name)}}><option value="">Not assigned</option>{units.filter(u=>u.kind===kind).map(u=><option key={u.id} value={u.id}>{u.name} ({u.code})</option>)}</select></div>)}
     </div>
    </div>
    <div className="employee-group"><div className="employee-group-head"><BriefcaseBusiness size={18}/><div><h3>Project incentive policy</h3><p>Leave blank to inherit the company default on every sourced project</p></div></div><div className="employee-form-grid"><div className="employee-field"><label htmlFor="emp-project-bonus">Bonus per sourced project (INR)</label><input id="emp-project-bonus" type="number" min="0" max="100000000" step="0.01" value={master.project_bonus_inr||""} onChange={e=>setMaster(m=>({...m,project_bonus_inr:e.target.value}))} placeholder="Company policy default (₹10,000)"/><span className="field-help">HR-managed, per-project milestone bonus. Optional employee-specific amount; blank inherits Policies.</span></div></div></div>
    <div className="employee-group"><div className="employee-group-head"><ShieldCheck size={18}/><div><h3>Account security</h3><p>Only HR/Admin can create an employee login</p></div></div>
     <div className="employee-form-grid">
      {field("password","Temporary password",{required:true,type:showPassword?"text":"password",placeholder:"Create a strong password",hint:"At least 12 characters, uppercase, lowercase, number and symbol."})}
      <div className="employee-field employee-security-note"><label>Access guidelines</label><p>Only grant HR or Admin access when required. Ask the employee to reset their temporary password after first login.</p><button type="button" className="employee-link" onClick={()=>setShowPassword(!showPassword)}>{showPassword?"Hide":"Show"} password</button></div>
     </div>
    </div>
    <div className="employee-group"><div className="employee-group-head"><FileUp size={18}/><div><h3>Employee documents</h3><p>Optional initial document for this account</p></div></div>
     <div className="employee-field employee-upload"><label htmlFor="employee-document">Upload a document (PDF, PNG, JPG · max 5 MB)</label><input id="employee-document" type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={e=>setDocument(e.target.files?.[0]||null)}/>{document&&<span className="field-help">{document.name}</span>}</div>
    </div>
    <div className="employee-form-footer"><button type="button" className="employee-cancel" onClick={()=>{setOpen(false);setFailure("")}}>Cancel</button><button className="employee-primary" disabled={saving}>{saving?"Creating employee…":"Save employee"}</button></div>
   </form>
  </section>}
  {docsFor&&<div className="employee-modal-backdrop" role="presentation"><div className="employee-modal" role="dialog" aria-modal="true" aria-label={"Documents for "+docsFor.name}><div className="employee-title-row"><div><h2>{docsFor.name}</h2><p>Employee documents</p></div><button className="employee-icon-button" onClick={()=>setDocsFor(null)} aria-label="Close"><X size={20}/></button></div>{docError&&<div className="error">{docError}</div>}{!documents.length?<p className="muted">No documents on file.</p>:documents.map(doc=><div key={doc.id} className="employee-doc"><span>{doc.name}</span><button className="employee-link" onClick={()=>downloadFile(doc.id,doc.name)}>Download</button></div>)}</div></div>}
 </div>;
}

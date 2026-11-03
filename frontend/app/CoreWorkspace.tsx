"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowLeft, BadgeCheck, Building2, CalendarClock, Check, Download, FileDown, FilePlus2, GitBranch, LockKeyhole, Search, ShieldCheck, Upload, UserRound, Users, X } from "lucide-react";

type Person = {id:number;name:string;email:string;employee_code?:string;designation:string;department:string;role:string;status:string;phone?:string;joining_date?:string};
type Unit={id:number;kind:string;name:string;code:string};
type Core={manager_id?:number|null;hod_id?:number|null;department_id?:number|null;designation_id?:number|null;grade_id?:number|null;branch_id?:number|null;cost_center_id?:number|null;date_of_birth?:string|null;personal_email?:string|null;address?:string;emergency_name?:string;emergency_phone?:string;bank_account?:string;bank_ifsc?:string;pan?:string;aadhaar?:string;uan?:string;lifecycle?:string};
type RecordType=Person&{master:Core};
type Change={id:number;employee_id:number;field:string;status:string;requested_at:string;value:string};
type Doc={id:number;name:string;category:string;type:string;expiry_date?:string|null};
type History={event:string;note:string;date:string;by:number};
type ChartNode={id:number;name:string;code:string;designation:string;department:string;manager_id:number|null};
type Mode="profile"|"organization"|"orgchart"|"approvals"|"bulk";
const sensitive=["bank_account","bank_ifsc","pan","aadhaar","uan"];
const categories=[["offer_letter","Offer letter"],["id_proof","ID proof"],["certificate","Certificate"],["contract","Contract"],["other","Other"]];
const kinds:[string,string][]=[["department","Departments"],["designation","Designations"],["grade","Grades"],["branch","Branches"],["cost_center","Cost centers"]];
const fields:[keyof Core,string][]=[["date_of_birth","Date of birth"],["personal_email","Personal email"],["address","Residential address"],["emergency_name","Emergency contact name"],["emergency_phone","Emergency contact number"],["bank_account","Bank account number"],["bank_ifsc","IFSC code"],["pan","PAN"],["aadhaar","Aadhaar"],["uan","UAN"]];
const changes=["personal_email","address","emergency_name","emergency_phone","date_of_birth","bank_account","bank_ifsc","pan","aadhaar","uan"];
function errorText(value:any){
 const detail=value?.detail||value;
 if(typeof detail==="string")return detail;
 if(typeof detail?.message==="string")return detail.message;
 if(Array.isArray(detail)&&detail.length)return detail.map((v:any)=>(v.loc?.slice(-1)[0]||"Field")+": "+String(v.msg||"Invalid value").replace(/^Value error, /,"")).join("; ");
 return "Request could not be completed. Please check the information.";
}
export default function CoreWorkspace({api,mode,user,employeeId,onBack}:{api:string;mode:Mode;user:Person;employeeId?:number|null;onBack?:()=>void}){
 const isHR=["super_admin","admin","hr"].includes(user.role);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [success,setSuccess]=useState("");
 const [person,setPerson]=useState<RecordType|null>(null);
 const [draft,setDraft]=useState<Core>({});
 const [people,setPeople]=useState<Person[]>([]);
 const [units,setUnits]=useState<Unit[]>([]);
 const [documents,setDocuments]=useState<Doc[]>([]);
 const [alerts,setAlerts]=useState<(Doc&{employee_id:number;document_id:number})[]>([]);
 const [history,setHistory]=useState<History[]>([]);
 const [changeRequests,setChangeRequests]=useState<Change[]>([]);
 const [chart,setChart]=useState<ChartNode[]>([]);
 const [unitKind,setUnitKind]=useState("department");
 const [unitName,setUnitName]=useState("");
 const [unitCode,setUnitCode]=useState("");
 const [eventType,setEventType]=useState("confirmed");
 const [eventNote,setEventNote]=useState("");
 const [category,setCategory]=useState("other");
 const [expiry,setExpiry]=useState("");
 const [document,setDocument]=useState<File|null>(null);
 const [selectedFile,setSelectedFile]=useState<File|null>(null);
 const [preview,setPreview]=useState<{valid:boolean;row_count:number;errors:{row:number;error:string}[];created:number;note?:string}|null>(null);
 const [changeField,setChangeField]=useState("personal_email");
 const [changeValue,setChangeValue]=useState("");
 const [search,setSearch]=useState("");
 const target=employeeId||user.id;
 const apiCall=useCallback(async(path:string,init?:RequestInit)=>{
  const response=await fetch(api+path,{credentials:"include",...init});
  const payload=await response.json().catch(()=>({}));
  if(!response.ok)throw Error(errorText(payload));
  return payload;
 },[api]);
 const reload=useCallback(async()=>{
  setError("");
  try{
   if(mode==="profile"){
    const record=await apiCall("/core/employees/"+target);
    setPerson(record);setDraft(record.master||{});
    const [docs,events]=await Promise.all([apiCall("/core/employees/"+target+"/documents"),apiCall("/core/employees/"+target+"/lifecycle")]);
    setDocuments(docs);setHistory(events);
   }
   if(mode==="organization"){setUnits(await apiCall("/core/units"));}
   if(mode==="orgchart"){setChart(await apiCall("/core/org-chart"));}
   if(mode==="approvals"){const [requests,staff]=await Promise.all([apiCall("/core/changes"),isHR?apiCall("/core/employees"):Promise.resolve([])]);setChangeRequests(requests);setPeople(staff);}
   if(mode==="bulk"){setAlerts(await apiCall("/core/document-alerts"));}
   if(mode==="profile"){
    const [staff,org]=await Promise.all([isHR?apiCall("/core/employees"):Promise.resolve([]),apiCall("/core/units")]);
    setPeople(staff);setUnits(org);
   }
  }catch(err){setError((err as Error).message)}
 },[mode,target,apiCall,isHR]);
 useEffect(()=>{void reload()},[reload]);
 async function run(task:()=>Promise<void>){
  setBusy(true);setError("");setSuccess("");
  try{await task()}catch(err){setError((err as Error).message)}finally{setBusy(false)}
 }
 async function createUnit(event:React.FormEvent){
  event.preventDefault();
  await run(async()=>{
   await apiCall("/core/units",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({kind:unitKind,name:unitName.trim(),code:unitCode.trim()})});
   setUnitName("");setUnitCode("");setSuccess("Organization unit created.");await reload();
  });
 }
 async function saveMaster(event:React.FormEvent){
  event.preventDefault();
  await run(async()=>{
   const payload:Record<string,unknown>={...draft};
   for(const key of sensitive){if(!payload[key]||String(payload[key]).includes("•"))payload[key]=""}
   for(const key of ["manager_id","hod_id","department_id","designation_id","grade_id","branch_id","cost_center_id"]){payload[key]=payload[key]?Number(payload[key]):null}
   if(!payload.date_of_birth)payload.date_of_birth=null;
   if(!payload.personal_email)payload.personal_email=null;
   await apiCall("/core/employees/"+target,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
   setSuccess("Employee master record updated.");await reload();
  });
 }
 async function submitChange(event:React.FormEvent){
  event.preventDefault();
  await run(async()=>{
   await apiCall("/core/me/change-requests",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({field_name:changeField,value:changeValue})});
   setChangeValue("");setSuccess("Your profile update request has been sent to HR.");
  });
 }
 async function review(id:number,approve:boolean){
  await run(async()=>{
   await apiCall("/core/changes/"+id+"/review",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({approve})});
   setSuccess(approve?"Change approved.":"Change rejected.");await reload();
  });
 }
 async function lifecycle(event:React.FormEvent){
  event.preventDefault();
  await run(async()=>{
   await apiCall("/core/employees/"+target+"/lifecycle",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({event:eventType,note:eventNote,effective_date:new Date().toISOString().slice(0,10)})});
   setSuccess("Employee lifecycle event recorded.");setEventNote("");await reload();
  });
 }
 async function upload(event:React.FormEvent){
  event.preventDefault();
  if(!document){setError("Choose a document to upload.");return}
  await run(async()=>{
   const params=new URLSearchParams({category});if(expiry)params.set("expiry_date",expiry);
   const form=new FormData();form.set("document",document);
   const response=await fetch(api+"/core/employees/"+target+"/documents?"+params,{method:"POST",credentials:"include",body:form});
   const result=await response.json().catch(()=>({}));
   if(!response.ok)throw Error(errorText(result));
   setDocument(null);setExpiry("");setSuccess("Document uploaded securely.");await reload();
  });
 }
 async function downloadDoc(doc:Doc){
  await run(async()=>{
   const response=await fetch(api+"/documents/"+doc.id,{credentials:"include"});
   if(!response.ok)throw Error("Document download was denied.");
   const link=URL.createObjectURL(await response.blob());
   const a=window.document.createElement("a");a.href=link;a.download=doc.name;a.click();
   URL.revokeObjectURL(link);
  });
 }
 async function exportFile(format:"csv"|"xlsx"){
  await run(async()=>{
   const response=await fetch(api+"/core/employees-export?format="+format,{credentials:"include"});
   if(!response.ok)throw Error("Unable to export employees");
   const objectUrl=URL.createObjectURL(await response.blob());
   const a=window.document.createElement("a");a.href=objectUrl;a.download="jellygit-employees."+format;a.click();
   URL.revokeObjectURL(objectUrl);
  });
 }
 async function importFile(dryRun:boolean){
  if(!selectedFile){setError("Choose a CSV or XLSX file.");return}
  await run(async()=>{
   const form=new FormData();form.set("document",selectedFile);
   const response=await fetch(api+"/core/employees-import?dry_run="+dryRun,{method:"POST",credentials:"include",body:form});
   const result=await response.json();
   if(!response.ok)throw Error(errorText(result));
   setPreview(result);
   if(result.created){setSuccess(result.created+" employee accounts imported.");setSelectedFile(null)}
  });
 }
 const managerLabels=useMemo(()=>Object.fromEntries(people.map(p=>[p.id,p.name+" · "+(p.employee_code||p.email)])),[people]);
 function input(field:keyof Core,label:string,type="text"){
  return <label key={field} className="core-label">{label}<input type={type} value={String(draft[field]||"")} onChange={e=>setDraft(d=>({...d,[field]:e.target.value}))} disabled={!isHR}/></label>;
 }
 function selectRelation(field:keyof Core,label:string,options:{id:number;name:string}[]){
  return <label key={field} className="core-label">{label}<select value={String(draft[field]||"")} disabled={!isHR} onChange={e=>setDraft(d=>({...d,[field]:e.target.value?Number(e.target.value):null}))}><option value="">Not assigned</option>{options.map(v=><option key={v.id} value={v.id}>{v.name}</option>)}</select></label>;
 }
 function renderOrgTree(){
  const children=new Map<number|null,ChartNode[]>();
  const ids=new Set(chart.map(n=>n.id));
  chart.forEach(node=>{const parent=node.manager_id&&ids.has(node.manager_id)?node.manager_id:null;children.set(parent,[...(children.get(parent)||[]),node])});
  function branch(parent:number|null,visited:Set<number>,depth:number):React.ReactNode{
   return (children.get(parent)||[]).map(node=><div className="core-org-node" key={node.id}><div className="core-org-person"><div className="employee-avatar">{node.name.split(" ").map(n=>n[0]).slice(0,2).join("")}</div><div><strong>{node.name}</strong><span>{node.designation||"—"} · {node.department||"Unassigned"} · {node.code||"Legacy"}</span></div></div>{depth<15&&!visited.has(node.id)&&<div className="core-org-children">{branch(node.id,new Set([...visited,node.id]),depth+1)}</div>}</div>);
  }
  return <div className="core-org-tree">{branch(null,new Set(),0)}</div>;
 }
 return <div className="core-workspace">
  {onBack&&<button type="button" className="employee-back" onClick={onBack}><ArrowLeft size={15}/> Employee directory</button>}
  {error&&<div className="error" role="alert">{error}</div>}
  {success&&<div className="employee-success" role="status"><BadgeCheck size={17}/>{success}</div>}
  {mode==="organization"&&<section className="employee-surface"><header className="core-head"><Building2 size={21}/><div><h2>Organization structure</h2><p>Manage departments, designations, grades, branches and cost centers.</p></div></header>
   {isHR&&<form className="core-inline-form" onSubmit={createUnit}><select value={unitKind} onChange={e=>setUnitKind(e.target.value)}>{kinds.map(([key,label])=><option key={key} value={key}>{label}</option>)}</select><input value={unitName} onChange={e=>setUnitName(e.target.value)} placeholder="Unit name" required minLength={2}/><input value={unitCode} onChange={e=>setUnitCode(e.target.value)} placeholder="Code (e.g. ENG)" required/><button disabled={busy} className="employee-primary">Add unit</button></form>}
   <div className="core-unit-grid">{kinds.map(([key,label])=><div className="core-unit-card" key={key}><h3>{label} <span>{units.filter(u=>u.kind===key).length}</span></h3>{units.filter(u=>u.kind===key).map(u=><div key={u.id} className="core-unit-row"><strong>{u.name}</strong><small>{u.code}</small></div>)}{!units.some(u=>u.kind===key)&&<p className="muted">No units created</p>}</div>)}</div>
  </section>}
  {mode==="orgchart"&&<section className="employee-surface"><header className="core-head"><GitBranch size={21}/><div><h2>Reporting hierarchy</h2><p>A visual org chart based on the assigned reporting manager.</p></div></header>{chart.length?renderOrgTree():<div className="empty">No employees found.</div>}</section>}
  {mode==="profile"&&person&&<><section className="employee-surface"><header className="core-head"><UserRound size={22}/><div><h2>{person.name} <span className="employee-id">{person.employee_code||"Legacy"}</span></h2><p>{person.designation} · {person.department} · {person.email}</p></div></header>
   <div className="core-stat-row"><span>Role <strong>{person.role.replace("_"," ")}</strong></span><span>Status <strong>{person.status}</strong></span><span>Lifecycle <strong>{person.master?.lifecycle||"Not set"}</strong></span><span>Joining date <strong>{person.joining_date||"—"}</strong></span></div>
   <h3 className="core-subhead">Reporting & organization</h3>
   <form onSubmit={saveMaster} className="core-form">
    <div className="employee-form-grid">
     {selectRelation("manager_id","Reporting manager",people.filter(p=>p.id!==target).map(p=>({id:p.id,name:managerLabels[p.id]})))}
     {selectRelation("hod_id","Second-level manager / HOD",people.filter(p=>p.id!==target).map(p=>({id:p.id,name:managerLabels[p.id]})))}
     {kinds.map(([kind,label])=>selectRelation((kind+"_id") as keyof Core,label,units.filter(u=>u.kind===kind)))}
    </div>
    <h3 className="core-subhead">Personal details & emergency contact</h3>
    <div className="employee-form-grid">{fields.filter(([field])=>!sensitive.includes(field)).map(([field,label])=>input(field,label,field==="date_of_birth"?"date":field==="personal_email"?"email":"text"))}</div>
    {isHR&&<><h3 className="core-subhead"><LockKeyhole size={17}/> Restricted HR-only identifiers and bank details</h3><div className="employee-form-grid">{fields.filter(([field])=>sensitive.includes(field)).map(([field,label])=>input(field,label))}</div><div className="core-form-actions"><button disabled={busy} className="employee-primary">Save master record</button></div></>}
   </form>
  </section>
  <section className="employee-surface"><header className="core-head"><FilePlus2 size={20}/><div><h2>Employee documents</h2><p>Offer letters, ID proofs, certificates and their expiry dates.</p></div></header>
    {isHR&&<form className="core-inline-form" onSubmit={upload}><select value={category} onChange={e=>setCategory(e.target.value)}>{categories.map(([key,label])=><option key={key} value={key}>{label}</option>)}</select><input type="date" aria-label="Document expiry date" value={expiry} onChange={e=>setExpiry(e.target.value)}/><input type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={e=>setDocument(e.target.files?.[0]||null)}/><button disabled={busy} className="employee-primary"><Upload size={15}/> Upload</button></form>}
    {documents.length?<div className="table-wrap"><table><thead><tr><th>Document</th><th>Category</th><th>Expiry</th><th>Action</th></tr></thead><tbody>{documents.map(d=><tr key={d.id}><td>{d.name}</td><td>{d.category.replace("_"," ")}</td><td>{d.expiry_date||"—"}</td><td><button className="employee-link" onClick={()=>downloadDoc(d)}>Download</button></td></tr>)}</tbody></table></div>:<div className="empty">No documents uploaded yet.</div>}
  </section>
  <section className="employee-surface"><header className="core-head"><CalendarClock size={21}/><div><h2>Employee lifecycle</h2><p>Probation, confirmation, transfer, promotion and exit history.</p></div></header>
   {isHR&&<form className="core-inline-form" onSubmit={lifecycle}><select value={eventType} onChange={e=>setEventType(e.target.value)}>{["probation","confirmed","transferred","promoted","exited"].map(s=><option key={s}>{s}</option>)}</select><input value={eventNote} onChange={e=>setEventNote(e.target.value)} placeholder="Reason or notes" maxLength={500}/><button className="employee-primary" disabled={busy}>Record change</button></form>}
   <div className="core-timeline">{history.map((h,i)=><div key={i}><span>{h.date}</span><strong>{h.event.replace("_"," ")}</strong><small>{h.note}</small></div>)}{!history.length&&<div className="empty">No status changes yet.</div>}</div>
  </section>
  {!isHR&&target===user.id&&<section className="employee-surface"><header className="core-head"><ShieldCheck size={21}/><div><h2>Request profile update</h2><p>HR will review sensitive profile edits before applying them.</p></div></header><form className="core-inline-form" onSubmit={submitChange}><select value={changeField} onChange={e=>setChangeField(e.target.value)}>{changes.map(key=><option key={key} value={key}>{key.replace("_"," ")}</option>)}</select><input type={changeField==="date_of_birth"?"date":"text"} value={changeValue} onChange={e=>setChangeValue(e.target.value)} placeholder="Requested new value" required/><button disabled={busy} className="employee-primary">Submit request</button></form></section>}
  </>}
  {mode==="approvals"&&<section className="employee-surface"><header className="core-head"><ShieldCheck size={21}/><div><h2>{isHR?"Profile change approvals":"My profile requests"}</h2><p>{isHR?"Review employee requests before sensitive changes are applied.":"Track HR approval of your profile changes."}</p></div></header><div className="table-wrap"><table><thead><tr><th>Employee</th><th>Field</th><th>Requested</th><th>Status</th>{isHR&&<th>Review</th>}</tr></thead><tbody>{changeRequests.map(r=><tr key={r.id}><td>{people.find(p=>p.id===r.employee_id)?.name||"Employee #"+r.employee_id}</td><td>{r.field.replace("_"," ")}</td><td>{r.value}</td><td><span className={"pill "+r.status}>{r.status}</span></td>{isHR&&<td>{r.status==="pending"?<div className="actions"><button className="secondary" disabled={busy} onClick={()=>review(r.id,true)}>Approve</button><button className="secondary" disabled={busy} onClick={()=>review(r.id,false)}>Reject</button></div>:"—"}</td>}</tr>)}</tbody></table>{!changeRequests.length&&<div className="empty">No profile-change requests.</div>}</div></section>}
  {mode==="bulk"&&isHR&&<><section className="employee-surface"><header className="core-head"><FileDown size={21}/><div><h2>Employee import / export</h2><p>Bulk employee onboarding using CSV or XLSX, and safe employee directory exports.</p></div></header><div className="actions"><button className="employee-cancel" disabled={busy} onClick={()=>exportFile("csv")}><Download size={15}/> Export CSV</button><button className="employee-cancel" disabled={busy} onClick={()=>exportFile("xlsx")}><Download size={15}/> Export Excel</button></div><p className="field-help core-import-note">Required columns: name, email, designation, department. Optional: role, joining_date, phone, manager_email. Manager emails must already exist. Bulk-imported users must activate access using password reset.</p><div className="core-inline-form"><input type="file" accept=".csv,.xlsx" onChange={e=>{setSelectedFile(e.target.files?.[0]||null);setPreview(null)}}/><button className="employee-primary" disabled={busy||!selectedFile} onClick={()=>importFile(true)}>Validate import</button>{preview?.valid&&preview.dry_run&&<button className="employee-cancel" disabled={busy} onClick={()=>importFile(false)}>Confirm import ({preview.row_count})</button>}</div>{preview&&<div className={preview.valid?"employee-success":"error"}>{preview.valid?preview.row_count+" rows validated. "+(preview.note||""):preview.errors.length+" validation errors found."}</div>}{preview?.errors.map(e=><p className="field-error" key={e.row}>Row {e.row}: {e.error}</p>)}</section>
  <section className="employee-surface"><header className="core-head"><CalendarClock size={21}/><div><h2>Expiring documents</h2><p>Certificates and other employee documents due within 30 days (including expired).</p></div></header><div className="table-wrap"><table><thead><tr><th>Employee ID</th><th>Document</th><th>Category</th><th>Expiry</th></tr></thead><tbody>{alerts.map(a=><tr key={a.document_id}><td>{a.employee_id}</td><td>{a.name}</td><td>{a.category.replace("_"," ")}</td><td>{a.expiry_date||"—"}</td></tr>)}</tbody></table>{!alerts.length&&<div className="empty">No upcoming document expiries.</div>}</div></section></>}
 </div>;
}

"use client";
import UploadInput from "./UploadInput";
import DeviceMonitoringDashboard from "./DeviceMonitoringDashboard";
import AppSelect from "./AppSelect";
import AnnouncementTemplates,{type AnnouncementPreset} from "./AnnouncementTemplates";
import {useTransientMessage} from "./useTransientMessage";
import {useEffect,useState} from "react";
import {ClipboardCheck,Send,LifeBuoy,UserRoundX,BarChart3,Bell,ShieldCheck,FileSignature} from "lucide-react";
import FeedbackMotion from "./FeedbackMotion";
import {explainError} from "./formErrors";
import PeopleOpsExtras from "./PeopleOpsExtras";
import BrandIllustration,{WelcomeAnimation} from "./BrandIllustration";
type Row=Record<string,any>;
type Area="offers"|"onboarding"|"announcements"|"helpdesk"|"exit"|"analytics"|"monitoring"|"notifications"|"audit"|"assets";
const areas:[Area,string][]=[["offers","Offer letters"],["onboarding","Onboarding"],["announcements","Announcements"],["helpdesk","Helpdesk"],["exit","Exit management"],
 ["monitoring","Monitoring"],["analytics","Analytics"],["notifications","Notifications"],["audit","Audit & security"],["assets","Assets & clearances"]];
const today=()=>new Date().toISOString().slice(0,10);
export default function PeopleOpsWorkspace({api,user,initialTab="announcements"}:{api:string;user:{id:number;name:string;role:string};initialTab?:string}){
 const hr=["super_admin","admin","hr"].includes(user.role);
 const [tab,setTab]=useState<Area>("announcements");
 useEffect(()=>{
  const matched=areas.find(([key])=>key===initialTab)?.[0]||"announcements";
  if(["analytics","monitoring","notifications","audit"].includes(matched)&&!hr)return;
  setTab(matched);
 },[initialTab,hr]);
 const [staff,setStaff]=useState<Row[]>([]);
 const [templates,setTemplates]=useState<Row[]>([]);
 const [editingOfferTemplate,setEditingOfferTemplate]=useState<number|null>(null);
 const [companyLogo,setCompanyLogo]=useState<File|null>(null);
 const [announcementImage,setAnnouncementImage]=useState<File|null>(null);
 const [announcementPreview,setAnnouncementPreview]=useState("");
 const [announcementAudience,setAnnouncementAudience]=useState<number[]>([]);
 const [announcementPreset,setAnnouncementPreset]=useState("");
 const [audienceSearch,setAudienceSearch]=useState("");
 const [offers,setOffers]=useState<Row[]>([]);
 const [tasks,setTasks]=useState<Row[]>([]);
 const [onboardingEmployee,setOnboardingEmployee]=useState("");
 const [onboardingCategories,setOnboardingCategories]=useState<Row[]>([]);
 const [categoryName,setCategoryName]=useState("");
 const [categorySlug,setCategorySlug]=useState("");
 const [editingCategory,setEditingCategory]=useState<number|null>(null);
 const [editingCategoryName,setEditingCategoryName]=useState("");
 const [notices,setNotices]=useState<Row[]>([]);
 const [tickets,setTickets]=useState<Row[]>([]);
 const [allTickets,setAllTickets]=useState<Row[]>([]);
 const [exits,setExits]=useState<Row[]>([]);
 const [allExits,setAllExits]=useState<Row[]>([]);
 const [metrics,setMetrics]=useState<Row|null>(null);
 const [activityDevices,setActivityDevices]=useState<Row[]>([]);
 const [activityEmployee,setActivityEmployee]=useState("");
 const [enrollment,setEnrollment]=useState<Row|null>(null);
  const [installInvite,setInstallInvite]=useState<Row|null>(null);
  const [pendingAssignments,setPendingAssignments]=useState<Record<number,string>>({});
 const [rules,setRules]=useState<Row[]>([]);
 const [notifications,setNotifications]=useState<Row[]>([]);
 const [audits,setAudits]=useState<Row[]>([]);
 const [info,setInfo]=useTransientMessage();const [error,setError]=useState("");const [busy,setBusy]=useState(false);
 const [draft,setDraft]=useState<Row>({});
 const [selected,setSelected]=useState("");
 const [reply,setReply]=useState("");
 const [exitEmployee,setExitEmployee]=useState("");
 const [exitReason,setExitReason]=useState("");
 const [exitNotice,setExitNotice]=useState("30");
 const [noticeEditCase,setNoticeEditCase]=useState<number|null>(null);
 const [noticeReason,setNoticeReason]=useState("");
 const [exitTemplates,setExitTemplates]=useState<Row[]>([]);
 const [templateTitle,setTemplateTitle]=useState("");
 const [templateRole,setTemplateRole]=useState("hr");
 const [editingExitTemplate,setEditingExitTemplate]=useState<number|null>(null);
 const [editExitTitle,setEditExitTitle]=useState("");
 const [editExitRole,setEditExitRole]=useState("hr");
 const [exitTasks,setExitTasks]=useState<Record<number,Row[]>>({});
 const [exitTaskNotes,setExitTaskNotes]=useState<Record<number,string>>({});
 async function call(path:string,method="GET",body?:unknown){
  const r=await fetch(api+"/people"+path,{method,credentials:"include",
   headers:{"Content-Type":"application/json"},body:body===undefined?undefined:JSON.stringify(body)});
  const j=await r.json().catch(()=>({}));
  if(!r.ok)throw Error(explainError(j,r.status));
  return j;
 }
 const get=(path:string)=>call(path).catch(()=>[]);
 async function refresh(){
  const [a,b,c,d,e,f,g,h,i,j,k,l]=await Promise.all([
   hr?fetch(api+"/employees",{credentials:"include"}).then(r=>r.ok?r.json():[]):Promise.resolve([]),
   hr?get("/offer-templates"):Promise.resolve([]),get("/offers"),get("/onboarding"),get("/announcements"),
   get("/tickets"),hr?get("/tickets?scope=all"):Promise.resolve([]),get("/exits"),
   hr?get("/exits?scope=all"):Promise.resolve([]),hr?call("/analytics").catch(()=>null):Promise.resolve(null),
   get("/notifications"),hr?get("/audit"):Promise.resolve([])]);
  setStaff(a);setTemplates(b);setOffers(c);setTasks(d);setNotices(e);setTickets(f);setAllTickets(g);setExits(h);
  setAllExits(i);setMetrics(j);setNotifications(k);setAudits(l);
  setOnboardingCategories(await get("/onboarding/categories"));
  if(hr){setRules(await get("/notification-rules"));fetch(api+"/activity-agent/devices",{credentials:"include"}).then(v=>v.ok?v.json():[]).then(setActivityDevices).catch(()=>{});}
 }
 useEffect(()=>{if(!hr||tab!=="analytics")return;const refreshDevices=()=>{void fetch(api+"/activity-agent/devices",{credentials:"include"}).then(r=>r.ok?r.json():[]).then(setActivityDevices).catch(()=>{})};refreshDevices();const timer=window.setInterval(refreshDevices,30000);return()=>window.clearInterval(timer)},[api,hr,tab]);
 useEffect(()=>{void refresh();if(hr)void fetch(api+"/exit-workflow/templates",{credentials:"include"})
  .then(r=>r.ok?r.json():[]).then(setExitTemplates).catch(()=>{})},[api,user.id]);
 async function save(fn:()=>Promise<unknown>,msg:string){
  setBusy(true);setError("");setInfo("");
  try{await fn();setInfo(msg);setDraft({});setSelected("");setReply("");await refresh()}
  catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 const input=(key:string,label:string,required=false,type="text")=><label key={key}>{label}<input type={type} required={required}
  value={draft[key]??""} onChange={e=>setDraft(v=>({...v,[key]:e.target.value}))}/></label>;
 const emp=(key="employee_id")=><label>Employee<AppSelect required value={draft[key]??""} onChange={e=>setDraft(v=>({...v,[key]:e.target.value}))}>
  <option value="">Select employee</option>{staff.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</AppSelect></label>;
 async function exitCall(path:string,method="GET",body?:unknown){
  const response=await fetch(api+"/exit-workflow"+path,{method,credentials:"include",
   headers:{"Content-Type":"application/json"},body:body===undefined?undefined:JSON.stringify(body)});
  const payload=await response.json().catch(()=>null);
  if(!response.ok)throw Error(explainError(payload,response.status));
  return payload;
 }
 async function initiateExit(e:React.FormEvent){
  e.preventDefault();
  await save(async()=>{
   await exitCall("/cases","POST",{employee_id:Number(exitEmployee),reason:exitReason,
     notice_days:Number(exitNotice),requested_date:today()});
   setExitEmployee("");setExitReason("");
  },"Exit case created. Employee and HR checklist tasks assigned.");
 }
 async function addExitTemplate(e:React.FormEvent){
  e.preventDefault();
  await save(async()=>{
   await exitCall("/templates","POST",{title:templateTitle,assignee_role:templateRole,active:true});
   setExitTemplates(await exitCall("/templates"));setTemplateTitle("");
  },"Exit checklist task configured.");
 }
 async function saveExitTemplate(id:number,active:boolean,title:string,role:string){
  await save(async()=>{
    await exitCall("/templates/"+id,"PUT",{title,assignee_role:role,active});
    setExitTemplates(await exitCall("/templates"));
    setEditingExitTemplate(null);
  },active?"Exit checklist template updated.":"Exit checklist template disabled for future exits.");
 }
 async function loadExitTasks(caseId:number){
  try{
   const items=await exitCall("/cases/"+caseId+"/tasks");
   setExitTasks(v=>({...v,[caseId]:items}));
  }catch(e){setError((e as Error).message)}
 }
 async function completeExitTask(caseId:number,taskId:number){
  await save(async()=>{
   await exitCall("/tasks/"+taskId+"/complete","POST",{note:exitTaskNotes[taskId]||""});
   await loadExitTasks(caseId);
  },"Exit task completed with the audit note.");
 }
 const submit=(path:string,data:Row,success:string)=>save(()=>call(path,"POST",data),success);
 return <div className="ops-area">
  <p className="ops-intro">Employee lifecycle workflows, approvals, announcements and HR support. Confidential workflows are available only to the employee or authorized HR staff.</p>
  <div className="time-tabs" role="tablist">{areas.filter(([id])=>hr||!["analytics","monitoring","notifications","audit"].includes(id)).map(([id,label])=>
   <button key={id} role="tab" aria-selected={tab===id} className={tab===id?"active":""} onClick={()=>{setTab(id);setError("");setInfo("");setDraft({})}}>{label}</button>)}</div>
  {error&&<div role="alert" className="time-form-error">{error}</div>}
  {info&&<FeedbackMotion type={info.includes("accepted")?"congrats":"success"} compact message={info}/>}
  {busy&&<FeedbackMotion type="loading" compact message="Updating HRMS…"/>}
  {tab==="offers"&&<div className="ops-columns">
    <section className="employee-surface"><h3><FileSignature size={17}/> Offer letters</h3>
     {hr&&<div className="ops-form"><h4>Company letterhead</h4><p className="field-help">Upload a verified PNG or JPEG logo (max 2 MB). It will appear on generated offer PDFs.</p><label>Company logo<UploadInput accept="image/png,image/jpeg" onChange={e=>setCompanyLogo(e.target.files?.[0]||null)}/></label><button type="button" className="employee-primary" disabled={!companyLogo||busy} onClick={()=>void save(async()=>{const form=new FormData();form.append("file",companyLogo!);const res=await fetch(api+"/people/letterhead/logo",{method:"POST",credentials:"include",body:form});if(!res.ok)throw Error("Logo upload failed. Use a valid PNG/JPEG under 2 MB.");setCompanyLogo(null)},"Company logo updated.")}>Upload company logo</button></div>}
     {hr&&<><form className="ops-form" onSubmit={e=>{e.preventDefault();void save(async()=>{await call(editingOfferTemplate?"/offer-templates/"+editingOfferTemplate:"/offer-templates",editingOfferTemplate?"PUT":"POST",{name:draft.template_name,content:draft.template_content});setEditingOfferTemplate(null)},editingOfferTemplate?"Template updated.":"Template created.")}}>
      <h4>{editingOfferTemplate?"Edit offer template":"Create offer template"}</h4>{input("template_name","Template name",true)}
      <label className="wide">Offer text with placeholders<textarea rows={5} minLength={30} required
       placeholder="Dear {{employee_name}}, we offer {{job_title}}…" value={draft.template_content||""}
       onChange={e=>setDraft(v=>({...v,template_content:e.target.value}))}/></label>
      <button className="employee-primary" disabled={busy}>Save template</button>{editingOfferTemplate&&<button type="button" className="employee-cancel" onClick={()=>{setEditingOfferTemplate(null);setDraft({})}}>Cancel editing</button>}
     </form><div className="ops-table"><h4>Existing offer templates</h4>{templates.map(t=><div className="ops-row" key={t.id}><strong>{t.name}</strong><span>{t.active?"Active":"Archived"}</span>{t.active&&<div className="actions"><button type="button" className="employee-cancel" onClick={()=>{setEditingOfferTemplate(t.id);setDraft({template_name:t.name,template_content:t.content})}}>Edit</button><button type="button" className="employee-cancel" onClick={()=>{if(window.confirm("Archive this template? Existing offers remain unchanged."))void save(()=>call("/offer-templates/"+t.id,"DELETE"),"Template archived.")}}>Archive</button></div>}</div>)}</div><hr/><form className="ops-form" onSubmit={e=>{e.preventDefault();void submit("/offers",{
       employee_id:Number(draft.employee_id),template_id:Number(draft.template_id),title:draft.title,
       annual_ctc:Number(draft.annual_ctc),joining_date:draft.joining_date||today()
      },"Offer generated.")}}>
      <h4>Generate offer</h4>{emp()}
      <label>Template<AppSelect required value={draft.template_id||""} onChange={e=>setDraft(v=>({...v,template_id:e.target.value}))}>
       <option value="">Choose template</option>{templates.filter(t=>t.active).map(t=><option key={t.id} value={t.id}>{t.name}</option>)}</AppSelect></label>
      {input("title","Job title",true)}{input("annual_ctc","Annual CTC (INR)",true,"number")}
      <label>Joining date<input type="date" required value={draft.joining_date||today()} onChange={e=>setDraft(v=>({...v,joining_date:e.target.value}))}/></label>
      <button className="employee-primary" disabled={busy}>Generate offer</button></form></>}
     {!hr&&<p>Review any offer shared by HR. Typed-name acceptance records an internal consent, not a third-party qualified e-signature.</p>}
    </section>
    <section className="employee-surface"><h3>Offer history</h3><div className="ops-table">{offers.map(o=><div className="ops-row" key={o.id}>
     <strong>{o.title}</strong><span>{staff.find(p=>p.id===o.employee_id)?.name||(!hr?"Your offer":"Employee record unavailable")} · {o.status}</span><a href={api+"/people/offers/"+o.id+".pdf"} target="_blank" rel="noopener noreferrer">{hr&&o.status==="draft"?"Preview PDF":"View PDF"}</a>
     {hr&&o.status==="draft"&&<button className="employee-primary" onClick={()=>void save(()=>call("/offers/"+o.id+"/send","POST"),"Offer sent.")}>Send offer</button>}
     {!hr&&o.status==="sent"&&<button className="employee-primary" onClick={()=>void save(()=>call("/offers/"+o.id+"/sign","POST",
       {printed_name:user.name,consent:true}),"Offer accepted and acknowledgement recorded.")}>Accept offer</button>}
    </div>)}</div></section>
   </div>}
  {tab==="onboarding"&&<div className="ops-columns">
   <section className="employee-surface"><h3><ClipboardCheck size={17}/> Onboarding checklist</h3>
    <div className="jellygit-onboarding-welcome"><WelcomeAnimation/><div><strong>Welcome to your JellyGit journey</strong><p className="muted">Complete your orientation, review company policies and meet your team.</p></div></div>
    {hr&&<form className="ops-form" onSubmit={e=>{e.preventDefault();void submit("/onboarding",{
      employee_id:Number(draft.employee_id),category:draft.category||"document",
      title:draft.title,due_date:draft.due_date||null,assigned_to:draft.assigned_to?Number(draft.assigned_to):null,
      asset_code:draft.asset_code||""},"Onboarding task created.")}}>
     {emp()}<label>Category<AppSelect value={draft.category||"document"} onChange={e=>setDraft(v=>({...v,category:e.target.value}))}>
      {onboardingCategories.filter(c=>c.active).map(c=><option key={c.id} value={c.slug}>{c.display_name}</option>)}</AppSelect></label>
     {input("title","Task title",true)}{input("asset_code","Asset code (optional)")}
     {input("due_date","Due date",false,"date")}
     <label>Responsible person<AppSelect required value={draft.assigned_to||""} onChange={e=>setDraft(v=>({...v,assigned_to:e.target.value}))}>
      <option value="">Choose a responsible employee</option>{staff.map(e=><option key={e.id} value={e.id}>{e.name}</option>)}</AppSelect></label>
     <button className="employee-primary">Assign task</button>
     <button type="button" className="employee-cancel" disabled={!draft.employee_id} onClick={()=>void save(()=>call("/onboarding/orientation/"+draft.employee_id,"POST"),"Seven-step welcome orientation initialized.")}>Start welcome orientation (7 steps)</button></form>}
   {hr&&<details className="ops-category-manager"><summary>Manage onboarding categories</summary><div className="ops-form"><label>New category name<input minLength={2} maxLength={80} value={categoryName} onChange={e=>{setCategoryName(e.target.value);setCategorySlug(e.target.value.trim().toLowerCase().replace(/[^a-z0-9]+/g,"_").replace(/^_+|_+$/g,""))}}/></label><label>Category code<input pattern="[a-z][a-z0-9_]*" minLength={2} maxLength={30} value={categorySlug} onChange={e=>setCategorySlug(e.target.value)}/></label><button type="button" className="employee-primary" disabled={busy||categoryName.trim().length<2||categorySlug.length<2} onClick={()=>void save(async()=>{await call("/onboarding/categories","POST",{display_name:categoryName.trim(),slug:categorySlug});setCategoryName("");setCategorySlug("")},"Onboarding category created.")}>Add category</button></div><div className="ops-table">{onboardingCategories.map(category=><div className="ops-row" key={category.id}><strong>{category.display_name}</strong><small>{category.slug} · {category.active?"Active":"Archived"}</small><div className="actions">{editingCategory===category.id?<><label>Category name<input type="text" minLength={2} maxLength={80} value={editingCategoryName} onChange={e=>setEditingCategoryName(e.target.value)}/></label><button type="button" className="employee-primary" disabled={busy||editingCategoryName.trim().length<2} onClick={()=>void save(async()=>{await call("/onboarding/categories/"+category.id,"PUT",{display_name:editingCategoryName.trim(),active:category.active});setEditingCategory(null)},"Category updated.")}>Save name</button><button type="button" className="employee-cancel" onClick={()=>setEditingCategory(null)}>Cancel</button></>:<button type="button" className="employee-cancel" onClick={()=>{setEditingCategory(category.id);setEditingCategoryName(category.display_name)}}>Rename</button>}{category.active&&<button type="button" className="employee-cancel" onClick={()=>{if(window.confirm("Archive this category? Existing task history will remain."))void save(()=>call("/onboarding/categories/"+category.id,"DELETE"),"Category archived.")}}>Archive</button>}</div></div>)}</div></details>}
   </section>
   <section className="employee-surface"><h3>Employee onboarding progress</h3>
    {hr&&<label>Employee<AppSelect value={onboardingEmployee} onChange={e=>setOnboardingEmployee(e.target.value)}><option value="">Select employee to review</option>{staff.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</AppSelect></label>}
    <p className="muted">Welcome journey: {tasks.filter(t=>(!hr||t.employee_id===Number(onboardingEmployee))&&t.status==="completed").length} of {tasks.filter(t=>!hr||t.employee_id===Number(onboardingEmployee)).length} tasks completed</p>
    <progress max={Math.max(1,tasks.filter(t=>!hr||t.employee_id===Number(onboardingEmployee)).length)} value={tasks.filter(t=>(!hr||t.employee_id===Number(onboardingEmployee))&&t.status==="completed").length} style={{width:"100%"}} aria-label="Onboarding progress"/>
    <div className="ops-table">{tasks.filter(t=>!hr||t.employee_id===Number(onboardingEmployee)).map(t=><div className="ops-row" key={t.id}>
    <strong>{t.title}</strong><span>{onboardingCategories.find(c=>c.slug===t.category)?.display_name||String(t.category).replace(/^./,(x:string)=>x.toUpperCase())} · {t.status} · {staff.find(p=>p.id===t.employee_id)?.name||("Employee #"+t.employee_id)}</span><small>Responsible: {staff.find(p=>p.id===t.assigned_to)?.name||"Not assigned"}</small>
    {t.asset_code&&<small>Asset: {t.asset_code}</small>}
    {t.status==="pending"&&(hr||t.assigned_to===user.id)&&<button className="employee-primary" onClick={()=>void save(()=>call("/onboarding/"+t.id+"/complete","POST"),"Task completed.")}>Complete</button>}
   </div>)}{(!tasks.length||(hr&&!onboardingEmployee))&&<div className="jellygit-empty-state"><BrandIllustration asset="empty-folder-state" alt="" className="jellygit-empty-art"/><p>{hr&&!onboardingEmployee?"Select an employee to view their onboarding tasks.":"No onboarding tasks yet."}</p></div>}</div></section>
  </div>}
  {tab==="announcements"&&<div className="ops-columns">
   <section className="employee-surface"><h3><Send size={17}/> Announcements and policies</h3>
    {hr&&<AnnouncementTemplates selected={announcementPreset} onPick={(p:AnnouncementPreset)=>{setAnnouncementPreset(p.key);setDraft(v=>({...v,title:p.headline,body:p.message}))}}/>}
    {hr&&<form className="ops-form" onSubmit={e=>{e.preventDefault();void save(async()=>{const form=new FormData();form.append("title",String(draft.title));form.append("body",String(draft.body));form.append("requires_ack",String(Boolean(draft.requires_ack)));form.append("audience_json",JSON.stringify(announcementAudience));if(announcementImage)form.append("image",announcementImage);const response=await fetch(api+"/people/announcements/with-media",{method:"POST",credentials:"include",body:form});if(!response.ok){const data=await response.json().catch(()=>({}));throw Error(explainError(data,response.status))}setAnnouncementImage(null);setAnnouncementPreview("");setAnnouncementAudience([]);setAnnouncementPreset("");setAudienceSearch("")},"Announcement published.")}}>
      {input("title","Title",true)}
      <label className="wide">Announcement<textarea minLength={12} required rows={4} value={draft.body||""}
       onChange={e=>setDraft(v=>({...v,body:e.target.value}))}/></label>
      <label className="wide ops-check"><input type="checkbox" checked={!!draft.requires_ack}
       onChange={e=>setDraft(v=>({...v,requires_ack:e.target.checked}))}/>Require employee acknowledgement</label>
      <label className="wide">Announcement image (optional, PNG/JPEG/WebP; max 3 MB)<UploadInput accept="image/png,image/jpeg,image/webp" onChange={e=>{const file=e.target.files?.[0]||null;setAnnouncementImage(file);if(file){const reader=new FileReader();reader.onload=()=>setAnnouncementPreview(String(reader.result||""));reader.readAsDataURL(file)}else setAnnouncementPreview("")}}/></label>
      <div className="wide jg-audience-picker"><div><strong>Announcement audience</strong><p className="field-help">{announcementAudience.length?`${announcementAudience.length} selected employee(s)`:"All active employees will receive this announcement."}</p></div>
  <input type="search" aria-label="Find announcement recipients" placeholder="Search employees…" value={audienceSearch} onChange={e=>setAudienceSearch(e.target.value)}/>
  <div className="jg-preset-actions"><button type="button" className="employee-cancel" onClick={()=>setAnnouncementAudience(staff.filter(p=>p.status==="active").map(p=>p.id))}>Select all</button><button type="button" className="employee-cancel" onClick={()=>setAnnouncementAudience([])}>Everyone</button></div>
  <div className="jg-audience-list" role="group" aria-label="Select announcement recipients">{staff.filter(p=>p.status==="active"&&p.name.toLowerCase().includes(audienceSearch.toLowerCase())).map(p=><label key={p.id}><input type="checkbox" checked={announcementAudience.includes(p.id)} onChange={e=>setAnnouncementAudience(prev=>e.target.checked?[...prev,p.id]:prev.filter(id=>id!==p.id))}/><span>{p.name}</span></label>)}</div>
 </div>
      <div className="wide ops-announcement-preview"><strong>Preview before publishing</strong><h4>{draft.title||"Announcement title"}</h4>{announcementPreview&&<img src={announcementPreview} alt="Announcement preview" style={{maxWidth:"100%",maxHeight:240,objectFit:"contain",borderRadius:10}}/>}<p>{draft.body||"Announcement body will appear here."}</p><small>{announcementAudience.length?announcementAudience.length+" selected employees":"All active employees"}</small></div><button className="employee-primary" disabled={busy}>Publish</button></form>}
   </section>
   <section className="employee-surface"><h3>Company feed</h3><div className="ops-table">{notices.map(n=><article className="ops-row" key={n.id}>
     <strong>{n.title}</strong><p>{n.body}</p>{n.has_media&&<a href={api+"/people/announcements/"+n.id+"/image"} target="_blank" rel="noopener noreferrer">View announcement image</a>}
     {n.requires_ack&&!n.acknowledged&&<button className="employee-primary" onClick={()=>void save(()=>call("/announcements/"+n.id+"/ack","POST"),"Acknowledged.")}>Acknowledge</button>}
     {n.acknowledged&&<small>Acknowledged</small>}
    </article>)}{!notices.length&&<p>No announcements yet.</p>}</div></section>
  </div>}
  {tab==="helpdesk"&&<div className="ops-columns">
   <section className="employee-surface"><h3><LifeBuoy size={17}/> HR helpdesk</h3>
    <form className="ops-form" onSubmit={e=>{e.preventDefault();void submit("/tickets",{
     category:draft.category||"other",subject:draft.subject,description:draft.description},"Helpdesk ticket opened.")}}>
     <label>Category<AppSelect value={draft.category||"other"} onChange={e=>setDraft(v=>({...v,category:e.target.value}))}>
     {["payroll","leave","attendance","benefits","it","other"].map(c=><option key={c} value={c}>{c==="it"?"IT":c.charAt(0).toUpperCase()+c.slice(1)}</option>)}</AppSelect></label>
     {input("subject","Subject",true)}
     <label className="wide">Question or concern<textarea minLength={12} required rows={4} value={draft.description||""}
      onChange={e=>setDraft(v=>({...v,description:e.target.value}))}/></label>
     <button className="employee-primary">Create ticket</button></form>
   </section>
   <section className="employee-surface"><h3>{hr?"HR ticket queue":"My tickets"}</h3><div className="ops-table">{(hr?allTickets:tickets).map(t=><article className="ops-row" key={t.id}>
    <strong>{t.subject} · {t.status}</strong><small>{String(t.category).replace(/^./,s=>s.toUpperCase())} · {staff.find(p=>p.id===t.employee_id)?.name||(!hr?"Your ticket":"Employee record unavailable")}</small><p>{t.description}</p>
    {t.hr_response&&<p>HR: {t.hr_response}</p>}
    {hr&&t.status!=="closed"&&<><textarea placeholder="HR response" value={selected===String(t.id)?reply:""}
      onChange={e=>{setSelected(String(t.id));setReply(e.target.value)}}/>
      <button className="employee-primary" disabled={busy||selected!==String(t.id)||reply.length<5}
       onClick={()=>void save(()=>call("/tickets/"+t.id+"/review","POST",{status:"resolved",reply}),"Ticket resolved.")}>Resolve</button></>}
   </article>)}</div></section>
  </div>}
  {tab==="exit"&&<div className="ops-columns">
   <section className="employee-surface"><h3><UserRoundX size={17}/> Exit request</h3>
    {!hr&&<form className="ops-form" onSubmit={e=>{e.preventDefault();void submit("/exits",{
      reason:draft.reason,
      requested_date:draft.requested_date||today()},"Resignation request submitted.")}}>
      <label className="wide">Resignation reason<textarea minLength={10} required rows={4} value={draft.reason||""}
       onChange={e=>setDraft(v=>({...v,reason:e.target.value}))}/></label>
      <label>Request date<input type="date" value={draft.requested_date||today()}
       onChange={e=>setDraft(v=>({...v,requested_date:e.target.value}))}/></label>
      <p className="field-help">HR determines the applicable notice period and reviews your final working day.</p><button className="employee-primary">Request resignation</button></form>}
    {hr&&<><p className="muted">Select an employee to begin their exit, then assign the configured employee and HR checklist tasks.</p>
     <form className="ops-form ops-compact-form" onSubmit={initiateExit}>
      <label>Employee<AppSelect required value={exitEmployee} onChange={e=>setExitEmployee(e.target.value)}>
       <option value="">Select an active employee</option>{staff.filter(p=>p.status==="active").map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
      </AppSelect></label>
      <label>Notice period (days)<input type="number" required min="0" max="365" value={exitNotice} onChange={e=>setExitNotice(e.target.value)}/></label>
      <label className="wide">Reason for exit<textarea required minLength={10} rows={3} value={exitReason} onChange={e=>setExitReason(e.target.value)} placeholder="Enter at least ten characters explaining the exit…"/></label>
      <div className="ops-form-actions"><button className="employee-primary" disabled={busy||!exitEmployee||exitReason.trim().length<10}>Start employee exit</button></div>
     </form>
     <details className="employee-surface exit-config-panel"><summary>Configure exit tasks</summary>
      <p className="muted">These tasks are automatically assigned whenever an exit case is opened. HR tasks go to HR; employee tasks go to the departing employee.</p>
      <div className="exit-task-list">{exitTemplates.map((x,i)=><div key={x.id??"default"+i} className="ops-row">
        {editingExitTemplate===x.id&&x.id!=null?<div className="ops-form">
         <label>Task name<input required minLength={5} maxLength={180} value={editExitTitle}
           onChange={e=>setEditExitTitle(e.target.value)}/></label>
         <label>Assigned to<AppSelect value={editExitRole} onChange={e=>setEditExitRole(e.target.value)}>
          <option value="hr">HR team</option><option value="employee">Exiting employee</option>
         </AppSelect></label>
         <button type="button" className="employee-primary" disabled={busy||editExitTitle.trim().length<5}
           onClick={()=>void saveExitTemplate(x.id,x.active,editExitTitle.trim(),editExitRole)}>Save template</button>
         <button type="button" className="employee-cancel" onClick={()=>setEditingExitTemplate(null)}>Cancel</button>
        </div>:<>
         <strong>{x.title}</strong> <small>· {x.assignee_role==="hr"?"HR":"Employee"} · {x.active?"Active":"Disabled"}</small>
         {x.id!=null&&<><button type="button" className="employee-cancel" disabled={busy}
          onClick={()=>{setEditingExitTemplate(x.id);setEditExitTitle(x.title);setEditExitRole(x.assignee_role)}}>
          Edit</button>
         <button type="button" className="employee-cancel" disabled={busy}
          onClick={()=>void saveExitTemplate(x.id,!x.active,x.title,x.assignee_role)}>
          {x.active?"Disable":"Enable"}</button></>}
        </>}
       </div>)}</div>
      <form className="ops-form ops-compact-form" onSubmit={addExitTemplate}>
       <label>New task name<input required minLength={5} maxLength={180} value={templateTitle} onChange={e=>setTemplateTitle(e.target.value)} placeholder="e.g. Confirm returned access badge"/></label>
       <label>Assigned to<AppSelect value={templateRole} onChange={e=>setTemplateRole(e.target.value)}><option value="hr">HR team</option><option value="employee">Exiting employee</option></AppSelect></label>
       <div className="ops-form-actions"><button className="employee-primary" disabled={busy||templateTitle.trim().length<5}>Add checklist task</button></div>
      </form>
     </details>
     <p className="muted">Final settlement requires documented asset, IT and Finance clearance. This process does not send a payment.</p>
    </>}
   </section>
   <section className="employee-surface"><h3>Exit cases</h3><div className="ops-table">{(hr?allExits:exits).map(x=><div className="ops-row exit-case-row" key={x.id}>
     <div className="exit-case-heading"><strong>Case #{x.id} · {x.status}</strong><span>{staff.find(p=>p.id===x.employee_id)?.name||"Employee #"+x.employee_id} · {x.notice_days===0&&x.status==="requested"?"Notice review pending · Last working day not confirmed":"Last day "+x.planned_last_day}</span></div><p>{x.reason}</p>
      {hr&&x.status!=="settled"&&x.status!=="rejected"&&<div className="ops-form"><button type="button" className="employee-cancel" onClick={()=>{setNoticeEditCase(noticeEditCase===x.id?null:x.id);setExitNotice(String(x.notice_days));setNoticeReason("")}}>Review notice period ({x.notice_days} days)</button>{noticeEditCase===x.id&&<><label>Approved notice days<input type="number" min="0" max="365" value={exitNotice} onChange={e=>setExitNotice(e.target.value)}/></label><label>Reason for change<textarea minLength={10} required value={noticeReason} onChange={e=>setNoticeReason(e.target.value)}/></label><button type="button" className="employee-primary" disabled={busy||noticeReason.trim().length<10} onClick={()=>void save(async()=>{await call("/exits/"+x.id+"/notice","PUT",{notice_days:Number(exitNotice),reason:noticeReason});setNoticeEditCase(null)},"Employee notice period reviewed.")}>Save notice review</button></>}</div>}
      <div className="exit-task-controls"><button className="employee-cancel" type="button" onClick={()=>void loadExitTasks(x.id)}>View assigned exit tasks</button>
       {(exitTasks[x.id]||[]).map(t=><div className="exit-task-entry" key={t.id}>
        <strong>{t.title}</strong><small>{t.assignee_role==="hr"?"HR task":"Employee task"} · {t.status}</small>
        {t.status==="pending"&&<><label>Completion note<input placeholder="Explain what was completed" minLength={5} maxLength={1000}
          value={exitTaskNotes[t.id]||""} onChange={e=>setExitTaskNotes(old=>({...old,[t.id]:e.target.value}))}/></label>
         <button className="employee-primary" type="button" disabled={busy||(exitTaskNotes[t.id]||"").trim().length<5}
          onClick={()=>void completeExitTask(x.id,t.id)}>Complete task</button></>}
       </div>)}
      </div>
     {hr&&x.status!=="settled"&&x.status!=="rejected"&&<div className="exit-case-actions"><label>Final settlement (F&F) amount in INR<input type="number" min="0" step=".01" placeholder="Enter amount before final settlement" value={selected===String(x.id)?draft.amount||"":""}
      onFocus={()=>setSelected(String(x.id))} onChange={e=>setDraft(v=>({...v,amount:e.target.value}))}/></label>
      <button className="employee-primary" onClick={()=>void save(()=>call("/exits/"+x.id+"/review","POST",{
       status:"approved",clearance_assets:false,clearance_it:false,clearance_finance:false}),"Exit request approved.")}>Approve</button>
      <button className="employee-cancel" onClick={()=>void save(()=>call("/exits/"+x.id+"/review","POST",{status:"rejected"}),"Exit request rejected.")}>Reject</button>
      <button className="employee-primary" disabled={selected!==String(x.id)||draft.amount===""||draft.amount===undefined}
       onClick={()=>void save(()=>call("/exits/"+x.id+"/review","POST",{
        status:"settled",clearance_assets:true,clearance_it:true,clearance_finance:true,
        final_settlement_inr:Number(draft.amount),final_settlement_note:"HR reviewed all clearances and F&F draft."}),"Clearances recorded and settlement finalized.")}>Confirm clearances & F&F</button>
     <p className="exit-case-help">Complete the assigned exit tasks and documented clearances before final settlement. Approval alone does not release payment.</p></div>}
    </div>)}</div></section>
  </div>}
  {tab==="monitoring"&&hr&&<DeviceMonitoringDashboard api={api}/>}
  {tab==="analytics"&&hr&&<section className="employee-surface"><h3><BarChart3 size={17}/> Workforce analytics</h3>
   {metrics&&<><div className="ops-metrics">{[["Active employees",metrics.active_headcount],["Inactive",metrics.inactive_headcount],
    ["Pending leave",metrics.pending_leave],["Open helpdesk",metrics.open_tickets],["Inactive share",metrics.attrition_proxy_pct+"%"]].map(([label,value])=><div key={String(label)}><span>{label}</span><strong>{value}</strong></div>)}</div>
    <p className="field-help">{metrics.note}</p>
    <div className="ops-columns"><div><h4>Department distribution</h4>{metrics.departments?.map((d:Row)=><div className="department-distribution-row" key={d.department}><span>{d.department}</span><div className="department-distribution-track"><div style={{width:Math.min(100,100*Number(d.employees)/Math.max(1,Number(metrics.active_headcount)))+"%"}}/></div><strong>{d.employees} {Number(d.employees)===1?"employee":"employees"}</strong></div>)}</div>
    <div><h4>Published payroll cost</h4>{metrics.published_monthly_net?.map((p:Row)=><div className="ops-row" key={p.period}>{p.period} · ₹{Number(p.net).toLocaleString("en-IN")}</div>)}</div></div></>}
    <div className="jg-device-monitor">
     <div className="jg-device-header"><div><h3>Employee device monitoring</h3><p>Manage company workstations and employee assignments. Activity is reported only after assignment and monitoring notice.</p></div><span className="jg-device-count">{activityDevices.length} devices</span></div>
     <section className="jg-device-panel" aria-label="Pending device enrollment">
      <div className="jg-device-panel-heading"><div><h4>Pending devices <span className="jg-device-count">{activityDevices.filter(d=>d.status==="pending").length}</span></h4><p>Verify the company laptop, then choose the employee who uses it.</p></div></div>
      <div className="jg-device-list">
       {activityDevices.filter(d=>d.status==="pending").map(d=><div className="jg-device-item" key={d.id}>
        <div className="jg-device-identity"><strong>{d.device_label}</strong><span>Device #{d.id} <span className="jg-device-status pending">Pending</span></span><small>Last connection: {d.last_seen?new Date(d.last_seen).toLocaleString():"Not yet reported"}</small></div>
        <div className="jg-device-assign">
         <label htmlFor={"jg-device-employee-"+d.id}>Assign to employee</label>
         <select id={"jg-device-employee-"+d.id} value={pendingAssignments[d.id]||""} onChange={e=>setPendingAssignments(v=>({...v,[d.id]:e.target.value}))} aria-label={"Assign "+d.device_label+" to an active employee"}>
          <option value="">Choose employee</option>{staff.filter(p=>p.status==="active").map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
         </select>
         <button type="button" className="employee-primary" disabled={busy||!pendingAssignments[d.id]} onClick={()=>void save(async()=>{const response=await fetch(api+"/activity-agent/devices/"+d.id+"/assign",{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({employee_id:Number(pendingAssignments[d.id])})});const data=await response.json().catch(()=>({}));if(!response.ok)throw Error(explainError(data,response.status));setPendingAssignments(v=>({...v,[d.id]:""}))},"Device assigned. Monitoring can now begin.")}>Assign device</button>
        </div>
       </div>)}
       {!activityDevices.some(d=>d.status==="pending")&&<p className="jg-device-empty">No pending laptops. Installed company devices will appear here after registration.</p>}
      </div>
     </section>
     <section className="jg-device-panel" aria-label="Assigned employee devices">
      <div className="jg-device-panel-heading"><div><h4>Assigned devices</h4><p>Current connection and activity summary for assigned company laptops.</p></div></div>
      <div className="jg-device-list">
       {activityDevices.filter(d=>d.status!=="pending").map(d=><div className="jg-device-item" key={d.id}>
        <div className="jg-device-identity"><strong>{d.employee_name}</strong><span>{d.device_label} · Device #{d.id}</span><small>Last heartbeat: {d.last_seen?new Date(d.last_seen).toLocaleString():"Never"}</small></div>
        <div className="jg-device-usage">
         <span className={"jg-device-status "+(d.status==="monitoring"?"active":"inactive")}>{d.status==="monitoring"?"Monitoring":d.status==="stopped"?"Stopped":d.status==="revoked"?"Revoked":"Offline"}</span>
         <span>Active <strong>{Math.round(d.active_seconds/60)}m</strong> · Idle <strong>{Math.round(d.idle_seconds/60)}m</strong></span>
         <small>Applications: {Object.entries(d.apps||{}).sort((a,b)=>Number(b[1])-Number(a[1])).slice(0,5).map(([name,seconds])=>name+" "+Math.round(Number(seconds)/60)+"m").join(", ")||"No activity reported"}</small>
         {d.exit_reason&&<small>Exit reason: {d.exit_reason}</small>}
        </div>
        {!d.revoked&&<button type="button" className="employee-cancel jg-device-revoke" disabled={busy} onClick={()=>void save(async()=>{const response=await fetch(api+"/activity-agent/devices/"+d.id+"/revoke",{method:"POST",credentials:"include"});if(!response.ok)throw Error("Unable to revoke device.")},"Device access revoked.")}>Revoke</button>}
       </div>)}
       {!activityDevices.some(d=>d.status!=="pending")&&<p className="jg-device-empty">No assigned devices yet. Assign a pending laptop above to get started.</p>}
      </div>
     </section>
     <details className="jg-device-advanced"><summary>Manual enrollment · advanced options</summary>
      <p className="field-help">Most company laptops register automatically with v0.6. Use one-time codes or manual tokens only for a supported legacy installation. Keep codes private.</p>
      <div className="jg-device-manual-actions"><button type="button" className="employee-cancel" disabled={busy} onClick={()=>void save(async()=>{const response=await fetch(api+"/activity-agent/invitations",{method:"POST",credentials:"include"});const data=await response.json().catch(()=>({}));if(!response.ok)throw Error(explainError(data,response.status));setInstallInvite(data)},"Installation code generated.")}>Generate one-time code</button>
       <label htmlFor="jg-manual-employee">Enroll an existing employee device</label>
       <select id="jg-manual-employee" value={activityEmployee} onChange={e=>setActivityEmployee(e.target.value)}><option value="">Choose employee</option>{staff.filter(p=>p.status==="active").map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
       <button type="button" className="employee-cancel" disabled={!activityEmployee||busy} onClick={()=>void save(async()=>{const response=await fetch(api+"/activity-agent/devices",{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({employee_id:Number(activityEmployee),device_label:"Windows workstation"})});if(!response.ok)throw Error("Unable to enroll employee device.");setEnrollment(await response.json())},"Device enrolled. Copy the one-time token securely.")}>Create legacy token</button>
      </div>
      {installInvite&&<div className="jg-device-credential"><strong>One-time code · expires {new Date(installInvite.expires_at).toLocaleString()}</strong><code>{installInvite.invitation_code}</code><button type="button" className="employee-cancel" onClick={()=>void navigator.clipboard.writeText(String(installInvite.invitation_code))}>Copy</button></div>}
      {enrollment&&<div className="jg-device-credential"><strong>Legacy enrollment token · Device #{enrollment.device_id}</strong><code>{enrollment.token}</code><button type="button" className="employee-cancel" onClick={()=>void navigator.clipboard.writeText(String(enrollment.token))}>Copy</button><button type="button" className="employee-cancel" onClick={()=>setEnrollment(null)}>Dismiss</button></div>}
     </details>
    </div>
   </section>}
  {tab==="notifications"&&hr&&<section className="employee-surface"><h3><Bell size={17}/> Notification channel rules</h3>
   <p className="field-help">Rules control notification queues. Email/SMS/push/WhatsApp are not marked as delivered without provider connections.</p>
   <div className="ops-table">{["approval","birthday","document_renewal","helpdesk","offer","exit"].map(event=>{
    const config=rules.find(r=>r.event===event)||{event,email:true,sms:false,push:false,whatsapp:false};
    return <div className="ops-row" key={event}><strong>{event.replace(/_/g," ")}</strong>{(["email","sms","push","whatsapp"] as const).map(ch=>
     <label key={ch} className="ops-check"><input type="checkbox" checked={Boolean(config[ch])}
      onChange={e=>void save(()=>call("/notification-rules","PUT",{...config,[ch]:e.target.checked}),"Notification rule updated.")}/>{ch}</label>)}</div>
   })}</div>
   <h3>My notification queue</h3><div className="ops-table">{notifications.map(n=><div className="ops-row" key={n.id}><strong>{n.subject}</strong><span>{n.channel} · {n.status}</span><small>{n.body}</small></div>)}</div>
  </section>}
  {tab==="assets"&&<PeopleOpsExtras api={api} user={user}/>}
  {tab==="audit"&&hr&&<section className="employee-surface"><h3><ShieldCheck size={17}/> HR change audit</h3>
   <p className="field-help">Append-only event records for new People Operations workflows. Existing legacy endpoints need an expanded audit migration.</p>
   <div className="ops-table">{audits.map(a=><div className="ops-row" key={a.id}><strong>{a.kind} · {a.action}</strong><span>Object #{a.object_id} · Actor #{a.actor_id}</span><small>{String(a.created_at||"").slice(0,19)}</small></div>)}</div>
   <p>SSO requires an organization identity provider. 2FA enrollment/login enforcement is a separate security rollout and is not enabled by this release.</p>
  </section>}
 </div>;
}

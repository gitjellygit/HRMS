"use client";
import {useEffect,useState} from "react";
import {BriefcaseBusiness,CalendarDays,ClipboardCheck,Megaphone,ReceiptText,Users} from "lucide-react";
import OverviewAttendance from "./OverviewAttendance";
type Item=Record<string,any>;
export default function RoleOverview({api,role,onNavigate,refreshKey}:{
 api:string;role:string;onNavigate:(section:string)=>void;refreshKey:number;
}){
 const hr=["admin","super_admin","hr"].includes(role);
 const accountant=role==="accountant";
 const [projects,setProjects]=useState<Item[]>([]);
 const [notices,setNotices]=useState<Item[]>([]);
 const [invoices,setInvoices]=useState<Item[]>([]);
 const [error,setError]=useState("");
 useEffect(()=>{
  let current=true;
  const get=async(path:string)=>{
    const r=await fetch(api+path,{credentials:"include"});
    if(!r.ok)throw Error("Could not load overview updates");
    return r.json();
  };
  Promise.all([
   get("/project-management/projects"),
   get("/people/announcements"),
   accountant?get("/finance/invoices"):Promise.resolve([])
  ]).then(([p,n,i])=>{if(current){setProjects(p);setNotices(n);setInvoices(i);setError("")}})
    .catch(e=>{if(current)setError((e as Error).message)});
  return()=>{current=false};
 },[api,role,refreshKey]);
 const active=projects.filter(p=>p.status==="active");
 const unpaid=invoices.filter(i=>["sent","overdue"].includes(i.status));
 return <div className="overview-personalized">
  {error&&<p role="alert" className="error">{error}</p>}
  <div className="overview-priority-grid">
   <section className="overview-feature-card">
    <div className="overview-feature-heading"><BriefcaseBusiness size={18}/><h2>{hr?"Active company projects":accountant?"Active billable projects":"My active placements"}</h2></div>
    <p className="overview-big-number">{active.length}</p>
    {active.length?active.slice(0,3).map(p=><div className="overview-tile-row" key={p.id}>
      <strong>{p.name}</strong><small>{p.client||"Client not specified"} · {p.project_number||"Project"}</small>
    </div>):<p className="muted">No active projects assigned yet.</p>}
    <button className="overview-text-link" onClick={()=>onNavigate(accountant?"finance":"projects")}>View {accountant?"billing projects":"projects"} →</button>
   </section>
   <section className="overview-feature-card">
    <div className="overview-feature-heading"><Megaphone size={18}/><h2>Company announcements</h2></div>
    {notices.length?notices.slice(0,3).map(n=><div className="overview-tile-row" key={n.id}>
      <strong>{n.title}</strong><small>{String(n.body||"").slice(0,115)}{String(n.body||"").length>115?"…":""}</small>
    </div>):<p className="muted">No company announcements yet.</p>}
    <button className="overview-text-link" onClick={()=>onNavigate("people")}>View announcements →</button>
   </section>
   <section className="overview-feature-card overview-action-card">
    <div className="overview-feature-heading">{accountant?<ReceiptText size={18}/>:hr?<Users size={18}/>:<CalendarDays size={18}/>}
     <h2>{accountant?"Invoices requiring follow-up":hr?"HR priorities":"Leave & attendance"}</h2>
    </div>
    {accountant?<><p className="overview-big-number">{unpaid.length}</p><p className="muted">Sent or overdue invoices awaiting payment.</p>
       <button className="overview-text-link" onClick={()=>onNavigate("finance")}>Open invoice ledger →</button></>:
     hr?<><p className="muted">Manage employee onboarding, company policies, and approvals from one place.</p>
       <button className="overview-text-link" onClick={()=>onNavigate("governance")}>Review pending HR changes →</button></>:
     <><p className="muted">Check leave balances, submit a request, or open your time records.</p>
       <button className="overview-text-link" onClick={()=>onNavigate("leaves")}>Request or review leave →</button></>}
   </section>
  </div>
  <details className="overview-attendance-collapse">
   <summary><ClipboardCheck size={17}/> Recent attendance <span>Expand only when needed</span></summary>
   <OverviewAttendance api={api} refreshKey={refreshKey}/>
  </details>
 </div>;
}

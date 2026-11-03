"use client";
import { useEffect, useState } from "react";
import { LayoutDashboard, Users, Clock3, CalendarDays, BriefcaseBusiness, Wallet, Award, LogOut } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
type Employee = { id:number; name:string; email:string; role:string; designation:string; department:string; joining_date:string; status:string };
type User = Employee;
type Entry = Record<string, any>;
const sections = [
  { id:"dashboard",label:"Overview",Icon:LayoutDashboard },
  { id:"employees",label:"Employees",Icon:Users },
  { id:"attendance",label:"Attendance",Icon:Clock3 },
  { id:"leaves",label:"Leave requests",Icon:CalendarDays },
  { id:"projects",label:"Projects",Icon:BriefcaseBusiness },
  { id:"bonuses",label:"Bonuses",Icon:Wallet },
  { id:"appraisals",label:"Appraisals",Icon:Award },
];
export default function Home() {
  const [token,setToken] = useState("");
  const [user,setUser] = useState<User|null>(null);
  const [section,setSection] = useState("dashboard");
  const [rows,setRows] = useState<Entry[]>([]);
  const [employees,setEmployees] = useState<Employee[]>([]);
  const [stats,setStats] = useState<Entry>({});
  const [form,setForm] = useState(false);
  const [fields,setFields] = useState<Entry>({});
  const [error,setError] = useState("");
  const [loading,setLoading] = useState(false);
  const canHR = user?.role === "admin" || user?.role === "hr";
  const canFinance = canHR || user?.role === "accountant";
  const canSeeEmployees = canFinance;
  const visible = sections.filter(s=>!(["employees","bonuses"].includes(s.id) && !canSeeEmployees));
  async function request(path:string,method="GET",body?:Entry,t=token) {
    const response = await fetch(API+path,{method,headers:{"Content-Type":"application/json",...(t?{Authorization:"Bearer "+t}:{})},body:body?JSON.stringify(body):undefined});
    if(!response.ok){ const detail=await response.json().catch(()=>({detail:"Request failed"})); throw Error(typeof detail.detail==="string"?detail.detail:"Please check your input"); }
    return response.json();
  }
  async function refresh(id=section,t=token) {
    try {
      setError("");
      const [data,people] = await Promise.all([
        request(id==="dashboard"?"/dashboard":"/"+id,"GET",undefined,t),
        user && ["admin","hr","accountant"].includes(user.role)?request("/employees","GET",undefined,t):Promise.resolve([])
      ]);
      if(id==="dashboard")setStats(data);else setRows(data);
      setEmployees(people);
    } catch(e){setError((e as Error).message);}
  }
  useEffect(()=>{const saved=sessionStorage.getItem("hrms_token");if(saved){request("/me","GET",undefined,saved).then(u=>{setToken(saved);setUser(u)}).catch(()=>sessionStorage.removeItem("hrms_token"));}},[]);
  useEffect(()=>{if(user&&token)refresh(section,token);},[user,token,section]);
  async function signIn(e:React.FormEvent<HTMLFormElement>) {
    e.preventDefault();setLoading(true);setError("");
    const fd=new FormData(e.currentTarget);
    try{const result=await request("/auth/login","POST",{email:fd.get("email"),password:fd.get("password")},"");sessionStorage.setItem("hrms_token",result.access_token);setToken(result.access_token);setUser(result.user);}
    catch(err){setError((err as Error).message)}finally{setLoading(false)}
  }
  function logout(){sessionStorage.removeItem("hrms_token");setUser(null);setToken("");setRows([]);}
  async function submit(e:React.FormEvent<HTMLFormElement>){
    e.preventDefault();setLoading(true);setError("");
    const fd=new FormData(e.currentTarget);const data=Object.fromEntries(fd.entries());
    try {
      const endpoint=section==="leaves"?"/leaves":section==="employees"?"/employees":section==="projects"?"/projects":section==="bonuses"?"/bonuses":"/appraisals";
      await request(endpoint,"POST",data);setForm(false);setFields({});await refresh();
    }catch(err){setError((err as Error).message)}finally{setLoading(false)}
  }
  async function action(path:string,body?:Entry){
    setLoading(true);setError("");
    try{await request(path,body?"PATCH":"POST",body);await refresh();}catch(err){setError((err as Error).message)}finally{setLoading(false)}
  }
  const names:Record<string,string> = Object.fromEntries(employees.map(e=>[String(e.id),e.name]));
  const formMap:Record<string,[string,string,string?][]> = {
    employees:[["name","Full name"],["email","Work email","email"],["password","Temporary password (12+ characters)","password"],["role","Role","role"],["designation","Job title"],["department","Department"],["phone","Phone"],["joining_date","Joining date","date"]],
    leaves:[["leave_type","Leave type","leave"],["start_date","From","date"],["end_date","To","date"],["reason","Reason"]],
    projects:[["name","Project name"],["client","Client"],["description","Description"]],
    bonuses:[["employee_id","Employee","employee"],["amount","Amount (INR)","number"],["period","Period (YYYY-MM)"],["reason","Reason"]],
    appraisals:[["employee_id","Employee","employee"],["period","Review period"],["rating","Rating (1–5)","rating"],["feedback","Feedback"]]
  };
  const headings:Record<string,string[]> = {
    employees:["Name","Email","Department","Designation","Role","Status"],
    attendance:["Employee","Punch in","Punch out","Hours"],
    leaves:["Employee","Type","From","To","Status","Action"],
    projects:["Project","Client","Status","Team"],
    bonuses:["Employee","Period","Amount","Reason","Status","Action"],
    appraisals:["Employee","Period","Rating","Feedback"]
  };
  function humanDate(value?:string){return value?new Date(value).toLocaleString("en-IN",{dateStyle:"medium",timeStyle:"short"}):"—"}
  function cell(row:Entry,key:string){
    if(key==="Name")return row.name;
    if(key==="Email")return row.email;
    if(key==="Department")return row.department || "—";
    if(key==="Designation")return row.designation || "—";
    if(key==="Role")return row.role;
    if(key==="Employee")return names[String(row.employee_id)]|| (row.employee_id===user?.id?user?.name:"Employee #"+row.employee_id);
    if(key==="Punch in")return humanDate(row.punch_in);
    if(key==="Punch out")return humanDate(row.punch_out);
    if(key==="Hours")return row.punch_out?((new Date(row.punch_out).getTime()-new Date(row.punch_in).getTime())/3600000).toFixed(2):"Working";
    if(key==="Type")return row.leave_type;
    if(key==="From")return row.start_date;
    if(key==="To")return row.end_date;
    if(key==="Action" && section==="leaves" && canHR && row.status==="pending")return <div className="actions"><button className="secondary" onClick={()=>action("/leaves/"+row.id,{status:"approved"})}>Approve</button><button className="secondary" onClick={()=>action("/leaves/"+row.id,{status:"rejected"})}>Reject</button></div>;
    if(key==="Action" && section==="bonuses" && (user?.role==="admin"||user?.role==="accountant") && row.status!=="paid")return <button className="secondary" onClick={()=>action("/bonuses/"+row.id,{status:row.status==="planned"?"approved":"paid"})}>{row.status==="planned"?"Approve":"Mark paid"}</button>;
    if(key==="Status")return <span className={"pill "+row.status}>{row.status}</span>;
    if(key==="Project")return row.name;
    if(key==="Client")return row.client||"—";
    if(key==="Team")return <button className="secondary" onClick={async()=>{try{const people=await request("/projects/"+row.id+"/team");alert(people.length?people.map((p:Employee)=>p.name).join(", "):"No one assigned yet")}catch(err){setError((err as Error).message)}}}>View team</button>;
    if(key==="Period")return row.period;
    if(key==="Amount")return "₹"+Number(row.amount).toLocaleString("en-IN");
    if(key==="Reason")return row.reason;
    if(key==="Rating")return row.rating+"/5";
    if(key==="Feedback")return row.feedback||"—";
    return "—";
  }
  if(!user)return <main className="login-wrap"><form className="login" onSubmit={signIn}><h1>JellyGit HRMS</h1><p className="muted">Sign in to manage your team.</p>{error&&<div className="error">{error}</div>}<input name="email" type="email" placeholder="Work email" required/><input name="password" type="password" placeholder="Password" required/><button className="primary" disabled={loading}>Sign in</button></form></main>;
  return <div className="shell"><aside className="sidebar"><div className="brand">Jelly<span>Git</span> HRMS</div><nav className="menu">{visible.map(({id,label,Icon})=><button key={id} onClick={()=>{setSection(id);setForm(false);setError("")}} className={section===id?"active":""}><Icon size={18}/>{label}</button>)}<button onClick={logout}><LogOut size={18}/>Sign out</button></nav></aside><main className="content"><div className="top"><div><h1 className="title">{sections.find(s=>s.id===section)?.label}</h1><div className="muted">Your team, in one place</div></div><div className="user"><b>{user.name}</b><br/><span className="muted">{user.role}</span></div></div>{error&&<div className="error">{error}</div>}
    {section==="dashboard"?<><div className="grid">{[["Team members",stats.employees??"—"],["Active projects",stats.active_projects??0],["Leave approvals",stats.pending_leaves??"—"],["My pending requests",stats.my_pending_leaves??0]].map(([name,value])=><div className="card" key={name}><div className="muted">{name}</div><h3>{value}</h3></div>)}</div><section className="panel"><h2>Quick actions</h2><p className="muted">Punch in or out, submit a leave request, or check your current work.</p><div className="actions"><button className="primary" disabled={loading} onClick={()=>action("/attendance/punch")}>Punch in / out</button><button className="secondary" onClick={()=>{setSection("leaves");setForm(true)}}>Request leave</button><button className="secondary" onClick={()=>setSection("projects")}>View projects</button></div></section></>:<section className="panel"><div className="section-head"><h2>{sections.find(s=>s.id===section)?.label}</h2><div className="actions">{section==="attendance"&&<button className="primary" disabled={loading} onClick={()=>action("/attendance/punch")}>Punch in / out</button>}{(section==="leaves"|| (canHR && ["employees","projects","bonuses","appraisals"].includes(section)))&&<button className="primary" onClick={()=>setForm(!form)}>{form?"Cancel":"+ Add new"}</button>}</div></div>
    {form&&formMap[section]&&<form className="form" onSubmit={submit}>{formMap[section].map(([key,label,type])=><label key={key}>{label}{type==="role"?<select name={key} required>{["employee","hr","accountant","admin"].map(r=><option key={r}>{r}</option>)}</select>:type==="leave"?<select name={key} required>{["Annual","Sick","Casual","Unpaid"].map(r=><option key={r}>{r}</option>)}</select>:type==="employee"?<select name={key} required><option value="">Select employee</option>{employees.map(e=><option key={e.id} value={e.id}>{e.name}</option>)}</select>:type==="rating"?<select name={key} required>{[1,2,3,4,5].map(r=><option key={r}>{r}</option>)}</select>:<input name={key} type={type||"text"} required={["name","email","password","leave_type","start_date","end_date","employee_id","amount","period","rating"].includes(key)} min={type==="number"?"0.01":undefined} step={type==="number"?"0.01":undefined}/>}</label>)}<button className="primary wide" disabled={loading}>Save</button></form>}
    <div className="table-wrap"><table><thead><tr>{headings[section].map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{rows.map(row=><tr key={row.id}>{headings[section].map(h=><td key={h}>{cell(row,h)}</td>)}</tr>)}</tbody></table>{rows.length===0&&<div className="empty">No records yet. {section==="attendance"?"Punch in to get started.":"Add your first record to get started."}</div>}</div></section>}
  </main></div>;
}

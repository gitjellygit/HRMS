"use client";
import {useCallback,useEffect,useRef,useState} from "react";
import {Bell,Check,CheckCheck,Archive,ChevronRight,X,RotateCcw,Trash2} from "lucide-react";

type Notice={id:number;event:string;title:string;body:string;destination:string;
 created_at:string;read:boolean;archived:boolean};
type Payload={items:Notice[];unread_count:number};

export default function NotificationCenter({api,onNavigate,viewAll=false,onBack}:{
 api:string;onNavigate:(section:string)=>void;viewAll?:boolean;onBack?:()=>void;
}){
 const [data,setData]=useState<Payload>({items:[],unread_count:0});
 const [open,setOpen]=useState(false);
 const [expanded,setExpanded]=useState<number|null>(null);
 const [showArchived,setShowArchived]=useState(false);
 const [error,setError]=useState("");
 const box=useRef<HTMLDivElement|null>(null);
 const load=useCallback(async(archived=false)=>{
   const r=await fetch(api+"/notification-center?limit=200&include_archived="+archived,{credentials:"include"});
   if(!r.ok)throw Error("Unable to load notifications");
   const json:Payload=await r.json();setData(json);
 },[api]);
 useEffect(()=>{
   let active=true;
   const fetchFresh=()=>{if(!active||document.visibilityState==="hidden")return;
     void load(viewAll&&showArchived).catch(e=>setError((e as Error).message))};
   fetchFresh();
   const interval=window.setInterval(fetchFresh,30000);
   document.addEventListener("visibilitychange",fetchFresh);
   window.addEventListener("focus",fetchFresh);
   return()=>{active=false;window.clearInterval(interval);document.removeEventListener("visibilitychange",fetchFresh);window.removeEventListener("focus",fetchFresh)};
 },[load,viewAll,showArchived]);
 useEffect(()=>{
   if(viewAll||!open)return;
   const outside=(e:MouseEvent)=>{if(box.current&&!box.current.contains(e.target as Node))setOpen(false)};
   const escape=(e:KeyboardEvent)=>{if(e.key==="Escape")setOpen(false)};
   document.addEventListener("mousedown",outside);
   document.addEventListener("keydown",escape);
   return()=>{document.removeEventListener("mousedown",outside);document.removeEventListener("keydown",escape)};
 },[open,viewAll]);
 async function post(path:string){
   setError("");
   try{
    const r=await fetch(api+"/notification-center"+path,{method:"POST",credentials:"include"});
    if(!r.ok)throw Error("Unable to update notification");
    await load(viewAll&&showArchived);
   }catch(e){setError((e as Error).message)}
 }
 function NotificationRow({item}:{item:Notice}){
  return <article className={"notification-item "+(!item.read?"is-unread":"")}>
   <div className="notification-item-header">
    <button className="notification-item-title" aria-expanded={expanded===item.id}
      onClick={()=>{setExpanded(expanded===item.id?null:item.id);if(!item.read)void post("/"+item.id+"/read")}}>
      <span className="notification-event">{item.event.replace(/_/g," ")}</span>
      <strong>{item.title}</strong>
      <small>{new Date(item.created_at).toLocaleString()}</small>
    </button>
    <div className="notification-row-actions">
      {!item.read&&!item.archived&&<button aria-label={"Mark "+item.title+" as read"} title="Mark as read" onClick={()=>void post("/"+item.id+"/read")}><Check size={16}/></button>}
      {!item.archived?<button aria-label={"Remove "+item.title+" from inbox"} title="Remove from inbox (kept in history)" onClick={()=>void post("/"+item.id+"/archive")}><Trash2 size={16}/></button>:
       <button aria-label={"Restore "+item.title} title="Restore to inbox" onClick={()=>void post("/"+item.id+"/restore")}><RotateCcw size={16}/></button>}
    </div>
   </div>
   {expanded===item.id&&<div className="notification-item-body"><p>{item.body}</p>
     {["dashboard","people","leaves","finance","projects","governance","payroll"].includes(item.destination)&&
       <button className="notification-action" onClick={()=>{setOpen(false);onNavigate(item.destination)}}>Open related section <ChevronRight size={14}/></button>}
   </div>}
  </article>
 }
 const list=data.items.filter(n=>showArchived||!n.archived);
 return viewAll?<section className="notification-page">
   <div className="notification-page-header"><div><h2>All notifications</h2><p>Mark messages as read or remove them from your inbox. Removed messages remain available in archived history.</p></div>
    <div className="notification-toolbar">
     <label className="notification-checkbox"><input type="checkbox" checked={showArchived} onChange={e=>setShowArchived(e.target.checked)}/>Show archived</label>
     <button className="notification-action" onClick={()=>void post("/read-all")}><CheckCheck size={15}/>Mark all read</button>
     <button className="notification-action" onClick={()=>void post("/archive-read")}><Trash2 size={15}/>Clear read</button>
     {onBack&&<button className="notification-action" onClick={onBack}>Back</button>}
    </div></div>
   {error&&<p role="alert" className="error">{error}</p>}
   <div className="notification-history">{list.map(item=><NotificationRow key={item.id} item={item}/>)}
    {!list.length&&<div className="notification-empty">No notifications to display.</div>}</div>
 </section>:<div className="notification-bell-wrap" ref={box}>
   <button type="button" className="notification-bell" aria-label={"Notifications, "+data.unread_count+" unread"}
     aria-expanded={open} aria-haspopup="dialog" title="Notifications" onClick={()=>{setOpen(v=>!v);void load().catch(()=>{})}}>
    <Bell size={19}/>{data.unread_count>0&&<span className="notification-count">{data.unread_count>99?"99+":data.unread_count}</span>}
   </button>
   {open&&<div role="dialog" aria-label="Recent notifications" className="notification-popover">
    <div className="notification-popover-heading"><strong>Notifications</strong>
      <div><button className="notification-action" onClick={()=>void post("/read-all")}><CheckCheck size={14}/>Read all</button>
      <button className="notification-action" onClick={()=>void post("/archive-read")}><Trash2 size={14}/>Clear read</button>
      <button aria-label="Close notifications" className="notification-close" onClick={()=>setOpen(false)}><X size={17}/></button></div>
    </div>
    {error&&<p role="alert" className="error">{error}</p>}
    <div className="notification-scroll">{list.slice(0,6).map(item=><NotificationRow key={item.id} item={item}/>)}
     {!list.length&&<div className="notification-empty">You're all caught up.</div>}</div>
    <button className="notification-see-all" onClick={()=>{setOpen(false);onNavigate("notifications")}}>See all notifications <ChevronRight size={15}/></button>
   </div>}
 </div>;
}

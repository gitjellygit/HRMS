"use client";
import {useMemo,useState} from "react";
import {ChevronDown,ChevronRight,CalendarDays} from "lucide-react";

type Punch={id:number;employee_id:number;punch_in:string;punch_out:string|null};
const dateKey=(value:string)=>new Date(value).toLocaleDateString("en-CA",{year:"numeric",month:"2-digit",day:"2-digit"});
const clock=(value:string)=>new Date(value).toLocaleTimeString("en-IN",{hour:"2-digit",minute:"2-digit"});
const duration=(p:Punch)=>p.punch_out?Math.max(0,(new Date(p.punch_out).getTime()-new Date(p.punch_in).getTime())/3600000):0;

export default function AttendanceByDay({records}:{records:Punch[]}){
 const groups=useMemo(()=>{
  const map=new Map<string,Punch[]>();
  for(const p of records){const key=dateKey(p.punch_in);map.set(key,[...(map.get(key)||[]),p])}
  return [...map.entries()].sort(([a],[b])=>b.localeCompare(a));
 },[records]);
 const [expanded,setExpanded]=useState<Record<string,boolean>>({});
 if(!records.length)return <div className="empty">No attendance yet. Punch in to start recording sessions.</div>;
 return <div className="attendance-days">{groups.map(([date,items],idx)=>{
  const open=expanded[date]??false;
  const total=items.reduce((hours,p)=>hours+duration(p),0);
  const live=items.some(p=>!p.punch_out);
  return <section className="attendance-day" key={date}>
   <button type="button" className="attendance-day-toggle" aria-expanded={open} onClick={()=>setExpanded(e=>({...e,[date]:!open}))}>
    {open?<ChevronDown size={18}/>:<ChevronRight size={18}/>}
    <CalendarDays size={17}/>
    <strong>{new Date(date+"T12:00:00").toLocaleDateString("en-IN",{day:"numeric",month:"short",year:"numeric",weekday:"short"})}</strong>
    <span>{items.length} {items.length===1?"session":"sessions"}</span>
    <span>{total.toFixed(2)} hours{live?" · Currently punched in":""}</span>
   </button>
   {open&&<div className="table-wrap"><table className="attendance-session-table"><thead><tr><th>Punch in</th><th>Punch out</th><th>Hours</th></tr></thead><tbody>{items.map(item=><tr key={item.id}><td>{clock(item.punch_in)}</td><td>{item.punch_out?clock(item.punch_out):<strong>Working now</strong>}</td><td>{item.punch_out?duration(item).toFixed(2):"In progress"}</td></tr>)}</tbody></table></div>}
  </section>;
 })}</div>;
}

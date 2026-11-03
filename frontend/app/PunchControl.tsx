"use client";
import {useCallback,useEffect,useState} from "react";
import {Clock3, LogIn, LogOut, RefreshCw} from "lucide-react";
type State={checked_in:boolean;punch_in:string|null;next_action:"punch_in"|"punch_out"};
export default function PunchControl({api,onChanged}:{api:string;onChanged?:()=>void}){
 const [state,setState]=useState<State|null>(null);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const fetchState=useCallback(async()=>{
  try{
   const r=await fetch(api+"/attendance/status",{credentials:"include"});
   if(!r.ok)throw Error("Could not retrieve your attendance status.");
   setState(await r.json());
  }catch(e){setError((e as Error).message)}
 },[api]);
 useEffect(()=>{void fetchState()},[fetchState]);
 async function punch(){
  setBusy(true);setError("");
  try{
   const res=await fetch(api+"/attendance/punch",{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"}});
   if(!res.ok)throw Error("Attendance action failed. Please retry.");
   await fetchState();
   onChanged?.();
  }catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 return <div className="punch-control"><div className="punch-status"><Clock3 size={17}/><div><strong>{state?.checked_in?"Currently punched in":"Not punched in"}</strong><small>{state?.checked_in&&state.punch_in?"Since "+new Date(state.punch_in).toLocaleString("en-IN"):"Your current attendance status"}</small></div></div><div className="punch-buttons"><button type="button" className="employee-primary" onClick={punch} disabled={busy||!state}>{state?.checked_in?<LogOut size={16}/>:<LogIn size={16}/>} {busy?"Updating…":state?.checked_in?"Punch out":"Punch in"}</button><button className="employee-icon-button" title="Refresh status" aria-label="Refresh attendance status" onClick={fetchState}><RefreshCw size={16}/></button></div>{error&&<p className="field-error" role="alert">{error}</p>}</div>;
}

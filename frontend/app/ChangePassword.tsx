"use client";
import {useState} from "react";
import FeedbackMotion from "./FeedbackMotion";
import {LockKeyhole,Eye,EyeOff} from "lucide-react";

export default function ChangePassword({api,required,onComplete}:{api:string;required:boolean;onComplete:()=>void}){
 const [oldPass,setOldPass]=useState("");
 const [newPass,setNewPass]=useState("");
 const [repeat,setRepeat]=useState("");
 const [show,setShow]=useState(false);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 async function change(event:React.FormEvent){
  event.preventDefault();setError("");
  if(newPass!==repeat){setError("New passwords do not match.");return}
  if(newPass.length<12||!/[A-Z]/.test(newPass)||!/[a-z]/.test(newPass)||!/[0-9]/.test(newPass)||!/[^A-Za-z0-9]/.test(newPass)){
   setError("Use 12+ characters with uppercase, lowercase, a number and special character.");return
  }
  setBusy(true);
  try{
   const r=await fetch(api+"/auth/change-password",{method:"POST",credentials:"include",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({current_password:required?null:oldPass,new_password:newPass})});
   const data=await r.json().catch(()=>({}));
   if(!r.ok)throw Error(typeof data.detail==="string"?data.detail:"Unable to change password.");
   setOldPass("");setNewPass("");setRepeat("");onComplete();
  }catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 return <section className={required?"password-change-required":"password-change-inline"}>
  <div className="password-change-card">
   <div className="core-head"><LockKeyhole size={21}/><div><h2>{required?"Change your temporary password":"Change password"}</h2><p>{required?"For security, set your own password before accessing HRMS.":"Change your password; you will then sign in again."}</p></div></div>
   {error&&<FeedbackMotion type="error" compact message={error}/>}{busy&&<FeedbackMotion type="loading" compact message="Updating your password…"/>}
   <form className="password-change-form" onSubmit={change}>
    {!required&&<label>Current password<input type={show?"text":"password"} autoComplete="current-password" required value={oldPass} onChange={e=>setOldPass(e.target.value)}/></label>}
    <label>New password<input type={show?"text":"password"} autoComplete="new-password" required minLength={12} value={newPass} onChange={e=>setNewPass(e.target.value)}/></label>
    <label>Confirm new password<input type={show?"text":"password"} autoComplete="new-password" required minLength={12} value={repeat} onChange={e=>setRepeat(e.target.value)}/></label>
    <label className="password-visibility"><input type="checkbox" checked={show} onChange={e=>setShow(e.target.checked)}/>{show?<EyeOff size={15}/>:<Eye size={15}/>} Show passwords</label>
    <button className="employee-primary" disabled={busy}>{busy?"Saving…":"Change password and sign out"}</button>
   </form>
  </div>
 </section>;
}

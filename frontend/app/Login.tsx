"use client";
import { useEffect, useState } from "react";
import FeedbackMotion from "./FeedbackMotion";
import BrandIllustration from "./BrandIllustration";
import { ArrowLeft, Eye, EyeOff, LockKeyhole, Mail, ShieldCheck } from "lucide-react";

type User={id:number;name:string;email:string;role:string;designation:string;department:string;joining_date:string;status:string;must_change_password?:boolean};
export default function Login({api,onLogin,initialNotice=""}:{api:string;onLogin:(user:User)=>void;initialNotice?:string}){
 const [mode,setMode]=useState<"login"|"forgot"|"reset">("login");
 const [token,setToken]=useState("");
 const [email,setEmail]=useState("");
 const [remember,setRemember]=useState(false);
 const [show,setShow]=useState(false);
 const [error,setError]=useState("");
 const [message,setMessage]=useState(initialNotice);
 const [loading,setLoading]=useState(false);
 useEffect(()=>{
   setEmail(localStorage.getItem("hrms_email")||"");
   const reset=new URLSearchParams(window.location.search).get("reset");
   if(reset){setToken(reset);setMode("reset");window.history.replaceState(null,"",window.location.pathname);}
 },[]);
 async function submit(e:React.FormEvent<HTMLFormElement>){
   e.preventDefault();setError("");setMessage("");setLoading(true);
   const fd=new FormData(e.currentTarget);
   try{
     const path=mode==="login"?"/auth/login":mode==="forgot"?"/auth/forgot-password":"/auth/reset-password";
     const payload=mode==="login"?{email:fd.get("email"),password:fd.get("password"),remember,otp:fd.get("otp")||null}:mode==="forgot"?{email:fd.get("email")}:{token,password:fd.get("password")};
     if(mode==="reset"&&fd.get("password")!==fd.get("confirm"))throw Error("Passwords do not match");
     const response=await fetch(api+path,{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
     const data=await response.json().catch(()=>({}));
     if(!response.ok)throw Error(typeof data.detail==="string"?data.detail:"Unable to complete request");
     if(mode==="login"){
       if(remember)localStorage.setItem("hrms_email",String(fd.get("email")));else localStorage.removeItem("hrms_email");
       onLogin(data.user);
     }else if(mode==="forgot"){setMessage(data.message||"If your email is registered, you will receive a reset link.");}
     else{setMode("login");setMessage("Password updated. Sign in with your new password.");}
   }catch(err){setError((err as Error).message)}finally{setLoading(false)}
 }
 function go(mode:"login"|"forgot"){setMode(mode);setError("");setMessage("");}
 return <main className="auth-layout">
  <aside className="auth-showcase"><div className="showcase-content">
   <img className="brand-logo" src="https://jellygit.com/img/Logo.png" alt="JellyGit logo — Let's Bridge IT"/>
   <div className="showcase-tag">JELLYGIT · PEOPLE OPERATIONS</div>
   <h1>People first.<br/><em>Everything in one place.</em></h1>
   <p>A thoughtfully simple space for your people, attendance, leave, projects and growth.</p>
   <BrandIllustration asset="login-team" alt="JellyGit teammates collaborating around a laptop" className="showcase-team-art" loading="eager"/>
   <div className="showcase-foot"><ShieldCheck size={19}/>Built for your team. Private by design.</div>
  </div></aside>
  <section className="auth-side"><div className="auth-top"><span className="auth-brand">JELLYGIT <b>HRMS</b></span><span className="auth-secure"><LockKeyhole size={14}/> Secure access</span></div>
   <div className="auth-card">
    <div className="auth-icon">{mode==="login"?<LockKeyhole size={24}/>:<Mail size={24}/>}</div>
    <h2>{mode==="login"?"Welcome back":mode==="forgot"?"Forgot your password?":"Set a new password"}</h2>
    <p className="auth-subtitle">{mode==="login"?"Sign in with your JellyGit work account.":mode==="forgot"?"We'll send a secure reset link to your registered work email.":"Choose a new password (at least 12 characters)."}</p>
    {error&&<div className="error" role="alert">{error}</div>}
    {message&&<FeedbackMotion type="success" compact message={message}/>}
    <form className="auth-form" onSubmit={submit}>
     {mode!=="reset"&&<label>Work email<input name="email" type="email" placeholder="you@jellygit.com" defaultValue={email} autoComplete="username" required/></label>}
     {mode!=="forgot"&&<label>{mode==="login"?"Password":"New password"}<div className="password-field"><input name="password" type={show?"text":"password"} placeholder="Enter password" autoComplete={mode==="login"?"current-password":"new-password"} minLength={mode==="reset"?12:undefined} required/><button type="button" aria-label={show?"Hide password":"Show password"} onClick={()=>setShow(!show)}>{show?<EyeOff size={18}/>:<Eye size={18}/>}</button></div></label>}
     {mode==="login"&&<label>Authenticator code (if enabled)<input name="otp" type="text" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} autoComplete="one-time-code" placeholder="6-digit code"/></label>}
     {mode==="reset"&&<label>Confirm new password<input name="confirm" type="password" placeholder="Repeat password" autoComplete="new-password" minLength={12} required/></label>}
     {mode==="login"&&<div className="auth-options"><label className="auth-check"><input type="checkbox" checked={remember} onChange={e=>setRemember(e.target.checked)}/> Remember me for 30 days</label><button type="button" className="text-link" onClick={()=>go("forgot")}>Forgot password?</button></div>}
     <button className="auth-submit" disabled={loading}>{loading?"Please wait…":mode==="login"?"Sign in to HRMS":mode==="forgot"?"Send reset link":"Update password"}</button>
    </form>
    {mode!=="login"&&<button className="auth-back" onClick={()=>go("login")}><ArrowLeft size={16}/> Back to sign in</button>}
    <div className="auth-note"><ShieldCheck size={18}/>Accounts are created by JellyGit administrators only. Public registration is disabled.</div>
   </div>
   <footer className="auth-footer">© {new Date().getFullYear()} JellyGit · Internal HR management</footer>
  </section>
 </main>;
}

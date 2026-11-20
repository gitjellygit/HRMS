"use client";
import {useEffect,useState} from "react";
import {ShieldCheck,KeyRound} from "lucide-react";
import FeedbackMotion from "./FeedbackMotion";
export default function AccountSecurity({api}:{api:string}){
 const [enabled,setEnabled]=useState(false);
 const [current,setCurrent]=useState("");
 const [otp,setOtp]=useState("");
 const [secret,setSecret]=useState("");
 const [uri,setUri]=useState("");
 const [message,setMessage]=useState("");const [error,setError]=useState("");const [busy,setBusy]=useState(false);
 const status=()=>fetch(api+"/security/mfa",{credentials:"include"}).then(r=>r.ok?r.json():null).then(r=>setEnabled(!!r?.enabled)).catch(()=>{});
 useEffect(()=>{void status()},[api]);
 async function act(path:string,body:unknown,success:string){
  setBusy(true);setError("");setMessage("");
  try{
   const r=await fetch(api+"/security/mfa/"+path,{method:"POST",credentials:"include",
    headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
   const j=await r.json().catch(()=>({}));
   if(!r.ok)throw Error(typeof j.detail==="string"?j.detail:"Security action failed.");
   if(path==="setup"){setSecret(j.secret);setUri(j.otpauth_uri);}
   else{setSecret("");setUri("");setCurrent("");setOtp("");await status();}
   setMessage(success);
  }catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 return <section className="employee-surface account-security"><div className="core-head"><ShieldCheck size={19}/>
  <div><h3>Two-factor authentication</h3><p>Protect your account with an authenticator app.</p></div></div>
  {message&&<FeedbackMotion type="success" compact message={message}/>}
  {error&&<p role="alert" className="field-error">{error}</p>}
  <p className="field-help">Status: <strong>{enabled?"Enabled":"Not enabled"}</strong>. Authenticator codes rotate every 30 seconds. Save your recovery options securely.</p>
  {secret&&<div className="account-totp-secret">
   <strong>Set up authenticator</strong>
   <p>Enter this key manually in your authenticator app. The key is shown once.</p>
   <code>{secret}</code>
   <details><summary>Advanced provisioning URI</summary><code>{uri}</code></details>
   <label>Code from app<input inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={otp}
    onChange={e=>setOtp(e.target.value.replace(/\D/g,""))}/></label>
   <button className="employee-primary" disabled={busy||otp.length!==6}
    onClick={()=>void act("enable",{code:otp},"Two-factor authentication enabled.")}>Verify and enable</button>
  </div>}
  {!secret&&<div className="account-security-form">
   <label>Current password<input type="password" autoComplete="current-password" value={current}
    onChange={e=>setCurrent(e.target.value)}/></label>
   {enabled&&<label>Authenticator code<input inputMode="numeric" maxLength={6} pattern="[0-9]{6}"
    value={otp} onChange={e=>setOtp(e.target.value.replace(/\D/g,""))}/></label>}
   <button className={enabled?"employee-cancel":"employee-primary"} disabled={busy||!current||(enabled&&otp.length!==6)}
    onClick={()=>void act(enabled?"disable":"setup",enabled?{current_password:current,code:otp}:{current_password:current},
    enabled?"Two-factor authentication disabled.":"Enrollment started; verify the authenticator code.")}>
    <KeyRound size={15}/>{enabled?"Disable 2FA":"Set up 2FA"}</button>
  </div>}
 </section>;
}

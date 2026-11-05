"use client";
import dynamic from "next/dynamic";
import BrandIllustration from "./BrandIllustration";
import {CheckCircle2,AlertCircle,LoaderCircle,PartyPopper} from "lucide-react";
const Player=dynamic(()=>import("@lottiefiles/dotlottie-react").then(m=>m.DotLottieReact),{ssr:false});
const URLS={
 success:"https://assets-v2.lottiefiles.com/a/78bcb570-1171-11ee-af94-e3be98f41e97/Rp4s1hi13U.lottie",
 loading:"https://assets-v2.lottiefiles.com/a/7700e047-e40c-4ee5-acec-66aefd5ed2f8/pvT5LopBd6.lottie",
 congrats:"https://assets-v2.lottiefiles.com/a/637a1ad6-1171-11ee-ae8b-2fdd664f0b2d/Uf0htNY4TG.lottie"
};
export default function FeedbackMotion({type,message,compact=false}:{type:"success"|"loading"|"error"|"congrats";message:string;compact?:boolean}){
 const icon=type==="error"?<AlertCircle/>:type==="loading"?<LoaderCircle className="motion-fallback-spin"/>:type==="congrats"?<PartyPopper/>:<CheckCircle2/>;
 return <div role={type==="error"?"alert":"status"} aria-live="polite" className={"motion-feedback motion-"+type+(compact?" compact":"")}>
  <div className="motion-visual" aria-hidden="true">{type==="error"?icon:type==="loading"?<Player src={URLS.loading} loop autoplay/>:<><BrandIllustration asset="success-checklist" alt="" className="jellygit-success-art"/><span className="jellygit-success-fallback">{icon}</span></>}</div>
  <span>{message}</span>
 </div>;
}

"use client";
import {useState} from "react";

type BrandAsset="login-team"|"success-checklist"|"empty-folder-state"|"welcome-card-template"|"hero-ai-banner";

/**
 * Optional media: until the user's Canva exports are committed to /public/assets,
 * keep the existing UX usable instead of showing broken image icons.
 */
export default function BrandIllustration({asset,alt,className="",loading="lazy"}:{
 asset:BrandAsset;alt:string;className?:string;loading?:"eager"|"lazy";
}){
 const [failed,setFailed]=useState(false);
 if(failed)return null;
 return <img className={className} src={"/assets/"+asset+".webp"} alt={alt}
   loading={loading} decoding="async" onError={()=>setFailed(true)}/>;
}

export function WelcomeAnimation({className=""}:{className?:string}){
 const [failed,setFailed]=useState(false);
 if(failed)return null;
 return <div className={"jellygit-welcome-media "+className}>
   <video src="/assets/onboarding-welcome.mp4" autoPlay muted loop playsInline preload="metadata"
    aria-label="Welcome to JellyGit HRMS onboarding" onError={()=>setFailed(true)}/>
   <div className="jellygit-welcome-static" aria-hidden="true">
     <BrandIllustration asset="login-team" alt="" />
   </div>
 </div>;
}

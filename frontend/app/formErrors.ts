/** Actionable errors shared by all HRMS screens. Never discard FastAPI 422 details. */
export function explainError(payload:any, status=0):string {
 const detail=payload?.detail??payload;
 if(typeof detail==="string"&&detail.trim())return detail;
 if(typeof detail?.message==="string"&&detail.message.trim())return detail.message;
 if(Array.isArray(detail)&&detail.length){
  return detail.map((issue:any)=>{
   const path=(issue.loc||[]).filter((p:string|number)=>!["body","query","path"].includes(String(p))).join(" → ");
   let message=String(issue.msg||"This value is invalid").replace(/^Value error, /,"");
   if(issue.type==="missing")message="This field is required";
   if(issue.type==="string_too_short")message="Enter at least "+issue.ctx?.min_length+" characters";
   if(issue.type==="string_too_long")message="Use no more than "+issue.ctx?.max_length+" characters";
   if(issue.type==="greater_than_equal")message="Must be at least "+issue.ctx?.ge;
   if(issue.type==="less_than_equal")message="Must be no more than "+issue.ctx?.le;
   return (path?path.replaceAll("_"," ")+": ":"")+message;
  }).join(". ");
 }
 if(status===401)return "Your session expired. Sign in again to save changes.";
 if(status===403)return "You do not have permission for this action. Contact HR or your administrator.";
 if(status===409)return "This record has changed or the action was already completed. Refresh and try again.";
 if(status===413)return "The file is too large. Choose a smaller file.";
 if(status===422)return "Some form fields are invalid. Check the highlighted required fields and formats.";
 if(status>=500)return "The server could not finish this action. Your changes may not have been saved; try again or contact support.";
 return "The action was not completed. Review the form and try again.";
}
export async function responseError(response:Response):Promise<Error>{
 const payload=await response.json().catch(()=>null);
 return new Error(explainError(payload,response.status));
}

/** Named IANA zones keep EST/EDT and CST/CDT transitions correct. */
export const TIME_ZONES = [
 ["America/New_York", "US Eastern (EST / EDT)"],
 ["America/Chicago", "US Central (CST / CDT)"],
 ["Asia/Kolkata", "India (IST)"],
 ["UTC", "UTC"]
] as const;

function localParts(instant:number, timeZone:string) {
 const parts=new Intl.DateTimeFormat("en-US",{timeZone,year:"numeric",month:"2-digit",day:"2-digit",
  hour:"2-digit",minute:"2-digit",second:"2-digit",hourCycle:"h23"}).formatToParts(new Date(instant));
 const read=(key:string)=>Number(parts.find(x=>x.type===key)?.value);
 return [read("year"),read("month"),read("day"),read("hour"),read("minute"),read("second")];
}

/** Reject nonexistent and ambiguous local DST times rather than silently changing submitted punch times. */
export function zonedLocalToIso(local:string, timeZone:string):string {
 const match=/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(local);
 if(!match)throw Error("Enter a valid punch date and time.");
 const [,y,mo,d,h,mi]=match.map(Number);
 const base=Date.UTC(y,mo-1,d,h,mi);
 const requested=[y,mo,d,h,mi,0];
 const candidates=new Set<number>();
 for(const delta of [-86400000,0,86400000]) {
  const probe=base+delta;
  const parts=localParts(probe,timeZone);
  const asUTC=Date.UTC(parts[0],parts[1]-1,parts[2],parts[3],parts[4],parts[5]);
  const instant=base-(asUTC-probe);
  if(localParts(instant,timeZone).every((v,i)=>v===requested[i]))candidates.add(instant);
 }
 if(candidates.size!==1)throw Error(candidates.size
  ?"This time occurs twice when daylight saving ends. Choose an unambiguous time and ask HR to review the repeated hour."
  :"This local time does not exist because daylight saving starts. Choose a valid local time.");
 return new Date([...candidates][0]).toISOString();
}

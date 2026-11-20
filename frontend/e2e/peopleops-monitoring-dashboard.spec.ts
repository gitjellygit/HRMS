import {test,expect} from "@playwright/test";
import {login,navigate,users} from "./helpers";

test("HR monitoring tab shows responsive devices, refresh and employee detail",async({page})=>{
 const hr=users().find(u=>u.key==="hr")!;
 await login(page,hr);
 let hits=0;
 await page.route("**/activity-agent/devices",async route=>{
  hits++;
  await route.fulfill({status:200,contentType:"application/json",body:JSON.stringify([
   {id:101,employee_id:hr.id,employee_name:"QA Monitor",device_label:"QA-LAPTOP-01",status:"monitoring",last_seen:new Date().toISOString(),active_seconds:600,idle_seconds:60,apps:{"Code.exe":400,"Chrome.exe":200},exit_reason:"",revoked:false},
   {id:102,employee_id:hr.id,employee_name:"Second Tester",device_label:"QA-LAPTOP-02",status:"offline",last_seen:null,active_seconds:0,idle_seconds:0,apps:{},exit_reason:"",revoked:false},
   {id:103,employee_id:null,employee_name:"Unassigned device",device_label:"QA-NEW-03",status:"pending",last_seen:null,active_seconds:0,idle_seconds:0,apps:{},exit_reason:"",revoked:false}
  ])});
 });
 await navigate(page,"People operations");
 await page.getByRole("tab",{name:"Monitoring"}).click();
 const monitor=page.getByRole("region",{name:"Employee activity monitoring"});
 await expect(monitor.getByText("Live device monitoring")).toBeVisible();
 const cards=monitor.locator(".jg-monitoring-card");
 await expect(cards).toHaveCount(2);
 await expect(monitor.getByText("QA-NEW-03")).toHaveCount(0);
 await cards.filter({hasText:"QA Monitor"}).click();
 await expect(monitor.getByRole("region",{name:"Activity details for QA Monitor"})).toContainText("Code.exe");
 await monitor.getByRole("searchbox",{name:"Find employee or laptop"}).fill("Second");
 await expect(cards).toHaveCount(1);
 await monitor.getByRole("button",{name:"Refresh",exact:true}).click();
 await expect.poll(()=>hits).toBeGreaterThan(1);
});

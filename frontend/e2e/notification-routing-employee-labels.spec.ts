import {test,expect} from "@playwright/test";
import {login,navigate,users} from "./helpers";

const hr=()=>users().find(x=>x.key==="hr")!;
test("Helpdesk notification opens Helpdesk tab, never Announcements",async({page})=>{
 await login(page,hr());
 await page.route("**/notification-center?*",async route=>{
   await route.fulfill({status:200,contentType:"application/json",body:JSON.stringify({
    unread_count:1,items:[{
      id:999991,event:"helpdesk",title:"New HR helpdesk ticket",body:"Leave query",
      destination:"people",created_at:new Date().toISOString(),read:false,archived:false
    }]
   })});
 });
 await page.route("**/notification-center/999991/read",async route=>{
  await route.fulfill({status:200,contentType:"application/json",body:"{}"});
 });
 const bell=page.getByRole("button",{name:/Notifications, \d+ unread/});
 await bell.click();
 const dialog=page.getByRole("dialog",{name:"Recent notifications"});
 await dialog.getByRole("button",{name:/New HR helpdesk ticket/}).click();
 await dialog.getByRole("button",{name:"Open related section"}).click();
 await expect(page.locator(".content h1.title")).toHaveText("People operations");
 await expect(page.getByRole("tab",{name:"Helpdesk"})).toHaveAttribute("aria-selected","true");
 await expect(page.getByRole("heading",{name:"HR helpdesk"})).toBeVisible();
});
test("Payroll employee selector renders names rather than option IDs",async({page})=>{
 await login(page,hr());
 await navigate(page,"Payroll & expenses");
 await page.getByRole("button",{name:"Employee for payroll configuration"}).click();
 await expect(page.locator('button[role="option"]').first()).toBeVisible();
 const buttons=await page.locator('button[role="option"]').allTextContents();
 expect(buttons.some(x=>/^[0-9]+$/.test(x.trim()))).toBe(false);
});

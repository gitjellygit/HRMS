import {test,expect} from "@playwright/test";
import {login,navigate,users} from "./helpers";
import {API_URL,WEB_URL} from "../playwright.config";

const role=(name:string)=>users().find(x=>x.key===name)!;

test("notification bell shows announcements, supports read/archive and historical view",async({page})=>{
 await login(page,role("hr"));
 const title="QA Notification Bell "+Date.now();
 const announced=await page.request.post(API_URL+"/people/announcements",{
  headers:{Origin:WEB_URL},data:{title,
   body:"Please read the employee-pilot announcement before continuing your tasks.",requires_ack:true}});
 expect(announced.status()).toBe(201);
 await page.locator(".sidebar nav").getByRole("button",{name:"Sign out"}).click();
 await login(page,role("developer_a"));
 const bell=page.getByRole("button",{name:/Notifications, \d+ unread/});
 await expect(bell).toBeVisible();
 await bell.click();
 await expect(page.getByRole("dialog",{name:"Recent notifications"}).getByText(title)).toBeVisible();
 await page.getByRole("dialog",{name:"Recent notifications"}).locator(".notification-item-title").filter({hasText:title}).click();
 await expect(page.getByRole("dialog",{name:"Recent notifications"})).toContainText("employee-pilot announcement");
 await page.getByRole("dialog",{name:"Recent notifications"}).getByRole("button",{name:"Archive "+title,exact:true}).click();
 await expect(page.getByRole("dialog",{name:"Recent notifications"}).getByText(title)).toHaveCount(0);
 await page.getByRole("dialog",{name:"Recent notifications"}).getByRole("button",{name:"See all notifications"}).click();
 await expect(page.getByRole("heading",{name:"All notifications"})).toBeVisible();
 await page.getByLabel("Show archived").check();
 await expect(page.getByText(title)).toBeVisible();
});

test("role-aware overview shows relevant projects and attendance starts collapsed",async({page})=>{
 await login(page,role("developer_a"));
 await navigate(page,"Overview");
 await expect(page.getByRole("heading",{name:"My active placements"})).toBeVisible();
 await expect(page.getByRole("heading",{name:"Company announcements"})).toBeVisible();
 const attend=page.locator("details.overview-attendance-collapse");
 await expect(attend).not.toHaveAttribute("open");
 await attend.locator("summary").click();
 await expect(attend).toHaveAttribute("open","");
 await expect(attend.getByRole("heading",{name:"Recent attendance"})).toBeVisible();
 await page.locator(".sidebar nav").getByRole("button",{name:"Sign out"}).click();
 await login(page,role("accountant"));
 await navigate(page,"Overview");
 await expect(page.getByRole("heading",{name:"Active billable projects"})).toBeVisible();
 await expect(page.getByRole("heading",{name:"Invoices requiring follow-up"})).toBeVisible();
});

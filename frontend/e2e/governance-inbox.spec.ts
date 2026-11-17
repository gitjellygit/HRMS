import {test,expect} from '@playwright/test';
import {login,navigate,users} from './helpers';
import {API_URL,WEB_URL} from '../playwright.config';

const actor=(key:string)=>users().find(u=>u.key===key)!;
const origin={Origin:WEB_URL};

test('governance request uses named requester, notifies admin, then moves into history',async({page})=>{
 await login(page,actor('hr'));
 const title='QA Governance Layout '+Date.now();
 const proposed=await page.request.post(API_URL+'/governance/requests',{headers:origin,data:{
  kind:'company_policy',reason:'Review updated testing policy with proper approval and visibility controls',
  payload:{title,category:'general',description:'Policy for verifying the redesigned admin approval and notification workflow.',
   effective_date:new Date().toISOString().slice(0,10),active:true,audience_ids:[]}
 }});
 expect(proposed.status()).toBe(201);
 const id=(await proposed.json()).id;
 const duplicate=await page.request.post(API_URL+'/governance/requests',{headers:origin,data:{
  kind:'company_policy',reason:'Another identical submission',
  payload:{title,category:'general',description:'Policy for verifying the redesigned admin approval and notification workflow.',
   effective_date:new Date().toISOString().slice(0,10),active:true,audience_ids:[]}
 }});
 expect(duplicate.status()).toBe(409);
 await page.locator('.sidebar nav').getByRole('button',{name:'Sign out'}).click();
 await login(page,actor('admin'));
 const notification=await page.request.get(API_URL+'/notification-center');
 expect(notification.ok()).toBeTruthy();
 expect((await notification.json()).items.some((n:{destination:string;title:string})=>n.destination==='governance'&&n.title.includes('Approval needed'))).toBeTruthy();
 await navigate(page,'Admin approvals');
 const item=page.locator('.governance-request').filter({hasText:title});
 await expect(item).toBeVisible();
 await expect(item).toContainText(actor('hr').name);
 await expect(item.getByText('Employee #'+actor('hr').id)).toHaveCount(0);
 await expect(item.getByText('Pending review')).toBeVisible();
 await item.getByText('View proposed changes').click();
 await expect(item).toContainText('Policy title');
 await expect(item.locator('pre')).toHaveCount(0);
 await item.getByLabel('Decision reason').fill('The proposed policy has been reviewed and is approved for the test audience.');
 await item.getByRole('button',{name:'Approve & apply'}).click();
 await expect(page.getByRole('status')).toContainText('approved and applied');
 await expect(page.locator('.governance-list').first().locator('.governance-request').filter({hasText:title})).toHaveCount(0);
 await page.getByRole('button',{name:/View older approvals & rejections/}).click();
 const history=page.locator('.governance-history .governance-request').filter({hasText:title});
 await expect(history).toContainText('Approved');
 await expect(history).toContainText('The proposed policy has been reviewed');
});

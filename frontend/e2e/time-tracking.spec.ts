import {test,expect} from '@playwright/test';
import {login,navigate,users} from './helpers';
import {API_URL,WEB_URL} from '../playwright.config';
const persona=(key:string)=>users().find(u=>u.key===key)!;
const headers={Origin:WEB_URL};

test('Time & shifts has request validation and highlighted missing reason',async({page})=>{
 await login(page,persona('developer_a'));
 await navigate(page,'Time & shifts');
 await page.getByRole('tab',{name:'Requests'}).click();
 await page.getByRole('button',{name:'Send for manager approval'}).click();
 await expect(page.locator('.time-form-error')).toContainText('Please explain');
 await expect(page.locator('[name=reason]')).toHaveAttribute('aria-invalid','true');
});

test('employee can request WFH and manager can approve it',async({page})=>{
 await login(page,persona('developer_b'));
 await navigate(page,'Time & shifts');
 await page.getByRole('tab',{name:'Requests'}).click();
 const reason='Remote sprint planning QA '+Date.now();
 await page.locator('[name=reason]').fill(reason);
 await page.getByRole('button',{name:'Send for manager approval'}).click();
 await expect(page.locator('.motion-feedback')).toContainText('Request sent');
 await expect(page.locator('.time-list')).toContainText(reason);
 await page.locator('.sidebar nav').getByRole('button',{name:'Sign out'}).click();
 await login(page,persona('manager'));
 await navigate(page,'Time & shifts');
 await page.getByRole('tab',{name:'Requests'}).click();
 const row=page.locator('.time-list>div').filter({hasText:reason});
 await expect(row).toBeVisible();
 await row.getByRole('button',{name:'Approve'}).click();
 await expect(page.locator('.motion-feedback')).toContainText('approved');
});

test('HR creates a shift and assigns a roster',async({page})=>{
 await login(page,persona('hr'));
 await navigate(page,'Time & shifts');
 await page.getByRole('tab',{name:'Shifts & roster'}).click();
 const unique='QA shift '+Date.now();
 await page.locator('.time-form [name=name]').fill(unique);
 await page.getByRole('button',{name:'Create shift'}).click();
 await expect(page.locator('.time-list')).toContainText(unique);
 const id=String((await (await page.request.get(API_URL+'/time/shifts')).json()).find((s:{name:string})=>s.name===unique).id);
 await page.locator('[name=employee_id]').selectOption(String(persona('developer_a').id));
 await page.locator('[name=shift_id]').selectOption(id);
 await page.getByRole('button',{name:'Assign shift'}).click();
 await expect(page.locator('.motion-feedback')).toContainText('Roster saved');
});

test('employee can save and submit a timesheet',async({page})=>{
 await login(page,persona('sales_c'));
 await navigate(page,'Time & shifts');
 await page.getByRole('tab',{name:'Timesheets'}).click();
 const task='Write test cases '+Date.now();
 await page.locator('[name=task]').fill(task);
 await page.locator('[name=hours]').fill('2.5');
 await page.getByRole('button',{name:'Save hours'}).click();
 await expect(page.locator('.time-list')).toContainText(task);
 const row=page.locator('.time-list>div').filter({hasText:task});
 await row.getByRole('button',{name:'Submit'}).click();
 await expect(row).toContainText('submitted');
});

test('non-HR cannot edit attendance policy or list all requests',async({page})=>{
 await login(page,persona('sales_a'));
 await navigate(page,'Time & shifts');
 await expect(page.getByRole('tab',{name:'Rules & GPS'})).toHaveCount(0);
 const r=await page.request.put(API_URL+'/time/policy',{headers,data:{location:'all',grace_minutes:0}});
 expect(r.status()).toBe(403);
 const all=await page.request.get(API_URL+'/time/requests?scope=all');
 expect(all.status()).toBe(403);
});

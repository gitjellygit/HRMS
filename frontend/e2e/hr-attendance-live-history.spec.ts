import {test,expect} from '@playwright/test';
import {login,navigate,users} from './helpers';

test('HR can open a specific employee punch-in/out history',async({page})=>{
 const hr=users().find(p=>p.key==='hr')!;
 await login(page,hr);
 const sessions=[
  {id:101,employee_id:hr.id,punch_in:'2026-11-19T09:00:00Z',punch_out:null},
  {id:100,employee_id:hr.id,punch_in:'2026-11-18T09:00:00Z',punch_out:'2026-11-18T17:00:00Z'}
 ];
 await page.route('**/attendance?employee_id=*',async route=>{
  const id=Number(new URL(route.request().url()).searchParams.get('employee_id'));
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(id===hr.id?sessions:[])});
 });
 await navigate(page,'HR overview');
 await expect(page.getByText(/Attendance status updates automatically every 30 seconds/)).toBeVisible();
 const row=page.locator('table tbody tr').filter({hasText:hr.name}).first();
 await row.getByRole('button',{name:'View history'}).click();
 const detail=page.getByRole('region',{name:'Employee attendance history'});
 await expect(detail).toContainText(hr.name+' · Punch history');
 await expect(detail.getByText('In progress')).toBeVisible();
 await expect(detail.getByText('8.00 hours')).toBeVisible();
 await expect(detail.getByText('Checked in')).toBeVisible();
 await expect(detail.getByText('Completed')).toBeVisible();
 await detail.getByRole('button',{name:'Close'}).click();
 await expect(detail).toHaveCount(0);
});

test('HR attendance summary refreshes without resetting employee search',async({page})=>{
 const hr=users().find(p=>p.key==='hr')!;
 await login(page,hr);
 await page.clock.install();
 let requests=0;
 await page.route('**/leave/hr-overview?fy=*',async route=>{
  const response=await route.fetch();
  const body=await response.json();
  requests+=1;
  await route.fulfill({response,json:{...body,currently_checked_in:requests>1?7:0}});
 });
 await navigate(page,'HR overview');
 await expect(page.getByText(/Attendance status updates automatically every 30 seconds/)).toBeVisible();
 const search=page.getByPlaceholder('Search employees / department');
 await search.fill('employee');
 const before=requests;
 await page.clock.fastForward(31000);
 await expect.poll(()=>requests).toBeGreaterThan(before);
 await expect(page.locator('.employee-metric').filter({hasText:'Currently checked in'})).toContainText('7');
 await expect(search).toHaveValue('employee');
});

import {test,expect} from '@playwright/test';
import {login,navigate,users} from './helpers';

test('HR attendance dashboard filters by employee and expands session timeline',async({page})=>{
 const hr=users().find(u=>u.key==='hr')!;
 await login(page,hr);
 const logs=[
  {id:901,employee_id:hr.id,employee_name:hr.name,punch_in:'2026-11-18T09:00:00Z',punch_out:'2026-11-18T17:00:00Z'},
  {id:902,employee_id:hr.id,employee_name:hr.name,punch_in:'2026-11-19T09:00:00Z',punch_out:null}
 ];
 let calls=0;
 await page.route('**/attendance/team?*',async route=>{
  calls++;
  const search=new URL(route.request().url()).searchParams;
  const employeeId=search.get('employee_id');
  const items=employeeId && employeeId!==String(hr.id)?[]:logs;
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({items,has_more:false,next_offset:items.length})});
 });
 await navigate(page,'Attendance');
 const dashboard=page.getByRole('region',{name:'Team attendance dashboard'});
 await expect(dashboard).toBeVisible();
 await expect(dashboard.getByText('Completed session hours')).toBeVisible();
 await expect(dashboard.getByText('8.0 h')).toBeVisible();
 await expect(dashboard.getByText('Not tracked',{exact:true})).toHaveCount(0);
 const day=dashboard.locator('.jg-team-attendance-day').first();
 await day.locator('.jg-team-attendance-toggle').click();
 await expect(day.locator('table')).toBeVisible();
 await expect(day.getByRole('cell',{name:'8.00',exact:true})).toBeVisible();
 await expect(day.getByText('Not tracked')).toBeVisible();
 const range=dashboard.getByRole('button',{name:'Attendance date range'});
 await range.click();
 await page.locator('button[role="option"]').filter({hasText:'Last year'}).click();
 await expect.poll(()=>calls).toBeGreaterThan(1);
 const filter=dashboard.getByRole('button',{name:'Filter by employee'});
 await filter.click();
 await page.locator('button[role="option"]').filter({hasText:hr.name}).click();
 await expect.poll(()=>calls).toBeGreaterThan(2);
});

test('HR leave editor shows monthly credits and probation setting without technical tiers',async({page})=>{
 const hr=users().find(u=>u.key==='hr')!;
 await login(page,hr);
 await navigate(page,'Leave requests');
 await page.getByRole('button',{name:'Policies & balances'}).click();
 const editor=page.locator('.jg-leave-simple-form');
 await expect(editor).toBeVisible();
 await expect(editor.getByRole('button',{name:/Yearly allowance at once/})).toBeVisible();
 await expect(editor.getByRole('button',{name:/Add leave each month/})).toBeVisible();
 await expect(editor.getByText('Monthly accrual (two rates)')).toHaveCount(0);
 await editor.getByRole('button',{name:/Add leave each month/}).click();
 await expect(editor.locator('.jg-leave-month-grid input')).toHaveCount(12);
 await editor.getByRole('button',{name:'Distribute evenly'}).click();
 await expect(editor.getByText('22.00 days')).toBeVisible();
 await expect(editor.getByRole('button',{name:'Preview new joiner entitlement'})).toBeVisible();
 await editor.getByRole('button',{name:'Preview new joiner entitlement'}).click();
 await editor.getByLabel('Sample joining date').fill('2026-07-10');
 await expect(editor.getByText(/Probation completion:/)).toBeVisible();
});

import {test,expect} from '@playwright/test';
import {login,navigate,users} from './helpers';

test('HR overview keeps email queue compact, explains queued state and aligns override controls',async({page})=>{
 const hr=users().find(p=>p.key==='hr')!;
 await login(page,hr);
 await page.route('**/leave/email-outbox',async route=>{
  const deliveries=Array.from({length:12},(_,index)=>({
   id:index+1,recipient_id:hr.id,request_id:index+1,
   status:index===2?'failed':'queued',attempts:index===2?5:0,
   error:index===2?'Mail server unavailable':'',created_at:'2026-11-19T12:00:00Z'
  }));
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(deliveries)});
 });
 await navigate(page,'HR overview');
 const toggle=page.getByRole('button',{name:/Leave email delivery/});
 await expect(toggle).toHaveAttribute('aria-expanded','false');
 await expect(toggle).toContainText('12 undelivered');
 await expect(toggle).toContainText('11 queued');
 await expect(toggle).toContainText('1 need attention');
 await expect(page.getByRole('table').filter({has:page.getByRole('columnheader',{name:'Delivery detail'})})).toHaveCount(0);
 await toggle.click();
 await expect(toggle).toHaveAttribute('aria-expanded','true');
 const table=page.locator('.hr-mail-table');
 await expect(table).toBeVisible();
 await expect(table.locator('tbody tr')).toHaveCount(5);
 await expect(table.getByRole('button',{name:'Retry'})).toHaveCount(1);
 await expect(table.getByText('Automatic')).toHaveCount(4);
 await expect(table.getByText('Mail server unavailable')).toBeVisible();
 await page.getByRole('button',{name:/Needs attention/}).click();
 await expect(table.locator('tbody tr')).toHaveCount(1);
 await expect(table.getByRole('button',{name:'Retry'})).toHaveCount(1);
 await page.getByRole('button',{name:/Undelivered \(12\)/}).click();
 await page.getByRole('button',{name:'Show 5 more messages'}).click();
 await expect(table.locator('tbody tr')).toHaveCount(10);
 const form=page.locator('.hr-override-form');
 await expect(form.getByLabel('Override employee')).toBeVisible();
 await expect(form.getByLabel('Override leave type')).toBeVisible();
 await expect(form.getByLabel('Override days')).toBeVisible();
 await expect(form.getByRole('button',{name:'Save override'})).toBeVisible();
 await toggle.click();
 await expect(table).toHaveCount(0);
});

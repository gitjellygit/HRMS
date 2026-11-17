import {test,expect} from '@playwright/test';
import {login,navigate,users} from './helpers';

test('HR sees effective-dated leave calendar editor and 12-month preview',async({page})=>{
 const hr=users().find(u=>u.key==='hr')!;
 await login(page,hr);
 await navigate(page,'Leave requests');
 await page.getByRole('button',{name:'Policies & balances'}).click();
 await expect(page.getByText('Leave policies',{exact:true})).toBeVisible();
 const year=page.getByLabel('Leave year');
 await expect(year).toBeVisible();
 await expect(year.locator('option')).toHaveText([
  'Financial year (April–March)','Calendar year (January–December)'
 ]);
 await expect(page.getByLabel('Effective from')).toBeVisible();
 await expect(page.getByLabel('Reason for policy update')).toBeVisible();
 const method=page.getByLabel('Accrual method');
 await method.selectOption('custom');
 const section=page.locator('.leave-policy-panel');
 await expect(section.getByLabel('Apr leave credit')).toBeVisible();
 await expect(section.getByLabel('Mar leave credit')).toBeVisible();
 await expect(section.locator('.leave-month-grid input')).toHaveCount(12);
 await expect(section.getByText('Annual entitlement: 22.00 days',{exact:false})).toBeVisible();
 await expect(page.getByText('Policy change history',{exact:false})).toBeVisible();
 await expect(page.getByRole('button',{name:'Save policy'})).toBeVisible();
});

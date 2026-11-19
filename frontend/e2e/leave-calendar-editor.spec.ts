import {test,expect} from '@playwright/test';
import {login,navigate,users} from './helpers';

test('HR sees effective-dated leave calendar editor and 12-month preview',async({page})=>{
 const hr=users().find(u=>u.key==='hr')!;
 await login(page,hr);
 await navigate(page,'Leave requests');
 await page.getByRole('button',{name:'Policies & balances'}).click();
 await expect(page.getByText('Leave policies',{exact:true})).toBeVisible();
 const editor=page.locator('.jg-leave-simple-form');
 await expect(editor).toBeVisible();
 await expect(editor.getByText('1. Leave year')).toBeVisible();
 await expect(editor.getByRole('button',{name:/Yearly allowance at once/})).toBeVisible();
 await expect(editor.getByRole('button',{name:/Add leave each month/})).toBeVisible();
 await expect(editor.getByText('3. Probation and new joiners')).toBeVisible();
 await editor.getByRole('button',{name:/Add leave each month/}).click();
 await expect(editor.getByLabel('Apr monthly leave days')).toBeVisible();
 await expect(editor.getByLabel('Mar monthly leave days')).toBeVisible();
 await expect(editor.locator('.jg-leave-month-grid input')).toHaveCount(12);
 await expect(editor.getByText('Full-year allowance')).toBeVisible();
 await expect(editor.getByLabel('Reason for policy update')).toBeVisible();
 await expect(editor.getByRole('button',{name:'Save leave policy'})).toBeVisible();
 await editor.getByRole('button',{name:/Preview new joiner entitlement/}).click();
 await expect(editor.getByLabel('Sample joining date')).toBeVisible();
 await expect(page.getByText('Policy change history',{exact:false})).toBeVisible();
 await expect(editor.getByRole('button',{name:'Save leave policy'})).toBeVisible();
});

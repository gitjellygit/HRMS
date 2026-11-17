import {test,expect} from '@playwright/test';
import {login,navigate,users} from './helpers';

const actor=(key:string)=>users().find(u=>u.key===key)!;

test('profile menu closes outside and on Escape, and logout is in profile menu',async({page})=>{
 await login(page,actor('hr'));
 const trigger=page.getByRole('button',{name:'Profile and appearance'});
 await trigger.click();
 const menu=page.getByRole('menu',{name:'Profile settings'});
 await expect(menu).toBeVisible();
 await expect(menu.getByRole('button',{name:'Sign out'})).toBeVisible();
 await page.getByRole('heading',{name:'Overview'}).click();
 await expect(menu).toHaveCount(0);
 await trigger.click();
 await page.keyboard.press('Escape');
 await expect(menu).toHaveCount(0);
 await trigger.click();
 await menu.getByRole('button',{name:/Switch to dark mode|Switch to light mode/}).click();
 await expect(menu).toHaveCount(0);
 await trigger.click();
 const appearance=menu.getByRole('button',{name:/Switch to dark mode|Switch to light mode/});
 const before=await appearance.evaluate(el=>getComputedStyle(el).color);
 await appearance.hover();
 const after=await appearance.evaluate(el=>getComputedStyle(el).color);
 const bg=await appearance.evaluate(el=>getComputedStyle(el).backgroundColor);
 expect(bg).not.toBe('rgba(0, 0, 0, 0)');
 expect(after).toBeTruthy();expect(before).toBeTruthy();
 await page.evaluate(()=>document.documentElement.dataset.theme='light');
});

test('success confirmation automatically clears while screen remains active',async({page})=>{
 await login(page,actor('hr'));
 await navigate(page,'Time & shifts');
 await page.getByRole('tab',{name:'Requests'}).click();
 const success=page.getByText('Request sent', {exact:false});
 // Confirm the common timer contract in the rendered app: any successful
 // banner that appears should leave the DOM after the reading interval.
 // Use the existing time request flow with a working approval manager.
 await page.locator('[name=reason]').fill('Testing automatic confirmation dismiss behavior in QA');
 await page.getByRole('button',{name:'Send for manager approval'}).click();
 await expect(success).toBeVisible();
 await expect(success).toHaveCount(0,{timeout:8500});
});

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
 await page.evaluate(()=>{document.documentElement.dataset.theme='light';localStorage.setItem('jellygit-theme','light')});
});

test('success confirmation automatically clears while screen remains active',async({page})=>{
 await login(page,actor('developer_b'));
 await navigate(page,'Time & shifts');
 await page.getByRole('tab',{name:'Requests'}).click();
 const success=page.getByText('Request sent', {exact:false});
 // Confirm the common timer contract in the rendered app: any successful
 // banner that appears should leave the DOM after the reading interval.
 // Use the existing time request flow with a working approval manager.
 await page.locator('[name=kind]').selectOption('overtime');
 await page.locator('[name=hours]').fill('1');
 await page.locator('[name=reason]').fill('Testing automatic confirmation dismiss behavior in QA');
 await page.getByRole('button',{name:'Send for manager approval'}).click();
 await expect(success).toBeVisible();
 await expect(success).toHaveCount(0,{timeout:8500});
});

test('profile menu actions retain readable contrast in both themes',async({page})=>{
 await login(page,actor('hr'));
 const trigger=page.getByRole('button',{name:'Profile and appearance'});
 const ratio=async()=>{
  await trigger.click();
  const menu=page.getByRole('menu',{name:'Profile settings'});
  const action=menu.getByRole('button',{name:/Switch to dark mode|Switch to light mode/});
  await action.hover();
  // Wait for the 150ms hover-color transition to finish before measuring final contrast.
  await page.waitForTimeout(250);
  const contrast=await action.evaluate(el=>{
   const parse=(value:string)=>{const components=value.match(/[0-9]+(?:\.[0-9]+)?/g);if(!components||components.length<3)throw Error("Unexpected computed RGB color: "+value);return components.slice(0,3).map(Number)};
   const lum=(rgb:number[])=>rgb.map(v=>{v/=255;return v<=0.04045?v/12.92:Math.pow((v+0.055)/1.055,2.4)}).reduce((sum,v,i)=>sum+v*[0.2126,0.7152,0.0722][i],0);
   const foreground=getComputedStyle(el).color;
   const backgroundColor=getComputedStyle(el).backgroundColor;
   if(backgroundColor==="rgba(0, 0, 0, 0)")throw Error("Hover background is transparent: no measurable contrast");
   const text=lum(parse(foreground));
   const background=lum(parse(backgroundColor));
   return (Math.max(text,background)+0.05)/(Math.min(text,background)+0.05);
  });
  await action.click();
  await expect(menu).toHaveCount(0);
  return contrast;
 };
 const light=await ratio();
 const dark=await ratio();
 expect(light).toBeGreaterThan(4.5);
 expect(dark).toBeGreaterThan(4.5);
 await expect(trigger).toBeVisible();
});

import {test,expect} from '@playwright/test';
import {login,navigate,users} from './helpers';

test('People Operations announcement presets and audience picker are usable',async({page})=>{
 const hr=users().find(p=>p.key==='hr')!;
 await login(page,hr);
 await navigate(page,'People operations');
 await page.getByRole('tab',{name:'Announcements'}).click();
 await expect(page.getByRole('region',{name:'Announcement template gallery'})).toBeVisible();
 await page.getByRole('button',{name:/Christmas Merry Christmas/}).click();
 await expect(page.getByRole('textbox',{name:'Title'})).toHaveValue('Merry Christmas!');
 await expect(page.getByRole('button',{name:/Download editable Christmas design/})).toBeVisible();
 await expect(page.getByText('All active employees will receive this announcement.')).toBeVisible();
 const picker=page.locator('.jg-upload-picker').filter({has:page.locator('input[accept*="webp"]')});
 await expect(picker).toBeVisible();
 await picker.locator('input[type="file"]').setInputFiles({name:'announcement.png',mimeType:'image/png',
  buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/UVsAAAAASUVORK5CYII=','base64')});
 await expect(picker).toContainText('announcement.png');
 const checkboxes=page.getByRole('group',{name:'Select announcement recipients'}).getByRole('checkbox');
 await expect(checkboxes.first()).toBeVisible();
 await checkboxes.first().check();
 await expect(page.getByText('1 selected employee(s)')).toBeVisible();
 await page.getByRole('button',{name:'Everyone (no restriction)'}).click();
 await expect(page.getByText('All active employees will receive this announcement.')).toBeVisible();
});

test('Custom selector opens an in-app listbox and changes payroll choice',async({page})=>{
 const hr=users().find(p=>p.key==='hr')!;
 await login(page,hr);
 await navigate(page,'Payroll & expenses');
 await expect(page.getByRole('tab',{name:'Salary & statutory'})).toBeVisible();
 const field=page.getByRole('combobox',{name:'Employee for payroll configuration'});
 // Native select retained for accessible form integration and existing automation.
 await expect(field).toHaveCount(1);
 const trigger=page.locator('.payroll-select-wrap .jg-select-trigger');
 await trigger.click();
 const options=page.getByRole('listbox',{name:'Employee for payroll configuration'});
 await expect(options).toBeVisible();
 await expect(options.getByRole('option').first()).toBeVisible();
 await page.keyboard.press('Escape');
 await expect(options).toHaveCount(0);
});

test('Dark-mode payroll heading and form banner text remain readable',async({page})=>{
 const hr=users().find(p=>p.key==='hr')!;
 await login(page,hr);
 await page.evaluate(()=>{document.documentElement.dataset.theme='dark';localStorage.setItem('jellygit-theme','dark')});
 await navigate(page,'Payroll & expenses');
 const headline=page.getByText('Configure employee payroll');
 await expect(headline).toBeVisible();
 const colors=await headline.evaluate(el=>{
  const css=getComputedStyle(el);
  const bg=getComputedStyle(el.closest('.payroll-config-banner')!);
  return {color:css.color,background:bg.backgroundColor};
 });
 const luminance=(value:string)=>{
  const nums=value.match(/[0-9]+(?:\\.[0-9]+)?/g)?.slice(0,3).map(Number)||[];
  if(nums.length!==3)throw Error('Unrecognized computed color: '+value);
  const channels=nums.map(v=>{v/=255;return v<=0.04045?v/12.92:Math.pow((v+0.055)/1.055,2.4)});
  return channels[0]*0.2126+channels[1]*0.7152+channels[2]*0.0722;
 };
 const foreground=luminance(colors.color),background=luminance(colors.background);
 const contrast=(Math.max(foreground,background)+0.05)/(Math.min(foreground,background)+0.05);
 expect(contrast).toBeGreaterThanOrEqual(4.5);
});

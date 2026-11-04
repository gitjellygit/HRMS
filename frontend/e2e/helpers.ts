import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { expect, type Page } from '@playwright/test';
import { TEST_PASSWORD } from './global-setup';

export type Persona = {
  key: string; name: string; department: string; code: string;
  role: string; designation: string; email: string; id: number;
};
export function users(): Persona[] {
  return JSON.parse(readFileSync(resolve(__dirname, '.auth/users.json'), 'utf8')).users as Persona[];
}
export async function login(page: Page, user: Persona) {
  await page.goto('/');
  await expect(page.locator('input[name="email"]')).toBeVisible();
  await page.locator('input[name="email"]').fill(user.email);
  await page.locator('input[name="password"]').fill(TEST_PASSWORD);
  await page.getByRole('button', { name: /sign in/i }).click();
  await expect(page.locator('.sidebar .brand')).toBeVisible();
  await expect(page.locator('.top .user')).toContainText(user.name);
}
export async function navigate(page: Page, label: string) {
  await page.locator('.sidebar nav').getByRole('button', { name: label, exact: true }).click();
  await expect(page.locator('.content h1.title')).toHaveText(label);
}
export const NAV = [
  'Overview', 'Employees', 'Attendance', 'Leave requests', 'Projects',
  'Bonuses', 'Appraisals', 'HR overview', 'Policies', 'Organization',
  'Org chart', 'My profile', 'Profile approvals', 'Bulk data & expiries',
] as const;
export function permitted(role: string): Set<string> {
  const hiddenHR = ['HR overview', 'Policies', 'Organization', 'Bulk data & expiries'];
  const hiddenEmployee = ['Employees', 'Bonuses'];
  const all = new Set<string>(NAV);
  if (!['super_admin', 'admin', 'hr'].includes(role)) hiddenHR.forEach(x => all.delete(x));
  if (!['super_admin', 'admin', 'hr', 'accountant'].includes(role)) hiddenEmployee.forEach(x => all.delete(x));
  if (!['super_admin', 'admin', 'hr', 'manager', 'employee'].includes(role)) all.delete('Profile approvals');
  return all;
}

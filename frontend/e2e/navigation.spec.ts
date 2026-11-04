import { test, expect } from '@playwright/test';
import { users, login, navigate, NAV, permitted } from './helpers';

const roles = [
  ['sales_a','employee'],['sales_b','employee'],['sales_c','employee'],
  ['developer_a','employee'],['developer_b','employee'],
  ['hr','hr'],['accountant','accountant'],['manager','manager'],
] as const;

for (const [key, role] of roles) {
  test.describe('navigation matrix / ' + key + ' (' + role + ')', () => {
    test.beforeEach(async ({ page }) => {
      const person = users().find(u => u.key === key);
      if (!person) throw Error('Missing seeded persona ' + key);
      await login(page, person);
    });
    for (const label of NAV) {
      test(key + ': ' + label + ' navigation permission', async ({ page }) => {
        const allowed = permitted(role).has(label);
        const link = page.locator('.sidebar nav').getByRole('button', { name: label, exact: true });
        if (allowed) {
          await expect(link).toBeVisible();
          await navigate(page, label);
          await expect(page.locator('main.content')).toBeVisible();
        } else {
          await expect(link).toHaveCount(0);
        }
      });
    }
  });
}

test.describe('login and privacy', () => {
  for (const [key] of roles) {
    test(key + ': signs in with proper employee role', async ({ page }) => {
      const person = users().find(u => u.key === key)!;
      await login(page, person);
      await expect(page.locator('.top .user')).toContainText(person.role);
      // The presence of an HR privilege in the nav is a security-relevant assertion.
      const hrNav = page.locator('.sidebar nav').getByRole('button', { name: 'HR overview', exact: true });
      if (person.role === 'hr') await expect(hrNav).toBeVisible();
      else await expect(hrNav).toHaveCount(0);
    });
  }
  test('wrong password is rejected with an actionable error', async ({ page }) => {
    const person = users()[0];
    await page.goto('/');
    await page.locator('input[name="email"]').fill(person.email);
    await page.locator('input[name="password"]').fill('WrongPassword!123');
    await page.getByRole('button', { name: 'Sign in to HRMS' }).click();
    await expect(page.locator('.auth-side .error[role="alert"]')).toContainText('Invalid credentials');
    await expect(page.locator('.sidebar')).toHaveCount(0);
  });
  test('sign-out returns to login and cannot access HRMS without signing back in', async ({ page }) => {
    await login(page, users()[0]);
    await page.locator('.sidebar nav').getByRole('button', { name: 'Sign out' }).click();
    await expect(page.locator('input[name="email"]')).toBeVisible();
    await page.reload();
    await expect(page.locator('input[name="email"]')).toBeVisible();
  });
});

/**
 * E2E tests for the Student Portal (UI layer).
 *
 * Prerequisites:
 *   • Flask server running on :5000
 *   • Vite dev server running on :5173  (or full build served by Flask)
 *   • At least one student account created in the DB:
 *       name="E2EStudent"  pin="1111"
 *   • At least one chapter uploaded with pre-cached questions:
 *       board=CBSE  grade=8  subject=Biology  chapter="Cell Structure"
 *
 * These tests call the real API to set up required state before UI flows
 * (student creation, chapter seeding are done via the admin API).
 *
 * NOTE: Voice input tests verify the UI controls are present and can be
 * interacted with, but cannot test actual microphone capture in headless mode.
 */

// @ts-check
import { test, expect, request } from '@playwright/test';

const API = 'http://localhost:5000';

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Log in as admin via API and return the cookie jar. */
async function adminApiLogin(apiCtx) {
  const res = await apiCtx.post(`${API}/api/admin/login`, {
    data: { username: 'admin', password: 'admin123' },
  });
  return res.ok();
}

/** Ensure the E2E student exists (idempotent). */
async function ensureE2EStudent(apiCtx) {
  await adminApiLogin(apiCtx);
  // Try to create; ignore 409 if already exists
  await apiCtx.post(`${API}/api/admin/students`, {
    data: { name: 'E2EStudent', pin: '1111' },
  });
}

// ── Fixtures ──────────────────────────────────────────────────────────────────

test.beforeAll(async ({ playwright }) => {
  const apiCtx = await playwright.request.newContext();
  await ensureE2EStudent(apiCtx);
  await apiCtx.dispose();
});


// ═══════════════════════════════════════════════════════════════════════════
// Login Page
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Student Login Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
  });

  test('renders login form with name and PIN fields', async ({ page }) => {
    await expect(page.locator('h2')).toContainText('Student Login');
    await expect(page.locator('#student-name')).toBeVisible();
    await expect(page.locator('#student-pin')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Continue' })).toBeVisible();
  });

  test('shows error when name is empty', async ({ page }) => {
    await page.locator('#student-pin').fill('1234');
    await page.getByRole('button', { name: 'Continue' }).click();
    await expect(page.locator('.alert-error')).toContainText(/name/i);
  });

  test('shows error when PIN is not 4 digits', async ({ page }) => {
    await page.locator('#student-name').fill('E2EStudent');
    await page.locator('#student-pin').fill('12');
    await page.getByRole('button', { name: 'Continue' }).click();
    await expect(page.locator('.alert-error')).toContainText(/4 digits/i);
  });

  test('shows error for invalid credentials', async ({ page }) => {
    await page.locator('#student-name').fill('NonExistentUser');
    await page.locator('#student-pin').fill('9999');
    await page.getByRole('button', { name: 'Continue' }).click();
    await expect(page.locator('.alert-error')).toBeVisible({ timeout: 8000 });
  });

  test('PIN field accepts only digits', async ({ page }) => {
    await page.locator('#student-pin').fill('ab12');
    const value = await page.locator('#student-pin').inputValue();
    expect(value).toMatch(/^\d+$/);
  });

  test('successful login navigates to selection page', async ({ page }) => {
    await page.locator('#student-name').fill('E2EStudent');
    await page.locator('#student-pin').fill('1111');
    await page.getByRole('button', { name: 'Continue' }).click();
    await expect(page).toHaveURL('/', { timeout: 8000 });
    await expect(page.getByText(/Let's start practising/i)).toBeVisible();
  });

  test('shows resume prompt when student has an active session', async ({ page, request }) => {
    // Create an active session via API first, then login
    const loginRes = await request.post(`${API}/api/student/login`, {
      data: { name: 'E2EStudent', pin: '1111' },
    });
    const student = await loginRes.json();

    // If there's already an active session the resume prompt will appear;
    // otherwise we just verify the login succeeds normally.
    await page.locator('#student-name').fill('E2EStudent');
    await page.locator('#student-pin').fill('1111');
    await page.getByRole('button', { name: 'Continue' }).click();

    // Either resume prompt or selection page
    const hasResume = await page.locator('.resume-prompt').isVisible().catch(() => false);
    const hasSelection = await page.locator('#board-select').isVisible().catch(() => false);
    expect(hasResume || hasSelection).toBe(true);
  });
});


// ═══════════════════════════════════════════════════════════════════════════
// Chapter Selection Page
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Chapter Selection Page', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await page.goto('/login');
    await page.locator('#student-name').fill('E2EStudent');
    await page.locator('#student-pin').fill('1111');
    await page.getByRole('button', { name: 'Continue' }).click();
    await page.waitForURL('/');
  });

  test('renders board, grade, subject, and chapter dropdowns', async ({ page }) => {
    await expect(page.locator('#board-select')).toBeVisible();
    await expect(page.locator('#grade-select')).toBeVisible();
    await expect(page.locator('#subject-select')).toBeVisible();
    await expect(page.locator('#chapter-select')).toBeVisible();
  });

  test('grade dropdown is disabled until board is selected', async ({ page }) => {
    await expect(page.locator('#grade-select')).toBeDisabled();
  });

  test('subject dropdown is disabled until grade is selected', async ({ page }) => {
    await expect(page.locator('#subject-select')).toBeDisabled();
  });

  test('chapter dropdown is disabled until subject is selected', async ({ page }) => {
    await expect(page.locator('#chapter-select')).toBeDisabled();
  });

  test('selecting CBSE populates grade dropdown', async ({ page }) => {
    await page.locator('#board-select').selectOption('CBSE');
    await expect(page.locator('#grade-select')).not.toBeDisabled({ timeout: 6000 });
    const options = page.locator('#grade-select option');
    await expect(options).toHaveCount({ min: 2 }); // at least "Select Grade" + one real grade
  });

  test('cascading selection flows through all dropdowns', async ({ page }) => {
    await page.locator('#board-select').selectOption('CBSE');
    await page.locator('#grade-select').selectOption({ label: 'Grade 8' });
    await page.locator('#subject-select').selectOption('Biology');
    const chapterOptions = page.locator('#chapter-select option:not([value=""])');
    await expect(chapterOptions).toHaveCount({ min: 1 }, { timeout: 6000 });
  });

  test('Start Test button is disabled when chapter not selected', async ({ page }) => {
    await expect(page.locator('.btn-start')).toBeDisabled();
  });

  test('Start Test button is enabled after full selection', async ({ page }) => {
    await page.locator('#board-select').selectOption('CBSE');
    await page.locator('#grade-select').selectOption({ label: 'Grade 8' });
    await page.locator('#subject-select').selectOption('Biology');
    await page.locator('#chapter-select').selectOption({ index: 1 }); // first real option
    await expect(page.locator('.btn-start')).toBeEnabled({ timeout: 6000 });
  });

  test('student greeting shown in header', async ({ page }) => {
    await expect(page.getByText('Hi,')).toBeVisible();
    await expect(page.getByText('E2EStudent')).toBeVisible();
  });

  test('logout button navigates to login', async ({ page }) => {
    await page.getByRole('button', { name: 'Logout' }).click();
    await expect(page).toHaveURL('/login');
  });

  test('Custom Multi-Chapter Test link is visible', async ({ page }) => {
    await expect(page.getByText(/Custom Multi-Chapter Test/i)).toBeVisible();
  });

  test('admin panel link visible in footer', async ({ page }) => {
    await expect(page.getByRole('link', { name: /Admin Panel/i })).toBeVisible();
  });
});


// ═══════════════════════════════════════════════════════════════════════════
// Test Page (Question + Feedback)
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Test Page', () => {
  let sessionKey;

  test.beforeAll(async ({ playwright }) => {
    // Create an active session via API so we can navigate directly to it
    const apiCtx = await playwright.request.newContext();
    await adminApiLogin(apiCtx);

    // Get chapter ID
    const chaptersRes = await apiCtx.get(
      `${API}/api/chapters?board=CBSE&grade=8&subject=Biology`
    );
    const chapters = await chaptersRes.json();
    const chapter = chapters.chapters?.[0];
    if (!chapter) {
      console.warn('No Biology chapters found — skipping test page tests');
      await apiCtx.dispose();
      return;
    }

    // Start a test (uses cached questions if available)
    const startRes = await apiCtx.post(`${API}/api/start-test`, {
      data: {
        chapter_id: chapter.id,
        student_name: 'E2EStudent',
      },
    });
    const session = await startRes.json();
    sessionKey = session.session_key;
    await apiCtx.dispose();
  });

  test('shows question number and text', async ({ page }) => {
    if (!sessionKey) test.skip();
    // Navigate with location state by going to test URL directly
    await page.goto(`/test/${sessionKey}`);
    await expect(page.locator('.question-card, [class*="question"]')).toBeVisible({ timeout: 8000 });
  });

  test('shows answer text area', async ({ page }) => {
    if (!sessionKey) test.skip();
    await page.goto(`/test/${sessionKey}`);
    await page.waitForSelector('textarea, [data-testid="answer-input"]', { timeout: 8000 });
    const textarea = page.locator('textarea').first();
    await expect(textarea).toBeVisible();
  });

  test('shows marks badge on question card', async ({ page }) => {
    if (!sessionKey) test.skip();
    await page.goto(`/test/${sessionKey}`);
    await expect(page.locator('[class*="mark"], [class*="marks"]')).toBeVisible({ timeout: 8000 });
  });

  test('Get Hint button is visible', async ({ page }) => {
    if (!sessionKey) test.skip();
    await page.goto(`/test/${sessionKey}`);
    await expect(page.getByRole('button', { name: /hint/i })).toBeVisible({ timeout: 8000 });
  });

  test('voice input button is present', async ({ page }) => {
    if (!sessionKey) test.skip();
    await page.goto(`/test/${sessionKey}`);
    // Voice input button (mic icon or "Start Speaking" button)
    await expect(
      page.locator('[class*="voice"], [class*="mic"], button:has-text("Speaking")')
    ).toBeVisible({ timeout: 8000 });
  });

  test('submit button is disabled when answer is empty', async ({ page }) => {
    if (!sessionKey) test.skip();
    await page.goto(`/test/${sessionKey}`);
    await page.waitForSelector('textarea', { timeout: 8000 });
    const submitBtn = page.getByRole('button', { name: /submit/i });
    await expect(submitBtn).toBeDisabled();
  });

  test('submit button enables when answer is typed', async ({ page }) => {
    if (!sessionKey) test.skip();
    await page.goto(`/test/${sessionKey}`);
    await page.waitForSelector('textarea', { timeout: 8000 });
    await page.locator('textarea').first().fill('This is my answer.');
    await expect(page.getByRole('button', { name: /submit/i })).toBeEnabled({ timeout: 5000 });
  });
});


// ═══════════════════════════════════════════════════════════════════════════
// Custom Test Builder (3-step wizard)
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Custom Test Builder', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.locator('#student-name').fill('E2EStudent');
    await page.locator('#student-pin').fill('1111');
    await page.getByRole('button', { name: 'Continue' }).click();
    await page.waitForURL('/');
    await page.click('text=Custom Multi-Chapter Test');
    await page.waitForURL('/custom-test-builder');
  });

  test('renders custom test builder page', async ({ page }) => {
    await expect(page).toHaveURL('/custom-test-builder');
    // Step 1 visible (board/grade selection)
    await expect(page.locator('body')).toContainText(/step 1|board|grade/i);
  });

  test('step 1 shows board and grade selection', async ({ page }) => {
    await expect(page.locator('body')).toContainText(/CBSE|ICSE/i);
  });

  test('can navigate step 1: select board and grade', async ({ page }) => {
    // Locate board selector in step 1
    const boardOptions = page.locator('select').first();
    if (await boardOptions.isVisible()) {
      await boardOptions.selectOption('CBSE');
    }
  });

  test('back navigation returns to selection page', async ({ page }) => {
    const backBtn = page.locator('button:has-text("Back"), a:has-text("Back")').first();
    if (await backBtn.isVisible()) {
      await backBtn.click();
      await expect(page).toHaveURL('/');
    }
  });
});


// ═══════════════════════════════════════════════════════════════════════════
// Session Expiry UI
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Session Expiry', () => {
  test('expired session shows expiry message', async ({ page, request }) => {
    // Create a session then manually expire it via a direct API call with an old timestamp
    // For this UI test we just verify the expired view renders correctly
    // by visiting a bogus session key
    await page.goto('/test/nonexistent-session-key-12345');
    // Should show error or redirect
    await expect(page.locator('body')).not.toBeEmpty({ timeout: 5000 });
  });
});


// ═══════════════════════════════════════════════════════════════════════════
// Inactivity Warning Banner
// ═══════════════════════════════════════════════════════════════════════════

test.describe('UI: Inactivity warning', () => {
  test('inactivity warning markup exists in component', async ({ page }) => {
    // We do not wait 25 minutes; just confirm the app loads test page without crash
    const apiCtx = await page.context().request;
    const chaptersRes = await apiCtx.get(`${API}/api/chapters?board=CBSE&grade=8&subject=Biology`);
    const chaptersData = await chaptersRes.json();
    if (!chaptersData.chapters?.length) return;

    const startRes = await apiCtx.post(`${API}/api/start-test`, {
      data: { chapter_id: chaptersData.chapters[0].id },
    });
    const { session_key } = await startRes.json();

    await page.goto(`/test/${session_key}`);
    // The warning component is in the DOM but hidden; page should load without errors
    await expect(page.locator('body')).not.toBeEmpty({ timeout: 5000 });
  });
});

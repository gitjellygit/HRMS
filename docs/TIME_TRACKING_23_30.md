# Attendance & Time Tracking (roadmap features 23–30)

## User flows

Open **Time & shifts** in the left navigation.

| # | Feature | Implemented in this PR | Future production dependencies |
|---|---|---|---|
| 23 | Punch in/out | Existing web attendance button reused; one open session per employee. Time & shifts adds GPS-checked punch. Responsive mobile browser. | Native iOS/Android client, production biometric mapping |
| 24 | GPS/geofencing | HR policy can enable GPS requirement; user explicitly grants location at each punch; server checks radius and accuracy; legacy endpoint can't bypass it. | HTTPS, location permission, threat-model for GPS spoofing |
| 25 | Shifts & rosters | HR creates shifts and assigns employee/date roster. Shift swap is initiated by employee, accepted by colleague and approved by manager. | Timezone/overnight shift enhancements, bulk rosters |
| 26 | Regularization | Employees provide a reason and corrected timestamps; managers approve/reject. Approved missed punch creates an audited session if it doesn't overlap. | Editing/replacing existing bad punches, payroll cutoffs |
| 27 | Overtime | Daily hours over configurable threshold computed; overtime request/approval recorded. | Pay multiplier, overtime eligibility, labor law review |
| 28 | Late and half-day | Classifications computed from punch totals/shift start and configured grace/threshold. An `auto_deduct` **policy preference** can be saved. | Automatic leave deduction and salary postings are **not yet performed**; unsafe without payroll and leave-policy reconciliation |
| 29 | WFH / on duty | Employee submits date ranges and a reason; reporting manager/HR approves or rejects. | Calendar integrations and notifications |
| 30 | Timesheets | Employees log project/task hours, daily 24h total enforced; submit drafts. HR can list entries by API. | Timesheet manager approval, project budgeting |

The database stores new time_* records and approval audits. Existing employee, leave and punch tables are preserved.

## Error UX and motion

- Inline error banners clearly tell users to fix an input. Invalid fields have a red border; Employee creation and time request handlers scroll/focus targeted fields.
- Shared `FeedbackMotion` plays lightweight dotLottie success/check, blue loading and confetti celebrations. Animations are **nonessential**—all actions have accessible text and reduced-motion styles.
- Assets are the actual free Lottie animations from:
  - Checked: https://lottiefiles.com/free-animation/checked-zBAXfHoRai
  - Loading: https://lottiefiles.com/free-animation/blue2-pvT5LopBd6
  - Confetti: https://lottiefiles.com/free-animation/confetti-effects-lottie-animation-2naH1Qyz3l
- These files are distributed under the **Lottie Simple License**, permitting commercial use and distribution subject to its terms: https://lottiefiles.com/page/license
- Assets are currently loaded from the LottieFiles assets CDN. For offline/private-network deployment, **download and self-host approved/licensed copies**, review external-asset CSP rules, and pin integrity where possible.
- Runtime package `@lottiefiles/dotlottie-react` is included for React playback.

## Test locally

```bash
git fetch origin
git switch --track origin/feature/attendance-time-23-30-and-motion
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec web npm install
```

Go to **http://localhost:3000 → Time & shifts**.

Existing development Docker volumes can retain outdated node_modules after an image rebuild. The explicit `exec web npm install` installs the animation package inside that persistent volume. Source changes hot reload normally afterward.

If the database schema is being initialized for the first time, the FastAPI startup automatically creates the additive `time_*` tables. Before production, use formal Alembic migration scripts and database backups rather than runtime `create_all`.

## API and security

- `GET /time/daily`: own daily attendance; authorized manager/HR may query team.
- `GET/PUT /time/policy`: public-to-staff policy visibility but HR-only mutations. The default policy applies to all locations.
- `POST /time/punch`: location-verified punch when geofence required; accuracy and radius checked **server-side**. Explicit consent per action. Coordinates are not stored with punches.
- `POST /time/biometric/events`: **integration staging endpoint only**. Requires `HRMS_BIOMETRIC_SHARED_TOKEN` (32+ characters) and unique event IDs. Stores signed vendor events, but does **not** automatically alter official punch history until vendor/device-to-employee mapping is implemented. Do not deploy this endpoint on a public network without additional device-level security.
- `GET/POST /time/shifts`, `PUT/GET /time/roster`: HR-managed shifts with personal/team visibility.
- `POST/GET /time/requests`, `POST /time/requests/{id}/colleague-response`, `POST /time/requests/{id}/review?approve=true|false`: employee requests, consent/manager approval, audit history.
- `GET/POST /time/timesheets`, `POST /time/timesheets/{id}/submit`: own time entries, HR list access.

## Follow-ups before production

1. Formal DB migrations, timezone and overnight shift edge cases, multi-location policies and holiday exclusions.
2. Payroll/leave-deduction engine, overtime pay rates, reconciliation against worked attendance, country-specific labor law policies.
3. Native mobile app if needed; web GPS can be spoofed, so don't treat as tamper-proof proof of employee presence.
4. Biometric vendor-specific event format, signed asymmetric tokens or mTLS, device credential rotation, duplicate/missed event reconciliation.
5. Bulk roster import, manager timesheet sign-off, notifications, access audit dashboards, accessibility QA.

## Manual acceptance tests

- Employee sees **Time & shifts**, can request WFH and submit timesheet.
- Manager sees only team's pending requests; employee cannot approve own request.
- HR creates a shift and assigns a roster; a colleague must accept before manager can approve a swap.
- HR enables geofence with valid coordinates, then punch rejects denied/low-accuracy/outside locations and succeeds for valid location.
- Legacy `/attendance/punch` rejects when geofencing is enabled.
- Approved regularization inserts a corrected nonoverlapping attendance session, rejecting overlapping times.
- Required fields highlight correctly; successful actions show Lottie/text feedback.

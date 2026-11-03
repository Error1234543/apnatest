# PrepGrid Backend & Security Workstream

> Work only on the `backend-security` branch. Do not merge into `main` or deploy to production until reviewed and approved.

## Safety rules
- Preserve all existing HTML pages, student content, URLs, and the current UI.
- Never commit API keys, Supabase service-role keys, bot tokens, passwords, private keys, or user data.
- Keep privileged operations server-side. Never expose the Supabase service-role key in browser code.
- Use least-privilege access and deny-by-default authorization.
- Make database changes through reviewed, reversible migrations.
- Do not enable maintenance mode, block users, or change production settings as part of testing.

## Phase 0 — Repository baseline
- [ ] Confirm this branch's base commit and compare it with `main`.
- [ ] Inventory existing API/backend entry points and deployment configuration.
- [ ] Identify all Supabase client initialization and authentication flows.
- [ ] Check repository history and current files for accidentally committed secrets.
- [ ] Record existing routes and content paths before any edits.

## Phase 1 — Supabase security audit
- [ ] Inventory tables, views, functions, storage buckets, and exposed schemas.
- [ ] Verify RLS is enabled on every user-accessible table.
- [ ] Specifically audit the `profiles` table used by the root homepage: SELECT and UPSERT must be restricted to the authenticated user's own `id` (auth.uid()).
- [ ] Review SELECT/INSERT/UPDATE/DELETE policies separately.
- [ ] Verify users can access only their own profile, progress, and test records.
- [ ] Verify admin actions require server-verified admin roles; never trust client-side role flags.
- [ ] Review RPC/function privileges, storage policies, and OAuth redirect settings.
- [ ] Confirm service-role credentials are server-only and rotated if exposed.

## Phase 2 — Backend foundation
- [ ] Select a server-side API layout compatible with the current hosting setup.
- [ ] Add authentication/session verification and centralized authorization.
- [ ] Add input validation, safe error handling, and rate limiting.
- [ ] Add structured audit events for privileged changes.
- [ ] Add health endpoint and safe operational status checks.

## Phase 3 — Telegram administration
- [ ] Verify Telegram webhook requests and admin identity.
- [ ] Enforce superadmin-only emergency commands on the server.
- [ ] Add maintenance switch, announcements, course publishing, and user controls.
- [ ] Log every administrative action with actor, action, target, and timestamp.
- [ ] Never place bot tokens in frontend files or repository history.

## Phase 4 — Protection and monitoring
- [ ] Configure Cloudflare WAF and rate limits after domain/proxy review.
- [ ] Add Turnstile only to appropriate public forms and verify tokens server-side.
- [ ] Monitor website/API health and backup job outcomes.
- [ ] Alert on suspicious authentication and privileged activity.

## Phase 5 — Verification
- [ ] Test Google and email login.
- [ ] Test per-user data isolation and admin authorization.
- [ ] Test Telegram alerts and command authorization.
- [ ] Test maintenance mode in preview/staging only.
- [ ] Test rate limits, Turnstile, and security policies.
- [ ] Confirm existing pages, content links, and student data remain unchanged.

## Known baseline notes (from prior repository inspection; re-verify before implementation)
- The repository contains thousands of static HTML resources; preserve them.
- The root homepage and Gujarati study hub use separate UI structures.
- The repository has previously used an FTP deployment workflow.
- A limited earlier scan found no matches for several common high-risk secret patterns; this is not a complete secret or history audit.
- Root `index.html` initializes Supabase Auth with a browser publishable key and Google OAuth.
- Root homepage reads `profiles` by `id = user.id` and upserts the signed-in user's profile. This requires matching RLS policies; frontend filters alone are not security controls.
- No service-role key was observed in the inspected homepage section. This is not a full repository/history secret audit.
- The Supabase project/schema and actual RLS policies have not yet been inspected.

## Current status
Repository inspection and security plan committed on `backend-security`. The homepage auth flow has been inspected; Supabase schema/RLS verification is pending. No production database, hosting, authentication, or security settings have been changed.

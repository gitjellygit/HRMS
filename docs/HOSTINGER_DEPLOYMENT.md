# Hostinger HRMS deployment playbook

This workflow is opt-in, disabled until the GitHub production environment variable HRMS_DEPLOY_ENABLED=true. A successful main branch HRMS checks run triggers a protected production environment approval, checks out the exact passing SHA, verifies SSH host identity, and deploys to Hostinger with Docker Compose.

Setup: GitHub Settings > Environments > production. Configure required reviewers, and secrets VPS_HOST (VPS public IP), VPS_USER (deploy), VPS_SSH_PRIVATE_KEY (a NEW dedicated GitHub Actions to VPS private key, whose public key is authorized for deploy), and VPS_SSH_KNOWN_HOSTS (the independently verified VPS host public key line). Never reuse the Mac's private login key or commit these secrets. Confirm the deploy account's Docker access before enabling. Set production environment variable HRMS_DEPLOY_ENABLED=true only after backup restore and first deployment tests.

The script refuses tracked local changes, changes under backend/migrations or docker-compose.yml, preserves the VPS-only .env and named volumes, builds/restarts API and web, updates leave-email-worker if already running, verifies API and frontend, and attempts rollback on failure. Changes requiring SQL migrations or Compose modifications need separate manual review and verified backups. Rollback is best effort; health passing alone does not establish employee data production readiness. CI tests use isolated data, not live records.

Protect main with required HRMS checks and Playwright pull-request checks before allowing automatic rollout. This is a small-team pilot solution; use CI-built immutable images and tested blue/green deployments for more demanding production uptime.

# JellyGit Activity Companion v0.6 (Windows pilot)

This portable Windows tray executable is built from the user's v0.5 Go source and adapted for **automatic pending device registration**, without manually creating a configuration file.

Build on a workstation with Go:
```bash
GOOS=windows GOARCH=amd64 CGO_ENABLED=0 go build -ldflags='-s -w -H windowsgui' -o JellyGit_Activity_Companion_Windows_v0.6.exe main.go
```

On first run it detects Windows hostname, calls `https://api-hrms.jellygit.com/activity-agent/register-auto` and automatically saves its device bearer token under the running user's local AppData directory. If offline, it retries. No activity should be collected until the backend reports that HR assigned an active employee. Assigned status is rechecked periodically.

The API requires `HRMS_ACTIVITY_AUTO_REGISTER_ENABLED=true` and the migration from PR #57 applied. Rate-limit this untrusted endpoint at the edge. **A self-reported hostname is not evidence of company device identity.** HR must verify the company asset and provide monitoring notice before assignment. The tray provides visible notice. No covert recording, screenshots, keystrokes or URLs are implemented.

**Release gates:** source review, Windows 10/11 end-to-end tests against Hostinger, authenticated role checks, reconnection/revocation verification, employee privacy review, signing and malware scan. No build artifacts or developer secrets should be committed to GitHub. This is a portable EXE, not a service or MSI installer.
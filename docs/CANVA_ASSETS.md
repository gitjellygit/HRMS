# JellyGit HRMS — Canva asset integration

The five user-supplied Canva illustrations and one onboarding MP4 are not embedded in source code. The owner must add the optimized assets under `frontend/public/assets/` and commit them to Git to make them available to CI, deployment, and other employees' installations.

| Filename | Purpose | UI integration |
|---|---|---|
| `login-team.webp` | Team collaboration illustration | Login showcase |
| `onboarding-welcome.mp4` | Welcome animation (muted, looped) | People Operations > Onboarding |
| `success-checklist.webp` | Success/checkmark | Success and congratulations feedback |
| `empty-folder-state.webp` | Empty-state folder | Project list, overview with no assignments, onboarding checklist |
| `welcome-card-template.webp` | Visual template with sample text | HR-facing reference/download in People Operations > Announcements |
| `hero-ai-banner.webp` | Technology/AI hero | Reserved for the public JellyGit website; not displayed in confidential HRMS |

## Install

Download `jellygit-hrms-canva-assets.zip` supplied in the HRMS conversation. Its internal paths already start with `frontend/public/assets/`.

From the **root of the HRMS Git repository**:

```sh
unzip ~/Downloads/jellygit-hrms-canva-assets.zip -d .
git add frontend/public/assets
git commit -m "assets: add optimized JellyGit Canva illustrations and onboarding video"
git push origin main
```

If you are collaborating, push these asset files on a feature branch and merge through a PR instead of committing directly to `main`.

### Design constraints

- Media components fail gracefully (without showing broken-image icons) while files are not yet present; UI still functions.
- GIF conversion is unnecessary: the provided MP4 is smaller and is played muted, looping, inline. Under reduced-motion settings a still illustration is used.
- The exported welcome card has text baked into its pixels. It is **not** a data-driven template or generated document. Modify the original Canva template before exporting a specific employee card; do not insert confidential employee details into public web URLs.
- The technology hero image belongs to the separate website integration. HRMS financial/accounting screens remain clean and data-focused.
- Video and image assets use local URLs; no paid Canva APIs or runtime image-generation credits are required.
- Test the production deployment only after the asset files have been added to Git and made available on your hosting server.

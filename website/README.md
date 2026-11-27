# DSOpus website

A static, dependency-free product website. It is intentionally independent from the Python desktop application and can be hosted on GitHub Pages.

## Run locally

From the repository root, start any static file server, for example:

```sh
python3 -m http.server 8000 --directory website
```

Then open <http://localhost:8000>. Opening `index.html` directly also works, though a local server is closer to the deployment environment.

## Publish with GitHub Pages

1. Push the repository branch containing the `website/` directory to GitHub.
2. Add a workflow at `.github/workflows/pages.yml` in the repository root. GitHub's branch-based Pages setting does not offer `/website` as a publish folder, so use the Actions workflow below to publish that directory as a Pages artifact.
3. In **Settings → Pages**, set the source to **GitHub Actions**.
4. Push the workflow to the selected branch. GitHub Actions will publish the site at the URL shown in Pages settings.

```yaml
name: Publish website

on:
  push:
    branches: [main]
    paths:
      - "website/**"
      - ".github/workflows/pages.yml"
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: website
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

All website links to scripts, styles, images, video, and icons are relative, so the site works under the repository subpath used by GitHub Pages. Windows, Linux, macOS Apple silicon, and macOS Intel buttons link directly to the release assets referenced by the repository's main `index.html`.

## Content and feature notes

- Product capabilities and external requirements are documented in the repository README and worker guide.
- The nine interactive before/after pairs are genuine deepSNR, Star Shrink, background extraction, sharpening, and Astro Upscale samples supplied in `../assets/website/`, resized and converted to WebP for this site.
- The 3D FLY video is the project sample at `../assets/3d_fly.mp4`.
- The repository does not contain a verified desktop-interface screenshot. The software section therefore uses a genuine processed sample image and explicitly identifies it as such.
- deepSNR, StarNet++, Skyshot Solver with catalogue index, and ffmpeg audio attachment require external tools or data. Altair requires its hosted service and internet access.

## Files

- `index.html` — page content and SEO metadata
- `styles.css` and `comparisons.css` — responsive dark design, motion, and larger before/after comparisons
- `script.js` — navigation, image comparisons, gallery, and scroll effects
- `assets/` — optimized project images and 3D FLY video
- `favicon.svg`, `favicon.ico`, `apple-touch-icon.png` — site icons

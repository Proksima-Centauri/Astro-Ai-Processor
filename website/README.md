# DSOpus website

A static, dependency-free product website. It is intentionally independent from the Python desktop application and can be hosted on GitHub Pages.

## Run locally

From the repository root, start any static file server, for example:

```sh
python3 -m http.server 8000 --directory website
```

Then open <http://localhost:8000>. Opening `index.html` directly also works, though a local server is closer to the deployment environment.

## Publish with GitHub Pages

1. In **Settings → Pages**, set the source to **GitHub Actions**. GitHub's branch-based Pages setting only offers the repository root and `/docs`, so this repository uses the workflow at `.github/workflows/pages.yml` to publish `website/`.
2. Push changes to `website/` or run **Publish website** from the Actions tab. GitHub Actions will publish the site at the URL shown in Pages settings.

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

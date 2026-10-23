
<p align="center">
  <img src="favicon-32.png" alt="Astro AI Processor application icon" width="120" />
</p>
# Astro AI Processor 

> **Astro AI Processor is a desktop astrophotography image processing application.**

Astro AI Processor processes and analyzes astrophotography images with FITS support, astronomy-specific analysis, plate solving, star tools, denoising, and traditional image-editing tools.


This repository keeps its documentation in this README.

## What is Astro AI Processor?

Astro AI Processor is a desktop application for processing and analyzing astrophotography images. It combines traditional image-processing tools with astronomy-specific analysis and AI-powered processing features.

Astro AI Processor combines classic editing tools (Levels, Curves, Histogram, Blur, Crop, Rotate) with astronomy-specific features: star analysis (FWHM/SNR), astronomical plate solving, StarNet++ star removal, deepSNR denoising, frame mosaics, and the 3D FLY animation filter.

## Key features

- Image I/O: PNG, JPG, TIFF, and FITS (`.fits`, `.fit`, `.fts`).
- Layers and history: undo/redo, thumbnails, basic layer operations.
- Tone and color tools: Levels, Curves (LUT), Histogram, GHS, RGB/HSL correction.
- Astro tools:
  - image analysis (FWHM, SNR, background noise),
   - local plate solving using Skyshot Solver,
  - StarNet++ star removal,
  - deepSNR external denoise,
  - frame mosaic stitching,
  - 3D FLY clip rendering (optional audio).
- Altair AI assistant using NVIDIA Nemotron 3 Super through OpenRouter's free route.
- PL/EN UI with configurable preferences and workspaces.

## Requirements

- Python 3.10+ (recommended 3.11-3.13).
- Linux or Windows (on Linux the app enables software OpenGL).
- Packages from `requirements.txt`: `numpy`, `opencv-python`, `largestinteriorrectangle`, `matplotlib`, `sep`, `astropy`, `photutils`, `SpeechRecognition`, `onnxruntime`, `PyQt5`, `pyserial`, `scikit-image`.

Optional external tools:

- Skyshot Solver CLI and a compatible catalogue index for local plate solving.
- StarNet++ CLI.
- deepSNR CLI.
- `ffmpeg` for attaching audio in 3D FLY output.
- OpenRouter API key for the default Nemotron provider (configure in Preferences → AI Chat; free route may have rate limits).

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python3 "Astro Ai Processor.py"
```

## Linux bundle installer (.desktop support)

If you build/extract the one-dir package (`dist/Astro AI Processor/`), you can install it to the user profile and generate a launcher:

```bash
chmod +x packaging/linux/install-linux.sh
./packaging/linux/install-linux.sh --source "dist/Astro AI Processor" --force
```

This installs to `~/.local/opt/astro-ai-processor` and creates `~/.local/share/applications/astro-ai-processor.desktop`.

## Linux GUI installer (one-click for end users)

End users do not need terminal commands.

1. Build a single-file GUI installer:

```bash
chmod +x packaging/linux/build-gui-installer.sh
./packaging/linux/build-gui-installer.sh --source "dist/Astro AI Processor"
```

2. Distribute `dist/Astro-Ai-Processor-Installer-Linux`.
3. User double-clicks installer, selects install folder, optionally enables `Create .desktop shortcut on Desktop`, then clicks `Install`.

The installer also creates the application menu entry in `~/.local/share/applications`.

## Debian package build (.deb)

To build a Debian package from the one-dir bundle:

```bash
chmod +x packaging/deb/build-deb.sh
./packaging/deb/build-deb.sh --source "dist/Astro AI Processor" --version "0.1.0"
```

Result file is generated as `dist/astro-ai-processor_<version>_amd64.deb`.

## Configuration

Settings are stored in the user's application config directory. The OpenRouter key can also be read from `OPENROUTER_API_KEY`.

Example fields:

- tool paths (`starnet_path`, `deepsnr_path`),
- deepSNR args (`deepsnr_args`),
- plate solving (`skyshot_binary`, `skyshot_index`),
- AI setting (`openrouter_api_key`),
- language, theme, core count, workspace.

Security note: keep private paths and local workspace data out of public repositories.

### Skyshot plate solving

Install/build the Skyshot Solver CLI from its source distribution (`cargo build
--release --locked` in the Skyshot repository) and download a compatible Full
catalogue index. The app automatically looks for `skyshot` on `PATH`, beside the
applicable Skyshot source checkout, and for indexes in standard Skyshot data,
Documents, Downloads and `data/` locations. Optional `SKYSHOT_BINARY` and
`SKYSHOT_INDEX` environment variables can override discovery; no solver or index
settings are shown in the Plate Solving dialog. No image upload, API key or
Astrometry.net fallback is used. Existing FITS WCS can still be reused.

Skyshot Solver 0.1.0 is Copyright 2026 Adam Jesionkiewicz, Apache-2.0; see NOTICE.
The implementation license is GPLv3-compatible. The adapter uses only its CLI;
Skyshot code/binaries and catalogue data are not bundled here. Obtain index data
separately from https://skyshot.app/downloads/ under its own terms. The small
synthetic index from the source demo cannot solve real images.

## Quick workflow

1. Open an image (`Open`) or drag-and-drop a file.
2. Apply base corrections (Levels/Curves/Histogram/Correction).
3. Run `Analyze` to compute metrics (FWHM, SNR).
4. Optional: `StarNet++`, `deepSNR`, `Mosaic`, `Plate Solve`.
5. For animation, run `3D FLY`.
6. Save output (`Save` / `Save As`).

## 3D FLY quick guide

1. Stage 1 `remove stars` (optional): run StarNet++.
2. Stage 2 `mark sections`: cut layer zones (`Cut`) or use `Load layers`.
3. Stage 3 `edge smoothing`: select a layer, set blur, click `Apply`.
4. Stage 4 `clip setup`: set duration and FPS.
5. Stage 5/6 `motion and position`: set direction, speed, and zoom per layer.
6. Final stage `add music`: choose audio and click `Render 3D FLY`.

Common issues:

- `No layers for motion` -> add layers in stage 2.
- Blur not visible -> in stage 3 select layer and click `Apply`.
- No render output -> open the final tab and set a valid output path.

## Useful in-app console commands

- `help`
- `open [path]`
- `save` / `save as [path]`
- `magic`
- `starnet++`
- `deepsnr`
- `3d fly`
- `analyze`
- `mosaic`
- `levels`, `curves`, `histogram`, `ghs`

## Project structure

- `Astro Ai Processor.py` - main app file.
- `deep_sky_catalog.py` - offline deep-sky object catalog.
- `3d_fly_help.md` - detailed 3D FLY manual.
- `requirements.txt` - Python dependencies.
- `assets/` - UI icons and resources.

## License

Astro AI Processor is licensed under the GNU General Public License v3.0. See [LICENSE](LICENSE) for details.

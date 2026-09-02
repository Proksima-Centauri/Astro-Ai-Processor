# Astro AI Processor

Desktopapp voor astrofotografie-bewerking gebouwd met Python (PyQt5 + OpenCV + NumPy).

## Belangrijkste functies

- Beeldformaten: PNG, JPG, TIFF, FITS.
- Tools: Levels, Curves, Histogram, GHS, Blur, Crop, Rotate.
- Astrofuncties: analyse (FWHM/SNR), plate solving, StarNet++, deepSNR, mosaic, 3D FLY.

## Installatie

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Starten

```bash
python3 "Astro Ai Processor.py"
```

## Belangrijke bestanden

- `Astro Ai Processor.py` - hoofdapplicatie.
- `deep_sky_catalog.py` - lokale DSO-catalogus.
- `3d_fly_help.md` - 3D FLY handleiding.

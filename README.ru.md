# Astro AI Processor

Nastolnoe prilozhenie dlia obrabotki astrofotografii na Python (PyQt5 + OpenCV + NumPy).

## Osnovnye vozmozhnosti

- Formaty izobrazhenii: PNG, JPG, TIFF, FITS.
- Instrumenty: Levels, Curves, Histogram, GHS, Blur, Crop, Rotate.
- Astro-funktsii: analiz (FWHM/SNR), plate solving, StarNet++, deepSNR, mosaic, 3D FLY.

## Ustanovka

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Zapusk

```bash
python3 "Astro Ai Processor.py"
```

## Vazhnye faily

- `Astro Ai Processor.py` - osnovnoe prilozhenie.
- `deep_sky_catalog.py` - lokalnyi katalog DSO.
- `3d_fly_help.md` - rukovodstvo po 3D FLY.

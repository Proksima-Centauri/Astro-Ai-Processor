# Astro Ai Processor

Aplicativo desktop para processamento de astrofotografia em Python (PyQt5 + OpenCV + NumPy).

## Recursos principais

- Formatos de imagem: PNG, JPG, TIFF, FITS.
- Ferramentas: Levels, Curves, Histogram, GHS, Blur, Crop, Rotate.
- Recursos astro: analise (FWHM/SNR), plate solving, StarNet++, deepSNR, mosaic, 3D FLY.

## Instalacao

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Execucao

```bash
python3 "Astro Ai Processor.py"
```

## Arquivos importantes

- `Astro Ai Processor.py` - aplicativo principal.
- `deep_sky_catalog.py` - catalogo DSO local.
- `3d_fly_help.md` - guia do 3D FLY.

# TODO: Astro AI Processor (UI/UX)

Priorytety: **P0** = błędy i atrapy (robić najpierw), **P1** = duży wpływ na użytkownika, **P2** = dopracowanie, **P3** = później.

## P0: Błędy i atrapy

- [x] **Historia miniatur:** podłączyć klik LPM do przywracania stanu (`_on_thumbnail_clicked`), a Rename/Remove przenieść na PPM.
- [x] **Kodowanie UTF-8:** naprawić mojibake w źródłach (`SiĹ‚a`, `UsuĹ„`, `Â°`, `â€ł/px`, `Ď`), w tym w nakładce plate solve i w nazwach.
- [x] **Crop:** zamienić porównania trybu siatki po tekście (`"TrĂłjpodziaĹ‚"`) na `itemData` (zrobić razem z poprzednim punktem).
- [x] **Star Shrink:** `reset_defaults()` zeruje wartości (0/0), a przy starcie jest 0,60/0,50. Ujednolicić domyślne.
- [x] **Halo reduction:** ujednolicić domyślną wartość (0 w `__init__` vs 0,35 w `reset_all_sliders`).
- [x] **Blend/Opacity** w panelu warstw: podłączyć albo usunąć.
- [x] **Kółko tokenów Altaira (0%):** podłączyć do realnych danych albo usunąć.
- [x] **Pasek postępu deepSNR** (sztuczny timer do 95%): zastąpić nieokreślonym wskaźnikiem.
- [x] **Wyszukiwarka dashboardu:** ukryć w zakładkach Scripts, Settings i Altair, gdzie nie działa.
- [x] **Okno postępu StarNet:** nie blokować zamknięcia po błędzie.
- [x] **Weryfikacja:** sprawdzić testem, czy wyłączony kanał R/G/B nie uszkadza zapisywanego obrazu.
- [x] **Literówki:** "sunchronizuj zoom", "Pedzel", "Czulosc", "Agresywnosc", "Powieksz".

## P1: Duży wpływ na użytkownika

### Nawigacja i menu
- [x] Przebudować menubar: Plik / Edycja / Warstwy / Obraz / Filtry / AI / Astro / Widok / Narzędzia / Pomoc.
- [x] Tłumaczenie tytułów menu w `_update_ui_language` (`setTitle`) i mnemoniki (`&Plik`).
- [x] Skróty: Ctrl+O, Ctrl+S, Ctrl+Shift+S, Ctrl+V (wklej do warstwy), Ctrl+Q.
- [x] Rozróżnić "Levels/Curves" (okno) od "Warstwa korekcyjna ▸ Levels/Curves".
- [x] Dodać menu Pomoc: instrukcja 3D FLY, skróty, aktualizacje, o programie.
- [x] Menubar widoczny także na dashboardzie (bez skoku układu).
- [x] Dodać powrót z edytora do dashboardu.

### Pasek ikon
- [x] Unikalne ikony dla każdej funkcji (teraz powtarzają się mosaic, blur, levels, shrink).
- [x] Ograniczyć do maksymalnie 10 ulubionych i przycisk "więcej".
- [x] Przycisk "Przywróć domyślną kolejność" oraz podpowiedź o przeciąganiu.
- [x] Obsługa przepełnienia przy wąskim oknie.

### Feedback
- [x] Dodać **pasek statusu**: współrzędne, wartość piksela (ADU/RGB), zoom, rozmiar, tryb stretch, aktywna operacja.
- [ ] Toasty zamiast części `QMessageBox` dla sukcesów.
- [ ] Spójna zasada: sukces = toast + log, błąd = okno + log.
- [ ] Przycisk Anuluj w długich operacjach (Magic, StarNet, Deconvolution, Stack, 3D FLY).
- [x] Plate solve: nie pokazywać ostrzeżeń przy każdym pliku, jeśli brak Skyshot (jednorazowa informacja lub opcja wyłączenia auto-solve).

### Viewer
- [x] Pan w trybie porównania (środkowy przycisk lub spacja), LPM tylko na uchwycie podziału.
- [x] Etykiety "Przed" / "Po" i pozycja podziału.
- [x] Wskaźnik zoomu w dolnym pasku.
- [x] Odczyt piksela pod kursorem.

### Filtry
- [ ] Podgląd zawsze asynchroniczny (Blur, LCE, Star Shrink wołają synchronicznie `apply_full_processing`).
- [ ] Niemodalne panele albo pan/zoom podczas strojenia parametrów.
- [ ] Deconvolution: ręczny PSF i pokazanie użytej wartości.
- [ ] Background Extraction: podgląd wyestymowanego tła.
- [ ] Stack: wybór BIAS/DARK/FLAT w zakładce Calibration (listy i liczniki), nie w trzech oknach po Run.

### 3D FLY
- [ ] Przyciski **Wstecz / Dalej** i wskaźnik postępu etapów.
- [ ] Walidacja na każdym etapie (maska gwiazd, warstwy), a nie dopiero przy renderze.
- [ ] Oznaczyć etap 1 jako opcjonalny, wyjaśnić kolejność.
- [ ] Zapis i odczyt projektu 3D FLY; potwierdzenie przy zamknięciu krzyżykiem.
- [ ] Anulowanie renderu, po zakończeniu "Otwórz plik / Pokaż w folderze".
- [ ] Zastąpić numery etapów w kodzie (`5`, `4`, `1`) stałymi/enumem.
- [ ] Zsynchronizować numerację w dokumentacji `3d_fly_help.md` z UI.
- [ ] Legenda interakcji w podglądzie ruchu.

## P2: Dopracowanie

### Spójność
- [ ] Przenieść wszystkie stringi do `I18N` (zamiast `AUTO_TEXT_MAP` po tekście).
- [ ] Ujednolicić terminologię ("Magic" / "Magic Filter" / pełna nazwa PL).
- [ ] Ujednolicić marginesy dialogów (`apply_standard_layout_margins` wszędzie).
- [ ] Dokończyć motyw Light (twardo zakodowane kolory `#1f2933`, `#00bcd4`, `#007acc`) albo go usunąć.
- [ ] Kolory widżetów z palety i akcentu.

### Ustawienia i Altair
- [ ] Scalić Preferencje i zakładkę Settings w jedno źródło.
- [ ] Jedna instancja Altaira (wspólny stan i worker).
- [ ] Pokazywać treść skryptu przed zgodą na wykonanie.
- [ ] Przycisk "Uruchom" przy odpowiedzi z kodem zamiast stałego "Uruchom Python".
- [ ] Informacja o wysyłaniu danych do OpenRouter przy pierwszym użyciu (zgoda).
- [ ] Informacja o użyciu usługi Google przy głosie na tekst.
- [ ] Uproszczony ekran powitalny w wąskim panelu; przycisk schowania panelu.
- [ ] Klucz API w keyringu systemowym.
- [ ] Scal model ekstkrakcji tłą do repo (bez potawania patch) zachwując licencję (w patch modelu).
### Okna tonalne
- [ ] Histogram z danych natywnych (nie tylko 8-bit) i skala logarytmiczna.
- [ ] Zmienić etykietę "ADU" lub liczyć z prawdziwych danych.
- [ ] Levels: półtony jako gamma zamiast 0–1 z 7 miejscami.
- [ ] Curves: próbniki punktu czerni/bieli.
- [ ] Ostrzeżenie lub pytanie przy zamknięciu okna z niezatwierdzonymi zmianami.
- [ ] Skróty `+`, `-`, `0` z modyfikatorem, żeby nie kolidowały z polami tekstowymi.

### Historia i warstwy
- [ ] Informacja o limicie 15 kroków; opcjonalnie zapis na dysk zamiast kopii w RAM.
- [ ] Przełączanie widoczności warstw bez dodawania wpisów do historii.
- [ ] Zmiana kolejności warstw i widoczne maski w UI.
- [ ] Konsola: sygnalizacja nowych wpisów (np. plakietka) lub podgląd ostatniego komunikatu na pasku statusu.

### Dashboard
- [ ] Siatka kart dopasowana do szerokości okna.
- [ ] Zmienić nazwę "Projects" na "Ostatnie" albo wprowadzić prawdziwe projekty.
- [ ] Możliwość dodania własnych obrazów do Galerii; konfigurowalny limit ostatnich plików.
- [ ] Nie zmieniać kolorów całej strony przy zakładce Altair.

### Paleta poleceń
- [x] Ranking i dopasowanie rozmyte zamiast samego podciągu.
- [x] Uzupełnić pozycje: Histogram, Konsola, GHS, Correction, SVG Pędzel, Timelapse, Planetary, motyw, język.
- [ ] Ostatnio używane polecenia i skróty przy pozycjach.
- [ ] Zastąpić wyrównanie skrótu spacjami prawdziwym układem.

### Niewielkie
- [x] Crop: użyć `QSpinBox` zamiast `QDoubleSpinBox` z 0 miejsc.
- [ ] Rotate: opcja przycięcia czarnych rogów.
- [ ] Wyszarzenie "Script Editor", gdy brak pliku `Astro Script Editor.py`.
- [ ] Znacznik wartości zerowej na suwakach Correction.

## P3: Dostępność i wydajność

### Dostępność
- [ ] Kontrast tekstów przygaszonych ≥ 4,5:1.
- [ ] Minimalna wielkość czcionki 11–12 px, skalowanie HiDPI (zamiast `setFixedSize`).
- [ ] Przywrócić standardowe wskaźniki checkboxów (styl toggle tylko dla R/G/B).
- [ ] Widoczny fokus i logiczna kolejność tabulacji w złożonych dialogach.
- [ ] Alternatywa klawiaturowa dla przeciągania (kolejność bloków skryptów, ikony, miniatury).
- [ ] Nie przekazywać informacji wyłącznie kolorem (plakietki, strzałki ruchu).
- [x] Onboarding pierwszego uruchomienia (wybór języka i motywu oraz oprowadzanie z gradientowym podświetleniem).
- [ ] Podpowiedzi w pustych stanach.

### Wydajność
- [ ] Miniatury dashboardu generować w tle (teraz w wątku GUI przy starcie).
- [ ] Ograniczyć kopiowanie pełnych obrazów w historii i snapshotach undo.
- [ ] Usunąć `processEvents()` z callbacków postępu (ryzyko re-entrancji).
- [ ] Jednolity model pracy: wszystkie ciężkie operacje asynchroniczne.

## Proponowana kolejność prac

1. **Sprint 1 (szybkie wygrane):** cały blok P0.
2. **Sprint 2:** menubar, pasek statusu, toasty, pan w porównaniu, Star Shrink/filtry asynchronicznie.
3. **Sprint 3:** 3D FLY (nawigacja, walidacja, zapis projektu), scalenie ustawień i Altaira.
4. **Sprint 4:** pasek ikon, paleta, dashboard, motyw Light.
5. **Sprint 5:** dostępność i wydajność.

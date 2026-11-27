const preferredLanguage = (navigator.languages && navigator.languages[0]) || navigator.language || 'en';
const polish = /^pl(?:-|$)/i.test(preferredLanguage);

if (polish) {
  document.documentElement.lang = 'pl';
  document.title = 'DSOpus — Poza zasięgiem ludzkiego wzroku';
  document.querySelector('meta[name="description"]').content = 'DSOpus to desktopowa aplikacja do obróbki astrofotografii. Odkrywaj więcej w zdjęciach głębokiego nieba dzięki narzędziom stworzonym dla astronomii.';
  document.querySelector('meta[property="og:title"]').content = document.title;
  document.querySelector('meta[property="og:description"]').content = 'Profesjonalna obróbka astrofotografii. Stworzona, by odkrywać ukryte piękno wszechświata.';

  const copy = {
    '.wordmark[aria-label]': 'DSOpus — strona główna',
    '.menu-toggle': 'Otwórz menu',
    '.navigation': 'Menu główne',
    '.navigation a[href="#universe"]': 'Wszechświat',
    '.navigation a[href="#tools"]': 'Możliwości',
    '.navigation a[href="#explore"]': 'Odkrywaj',
    '.navigation a[href="#software"]': 'Program',
    '.navigation .nav-download': 'Pobierz <span>↗</span>',
    '.hero-copy .eyebrow': '<span class="eyebrow-line"></span> ASTROFOTOGRAFIA NA NOWO',
    '#hero-title': 'Poza tym,<br>co widzi <em>oko.</em>',
    '.hero-description': 'Profesjonalna obróbka astrofotografii. Stworzona, by odkrywać ukryte piękno wszechświata.',
    '.hero-actions .button-primary': 'Pobierz DSOpus <span>↓</span>',
    '.hero-actions .button-quiet': 'Poznaj DSOpus <span>↓</span>',
    '.hero-caption span:last-child': 'Obraz opracowany w DSOpus',
    '.scroll-cue': 'Przewiń, aby odkryć',
    '#universe .eyebrow': 'NOWY SPOSÓB PATRZENIA',
    '#universe h2': 'Wszechświat skrywa więcej.<br><span>Wydobądź to na światło.</span>',
    '.intro-text': 'Od pierwszego rozciągnięcia słabej mgławicy po ostatnie poprawki barw galaktyki — DSOpus daje Twoim zdjęciom przestrzeń, by nabrały kształtu.',
    '.stateline span:first-child': 'Stworzony dla nocnego nieba',
    '.stateline span:last-child': 'Dla tych, którzy patrzą w górę',
    '.feature-image': 'Obraz głębokiego nieba: NGC 281',
    '.feature-image img': 'Szczegółowy obraz mgławicy Pacman, NGC 281',
    '.image-note span:first-child': '01 / WSZECHŚWIAT',
    '.image-note span:last-child': 'Lata świetlne na wyciągnięcie ręki.',
    '#tools .section-heading .eyebrow': 'ODKRYJ TO, CO NIEWIDOCZNE',
    '#tools .section-heading h2': 'Wydobądź subtelne<br><span>szczegóły.</span>',
    '#tools .section-heading>p:last-of-type': 'Narzędzia stworzone z myślą o astrofotografii pomagają wydobyć słabe struktury, dopracować gwiazdy i ukształtować sygnał zapisany w danych.',
    '.label-before': 'ORYGINAŁ',
    '.comparison-card:first-child .label-after': 'DEEPSNR',
    '.comparison-caption h3:first-child': 'Ciszej z szumem.',
    '.comparison-card:first-child .comparison-caption p': 'Redukcja szumu deepSNR',
    '.comparison-card:first-child .expand-image': 'Pokaż porównanie deepSNR na pełnym ekranie',
    '.comparison-card:last-child .label-after': 'STAR SHRINK',
    '.comparison-card:last-child .comparison-caption h3': 'Zrób miejsce dla mgławicy.',
    '.comparison-card:last-child .expand-image': 'Pokaż porównanie Star Shrink na pełnym ekranie',
    '.compare-range': 'Porównaj oryginalny obraz z obrazem po obróbce',
    '#tools>.fine-print': 'Wszystkie porównania wykorzystują autentyczne przykładowe obrazy projektu. Star Shrink jest wbudowany w DSOpus. deepSNR i StarNet++ wymagają osobno zainstalowanych narzędzi wiersza poleceń.',
    '.art-label span': '· ASYSTENT AI',
    '.intelligence-copy .eyebrow': 'INTELIGENCJA SPOTYKA ASTRONOMIĘ',
    '.intelligence h2': 'Poznaj Altaira.<br><span>Asystenta, który zna się na astronomii.</span>',
    '.intelligence-copy>p:nth-of-type(2)': 'Pytaj o aktualnie otwarty obraz, korzystaj ze wskazówek dotyczących pracy w DSOpus i wyszukuj zdjęcia w bibliotece po nazwie obiektu. Historia rozmów Altaira pozostaje na Twoim komputerze.',
    '.intelligence-copy .fine-print': 'Altair łączy się z usługą online i wymaga dostępu do internetu. Korzysta z modelu NVIDIA Nemotron 3.5 Lightning przez OpenRouter. Dostępność usługi i limity dostawcy mogą się zmieniać.',
    '.intelligence-copy .text-link': 'Jak działa Altair <span>↗</span>',
    '#precision .section-heading .eyebrow': 'PRECYZYJNA OBRÓBKA',
    '#precision .section-heading h2': 'Każda poprawka,<br><span>z wyczuciem.</span>',
    '#precision .section-heading>p:last-of-type': 'Od znanych narzędzi obrazu po analizę astronomiczną — wszystko, czego potrzebujesz, masz pod ręką.',
    '.photo-tag': 'USUWANIE GRADIENTU TŁA · PRZYKŁAD Z PROJEKTU',
    '.precision-list>div:nth-child(1) h3': 'Ton i kolor',
    '.precision-list>div:nth-child(1) p': 'Poziomy, krzywe, histogram, GHS, korekcja RGB i HSL.',
    '.precision-list>div:nth-child(2) h3': 'Analiza obrazu',
    '.precision-list>div:nth-child(2) p': 'Sprawdź FWHM, stosunek sygnału do szumu i szum tła.',
    '.precision-list>div:nth-child(3) h3': 'Narzędzia gwiazdowe',
    '.precision-list>div:nth-child(3) p': 'Star Shrink jest wbudowany. Integracja ze StarNet++ pozwala tworzyć obrazy bez gwiazd po zainstalowaniu zewnętrznego narzędzia CLI.',
    '.precision-list>div:nth-child(4) h3': 'Więcej szczegółów',
    '.precision-list>div:nth-child(4) p': 'Usuwanie gradientu tła, wyostrzanie oraz Astro Upscale, które powiększa obraz interpolacją Lanczosa lub bikubiczną, bez generowania nowych szczegółów.',
    '.upscale-label': 'ASTRO UPSCALE <span>Interpolacja, bez generowania szczegółów</span>',
    '#explore .eyebrow': 'ODKRYWAJ WSZECHŚWIAT',
    '.explore-intro h2': 'Od pojedynczego kadru<br>po szerszą <em>perspektywę.</em>',
    '.explore-item:nth-child(1)>.eyebrow': 'LOKALNE ASTROMETRYCZNE ROZPOZNAWANIE POLA',
    '.explore-item:nth-child(1) h3': 'Sprawdź,<br>na co patrzysz.',
    '.explore-item:nth-child(1)>p:not(.eyebrow)': 'Skyshot Solver może lokalnie wyznaczyć współrzędne obrazu przy użyciu zgodnego indeksu katalogowego. Można też wykorzystać istniejące dane WCS z pliku FITS.',
    '.explore-item:nth-child(1) .dependency': 'Wymaga Skyshot CLI i indeksu katalogowego',
    '.explore-item:nth-child(2)>.eyebrow': 'MOZAIKI Z WIELU KADRÓW',
    '.explore-item:nth-child(2) h3': 'Połącz kadry<br>w całość.',
    '.explore-item:nth-child(2)>p:not(.eyebrow)': 'Łącz wiele kadrów w większą mozaikę bezpośrednio w aplikacji.',
    '.explore-item:nth-child(2) .dependency': 'Obróbka obrazu odbywa się lokalnie',
    '.video-copy h3': 'Wyrusz w podróż<br>po swoim obrazie.',
    '.video-copy>p:not(.eyebrow)': 'Twórz animowane klipy z warstw obrazu, opcjonalnie usuwając gwiazdy narzędziem StarNet++ i dodając dźwięk.',
    '.video-copy .dependency': 'Dodanie dźwięku wymaga ffmpeg',
    '#software .section-heading .eyebrow': 'APLIKACJA',
    '#software .section-heading h2': 'Twoje miejsce<br><span>pod gwiazdami.</span>',
    '#software .section-heading>p:last-of-type': 'DSOpus to aplikacja desktopowa dla systemów Windows i Linux, obsługująca formaty FITS, PNG, JPG i TIFF. Zobacz aktualny interfejs w repozytorium projektu.',
    '#software .section-heading .text-link': 'Zobacz kod źródłowy na GitHubie <span>↗</span>',
    '.stage-overlay .expand-image': 'Pokaż przykładowy obraz na pełnym ekranie',
    '.comparison-card:first-child .compare-base': 'NGC 281 przed redukcją szumu',
    '.comparison-card:first-child .compare-overlay img': 'NGC 281 po redukcji szumu deepSNR',
    '.comparison-card:last-child .compare-base': 'NGC 281 przed zmniejszeniem gwiazd',
    '.comparison-card:last-child .compare-overlay img': 'NGC 281 po zmniejszeniu gwiazd Star Shrink',
    '.precision-photo img': 'Przykładowe zdjęcie C11 po usunięciu gradientu tła',
    '.upscale-strip img:first-child': 'NGC 281 przed interpolacyjnym powiększeniem',
    '.upscale-strip img:nth-of-type(2)': 'NGC 281 po interpolacyjnym powiększeniu Astro Upscale',
    '.explore-video video': 'Przykładowa animacja DSOpus 3D FLY',
    '.software-stage img': 'Obraz NGC 281 z zestawu przykładowych zdjęć DSOpus',
    '.stage-title': 'Bliżej<br>kosmosu.',
    '.software-note': 'Repozytorium nie zawiera obecnie zweryfikowanego zrzutu ekranu interfejsu aplikacji. W tej sekcji pokazujemy autentyczny przykładowy obraz z projektu.',
    '.download-content .eyebrow': 'NASTĘPNA POGODNA NOC',
    '.download-content h2': 'Zrób miejsce<br>na <em>zachwyt.</em>',
    '.download-content>p:not(.eyebrow)': 'Przybliż swój warsztat astrofotograficzny do gwiazd.',
    '.platform-downloads': 'Pobieranie DSOpus dla Twojego systemu operacyjnego',
    '.platform-link:nth-child(1)': 'Pobierz DSOpus dla Windows',
    '.platform-link:nth-child(2)': 'Pobierz DSOpus dla Linux',
    '.platform-link:nth-child(3)': 'Pobierz DSOpus dla macOS z procesorem Apple silicon',
    '.platform-link:nth-child(4)': 'Pobierz DSOpus dla macOS z procesorem Intel',
    '.platform-link:nth-child(1) .platform-label>strong': 'Windows',
    '.platform-link:nth-child(2) .platform-label>strong': 'Linux',
    '.platform-link:nth-child(3) .platform-label>strong': 'macOS <small class="architecture">Apple silicon</small>',
    '.platform-link:nth-child(4) .platform-label>strong': 'macOS <small class="architecture">Intel</small>',
    '.platform-label>small': 'Pobierz <i>↗</i>',
    '.download-meta': 'Bezpośrednie pliki do pobrania z GitHub Releases',
    '.site-footer>p': 'Stworzony z miłości do nocnego nieba.',
    '.site-footer>div a:nth-child(1)': 'GitHub',
    '.site-footer>div a:nth-child(3)': 'Dokumentacja',
    '.site-footer small': '© 2026 Współtwórcy DSOpus',
    '.gallery-dialog': 'Przeglądarka obrazów',
    '.gallery-close': 'Zamknij obraz na pełnym ekranie',
    '.gallery-prev': 'Poprzedni obraz',
    '.gallery-next': 'Następny obraz'
  };

  for (const [selector, value] of Object.entries(copy)) {
    const elements = document.querySelectorAll(selector);
    elements.forEach(element => {
      if (selector === '.navigation' || selector === '.wordmark[aria-label]' || selector === '.platform-downloads') element.setAttribute('aria-label', value);
      else if (selector.startsWith('.platform-link:nth-child')) element.setAttribute('aria-label', value);
      else if (selector === '.menu-toggle' || selector.endsWith('.expand-image') || selector.startsWith('.gallery-') || selector === '.scroll-cue' || selector === '.feature-image' || selector.endsWith(' video')) element.setAttribute('aria-label', value);
      else if (selector === '.comparison-range') element.setAttribute('aria-label', value);
      else if (selector.includes('img')) element.setAttribute('alt', value);
      else element.innerHTML = value;
    });
  }
}

const comparisons = [
  { tool:'deepSNR', toolPl:'deepSNR', target:'C11', before:'deepsnr-c11-before.webp', after:'deepsnr-c11-after.webp', note:'Noise reduction', notePl:'Redukcja szumu' },
  { tool:'deepSNR', toolPl:'deepSNR', target:'NGC 281', before:'deepsnr-before.webp', after:'deepsnr-after.webp', note:'Noise reduction', notePl:'Redukcja szumu' },
  { tool:'Star Shrink', toolPl:'Star Shrink', target:'C11', before:'shrink-c11-before.webp', after:'shrink-c11-after.webp', note:'Star size reduction', notePl:'Zmniejszanie gwiazd' },
  { tool:'Star Shrink', toolPl:'Star Shrink', target:'NGC 281', before:'shrink-before.webp', after:'shrink-after.webp', note:'Star size reduction', notePl:'Zmniejszanie gwiazd' },
  { tool:'Background extraction', toolPl:'Usuwanie gradientu tła', target:'C11', before:'background-before.webp', after:'background-after.webp', note:'Gradient removal', notePl:'Korekcja gradientu tła' },
  { tool:'Background extraction', toolPl:'Usuwanie gradientu tła', target:'NGC 281', before:'background-ngc281-before.webp', after:'background-ngc281-after.webp', note:'Gradient removal', notePl:'Korekcja gradientu tła' },
  { tool:'Sharpening', toolPl:'Wyostrzanie', target:'NGC 281', before:'sharpen-ngc281-before.webp', after:'sharpen-ngc281-after.webp', note:'Sharpening detail', notePl:'Wyostrzenie szczegółów' },
  { tool:'Astro Upscale', toolPl:'Astro Upscale', target:'C11', before:'upscale-c11-before.webp', after:'upscale-c11-after.webp', note:'Lanczos / bicubic resampling · no generated detail', notePl:'Interpolacja Lanczosa / bikubiczna · bez generowania detali' },
  { tool:'Astro Upscale', toolPl:'Astro Upscale', target:'NGC 281', before:'upscale-before.webp', after:'upscale-after.webp', note:'Lanczos / bicubic resampling · no generated detail', notePl:'Interpolacja Lanczosa / bikubiczna · bez generowania detali' }
];

const comparisonGrid = document.querySelector('#comparison-grid');
comparisonGrid.innerHTML = comparisons.map((item, index) => {
  const tool = polish ? item.toolPl : item.tool;
  const target = item.target;
  const beforeAlt = polish ? `${target} · obraz oryginalny` : `${target} · original image`;
  const afterAlt = polish ? `${target} · obraz po obróbce ${tool}` : `${target} · image after ${tool}`;
  const title = `${tool} · ${target}`;
  const note = polish ? item.notePl : item.note;
  const openLabel = polish ? `Pokaż porównanie ${tool} · ${target} na pełnym ekranie` : `View ${tool} · ${target} comparison fullscreen`;
  const rangeLabel = polish ? `Porównaj oryginalny obraz ${target} z obrazem po obróbce ${tool}` : `Compare original ${target} image with ${tool} result`;
  return `<article class="comparison-card reveal">
    <div class="compare-frame" data-compare>
      <img class="compare-base" src="assets/images/${item.before}" alt="${beforeAlt}" loading="lazy">
      <div class="compare-overlay"><img src="assets/images/${item.after}" alt="${afterAlt}" loading="lazy"></div>
      <span class="compare-label label-before">${polish ? 'ORYGINAŁ' : 'ORIGINAL'}</span><span class="compare-label label-after">${tool.toUpperCase()}</span>
      <input class="compare-range" type="range" min="0" max="100" value="50" aria-label="${rangeLabel}">
      <span class="compare-handle" aria-hidden="true"><b>←</b><b>→</b></span>
    </div>
    <div class="comparison-caption"><div><h3>${title}</h3><p>${note}</p></div><button class="expand-image" data-gallery-start="${index}" aria-label="${openLabel}">↗</button></div>
  </article>`;
}).join('');

const menuButton = document.querySelector('.menu-toggle');
const nav = document.querySelector('.navigation');
menuButton.addEventListener('click', () => {
  const open = menuButton.getAttribute('aria-expanded') !== 'true';
  menuButton.setAttribute('aria-expanded', String(open));
  menuButton.setAttribute('aria-label', polish ? (open ? 'Zamknij menu' : 'Otwórz menu') : (open ? 'Close navigation' : 'Open navigation'));
  nav.classList.toggle('open', open);
});
nav.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
  nav.classList.remove('open'); menuButton.setAttribute('aria-expanded', 'false'); menuButton.setAttribute('aria-label', polish ? 'Otwórz menu' : 'Open navigation');
}));

document.querySelectorAll('[data-compare]').forEach(frame => {
  const range = frame.querySelector('.compare-range');
  const overlay = frame.querySelector('.compare-overlay');
  const handle = frame.querySelector('.compare-handle');
  const update = () => {
    const split = Number(range.value);
    overlay.style.clipPath = `inset(0 ${100 - split}% 0 0)`;
    handle.style.left = `${split}%`;
  };
  range.addEventListener('input', update); update();
});

const gallery = document.querySelector('.gallery-dialog');
const galleryImage = gallery.querySelector('img');
const galleryCaption = gallery.querySelector('figcaption');
const images = [{
  src:'assets/images/hero.webp', alt:'NGC 281, the Pacman Nebula', altPl:'NGC 281, mgławica Pacman',
  caption:'NGC 281 · Project image sample', captionPl:'NGC 281 · Przykładowy obraz z projektu'
}, ...comparisons.flatMap(item => {
  const tool = polish ? item.toolPl : item.tool;
  const originalCaption = `${item.target} · ${tool} · ${polish ? 'Oryginał' : 'Original'}`;
  const resultCaption = `${item.target} · ${tool} · ${polish ? 'Po obróbce' : 'Processed'}`;
  return [
    { src:`assets/images/${item.before}`, alt:`${item.target} original image`, altPl:`${item.target} · obraz oryginalny`, caption:originalCaption, captionPl:originalCaption },
    { src:`assets/images/${item.after}`, alt:`${item.target} image after ${tool}`, altPl:`${item.target} · obraz po obróbce ${tool}`, caption:resultCaption, captionPl:resultCaption }
  ];
})];
let activeImage = 0;
function showImage(index) {
  activeImage = (index + images.length) % images.length;
  const item = images[activeImage];
  galleryImage.src = item.src; galleryImage.alt = polish ? item.altPl : item.alt; galleryCaption.textContent = polish ? item.captionPl : item.caption;
}
document.querySelectorAll('[data-gallery-start], [data-gallery="hero"]').forEach(button => button.addEventListener('click', () => {
  const pairIndex = Number(button.dataset.galleryStart);
  showImage(button.dataset.gallery === 'hero' ? 0 : 1 + pairIndex * 2);
  gallery.showModal();
}));
gallery.querySelector('.gallery-close').addEventListener('click', () => gallery.close());
gallery.querySelector('.gallery-prev').addEventListener('click', () => showImage(activeImage - 1));
gallery.querySelector('.gallery-next').addEventListener('click', () => showImage(activeImage + 1));
gallery.addEventListener('click', event => { if (event.target === gallery) gallery.close(); });
document.addEventListener('keydown', event => {
  if (!gallery.open) return;
  if (event.key === 'ArrowLeft') showImage(activeImage - 1);
  if (event.key === 'ArrowRight') showImage(activeImage + 1);
});

const revealObserver = new IntersectionObserver(entries => entries.forEach(entry => {
  if (entry.isIntersecting) { entry.target.classList.add('visible'); revealObserver.unobserve(entry.target); }
}), { threshold: 0.12, rootMargin: '0px 0px -35px 0px' });
document.querySelectorAll('.reveal').forEach(element => revealObserver.observe(element));

const hero = document.querySelector('.hero-image');
let ticking = false;
window.addEventListener('scroll', () => {
  if (ticking || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  ticking = true;
  requestAnimationFrame(() => {
    const y = Math.min(window.scrollY, window.innerHeight);
    hero.style.backgroundPosition = `center calc(43% + ${y * 0.13}px)`;
    ticking = false;
  });
}, { passive:true });

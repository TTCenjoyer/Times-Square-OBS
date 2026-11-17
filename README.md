# Times Square LIVE dla OBS

Wstaw kamerę, film, przechwytywane okno, przeglądarkę albo całą scenę na billboardy
Times Square w czasie rzeczywistym. Obraz podąża za ruchem kamery i jest przycinany
do ekranów, z zachowaniem obiektów znajdujących się przed nimi.

Projekt zawiera filtr **Lua**, shader GPU, przenośny zbiór scen i narzędzia do
zbudowania zsynchronizowanego filmu pomocniczego. Nie wymaga kompilowania DLL.

## Co działa

- Wyjście i scena wejściowa: **1920 × 1080, 30 kl./s**.
- Pionowy film jest wyśrodkowany i dopasowany do wysokości poziomego wyjścia.
- Ten sam obraz na wszystkich billboardach, z osobnym mapowaniem powierzchni.
- Siatka dopasowana do pełnych obrysów zakrzywionych ekranów.
- Dokładna animowana maska, śledzenie 900 klatek i zapętlenie co 30 sekund.
- Usunięte kreski poręczy na pierwszym dużym ekranie i wyrównany podział rzędów.
- Jasność, powiększenie, przesunięcie obrazu i podgląd maski we właściwościach filtra.
- Aktualizacja instalacji zachowuje kamery, układ scen, inne skrypty i przejścia.

## Wymagania

- Windows i OBS Studio z obsługą skryptów Lua; sprawdzone na **OBS 32.0.4**.
- Python **3.12** do jednorazowego zbudowania filmu i instalacji.
- Kilka GB wolnego miejsca. Film pomocniczy UtVideo zajmuje około **3,3 GB**.

Podczas codziennego używania w OBS Python ani połączenie z siecią nie są potrzebne.

## Instalacja

Pobierz repozytorium przez `git clone` albo **Code → Download ZIP**. Nie przenoś
folderu po instalacji: OBS przechowuje bezwzględne ścieżki do skryptu i mediów.

W PowerShell, w katalogu projektu:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe tools\build_atlas.py
```

Budowanie może potrwać kilka minut. Narzędzie najpierw składa i sprawdza sumy
kontrolne plików źródłowych, a potem generuje
`assets/generated/times-square-live-v2.mkv`. Baza, maska i współrzędne siatki
znajdują się w jednym pliku, więc nie mają niezależnych zegarów odtwarzania.

Zamknij OBS i zainstaluj przygotowany zbiór:

```powershell
.\.venv\Scripts\python.exe tools\install.py
```

Otwórz OBS i wybierz **profil Times Square LIVE** oraz **zbiór scen Times Square LIVE**.
Instalator tworzy profil 1920 × 1080 tylko wtedy, gdy taki profil jeszcze nie istnieje.

Jeśli masz już przygotowany film pomocniczy, możesz pominąć jego budowanie:

```powershell
py tools\install.py --atlas "D:\Media\times-square-live-v2.mkv"
```

### Aktualizacja istniejącego zbioru

```powershell
py tools\install.py --update-existing
```

Ta opcja aktualizuje wyłącznie ścieżkę skryptu Times Square oraz filmu z jego
filtrem. Zachowuje urządzenia, ustawienia źródeł, pozycje, inne skrypty, definicje
przejść i istniejący profil. Kopia zbioru trafia do `.obs-backups` w konfiguracji OBS.

Projekt nie instaluje osobnej wtyczki przejść ani panelu przejść. Jeśli są już
załadowane w Twoim zbiorze, aktualizacja ich nie usuwa.

## Używanie

1. W scenie **01 | Obraz na billboardach** dodaj swoje źródło.
2. Dopasuj je do całego kadru 1920 × 1080. **Ctrl+F** dopasowuje źródło z zachowaniem
   proporcji; przy innych proporcjach powiększ i przytnij je według potrzeb.
3. Ukryj **Plansza LIVE - ukryj po dodaniu swojego obrazu** przyciskiem oka.
4. Wybierz **02 | Times Square LIVE** jako wynik do nagrania, transmisji lub kamery wirtualnej.

Dźwięk źródeł ze sceny wejściowej przechodzi normalnie przez mikser OBS. W scenie
wynikowej jej dodatkowa instancja jest umieszczona poza kadrem, aby aktywować źródła
i dźwięk bez pokazywania ich w tle.

W scenie 02 wybierz źródło **Times Square - tlo 30 s + tracking → Filtry**. Filtr
**Times Square LIVE - maska i perspektywa** udostępnia regulację obrazu. Opcja
pobierania środkowego pasa 16:9 pozostaje wyłączona w tym poziomym układzie.

Jeśli nie można przeciągać źródła, wyłącz **Zablokuj podgląd** w menu pod prawym
przyciskiem i sprawdź kłódkę obok źródła.

## Struktura

| Ścieżka | Zawartość |
| --- | --- |
| `obs/times-square-live.lua` | Filtr OBS i wybór sceny wejściowej |
| `obs/times-square.effect` | Kompozycja obrazu w shaderze GPU |
| `obs/scene-collection.template.json` | Zbiór scen bez prywatnych urządzeń i ścieżek |
| `samples/plansza-live.html` | Animowana plansza testowa z zegarem |
| `tools/build_atlas.py` | Budowa filmu UtVideo z maską i mapą UV |
| `tools/mesh_mapping.py` | Mapowanie pełnych obrysów i korekty geometrii |
| `tools/install.py` | Instalacja i aktualizacja z zachowaniem innych ustawień |
| `assets/source/manifest.json` | Sumy kontrolne bazy, maski, trackingu i ich części |
| `assets/source/parts/` | Podzielone pliki źródłowe; składane automatycznie |

Duży film wynikowy, nagrania testowe, ustawienia urządzeń, tokeny i lokalna
konfiguracja OBS nie są przechowywane w repozytorium.

## Sprawdzenie projektu

```powershell
py -m unittest discover -s tests -v
py -m compileall -q tools
```

Krótki test generowania, bez przeliczania całego filmu:

```powershell
.\.venv\Scripts\python.exe tools\build_atlas.py --start-frame 493 --frames 2 --output assets\generated\test.mkv
```

Pełna wersja mapowania została sprawdzona dla 900 klatek, z kontrolą pokrycia
maski, orientacji siatki i synchronizacji. Efekt w OBS był sprawdzony w nagraniach
obejmujących więcej niż dwie pętle tła przy 30 kl./s.

## Materiał źródłowy i ograniczenia

Zobacz [NOTICE.md](NOTICE.md). Mapowanie jest przygotowane dla dostarczonego
30-sekundowego klipu Times Square. Inny film wymaga własnego trackingu i maski.
To deformacja obrazu na śledzonych powierzchniach, a nie rekonstrukcja sceny 3D.

# Materiały i zależności

## Film bazowy

Według informacji dostarczonych z materiałem roboczym, film bazowy pochodzi z:

[Vibrant nightlife in Times Square, NYC — Pexels](https://www.pexels.com/video/vibrant-nightlife-in-times-square-nyc-37072488/).

Wykorzystany fragment: 00:12–00:42. Wersja robocza ma rozdzielczość 1080 × 1920,
30 kl./s, 30 sekund. Baza, maska i tracking znajdują się w częściach w
`assets/source/parts/`. Ich identyfikatory i sumy kontrolne są zapisane w manifeście.
Prawa do materiału źródłowego pozostają przy jego właścicielach; sprawdź warunki
źródła przy dalszym wykorzystaniu.

Repozytorium nie zawiera nagrań z kamery użytkownika ani testowych montaży
z innymi filmami.

## Zależności

- OBS Studio i jego API Lua: <https://github.com/obsproject/obs-studio>
- NumPy, OpenCV, SciPy i Numba: obliczenia i przetwarzanie materiału podczas budowania.
- Python Triangle: <https://github.com/drufat/triangle>
- Triangle / Jonathan Richard Shewchuk: <https://www.cs.cmu.edu/~quake/triangle.html>
- imageio-ffmpeg i FFmpeg: kodowanie filmu pomocniczego.

Zależności mają własne warunki licencji. Repozytorium nie zawiera ich bibliotek
binarnych; instaluje je menedżer pakietów. W szczególności Triangle ma odrębne
warunki dotyczące dystrybucji i zastosowań komercyjnych.

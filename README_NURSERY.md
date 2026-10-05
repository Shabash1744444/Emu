# C4 Nursery — FLAT mobile-upload edition

Все файлы этого пакета лежат В КОРНЕ. Вложенных папок нет.

## Что загрузить в корень Emu
Загрузить все файлы из этого ZIP в корень репозитория.

`index.html` уже самодостаточный: CSS + runtime JS + app JS встроены внутрь.

## Единственный специальный файл
GitHub Actions по правилам GitHub читает workflow ТОЛЬКО из `.github/workflows/`.
Поэтому `BUILD_APK.yml` лежит в корне для удобной загрузки с телефона, но его
содержимое нужно один раз использовать как `.github/workflows/build.yml`.

После этого последующие обновления Nursery могут оставаться flat-root.

## Инвариант
C4 не знает tokens/prompts/message length. Ввод — поток; transport chunking не
создаёт независимые доказательства.

## Проверка
`TEST_RUNTIME.mjs` — deterministic stream/freeze/restore probe.

# Reelsator Test Fixtures Documentation

В данном документе приведено детальное описание тестовых фикстур, используемых в тестовом наборе Reelsator (`tests/test_integration_c2pa.py` и `tests/test_core.py`).

Фикстуры строго разделены на **независимые эталонные (Reference)** и **спецификационные синтетические (Synthetic)**.

---

## 1. Независимые эталонные фикстуры (Reference Fixtures)

### `c2pa_cai_reference.jpg`
* **Источник**: Официальный эталонный репозиторий [Content Authenticity Initiative (CAI) `contentauth/c2pa-rs`](https://github.com/contentauth/c2pa-rs/blob/main/sdk/tests/fixtures/C.jpg).
* **Лицензия**: MIT / Apache-2.0.
* **Размер**: 132 518 байт.
* **SHA-256**: `a2d14755db55de67a47c04090340d8266e892367be4104a45626d7a6fa6e9ffd`
* **Содержимое**: Полноценный подписанный манифест происхождения C2PA, инкапсулированный в JPEG APP11 маркер JUMBF (claim store, assertions, signature).
* **Назначение в тестах**: Независимый интеграционный тест эрадикации реальных подписанных манифестов C2PA модулем `core/c2pa_killer.py`. После обработки файл не должен содержать маркеров JUMBF / C2PA.

### `display_p3_reference.jpg`
* **Источник**: Профиль из эталонного набора [W3C Web Platform Tests (WPT)](https://github.com/web-platform-tests/wpt/tree/master/html/canvas/element/manual/wide-gamut-canvas/resources).
* **Копирайт профиля**: `Copyright Apple Inc., 2017`.
* **Размер**: 1 451 байт.
* **SHA-256**: `82621e7e0632b21bb318b3a410bf9ad0f36ce67eb9f80e195a89bb34ad76dcc2`
* **Содержимое**: Изображение 120×120 с аутентичным встроенным профилем Display P3 от Apple Inc. (DCI-P3 primaries, адаптированные к D50, трансферная функция sRGB).
* **Назначение в тестах**: Проверка преобразования цветового пространства из Display P3 в стандартный sRGB через LittleCMS. Исходный цвет `(200, 50, 50)` конвертируется в sRGB со сдвигом: красный канал расширяется ($> 205$), зеленый сужается ($< 35$).

---

## 2. Спецификационные синтетические фикстуры (Synthetic Fixtures)

Синтетические фикстуры генерируются детерминированно скриптом `tests/generate_fixtures.py` для быстрых регрессионных unit-тестов без сетевых зависимостей.

### `synthetic_c2pa_jumbf.jpg`
* **Спецификация**: ISO/IEC 19566-5 (JUMBF) и C2PA Technical Specification v1.x (JPEG encapsulation).
* **Размер**: 1 173 байт.
* **SHA-256**: `b24335604391554a4e6cf6a0e79a852c0a4e6a2e0931195193e7e5588f31cb55`
* **Содержимое**: Изображение 160×160 с синтезированным маркером APP11 (0xFFEB), содержащим JUMBF Description Box (UUID C2PA `63327061-0011-0010-8000-00aa00389b71`) и Content Box `c2pa`.
* **Назначение**: Проверка побайтового парсинга JPEG и удаления маркеров APP11 JUMBF.

### `synthetic_c2pa_cabx.png`
* **Спецификация**: C2PA PNG Binding Specification.
* **Размер**: 523 байт.
* **SHA-256**: `c896b07c58c13f1b5934c8b7b4ffa330fe917c441d18c7ab3feb7746aedc1444`
* **Содержимое**: PNG-изображение 160×160 со специализированным чанком `caBX` и корректной CRC32 контрольной суммой.
* **Назначение**: Проверка обнаружения и фильтрации чанков `caBX` / `c2pa` в PNG-структуре.

### `synthetic_display_p3_profile.jpg`
* **Спецификация**: ICC.1:2001-04 (ICC v2.4 profile format).
* **Размер**: 1 399 байт.
* **SHA-256**: `af8efe761b636daaf44a2500448edd0f92bfa079c21cc943b3e2a0a59c7ead6d`
* **Содержимое**: Изображение 120×120 с синтетическим матричным ICC-профилем Display P3 (DCI-P3 primaries, гамма 2.2).
* **Назначение**: Локальная быстрая валидация LittleCMS конвейера.

### `orientation_6.jpg`
* **Спецификация**: TIFF 6.0 / EXIF 2.3 Tag 0x0112 (Orientation = 6: Top-Right / поворот 90° по часовой стрелке).
* **Размер**: 1 029 байт.
* **SHA-256**: `04bfc769ecd63cf9ea5669794837f90f0015ee4343210bce820f3cfdb3d800bc`
* **Содержимое**: Физическое изображение 200×100 px с тегом Orientation=6.
* **Назначение**: Проверка предварительной нормализации ориентации (`ImageOps.exif_transpose`) до сноса EXIF: результирующий размер должен быть 100×200 px.

### `rgba_transparent.png`
* **Спецификация**: PNG 32-bit RGBA с прозрачной областью в центре.
* **Размер**: 377 байт.
* **SHA-256**: `68682915fcd01bd4bf560db1108ee86cf16fbfff80f1a7f20094a8b092727764`
* **Содержимое**: PNG 120×120 с альфа-вырезом 60×60 в центре (alpha = 0).
* **Назначение**: Проверка композитинга альфа-канала на сплошной белый фон перед экспортом в JPEG, исключающего черные артефакты.

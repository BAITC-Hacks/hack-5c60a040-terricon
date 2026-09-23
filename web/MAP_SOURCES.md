# Карта альтернативы, 23.09.2026

Основной проект не изменён. Только автономный index.html. Сервер остаётся localhost:8766.

## Геометрия
Публичные полигоны OpenStreetMap загружены через Nominatim: relation 3486954 (Сарыарка), 8593081 (Байконур), 20593940 (Нура), 3479876 (Есиль), 3482819 (Алматы), 19733918 (Сарайшык). Источник и лицензия: https://www.openstreetmap.org/copyright (ODbL). Исходный ответ: districts-osm.json. Производная пятирайонная геометрия: districts-model.geojson.

Алматы и Сарайшык объединены только для соответствия пятирайонному движку. Это адаптация современных контуров, НЕ точное историческое/нынешнее административное деление. Река взята как общая граница северных и южных береговых районов; канал и водоёмы отдельно не добавлялись. Проекция Mercator, одинаковый масштаб обеих осей. Центральный вид обрезает окраины; доступен общий контур. Силуэты увеличены и вынесены; пунктир ведёт к точке объекта.

## Ориентиры
- Сарыарка: музей Сакена Сейфуллина, 51.17143, 71.42349. https://www.komandirovka.ru/sights/astana/muzey-imeni-sakena-seyfullina/ ; принадлежность району: https://kazakhstan.travel/ru/attractions/438
- Байконур: дворец Жастар, 51.170014, 71.427702. https://www.komandirovka.ru/sights/astana/jastar/ ; https://visitastana.kz/ru/about-city/what-to-see/dvorets-zhastar/
- Нура: Хан Шатыр, 51.13222, 71.40389. https://iskatel.com/places/torgovo-razvlekatelnyy-tsentr-han-shatyr ; границы Нуры: https://www.gov.kz/memleket/entities/astana-nura/press/news/details/560659?lang=ru
- Есиль: Байтерек, 51.1283, 71.4305. https://kazakhstan.travel/ru/attractions/423 ; координаты: https://mapcarta.com/W230401645 ; расположение проверено внутри полигона Есиля. Координаты ориентиров приблизительные.
- Алматы в модели / современный Сарайшык: Дворец мира и согласия, 51.12315, 71.46355. https://iskatel.com/places/dvorets-mira-i-soglasiya ; https://visitastana.kz/ru/exhibition-areas/dvorets-mira-i-soglasiyaa/

Силуэты — оригинальные упрощённые SVG-иллюстрации, не архитектурные чертежи. Все показатели, бюджет и валидность по-прежнему возвращает существующий движок.

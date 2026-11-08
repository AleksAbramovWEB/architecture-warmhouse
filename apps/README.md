# Учебный контур датчиков «Тёплый дом»

В Compose запускаются исходный Go-монолит `smart_home`, PostgreSQL 16 и симулятор удалённого датчика `temperature-api` на **Java 21 и Spring Boot 3.5.16**. На хосте нужны Docker Engine и Docker Compose v2 с поддержкой `up --wait`; Java, Gradle и Go устанавливать не требуется.

## Запуск

Перед первым запуском скопируйте шаблон из корня репозитория:

```bash
cp -n apps/.env.example apps/.env
```

В `apps/.env` задайте `POSTGRES_USER` и непустой `POSTGRES_PASSWORD`, затем запустите:

```bash
./apps/init.sh
```

Скрипт сам переходит в `apps`, собирает оба приложения, запускает все три сервиса и ждёт healthcheck. Затем выводит фактические адреса и команды просмотра логов/остановки. JUnit-тесты нового сервиса выполняются при сборке его образа. Каталог `smart_home`, включая Dockerfile и SQL, используется без изменений.

Для PostgreSQL и монолита файл `apps/.env` подключён непосредственно через `env_file: .env`. Он содержит `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` и порты хоста. В Git включён только [.env.example](.env.example), локальные значения исключены через `.gitignore`. Без `.env` Compose останавливается с ошибкой; пустой пароль не позволяет PostgreSQL инициализировать новый том. Пароли с `$`, `#` или пробелами заключайте в одинарные кавычки. `APP_PORT` и `TEMPERATURE_PORT` используются для подстановки портов; для них переменные shell имеют приоритет.

Эквивалентный запуск вручную:

```bash
cd apps
docker compose up --build --detach --wait --wait-timeout 120
docker compose ps
```

Адреса по умолчанию:

| Сервис | Адрес |
| --- | --- |
| Smart Home API | http://localhost:8080 |
| Temperature API | http://localhost:8081 |
| PostgreSQL | `postgres:5432` внутри Compose-сети |

Для других портов можно запустить `APP_PORT=9080 TEMPERATURE_PORT=9081 ./apps/init.sh` из корня репозитория. Внутри сети приложения используют постоянные адреса `postgres:5432` и `temperature-api:8081`.

## Проверка как на ревью

Импортируйте [smarthome-api.postman_collection.json](smarthome-api.postman_collection.json). Сначала вызовите **Create Sensor**, затем несколько раз **Get All Sensors**. В коллекции используются стандартные порты `8080`; при их изменении измените адреса запросов в Postman.

Тот же сценарий через curl:

```bash
curl --fail-with-body -X POST http://localhost:8080/api/v1/sensors \
  -H 'Content-Type: application/json' \
  -d '{"name":"Living Room Temperature","type":"temperature","location":"Living Room","unit":"°C"}'
curl --fail-with-body http://localhost:8080/api/v1/sensors
curl --fail-with-body http://localhost:8080/api/v1/sensors
```

`POST` возвращает `201` с идентификатором и начальными значениями из БД (`value=0`, `status="inactive"`). При чтении списка или отдельного датчика исходный монолит обращается к симулятору: температура меняется, статус становится `active`. Сохраняются имя, расположение и остальные метаданные записи в БД. Значение и время измерения подставляются в ответ; чтение не пишет эти показания в PostgreSQL.

Автоматическая проверка из корня репозитория, после запуска Compose:

```bash
python3 tools/smoke_sensors.py
```

Скрипт берёт запросы **Create Sensor** и **Get All Sensors** из исходной коллекции, создаёт четыре собственных датчика, проверяет три последовательных чтения, отдельный датчик и произвольные ID. Расположение с пробелами/кириллицей/спецсимволами проверяется прямым запросом к Temperature API. В конце скрипт удаляет только созданные им записи. Для нестандартных портов доступны `--base-url` и `--temperature-url`.

## Temperature API

```bash
curl --fail-with-body --get --data-urlencode 'location=Living Room' http://localhost:8081/temperature
curl --fail-with-body http://localhost:8081/temperature/1
curl --fail-with-body 'http://localhost:8081/temperature?sensorId=2'
curl --fail-with-body http://localhost:8081/health
```

Поддерживаются `GET /temperature?location=...`, `GET /temperature/{sensorId}` и query-параметры `sensorId`/`sensor_id`. Маршрут по ID нужен существующему `TemperatureService` монолита. Если ID не передан, он определяется по комнате; если не передана комната — по ID:

| `sensor_id` | `location` |
| --- | --- |
| `1` | `Living Room` |
| `2` | `Bedroom` |
| `3` | `Kitchen` |
| другой ID | `Unknown`, ID сохраняется |
| `0` | неизвестная комната, когда ID не передан |

Без параметров возвращаются `sensor_id="0"`, `location="Unknown"`. Для неизвестной комнаты сохраняется переданное имя и назначается ID `0`. Симулятор выдаёт значения от **15.00 до 30.00 °C** с шагом 0.01 и исключает повтор предыдущего значения для пары `(sensor_id, location)` в рамках одного процесса. `timestamp` — UTC, `Cache-Control: no-store`. При перезапуске генератор начинает новую последовательность.

JSON содержит совместимые с монолитом поля: `value`, `unit`, `timestamp`, `location`, `status`, `sensor_id`, `sensor_type`, `description`.

### Устройство Java-приложения

- [build.gradle.kts](temperature-api/build.gradle.kts) задаёт Java 21, Spring Boot, Spring MVC и JUnit; сборка описана на Kotlin DSL. Совместимость Java 21 с выбранной веткой описана в [требованиях Spring Boot](https://docs.spring.io/spring-boot/3.5/system-requirements.html).
- [TemperatureController](temperature-api/src/main/java/ru/warmhouse/temperature/TemperatureController.java) принимает HTTP-запросы и устанавливает `Cache-Control: no-store`.
- [TemperatureService](temperature-api/src/main/java/ru/warmhouse/temperature/TemperatureService.java) сопоставляет ID/комнату и генерирует показание. Атомарный `ConcurrentHashMap.compute` исключает повтор соседних значений одного датчика при конкурентных запросах; температура представлена `BigDecimal`, время — `Instant`.
- [TemperatureResponse](temperature-api/src/main/java/ru/warmhouse/temperature/TemperatureResponse.java) задаёт JSON-контракт с `sensor_id` и `sensor_type`.
- [Dockerfile](temperature-api/Dockerfile) собирает исполняемый JAR через Gradle 8.14.3 на JDK 21 и запускает его в JRE 21 от UID `10001`. `gradle build` выполняет тесты перед упаковкой образа.

Для разработки вне Docker нужен JDK 21; Gradle 8.14.3 загружает включённый в репозиторий Gradle Wrapper. Контрольная сумма дистрибутива закреплена в [gradle-wrapper.properties](temperature-api/gradle/wrapper/gradle-wrapper.properties):

```bash
cd apps/temperature-api
./gradlew build
java -jar build/libs/temperature-api.jar
```

[Тесты](temperature-api/src/test/java/ru/warmhouse/temperature) проверяют HTTP-контракт через Spring MVC, сопоставление комнат/ID, диапазон и смену показаний. По умолчанию приложение слушает порт `8081`; настройки находятся в [application.properties](temperature-api/src/main/resources/application.properties).

## PostgreSQL и управление контейнерами

`POSTGRES_DB=postgres` задаёт начальную БД официального образа. Исходный [smart_home/init.sql](smart_home/init.sql) монтируется read-only в `/docker-entrypoint-initdb.d/001-init.sql`, сам создаёт базу `smarthome`, подключается к ней через `\c` и создаёт таблицу `sensors` и индексы. Это позволяет использовать SQL без изменений и избежать повторного создания `smarthome`.

Логин и пароль поступают из `.env` как `POSTGRES_USER`/`POSTGRES_PASSWORD`. Команда запуска монолита переносит их в `PGUSER`/`PGPASSWORD`, которые поддерживает его драйвер [pgx](https://pkg.go.dev/github.com/jackc/pgx/v5@v5.3.1/pgconn#ParseConfig), и через `exec` запускает исходный бинарник. Значения реквизитов в Compose не дублируются. Строка `DATABASE_URL` содержит только адрес, порт и имя БД: специальные символы в пароле не требуют URL-кодирования. Сохраните `POSTGRES_DB=postgres` в `.env`: базу `smarthome` создаёт исходный SQL.

Инициализация выполняется только для нового тома. Данные хранятся в именованном `postgres_data`; обычная остановка их сохраняет. Скрипт с `CREATE DATABASE` предназначен для первой инициализации и не запускается повторно при обычном перезапуске.

Изменение `POSTGRES_USER`/`POSTGRES_PASSWORD` в `.env` не меняет учётную запись в уже инициализированном томе. Для существующего тома используйте действующие реквизиты; смена пароля выполняется отдельно в PostgreSQL.

Команды из `apps`:

```bash
docker compose logs -f
docker compose down
```

`app` запускается после успешных healthcheck PostgreSQL и симулятора. Проверка PostgreSQL использует TCP, чтобы не принять временный сервер первичной инициализации за готовую БД. У каждого сервиса есть свой healthcheck; `init.sh` завершится ошибкой, если сервисы не стали готовы.

Правила запуска и инициализации: [Docker Compose — startup order](https://docs.docker.com/compose/how-tos/startup-order/), [переменные Compose и .env](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/), [официальный PostgreSQL image](https://hub.docker.com/_/postgres).

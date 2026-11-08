# DOLI producer-нода в Docker

[![DOLI](https://img.shields.io/badge/DOLI-v6.46.1-6c5ce7)](https://github.com/doli-network/doli/releases)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](node/docker-compose.yml)
[![Язык](https://img.shields.io/badge/язык-русский-lightgrey)](#)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Пошаговый гайд: как поставить producer'а сети [DOLI](https://doli.network) (mainnet) на свой Linux-сервер. Нода собирается из исходников и работает в Docker. Есть скрипт мониторинга, который пишет короткие сообщения в чат.

Проверено на v6.43.3 на чистом VPS 12.10.2026: сборка, синхронизация, `new`, `info`, `balance`, `producer status`. Версия v6.46.1 проверена на чистом VPS 08.11.2026 (2 vCPU, Ubuntu 24.04, процессор с ADX): сборка, синхронизация за 2 минуты, `check-branch.sh`, `new`, `info`, `balance`, `producer status`. На процессоре без ADX эта версия не проверялась.

## Содержание

1. [Что такое DOLI-producer и сколько он даёт](#1-что-такое-doli-producer)
2. [Что нужно](#2-что-нужно)
3. [Сборка и запуск ноды](#3-сборка-и-запуск-ноды)
4. [Кошелёк и ключ producer'а](#4-кошелёк-и-ключ-producerа)
5. [Faucet и регистрация](#5-faucet-и-регистрация)
6. [Проверка раз в день](#6-проверка-раз-в-день)
7. [Обновление](#7-обновление)
8. [Правила и грабли](#8-правила-и-грабли)
9. [Полезные команды](#9-полезные-команды)

## Слова, которые встретятся

| Слово | Что это |
|---|---|
| Нода | Программа, которая подключается к сети DOLI и хранит её данные |
| Producer | Нода, зарегистрированная в сети: она получает награду |
| Bond | Залог 10 DOLI, он нужен для регистрации producer'а |
| Эпоха | Период около часа (360 блоков), за который считается награда |
| Attestation | Подтверждение блоков вашей нодой. Награда идёт за эпоху, в которой нода была онлайн не меньше 90% времени ([rewards.md](https://github.com/doli-network/doli/blob/main/docs/rewards.md#5-epoch-reward-pool-math)) |
| Seed-фраза | 24 слова, из которых восстанавливается кошелёк. Потеряли фразу и файл ключа — доступ к деньгам потерян |
| Snap sync | Быстрая загрузка текущего состояния сети вместо всей истории блоков |
| Slashing | Наказание: сгорает весь bond, если один ключ работает на двух нодах ([slashing](https://github.com/doli-network/doli/blob/main/docs/becoming_a_producer.md#8-slashing)) |
| Healthy | Статус контейнера Docker: проверка внутри него проходит |

## 1. Что такое DOLI-producer

DOLI — L1 на Rust с Proof of Time (VDF) и моделью UTXO. Блок выходит раз в 10 секунд, эпоха длится 360 блоков (около часа) ([параметры](https://github.com/doli-network/doli/blob/main/README.md#protocol-parameters)).

- **Регистрация producer'а.** Нужен bond: 10 DOLI за один bond ([becoming_a_producer.md](https://github.com/doli-network/doli/blob/main/docs/becoming_a_producer.md#22-economic)). Первые деньги можно получить бесплатно через faucet в Discord: 10,000001 DOLI, то есть bond плюс комиссия регистрации ([faucet-bot.md](https://github.com/doli-network/doli/blob/main/docs/faucet-bot.md#what-you-get)).
- **Bond можно вернуть, но досрочный выход стоит денег.** Деньги приходят через 7 дней после заявки. Часть bond'а сгорает по возрасту bond'а ([Vesting](https://github.com/doli-network/doli/blob/main/docs/becoming_a_producer.md#66-vesting-schedule-and-early-withdrawal-penalties)):

| Возраст bond'а | Сгорает |
|---|---|
| меньше 1 года | 75% |
| от 1 до 2 лет | 50% |
| от 2 до 3 лет | 25% |
| 3 года и больше | 0% |

## 2. Что нужно

- **Сервер.** Linux x86_64 с Docker и Compose v2. Минимум для producer'а: **4 CPU, 8 GB RAM, 100 GB SSD**; рекомендуется 8 CPU, 16 GB, 500 GB NVMe ([требования](https://github.com/doli-network/doli/blob/main/docs/becoming_a_producer.md#21-hardware)). Если ядер меньше 4, контейнер с `cpus: 4` не стартует: уменьшите `DOLI_CPUS` в `.env`.
- **Аккаунт Discord старше 1 года** (365 дней) на сервере [DOLI](https://discord.gg/aTgHyDY9QY). Ждать 7 дней после вступления для faucet больше не нужно: это сказано в анонсе faucet в Discord DOLI. В документации ([faucet-bot.md](https://github.com/doli-network/doli/blob/main/docs/faucet-bot.md#eligibility-rules)) ещё старое правило, верьте анонсу.

**Проверьте процессор.** Готовые программы DOLI требуют у процессора возможность под названием ADX. Проверка:

```bash
grep -c -w adx /proc/cpuinfo
```

Любое число, кроме 0, — всё хорошо. Если вышло 0, этот гайд всё равно подходит, потому что собирает ноду на вашем сервере. Не подходит только готовый `install.sh` из официальной инструкции: он ставит программу, которая на таком процессоре вылетает. Версию v6.46.1 на таком процессоре мы не проверяли; по сообщению в [issue #230](https://github.com/doli-network/doli/issues/230) сборка на месте помогает. Если сборка или запуск упадёт, откройте Issue в этом репозитории.

## 3. Сборка и запуск ноды

Все команды гайда выполняйте на сервере, куда ставите ноду (подключитесь к нему по SSH). Файлы редактируйте в `nano`, например `nano .env`: сохранить — Ctrl+O и Enter, выйти — Ctrl+X.

```bash
git clone https://github.com/AntNodes/doli-node-guide.git && cd doli-node-guide/node
cp .env.example .env && chmod 600 .env       # при необходимости поправьте NODE_DIR и KEYS_DIR
sudo mkdir -p /srv/doli/node /srv/doli/keys
sudo chown -R 1000:1000 /srv/doli && sudo chmod 700 /srv/doli/keys
docker compose build doli                    # 15–50 минут (зависит от числа ядер); коммит тега сверяется с .env
docker compose up -d
docker logs -f --tail 50 doli-node
docker compose run --rm cli chain            # высота блока; сравните с эксплорером
```

В `.env` для первой установки обычно ничего менять не нужно. Поля:

| Поле | Что это |
|---|---|
| `NODE_DIR`, `KEYS_DIR` | Папки на сервере для данных ноды и для ключа |
| `DOLI_VERSION`, `DOLI_COMMIT` | Версия ноды и её проверочный код. Меняются только при обновлении |
| `DOLI_CPUS` | Сколько ядер дать ноде. Не больше числа ядер сервера (`nproc`) |
| `PRODUCER_ARGS` | Пусто, пока вы не зарегистрировались (см. раздел 5) |

`1000:1000` в `chown` — номер пользователя, под которым нода работает внутри контейнера.

**Почему мы собираем ноду сами.** Готовая программа из релиза DOLI использует ADX. Если его нет у процессора, программа вылетает с ошибкой `SIGILL` ([issue #230](https://github.com/doli-network/doli/issues/230), открыт на 08.11.2026). Когда ноду собираете вы, сборка подстраивается под ваш процессор ([blst](https://github.com/supranational/blst)). Поэтому собирайте на том же сервере, где будет работать нода, и не переносите готовый образ на другой сервер.

Snap sync занимает 1–2 минуты. Команда `chain` печатает строку `Best Height` — высоту блока. Она должна совпасть (с разницей в несколько блоков) с высотой на [эксплорере](https://explorer.doli.network/network.html). Команда `docker ps` в столбце STATUS должна показать `Up … (healthy)`.

**Проверьте ветку.** 5 ноября 2026 сеть раскололась на две ветки; верная ветка — у seed-нод команды DOLI. Скрипт берёт недавний блок вашей ноды и сравнивает его хеш с хешем того же блока у seed-ноды (блок 882251, на котором ветки разошлись, у свежей ноды отсутствует: snap sync не загружает историю):

```bash
bash check-branch.sh
```

Пример ответа: `OK: блок 884980 одинаковый у вас и у seed (223cd559). Вы на верной ветке.` Seed — сервер самой команды DOLI, с него берётся эталон. `РАЗНЫЕ ХЕШИ` — вы на неверной ветке: не регистрируйтесь и следуйте шагам команды DOLI в её Discord (анонс «DOLI mainnet: check your branch and update to v6.46.1»). Если вы уже producer, то же самое: не продолжайте работать на неверной ветке.

## 4. Кошелёк и ключ producer'а

**Как читать чужие инструкции.** В форме faucet и на сайте DOLI команды начинаются с `doli` (например, `doli sign …`). У нас `doli` живёт внутри контейнера, поэтому вместо `doli` пишите:

```bash
docker compose run --rm cli -w /keys/producer.json
```

Здесь `-w` — путь к файлу кошелька (внутри контейнера). Пример: `doli balance` у нас выглядит как `docker compose run --rm cli -w /keys/producer.json balance`. Команды всегда выполняйте из папки `node`.

Кошелёк создаёте **сами**, на сервере в своём терминале. Не поручайте это скриптам или ассистентам: они увидят seed-фразу.

```bash
docker compose run --rm cli -w /keys/producer.json new
```

1. Команда покажет **24 слова**. Сразу сохраните их в менеджер паролей.
2. Рядом с ключом появится `producer.seed.txt` с той же фразой. После сохранения фразы удалите его: `sudo rm /srv/doli/keys/producer.seed.txt`.
3. Посмотрите публичные данные. Адрес понадобится для faucet:
   ```bash
   docker compose run --rm cli -w /keys/producer.json info
   ```
4. **Скопируйте файл `producer.json`**, например на зашифрованный диск. Кошелёк, созданный командой `new`, восстанавливается из 24 слов, но копия файла надёжнее. Если ключ создан другим способом (не этим гайдом), фраза может не восстановить BLS-ключ ([bls-key-recovery.md](https://github.com/doli-network/doli/blob/main/docs/bls-key-recovery.md)).

## 5. Faucet и регистрация

1. В Discord DOLI в канале сервера (в личных сообщениях не работает) отправьте например в канале #doli-airdrop сообщение `/faucet`. Бот ответит личной ссылкой, она действует 10 минут.
2. Откройте ссылку и введите адрес из `info`. Форма попросит подписать вызов и вставить вывод `chain`. Выполните две команды, подставив текст вызова из формы:
   ```bash
   docker compose run --rm cli -w /keys/producer.json sign "ТЕКСТ_ИЗ_ФОРМЫ"
   ```
   ```bash
   docker compose run --rm cli chain
   ```
3. Вставьте результаты в форму и отправьте. Заявку одобряет человек. Faucet выдаёт 10,000001 DOLI (bond + комиссия регистрации): один раз на человека; адрес должен быть новым и пустым. Сообщения о выплате бот не присылает, срок одобрения нигде не указан: проверяйте баланс раз в несколько часов. Если личная ссылка больше минуты пишет «Preparing your claim», отправьте `/faucet` заново ([faucet-bot.md](https://github.com/doli-network/doli/blob/main/docs/faucet-bot.md#how-to-claim)).
4. Проверьте баланс:
   ```bash
   docker compose run --rm cli -w /keys/producer.json balance
   ```
5. Зарегистрируйтесь с одним bond'ом. Досрочный выход из него стоит штрафа (см. [раздел 1](#1-что-такое-doli-producer)):
   ```bash
   docker compose run --rm cli -w /keys/producer.json producer register --bonds 1
   ```
6. Включите режим producer. Откройте `.env` (`nano .env`), впишите `PRODUCER_ARGS=--producer --producer-key /keys/producer.json`, сохраните и выполните `docker compose up -d`.
7. Через эпоху (около часа) проверьте:
   ```bash
   docker compose run --rm cli -w /keys/producer.json producer status       # active
   docker logs doli-node 2>&1 | grep -E "ATTEST_EGRESS|slash" | tail      # пусто
   ```
   Статус должен быть `active`. Если во второй команде появились строки `ATTEST_EGRESS`, нода не смогла подписать подтверждение BLS-ключом: проверьте раздел 4 (шаг 4) и [bls-key-recovery.md](https://github.com/doli-network/doli/blob/main/docs/bls-key-recovery.md).
8. Необязательно: имя вместо длинного ключа в списке producer'ов. Откройте [doli.network/register.html](https://doli.network/register.html), выберите mainnet и введите имя (3–32 знака: `a–z`, `0–9`, `_`, `-`, `.`). Страница покажет команду подписи. Выполните её так:
   ```bash
   docker compose run --rm cli -w /keys/producer.json sign "ТЕКСТ_СО_СТРАНИЦЫ"
   ```
   Вставьте подпись обратно на страницу. Ключ странице не нужен, подпись делается у вас. Имя закрепляется сразу. Сменить его можно, но после смены следующая возможна только через 30 дней ([правила страницы](https://doli.network/register.html)). Нода к этому моменту должна быть в списке активных producer'ов.

## 6. Проверка раз в день

Отдельный мониторинг не обязателен. Пока нода запущена с `restart: unless-stopped`, Docker сам поднимет её после сбоя. Но она может молча отстать от сети или оказаться не на той ветке: тогда вы не получите награду за эпоху (нужно быть онлайн не меньше 90% часа, [rewards.md](https://github.com/doli-network/doli/blob/main/docs/rewards.md#5-epoch-reward-pool-math)) и не узнаете об этом. Раз в день выполните две команды:

```bash
bash check-branch.sh
docker compose run --rm cli -w /keys/producer.json producer status
```

Ждите `OK` и статус `active`. Автоматические уведомления в чат (cron, тревоги по отставанию, памяти и пирам) описаны отдельно: [monitoring/README.md](monitoring/README.md).

## 7. Обновление

Автообновление выключено (`--no-auto-update`). Обновляйте вручную, когда мониторинг сообщит о новом релизе. Если вы ставили ноду по этому гайду сегодня, у вас уже v6.46.1 и обновлять ничего не нужно. Перед обновлением прочитайте заметки релиза и анонс команды в Discord: бывают шаги, которые нужны одновременно с обновлением (так было при расколе 05.11.2026).

```bash
git ls-remote https://github.com/doli-network/doli refs/tags/vX.Y.Z   # вместо vX.Y.Z новая версия; коммит — первые 40 знаков ответа
# в .env поменять DOLI_VERSION и DOLI_COMMIT
docker compose build doli          # нода в это время работает
docker compose up -d               # простой несколько секунд
docker images local/doli                   # список образов; старую версию видно по столбцу TAG
docker image rm local/doli:<старая версия>
```

## 8. Правила и грабли

- **Один `producer.json` — одна работающая нода.** Если два экземпляра с одним ключом подпишут блоки в одном слоте, это двойное производство: slashing, сгорает 100% bond ([slashing](https://github.com/doli-network/doli/blob/main/docs/becoming_a_producer.md#8-slashing)). При переезде сначала полностью остановите старую ноду (`docker compose down`), и только потом запускайте новую. Не запускайте вторую ноду с копией ключа, даже временно и «для проверки бэкапа».
- **Выход из bond.** Вернуть bond можно, но досрочно — со штрафом (таблица в [разделе 1](#1-что-такое-doli-producer)).
- **`node_key`** (PeerId) нода пишет **в родительскую папку** `--data-dir`. Поэтому в контейнер монтируется `/node`, а данные лежат в `/node/data`. Если смонтировать только папку данных, при старте будет ошибка `Failed to write keypair: Permission denied`.
- **RPC** по умолчанию слушает `127.0.0.1` внутри контейнера. Чтобы работали healthcheck и CLI, нужен `--rpc-bind 0.0.0.0`. На сервере порт опубликован только на `127.0.0.1`.
- **Лимиты.** `mem_limit: 4g` и `cpus` (`DOLI_CPUS`, по умолчанию 4) защищают остальные сервисы на сервере, если нода начнёт разрастаться (так было при gossip flood в 6.43.0).

## 9. Полезные команды

Все команды выполняйте из папки `node`. Справка по любой: добавьте `--help`.

Статус producer'а:

```bash
docker compose run --rm cli -w /keys/producer.json producer status
```

Каждый bond и когда падает штраф:

```bash
docker compose run --rm cli -w /keys/producer.json producer vesting-summary
```

Добавить bond (всего от 1 до 3000):

```bash
docker compose run --rm cli -w /keys/producer.json producer add-bond --count 1
```

Посчитать вывод bond'ов, ничего не отправляя:

```bash
docker compose run --rm cli -w /keys/producer.json producer simulate-withdrawal --count 1
```

Логи ноды:

```bash
docker logs --tail 50 doli-node
```

Остановить ноду:

```bash
docker compose down
```

Остановка ноды **не возвращает bond**: producer остаётся в списке, но не подтверждает блоки и теряет награду. Запустить ноду снова можно командой `docker compose up -d`, данные сохранятся. Вернуть деньги можно командой `producer exit --force`, но со штрафом по таблице из [раздела 1](#1-что-такое-doli-producer). Без `--force` команда только показывает, что произойдёт. Перед выходом выполните `simulate-withdrawal`: он тоже ничего не отправляет.

Удалить ноду полностью: `docker compose down`, затем `sudo rm -rf /srv/doli/node`. Папку `/srv/doli/keys` и фразу из 24 слов не удаляйте, пока не вывели bond и не убедились, что кошелёк больше не нужен.

## Ссылки

- Сайт: https://doli.network
- Эксплорер: https://explorer.doli.network/network.html
- Код: https://github.com/doli-network/doli
- Документация producer'а: https://github.com/doli-network/doli/blob/main/docs/becoming_a_producer.md
- Faucet: https://github.com/doli-network/doli/blob/main/docs/faucet-bot.md
- Discord: https://discord.gg/aTgHyDY9QY

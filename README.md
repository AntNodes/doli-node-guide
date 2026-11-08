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

## 1. Что такое DOLI-producer

DOLI — L1 на Rust с Proof of Time (VDF) и моделью UTXO. Блок выходит раз в 10 секунд, эпоха длится 360 блоков (около часа) ([параметры](https://github.com/doli-network/doli/blob/main/README.md#protocol-parameters)).

- **Регистрация producer'а.** Нужен bond: 10 DOLI за один bond ([becoming_a_producer.md](https://github.com/doli-network/doli/blob/main/docs/becoming_a_producer.md#22-economic)). Первые 10 DOLI можно получить бесплатно через faucet в Discord ([faucet-bot.md](https://github.com/doli-network/doli/blob/main/docs/faucet-bot.md#what-you-get)).
- **Bond заморожен на 4 года.** Выход в 1-й год сжигает 75% bond'а, во 2-й — 50%, в 3-й — 25%, после 3 лет — 0%. Деньги приходят через 7 дней после заявки ([vesting](https://github.com/doli-network/doli/blob/main/docs/becoming_a_producer.md#66-vesting-schedule-and-early-withdrawal-penalties)).
- **Награда.** Каждая эпоха даёт до 360 DOLI (1 DOLI за блок). Они делятся пропорционально bond'ам между producer'ами, у которых attestation за эпоху не ниже 90% ([rewards.md](https://github.com/doli-network/doli/blob/main/docs/rewards.md#5-epoch-reward-pool-math)). Производить блоки для этого не нужно: достаточно, чтобы нода была онлайн и подписывала attestation.
- **Производство блоков.** Если producer'ов больше 50, блоки производят первые 50 по старшинству регистрации ([round-robin](https://github.com/doli-network/doli/blob/main/docs/becoming_a_producer.md#41-epoch-frozen-round-robin)).
- **Сколько это приносит.** Доход одного bond'а в сутки = 360 DOLI × 24 эпохи ÷ число bond'ов в сети. Число bond'ов смотрите на [эксплорере](https://explorer.doli.network/network.html) в день, когда считаете: оно растёт. Бирж нет: DOLI за USDT продаёт только команда по своему курсу ([buy_doli.md](https://github.com/doli-network/doli/blob/main/docs/buy_doli.md)). Поэтому участие похоже на дешёвую лотерею. Ставьте ноду изолированно, чтобы она не мешала другим сервисам на сервере.

## 2. Что нужно

- **Сервер.** Linux x86_64 с Docker и Compose v2. Минимум для producer'а: **4 CPU, 8 GB RAM, 100 GB SSD**; рекомендуется 8 CPU, 16 GB, 500 GB NVMe ([требования](https://github.com/doli-network/doli/blob/main/docs/becoming_a_producer.md#21-hardware)). Если ядер меньше 4, контейнер с `cpus: 4` не стартует: уменьшите `DOLI_CPUS` в `.env`.
- **Аккаунт Discord старше 1 года** на сервере [DOLI](https://discord.gg/aTgHyDY9QY). Faucet выдаёт монеты только тем, кто состоит на сервере **не меньше 7 дней** ([правила faucet](https://github.com/doli-network/doli/blob/main/docs/faucet-bot.md#eligibility-rules)), поэтому вступите заранее.
- **CPU с флагом ADX.** Проверка: `grep -c -w adx /proc/cpuinfo`. Больше 0 — подходит. 0 — тоже подходит именно этому гайду, потому что он собирает ноду на вашем сервере (объяснение в [разделе 3](#3-сборка-и-запуск-ноды)); не подходит готовый бинарник из `install.sh`.
- **Менеджер паролей** для seed-фразы.

## 3. Сборка и запуск ноды

```bash
git clone https://github.com/AntNodes/doli-node-guide.git && cd doli-node-guide/node
cp .env.example .env && chmod 600 .env       # при необходимости поправьте NODE_DIR и KEYS_DIR
sudo mkdir -p /srv/doli/node /srv/doli/keys
sudo chown -R 1000:1000 /srv/doli && sudo chmod 700 /srv/doli/keys
docker compose build doli                    # около 15 минут; коммит тега сверяется с .env
docker compose up -d
docker logs -f --tail 50 doli-node
docker compose run --rm cli chain            # высота блока; сравните с эксплорером
```

Почему сборка из исходников:
- Готовые бинарники релиза падают с `SIGILL` (illegal instruction) на процессорах без ADX, например на Xeon E5 v3 ([issue #230](https://github.com/doli-network/doli/issues/230), открыт на 08.11.2026). Падает уже `doli init`. Библиотека `blst` при сборке смотрит на процессор машины, где идёт сборка ([описание blst](https://github.com/supranational/blst)). Поэтому собирайте на том же сервере, где будет работать нода. Образ, собранный на одном процессоре, на другом без ADX может упасть.
- Готовые бинарники требуют glibc 2.39 или новее (Ubuntu 24.04).
- Официальный `docker/Dockerfile` собирает только `doli-node`, без CLI.

Snap sync занимает 1–2 минуты. Нода готова, когда её высота совпадает с эксплорером, а `docker ps` показывает `healthy`.

**Проверьте ветку.** 5 ноября 2026 сеть раскололась на две ветки; верная ветка — у seed-нод команды DOLI. Скрипт берёт недавний блок вашей ноды и сравнивает его хеш с хешем того же блока у seed-ноды (блок 882251, на котором ветки разошлись, у свежей ноды отсутствует: snap sync не загружает историю):

```bash
bash check-branch.sh
```

Ответ `OK` — вы на верной ветке. `РАЗНЫЕ ХЕШИ` — вы на неверной: не регистрируйтесь и следуйте шагам команды DOLI в её Discord (анонс «DOLI mainnet: check your branch and update to v6.46.1»).

## 4. Кошелёк и ключ producer'а

Кошелёк создаёте **сами**, в своём терминале. Не поручайте это скриптам или ассистентам: они увидят seed-фразу.

```bash
docker compose run --rm cli -w /keys/producer.json new
```

1. Команда покажет **24 слова**. Сразу сохраните их в менеджер паролей.
2. Рядом с ключом появится `producer.seed.txt` с той же фразой. После сохранения фразы удалите его: `sudo rm /srv/doli/keys/producer.seed.txt`.
3. Посмотрите публичные данные. Адрес понадобится для faucet:
   ```bash
   docker compose run --rm cli -w /keys/producer.json info
   ```
4. **Сделайте бэкап `producer.json`**, например на зашифрованный диск. У кошельков версии 3 оба ключа, основной и BLS, выводятся из фразы. Но если ключ создан другим способом, фраза BLS-ключ не восстановит (см. `docs/bls-key-recovery.md` в репозитории DOLI). Поэтому храните и фразу, и сам файл.

## 5. Faucet и регистрация

Порядок из [faucet-bot.md](https://github.com/doli-network/doli/blob/main/docs/faucet-bot.md#how-to-claim). Нода к этому моменту должна быть синхронна, кошелёк создан.

1. В Discord DOLI отправьте `/faucet`. Бот ответит личной ссылкой, её видите только вы.
2. Откройте ссылку и нажмите кнопку. Откроется форма.
3. Вставьте адрес из `info` и подтвердите, что адрес ваш (форма подскажет как).
4. Ждите: каждую заявку одобряет человек. Faucet выдаёт 10,000001 DOLI (bond + комиссия регистрации), один раз на человека, на новый пустой адрес. Сообщения о выплате бот не присылает.
5. Проверьте баланс:
   ```bash
   docker compose run --rm cli -w /keys/producer.json balance
   ```
6. Зарегистрируйтесь с одним bond'ом. Bond замораживается на 4 года (см. [раздел 1](#1-что-такое-doli-producer)):
   ```bash
   docker compose run --rm cli -w /keys/producer.json producer register --bonds 1
   ```
7. Включите режим producer. В `.env` укажите `PRODUCER_ARGS=--producer --producer-key /keys/producer.json`, затем выполните `docker compose up -d`.
8. Через эпоху (около часа) проверьте:
   ```bash
   docker compose run --rm cli -w /keys/producer.json producer status       # active
   docker logs doli-node 2>&1 | grep -E "ATTEST_EGRESS|slash" | tail      # пусто
   ```
9. Необязательно: имя вместо длинного ключа в списке producer'ов. Откройте [doli.network/register.html](https://doli.network/register.html), выберите сеть mainnet, введите имя (3–32 знака: `a–z`, `0–9`, `_`, `-`, `.`) и скопируйте команду подписи, которую покажет страница. Выполните её на своём сервере через контейнер: вместо `doli` подставьте `docker compose run --rm cli`, а путь кошелька — `/keys/producer.json`. Вставьте подпись обратно на страницу. Ключ странице не нужен, подпись делается у вас. Имя закрепляется сразу и навсегда ([правила страницы](https://doli.network/register.html)). Сменить его можно, но после этого 30 дней нельзя менять снова. Удаление регистрации закрывает регистрацию ключа на 30 дней. Нода к этому моменту должна быть в списке активных producer'ов.

## 6. Проверка раз в день

Отдельный мониторинг не обязателен. Пока нода запущена с `restart: unless-stopped`, Docker сам поднимет её после сбоя. Но она может молча отстать от сети или оказаться не на той ветке: тогда вы не получите награду за эпоху и не узнаете об этом. Раз в день выполните две команды:

```bash
bash check-branch.sh
docker compose run --rm cli -w /keys/producer.json producer status
```

Ждите `OK` и статус `active`. Автоматические уведомления в чат (cron, тревоги по отставанию, памяти и пирам) описаны отдельно: [monitoring/README.md](monitoring/README.md).

## 7. Обновление

Автообновление выключено (`--no-auto-update`). Обновляйте вручную, когда мониторинг сообщит о новом релизе. Перед обновлением прочитайте заметки релиза и анонс команды в Discord: бывают шаги, которые нужны одновременно с обновлением (так было при расколе 05.11.2026).

```bash
git ls-remote https://github.com/doli-network/doli refs/tags/vX.Y.Z   # коммит тега
# в .env поменять DOLI_VERSION и DOLI_COMMIT
docker compose build doli          # нода в это время работает
docker compose up -d               # простой несколько секунд
docker image rm local/doli:<старая версия>
```

## 8. Правила и грабли

- **Один `producer.json` — одна работающая нода.** Если два экземпляра с одним ключом подпишут блоки в одном слоте, это двойное производство: slashing, сгорает 100% bond ([slashing](https://github.com/doli-network/doli/blob/main/docs/becoming_a_producer.md#8-slashing)). При переезде сначала полностью остановите старую ноду (`docker compose down`), и только потом запускайте новую. Бэкап ключа нодой не запускайте.
- **Выход из bond.** Vesting длится 4 года, штраф за ранний выход — до 75% (таблица в [разделе 1](#1-что-такое-doli-producer)). Сутки — это vesting в testnet, не в mainnet.
- **`node_key`** (PeerId) нода пишет **в родительскую папку** `--data-dir`. Поэтому в контейнер монтируется `/node`, а данные лежат в `/node/data`. Если смонтировать только папку данных, при старте будет ошибка `Failed to write keypair: Permission denied`.
- **RPC** по умолчанию слушает `127.0.0.1` внутри контейнера. Чтобы работали healthcheck и CLI, нужен `--rpc-bind 0.0.0.0`. На сервере порт опубликован только на `127.0.0.1`.
- **Лимиты.** `mem_limit: 4g` и `cpus` (`DOLI_CPUS`, по умолчанию 4) защищают остальные сервисы на сервере, если нода начнёт разрастаться (так было при gossip flood в 6.43.0).

## 9. Полезные команды

Все команды — из папки `node`, кошелёк `-w /keys/producer.json`. Справка по любой: добавьте `--help`.

| Задача | Команда |
|---|---|
| Статус producer'а | `docker compose run --rm cli -w /keys/producer.json producer status` |
| Каждый bond и когда падает штраф | `... producer bonds` и `... producer vesting-summary` |
| Добавить bond (от 1 до 3000 всего) | `... producer add-bond --count 1` |
| Посчитать вывод bond'ов без отправки | `... producer simulate-withdrawal --count 1` |
| Логи ноды | `docker logs --tail 50 doli-node` |
| Остановить ноду | `docker compose down` |

Остановка ноды **не возвращает bond**: producer остаётся в списке, но не подтверждает блоки и теряет награду. Вернуть деньги можно командой `producer exit --force`, но со штрафом: до 1 года 75%, 1–2 года 50%, 2–3 года 25%, от 3 лет 0% ([Vesting](https://github.com/doli-network/doli/blob/main/docs/becoming_a_producer.md#66-vesting-schedule-and-early-withdrawal-penalties)). Сначала выполните `simulate-withdrawal`: он ничего не отправляет.

Удалить ноду полностью: `docker compose down`, затем `sudo rm -rf /srv/doli/node`. Папку `/srv/doli/keys` и фразу из 24 слов не удаляйте, пока не вывели bond и не убедились, что кошелёк больше не нужен.

## Ссылки

- Сайт: https://doli.network
- Эксплорер: https://explorer.doli.network/network.html
- Код: https://github.com/doli-network/doli
- Документация producer'а: https://github.com/doli-network/doli/blob/main/docs/becoming_a_producer.md
- Faucet: https://github.com/doli-network/doli/blob/main/docs/faucet-bot.md
- Discord: https://discord.gg/aTgHyDY9QY

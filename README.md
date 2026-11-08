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
6. [Мониторинг](#6-мониторинг)
7. [Обновление](#7-обновление)
8. [Правила и грабли](#8-правила-и-грабли)

## 1. Что такое DOLI-producer

DOLI — L1 на Rust с Proof of Time (VDF) и моделью UTXO. Блок выходит раз в 10 секунд, эпоха длится 360 блоков (около часа) ([параметры](https://github.com/doli-network/doli/blob/main/README.md#protocol-parameters)).

- **Регистрация producer'а.** Нужен bond: 10 DOLI за один bond ([becoming_a_producer.md](https://github.com/doli-network/doli/blob/main/docs/becoming_a_producer.md#22-economic)). Первые 10 DOLI можно получить бесплатно через faucet в Discord ([faucet-bot.md](https://github.com/doli-network/doli/blob/main/docs/faucet-bot.md#what-you-get)).
- **Bond заморожен на 4 года.** Выход в 1-й год сжигает 75% bond'а, во 2-й — 50%, в 3-й — 25%, после 3 лет — 0%. Деньги приходят через 7 дней после заявки ([vesting](https://github.com/doli-network/doli/blob/main/docs/becoming_a_producer.md#66-vesting-schedule-and-early-withdrawal-penalties)).
- **Награда.** Каждая эпоха даёт до 360 DOLI (1 DOLI за блок). Они делятся пропорционально bond'ам между producer'ами, у которых attestation за эпоху не ниже 90% ([rewards.md](https://github.com/doli-network/doli/blob/main/docs/rewards.md#5-epoch-reward-pool-math)). Производить блоки для этого не нужно: достаточно, чтобы нода была онлайн и подписывала attestation.
- **Производство блоков.** Если producer'ов больше 50, блоки производят первые 50 по старшинству регистрации ([round-robin](https://github.com/doli-network/doli/blob/main/docs/becoming_a_producer.md#41-epoch-frozen-round-robin)).
- **Ориентир на октябрь 2026.** Около 100 активных producer'ов и 36 700 bond'ов ([эксплорер](https://explorer.doli.network/network.html)). Доход одного bond'а: 360 DOLI ÷ 36 700 bond'ов ≈ 0,0098 DOLI за эпоху; × 24 эпохи ≈ 0,24 DOLI в сутки. Бирж нет: DOLI за USDT продаёт только команда по своему курсу ([buy_doli.md](https://github.com/doli-network/doli/blob/main/docs/buy_doli.md)). Поэтому участие похоже на дешёвую лотерею. Ставьте ноду изолированно, чтобы она не мешала другим сервисам на сервере.

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

## 6. Мониторинг

`monitoring/doli-status.py` печатает состояние ноды текстом. Подключите его к cron или к боту, который пересылает вывод в чат.

```bash
export DOLI_ADDRESS=doli1…  DOLI_PUBKEY=…  DOLI_NODE_DIR=/srv/doli/node   # из `info`
python3 monitoring/doli-status.py daily   # сводка, раз в день
python3 monitoring/doli-status.py watch   # раз в 10 минут; пустой вывод = всё в порядке
```

Что проверяет:
- контейнер и healthcheck;
- память: тревога, если занято больше 85% лимита (признак gossip flood);
- RPC;
- отставание от сети: тревога, если больше 30 блоков;
- пиров: тревога, если меньше 3;
- статус producer'а и пропуски attestation: тревога, если пропущено больше 6 минут за эпоху (ниже порога 90%);
- перезапуски контейнера;
- выход нового релиза на GitHub.

`watch` пишет только когда проблема появилась, изменилась или ушла.

```
*/10 * * * *  DOLI_ADDRESS=… DOLI_PUBKEY=… python3 /path/doli-status.py watch | your-notify
5 9 * * *     DOLI_ADDRESS=… DOLI_PUBKEY=… python3 /path/doli-status.py daily | your-notify
```

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

## Ссылки

- Сайт: https://doli.network
- Эксплорер: https://explorer.doli.network/network.html
- Код: https://github.com/doli-network/doli
- Документация producer'а: https://github.com/doli-network/doli/blob/main/docs/becoming_a_producer.md
- Faucet: https://github.com/doli-network/doli/blob/main/docs/faucet-bot.md
- Discord: https://discord.gg/aTgHyDY9QY

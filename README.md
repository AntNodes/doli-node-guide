# DOLI producer-нода в Docker

[![DOLI](https://img.shields.io/badge/DOLI-v6.43.3-6c5ce7)](https://github.com/doli-network/doli/releases)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](node/docker-compose.yml)
[![Язык](https://img.shields.io/badge/язык-русский-lightgrey)](#)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Пошаговый гайд: как поставить producer'а сети [DOLI](https://doli.network) (mainnet) на свой Linux-сервер. Нода собирается из исходников и работает в Docker. Есть скрипт мониторинга, который пишет короткие сообщения в чат.

Проверено на v6.43.3, октябрь 2026.

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

DOLI — L1 на Rust с Proof of Time (VDF) и моделью UTXO. Блок выходит раз в 10 секунд, эпоха длится 360 блоков (около часа).

- **Регистрация producer'а.** Нужен bond: 10 DOLI за один bond. Первые 10 DOLI можно получить бесплатно через faucet в Discord.
- **Награда.** Награда эпохи, около 360 DOLI, делится пропорционально bond'ам между всеми producer'ами, у которых attestation за эпоху не ниже 90%. Производить блоки для этого не нужно: достаточно, чтобы нода была онлайн и подписывала attestation.
- **Производство блоков.** Блоки производят только первые 50 producer'ов по старшинству регистрации.
- **Ориентир на октябрь 2026.** Около 100 активных producer'ов и 36 700 bond'ов. Один bond приносит примерно 0,01 DOLI за эпоху, это около 0,23 DOLI в сутки. Рынка у монеты пока нет, поэтому участие похоже на дешёвую лотерею. Ставьте ноду изолированно, чтобы она не мешала другим сервисам на сервере.

Актуальные цифры смотрите в [эксплорере](https://explorer.doli.network/network.html).

## 2. Что нужно

- **Сервер.** Linux x86_64 с Docker и Compose v2. Ноде хватает 4 GB RAM и 4 CPU. После snap sync данные занимают десятки MB.
- **Аккаунт Discord** на сервере [DOLI](https://discord.gg/aTgHyDY9QY). Faucet выдаёт монеты только тем, кто состоит на сервере **не меньше 7 дней**, поэтому вступите заранее.
- **Менеджер паролей** для seed-фразы.

## 3. Сборка и запуск ноды

```bash
git clone https://github.com/AntNodes/doli-node-guide.git && cd doli-node-guide/node
cp .env.example .env && chmod 600 .env       # при необходимости поправьте NODE_DIR и KEYS_DIR
sudo mkdir -p /srv/doli/node /srv/doli/keys
sudo chown -R 1000:1000 /srv/doli && sudo chmod 700 /srv/doli/keys
docker compose build doli                    # около 10 минут; коммит тега сверяется с .env
docker compose up -d
docker logs -f --tail 50 doli-node
docker compose run --rm cli chain            # высота блока; сравните с эксплорером
```

Почему сборка из исходников: официальные бинарники требуют glibc 2.38 или новее, а официальный `docker/Dockerfile` собирает только `doli-node`, без CLI.

Snap sync занимает пару минут. Нода готова, когда её высота совпадает с эксплорером, а `docker ps` показывает `healthy`.

Порты 30300/tcp и 30301/udp нужны для входящих пиров. Открывать их необязательно: без них нода тоже работает, просто пиров будет меньше. RPC слушает только `127.0.0.1` сервера.

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

1. В Discord DOLI отправьте `/faucet` с адресом из `info`. Faucet выдаёт 10,000001 DOLI: один раз на человека, на новый пустой адрес. Если вы на сервере меньше 7 дней, придёт отказ `guild_join_age`. Повторите через неделю.
2. Проверьте баланс:
   ```bash
   docker compose run --rm cli -w /keys/producer.json balance
   ```
3. Зарегистрируйтесь с одним bond'ом:
   ```bash
   docker compose run --rm cli -w /keys/producer.json producer register --bonds 1
   ```
4. Включите режим producer. В `.env` укажите `PRODUCER_ARGS=--producer --producer-key /keys/producer.json`, затем выполните `docker compose up -d`.
5. Через эпоху (около часа) проверьте:
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

Автообновление выключено (`--no-auto-update`). Обновляйте вручную, когда мониторинг сообщит о новом релизе:

```bash
git ls-remote https://github.com/doli-network/doli refs/tags/vX.Y.Z   # коммит тега
# в .env поменять DOLI_VERSION и DOLI_COMMIT
docker compose build doli          # нода в это время работает
docker compose up -d               # простой несколько секунд
docker image rm local/doli:<старая версия>
```

## 8. Правила и грабли

- **Один `producer.json` — одна работающая нода.** Если два экземпляра с одним ключом подпишут блоки в одном слоте, это двойное производство: slashing, сгорает 100% bond. При переезде сначала полностью остановите старую ноду (`docker compose down`), и только потом запускайте новую. Бэкап ключа нодой не запускайте.
- **Выход из bond.** Vesting bond длится одни сутки: при выходе раньше штраф до 75%. Unbonding занимает 7 дней.
- **`node_key`** (PeerId) нода пишет **в родительскую папку** `--data-dir`. Поэтому в контейнер монтируется `/node`, а данные лежат в `/node/data`. Если смонтировать только папку данных, при старте будет ошибка `Failed to write keypair: Permission denied`.
- **RPC** по умолчанию слушает `127.0.0.1` внутри контейнера. Чтобы работали healthcheck и CLI, нужен `--rpc-bind 0.0.0.0`. На сервере порт опубликован только на `127.0.0.1`.
- **Лимиты.** `mem_limit: 4g` и `cpus: 4` защищают остальные сервисы на сервере, если нода начнёт разрастаться (так было при gossip flood в 6.43.0).

## Ссылки

- Сайт: https://doli.network
- Эксплорер: https://explorer.doli.network/network.html
- Код: https://github.com/doli-network/doli
- Discord: https://discord.gg/aTgHyDY9QY

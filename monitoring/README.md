# Мониторинг DOLI-ноды

Необязательно. Основной гайд — [README.md](../README.md).

`doli-status.py` печатает состояние ноды текстом. Подключите его к cron или к боту, который пересылает вывод в чат.

```bash
export DOLI_ADDRESS=doli1…  DOLI_PUBKEY=…  DOLI_NODE_DIR=/srv/doli/node   # из `info`
python3 doli-status.py daily   # сводка, раз в день
python3 doli-status.py watch   # раз в 10 минут; пустой вывод = всё в порядке
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

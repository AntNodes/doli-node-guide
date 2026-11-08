#!/bin/bash
# Сравнивает хеш недавнего блока вашей ноды с хешем того же блока у seed-ноды DOLI.
# Одинаковые — вы на верной ветке. Запуск: bash check-branch.sh
set -u
LOCAL=${LOCAL_RPC:-http://127.0.0.1:8500}
SEED=${SEED_RPC:-https://explorer.doli.network/api/mainnet/seed1}
call() { curl -s --max-time 15 -H 'Content-Type: application/json' -d "$2" "$1"; }

top=$(call "$LOCAL" '{"jsonrpc":"2.0","method":"getChainInfo","params":{},"id":1}' | grep -oE '"bestHeight":[0-9]+' | cut -d: -f2)
[ -n "$top" ] || { echo "Нода не отвечает на $LOCAL"; exit 2; }
h=$((top - 5))
req="{\"jsonrpc\":\"2.0\",\"method\":\"getBlockByHeight\",\"params\":{\"height\":$h},\"id\":1}"
mine=$(call "$LOCAL" "$req" | grep -oE '"hash":"[0-9a-f]{8}' | cut -d'"' -f4)
seed=$(call "$SEED" "$req" | grep -oE '"hash":"[0-9a-f]{8}' | cut -d'"' -f4)
if [ -z "$mine" ] || [ -z "$seed" ]; then echo "Не удалось получить хеш блока $h (ваш: '${mine}', seed: '${seed}'). Повторите через минуту."; exit 2; fi
if [ "$mine" = "$seed" ]; then
  echo "OK: блок $h одинаковый у вас и у seed ($mine). Вы на верной ветке."
else
  echo "РАЗНЫЕ ХЕШИ на блоке $h: у вас $mine, у seed $seed. Не регистрируйтесь, ждите шагов команды DOLI."
  exit 1
fi

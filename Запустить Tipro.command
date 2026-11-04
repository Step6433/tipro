#!/bin/zsh
cd -- "$(dirname -- "$0")" || exit 1
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
if [[ ! -x backend/.venv/bin/python ]]; then
  echo 'Не найдено окружение Python. Первоначальная установка описана в backend/README.md.'
  read -r '?Нажмите Enter, чтобы закрыть окно…'
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo 'Не найден npm. Установите Node.js и повторите запуск.'
  read -r '?Нажмите Enter, чтобы закрыть окно…'
  exit 1
fi
npm start
launch_exit_code=$?
if (( launch_exit_code != 0 && launch_exit_code != 130 )); then
  read -r '?Нажмите Enter, чтобы закрыть окно…'
fi
exit "$launch_exit_code"

# Развёртывание и CI/CD

## Запуск на новом сервере через Docker Compose

Нужны Docker Engine и Compose v2. Из корня репозитория:

```sh
cp .env.example .env
python3 - <<'PY'
from pathlib import Path
import secrets
p = Path('.env')
s = p.read_text().replace('CHANGE-ME-IN-PRODUCTION-USE-openssl-rand-base64-32', secrets.token_urlsafe(48))
p.write_text(s + '\nSEED_DEMO=true\n')
p.chmod(0o600)
PY
docker compose up -d --build
curl --fail http://127.0.0.1:8000/health
```

Интерфейс: http://localhost:8000. Для прямого доступа по IP задайте
`APP_BIND=0.0.0.0` в `.env` и откройте TCP/8000 в firewall.
Для nginx оставьте привязку к localhost и проксируйте запросы на 127.0.0.1:8000.
`SEED_DEMO=true` создаёт синтетические данные и известные демо-аккаунты.
После первого запуска установите `SEED_DEMO=false`: сид обновляет существующие
демо-записи, поэтому его не следует повторять при каждой выкатке.
База хранится в Docker volume `sqlite-data`; `docker compose down -v` удаляет её.
Не используйте демонстрационные пароли для реальных данных. Без HTTPS трафик
не шифруется. Отправка писем и внешние интеграции в этой версии не настроены.
Dockerfile сохраняет структуру backend/frontend/content, необходимую для
раздачи интерфейса, таксономии и генератора данных. Docker-путь не был проверен
на текущем VPS из-за ограниченного диска; ранее VPS-выкатка использовала systemd.

## Пример развёртывания на Linux через systemd

Приложение: `/opt/razryad-final6/current`, база:
`/var/lib/razryad-final6/razryad.db`, секреты: `/opt/razryad-final6/app.env`.
Python 3.12, `python3.12-venv`, nginx, curl и flock должны быть установлены.
Сервис работает под системным пользователем `razryad-final6` и слушает
localhost:18006, nginx принимает публичный HTTP на порту 80.
Пример unit: [razryad-final6.service](razryad-final6.service).
Пример nginx: [nginx.conf](nginx.conf).

Для начальной установки создайте системного пользователя `razryad-final6`,
каталоги `/opt/razryad-final6/releases` и `/var/lib/razryad-final6`, передайте
backend/, frontend/dist/ и content/ в каталог релиза и создайте в нём venv.
Установите `backend/requirements.txt`; создайте root-only файл `app.env`:

```dotenv
DATABASE_URL=sqlite:////var/lib/razryad-final6/razryad.db
DEV_MODE=false
LLM_ENABLED=false
JWT_SECRET=<случайный секрет, например secrets.token_urlsafe(48)>
```

Из backend/ загрузите окружение (`set -a; . /opt/razryad-final6/app.env; set +a`),
выполните `../venv/bin/alembic upgrade head`, при необходимости один раз
`../venv/bin/python seed/seed.py`. Пользователь сервиса должен владеть каталогом
базы. Создайте symlink `current` на релиз, установите unit и nginx-конфигурацию,
проверьте `nginx -t`, затем включите сервис и перезагрузите конфигурацию nginx.
Файлы конфигурации, секреты, ключи и текущая база в Git не хранятся.

## GitHub Actions

Push и PR в `master` запускают backend-тесты, frontend-регрессии, production
сборку и миграции на пустой SQLite с `alembic check`. Job `test-build` обязателен
для защищённого master. Проверенный артефакт сохраняется на 7 дней.
`workflow_dispatch` позволяет запустить проверки вручную.

Автоматическая доставка на прежний VPS отключена при его выводе из эксплуатации
11 октября 2026 года. Deploy job удалён; SSH-ключ и секреты прежнего VPS отозваны.
Автоматическая доставка на Windows пока не настроена. Push не обновляет
Windows-приложение. Новый сервер нужно подключать отдельно после проверки
прав доступа, сохранения базы и безопасной схемы обновления.

`ci-deploy.sh` сохранён как пример ограниченного Linux deploy helper; он не
установлен на выведенном из эксплуатации VPS и не запускается текущим CI.
Не устанавливайте его автоматически и не восстанавливайте старые deploy secrets
для выключенного сервера. Для нового сервера требуется отдельная конфигурация.

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
на текущем VPS из-за ограниченного диска; текущая выкатка использует systemd.

## Текущий systemd-сервер

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

Push в `master`: 67 текущих backend-тестов, сборка TypeScript/React, миграции
на пустой SQLite и `alembic check`. Только после успешного job `test-build`
готовый артефакт передаётся на сервер, где выполняется выкатка.
PR в master запускает проверки без выкатки. `workflow_dispatch` позволяет
запустить проверки вручную; выкатка разрешена только для master.
Production job использует GitHub Environment `production` и секреты:

- `DEPLOY_HOST`: IP/host сервера.
- `DEPLOY_SSH_KEY`: отдельный приватный Ed25519-ключ CI.
- `DEPLOY_KNOWN_HOSTS`: заранее проверенный SSH host key сервера.

CI-ключ в root authorized_keys имеет `restrict` и forced command
`/usr/local/sbin/razryad-ci-deploy`. Он не даёт обычный shell, forwarding или PTY.
Установка выполняется владельцем сервера: скопируйте `ci-deploy.sh` в этот путь,
с правами root:root 0755 и добавьте ключ строкой:

```text
restrict,command="/usr/local/sbin/razryad-ci-deploy" ssh-ed25519 <public-key> razryad-github-actions
```

В CI используются только файлы протестированного артефакта. Сценарий сериализует
выкатки через flock, проверяет пути архива и ограничивает размер 30 MiB.
Установка Python-зависимостей и миграции выполняются без root от пользователя
приложения. Перед миграциями сервис кратковременно останавливается и делается
SQLite backup. Затем атомарно переключается symlink и проверяются health и HTML.
При ошибке после остановки возвращаются предыдущий релиз и копия базы.
Резервные копии и старые релизы автоматически не удаляются: следите за диском.
Один SHA выкатывается один раз; повторный запуск того же SHA остановится для
ручной проверки предыдущей попытки. Секреты/JWT и текущие пользовательские
данные сохраняются, демо-сид при выкатке не запускается.

Изменения deploy/ci-deploy.sh не обновляют root helper автоматически: владелец
сервера должен проверить изменения и установить новую версию отдельно.
CI-ключ позволяет публиковать приложение: ограничение shell не защищает от
намеренно вредоносного кода приложения. Доступ к master доверяйте разработчикам.
Job проверяет реальный HTTP и API, но не интерактивную работу UI в браузере.

# РАЗРЯД

Платформа обратного подбора ИТ-специалистов с подтверждённым грейдом.
FastAPI + SQLAlchemy + Alembic, SQLite, React 18 + TypeScript + Vite.
Кандидат заполняет профиль и проходит адаптивный тест; работодатель создаёт
потребность, получает подборку и отправляет приглашения с вилкой зарплаты.

## Быстрый запуск

Нужны Python 3.12 и make. Готовый frontend включён; для пересборки нужен Node.js 20.

```sh
make demo
```

Откройте http://localhost:8000. Для пересборки интерфейса:

```sh
cd frontend
npm ci --registry=https://registry.npmjs.org
npm run build
```

Демо-аккаунты (синтетические данные), общий пароль `DemoRazryad42!`:

| Аккаунт | Роль |
|---|---|
| novice@razryad.demo | Кандидат Backend Intern |
| middle@razryad.demo | Кандидат Backend Middle |
| provisional@razryad.demo | Кандидат с предварительным грейдом |
| employer1@razryad.demo | Работодатель |
| employer2@razryad.demo | Работодатель |

## Развёртывание и CI/CD

[Инструкция](deploy/README.md): Docker Compose, systemd, nginx, GitHub Secrets
и автоматическая выкатка. Push в master запускает тесты, сборку frontend,
миграции на пустой SQLite и проверку схемы; затем выкатывает готовый артефакт.
PR в master запускает проверки без выкатки. База и JWT-секрет сохраняются.
Перед миграциями создаётся backup; при ошибке запуска возвращаются предыдущий
релиз и копия базы.

## Тесты

```sh
cd backend
python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
```

Тесты изолируют SQLite от рабочей базы. Backend-проверки: авторизация, приватность,
подбор, адаптивное тестирование и сквозной сценарий. API: /api/v1,
OpenAPI: /docs, health-check: /health.

Frontend-регрессии (Node.js 20):

```sh
cd frontend
npm ci --registry=https://registry.npmjs.org
npm test
```

## Состав и ограничения

- backend/: API, модели, миграции, генератор синтетических данных, тесты.
- frontend/: исходники, lockfile, готовая сборка и шрифты.
- content/: таксономия и навыки.
- deploy/: инструкция, systemd/nginx-примеры, CI deploy helper.
- .github/workflows/: тесты, сборка и автоматическая выкатка.

Это демонстрационная версия. Отправка писем для подтверждения регистрации
в production не реализована; используйте демо-аккаунты. LLM, S3, Redis и внешняя
интеграция ФСП не настроены. При HTTP трафик не шифруется. API-тесты не заменяют
интерактивную приёмку UI. Презентации, исторические отчёты, инфраструктурные
архивы и приватные конфигурации в репозиторий не включены.

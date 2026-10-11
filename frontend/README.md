# РАЗРЯД Frontend

Фронтенд-приложение платформы обратного подбора ИТ-специалистов с подтверждённым грейдом.

## Стек

- **React 18** + **TypeScript** (strict mode)
- **Vite 5** — быстрая сборка и dev-сервер
- **TailwindCSS 3** — дизайн-система ФСП
- **React Router 6** — маршрутизация
- **TanStack Query 5** — управление серверным состоянием
- **MSW (Mock Service Worker)** — мок-слой для параллельной разработки с бэкендом
- **Recharts** — визуализация данных
- **lucide-react** — иконки

## Установка

```bash
cd frontend
npm install
```

## Запуск

### Dev-сервер с моками (по умолчанию)

```bash
npm run dev
```

Приложение доступно на [http://localhost:5173](http://localhost:5173)

**Моки включены по умолчанию** — работает полностью автономно, без бэкенда.

### Dev-сервер с реальным API

Создайте `.env.local`:

```
VITE_USE_MOCKS=false
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

Запустите dev-сервер:

```bash
npm run dev
```

Прокси настроен: `/api` проксируется на `http://localhost:8000`.

### Production build

```bash
npm run build
```

Собранные файлы попадают в `dist/` — их раздаёт FastAPI.

## Структура

```
frontend/
├── public/
│   └── fonts/              # Montserrat woff2 (офлайн)
├── src/
│   ├── api/                # API-клиент, типы, хуки, моки
│   │   ├── client.ts       # Fetch с JWT, auto-refresh
│   │   ├── types.ts        # TypeScript типы по OpenAPI
│   │   ├── hooks.ts        # TanStack Query хуки
│   │   ├── mocks.ts        # MSW handlers
│   │   └── msw.ts          # Инициализация MSW
│   ├── app/                # AppShell, роутинг, защищённые маршруты
│   ├── design/             # Дизайн-система ФСП
│   │   └── components/     # Button, Input, Card, Badge и т.д.
│   ├── pages/
│   │   ├── Landing.tsx     # Лендинг
│   │   ├── auth/           # Регистрация, вход
│   │   ├── candidate/      # Кабинет кандидата
│   │   └── employer/       # Заглушка для frontend-employer
│   ├── lib/
│   │   └── utils.ts        # Утилиты (cn, formatSalary и т.д.)
│   ├── index.css           # Tailwind + CSS-переменные токенов
│   ├── main.tsx            # Точка входа
│   └── App.tsx             # Роутинг
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.js
└── README.md
```

## Переключение моков

### Включить моки

Установите в `.env.local`:

```
VITE_USE_MOCKS=true
```

Или запустите без `.env.local` (моки включены по умолчанию).

### Выключить моки

Установите в `.env.local`:

```
VITE_USE_MOCKS=false
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

Убедитесь, что бэкенд запущен на `http://localhost:8000`.

## Дизайн-система

Компоненты находятся в `src/design/components/`:

- `Button` — primary/secondary/ghost/danger, размеры, состояние загрузки
- `Input`, `Textarea`, `Select` — формы с валидацией
- `Card` — карточки контента
- `Badge` — грейды, статусы, подтверждение
- `Skeleton` — загрузка

Цвета и токены из `contract/design-tokens.json` преобразованы в CSS-переменные и Tailwind-тему.

**WCAG AA контрастность проверена и указана в комментариях к `src/index.css`.**

## Шрифт Montserrat

Шрифт должен быть размещён в `frontend/public/fonts/` в формате `.woff2` для офлайн-работы.

**TODO:** Загрузить Montserrat woff2 и добавить `@font-face` в `src/index.css`.

## API-клиент

`src/api/client.ts` реализует:

- JWT Bearer авторизация
- Автоматический refresh токена при 401
- Обработка RFC 9457 problem+json
- TypeScript типы по контракту

Все запросы идут через хуки TanStack Query (`src/api/hooks.ts`):

```tsx
import { useLogin, useCandidateProfile } from '@/api'

const loginMutation = useLogin()
const { data: profile } = useCandidateProfile()
```

## Зона владения

**frontend-lead владеет:** `frontend/` целиком, КРОМЕ `frontend/src/pages/employer/`

**frontend-employer владеет:** `frontend/src/pages/employer/`

Не редактируйте чужую зону — координируйтесь через капитана.

## Lint & Format

```bash
npm run lint
npm run format
```

## Проверка сборки

```bash
npm run build
```

Убедитесь, что TypeScript компилируется без ошибок.

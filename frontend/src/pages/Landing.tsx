import { Link } from 'react-router-dom'

export default function Landing() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-secondary-dark via-secondary-base to-primary-accent">
      {/* Hero Section */}
      <div className="container mx-auto px-4 py-16">
        <div className="text-center text-white mb-16">
          <h1 className="text-5xl md:text-6xl font-bold mb-6">
            РАЗРЯД
          </h1>
          <p className="text-xl md:text-2xl mb-4 text-primary-lighter">
            Подтверждённый грейд. Работодатель сам выходит на связь.
          </p>
          <p className="text-lg md:text-xl max-w-3xl mx-auto opacity-90">
            Платформа обратного подбора ИТ-специалистов через объективно подтверждённый профиль, а не поток случайных откликов.
          </p>
        </div>

        {/* CTA Buttons */}
        <div className="flex flex-col md:flex-row gap-6 justify-center items-center mb-24">
          <Link
            to="/auth/register?role=candidate"
            className="w-full md:w-auto px-12 py-4 bg-primary-accent text-white text-lg font-semibold rounded-lg hover:bg-primary-light transition-colors shadow-xl"
          >
            Создать профиль кандидата
          </Link>
          <Link
            to="/auth/register?role=employer"
            className="w-full md:w-auto px-12 py-4 bg-white text-secondary-dark text-lg font-semibold rounded-lg hover:bg-primary-lighter transition-colors shadow-xl"
          >
            Найти специалиста
          </Link>
        </div>

        {/* How it works */}
        <div className="max-w-5xl mx-auto">
          <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-8 md:p-12 text-white">
            <h2 className="text-3xl font-bold mb-8 text-center">Как это работает</h2>
            
            <div className="grid md:grid-cols-2 gap-8 mb-12">
              <div className="space-y-6">
                <h3 className="text-xl font-semibold text-primary-lighter">Для кандидата:</h3>
                <ol className="space-y-3 list-decimal list-inside">
                  <li>Проходите опрос по специализации</li>
                  <li>Заявляете свой грейд (Intern→Lead)</li>
                  <li>Решаете адаптивный тест на заявленный уровень</li>
                  <li>Получаете подтверждённую или предварительную категорию</li>
                  <li>Работодатели сами отправляют приглашения с вилкой зарплаты</li>
                  <li>Вы принимаете — контакты раскрываются обеим сторонам</li>
                </ol>
              </div>

              <div className="space-y-6">
                <h3 className="text-xl font-semibold text-primary-lighter">Для работодателя:</h3>
                <ol className="space-y-3 list-decimal list-inside">
                  <li>Описываете потребность команды</li>
                  <li>Система рекомендует категории</li>
                  <li>Получаете подборку с объяснениями «Почему в подборке»</li>
                  <li>Видите псевдоним, грейд, стек — без ФИО до согласия</li>
                  <li>Отправляете приглашение с описанием и вилкой ЗП</li>
                  <li>После принятия — полный доступ к контактам</li>
                </ol>
              </div>
            </div>

            <div className="border-t border-white/20 pt-8">
              <h3 className="text-xl font-semibold mb-4 text-center">Подтверждённый грейд и ФСП</h3>
              <p className="text-center max-w-3xl mx-auto opacity-90">
                Категория присваивается на основе адаптивного тестирования по модели IRT (Item Response Theory). 
                Привязка достижений ФСП даёт дополнительное подтверждение, но не обязательна — 
                профиль работает и для специалистов без истории в реестре.
              </p>
            </div>

            <div className="mt-8 text-center">
              <p className="text-sm opacity-75">
                🔒 Контакты открываются только после принятия приглашения — никакого спама и нежелательных звонков
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t border-white/20 mt-16 py-8 text-center text-white/60">
        <p>© 2026 РАЗРЯД — платформа обратного подбора ИТ-специалистов</p>
      </footer>
    </div>
  )
}

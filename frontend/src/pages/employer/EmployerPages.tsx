import { FormEvent, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import AppShell from '@/app/AppShell'
import { Badge, Button, Card, CardContent, Input, Select, Textarea } from '@/design/components'
import { useCreateInvitation, useCreateNeed, useRecommendedCategories, useSearchCandidates, useSentInvitations, useShortlist, useVacancies, useWithdrawInvitation, useHireInvitation, useInvitationHistory, useCreateVacancy, useUpdateVacancy } from '@/api/hooks'
import type { ApiError, Invitation } from '@/api/types'
import taxonomy from '../../../../content/taxonomy.json'

const opts=(xs:string[])=>xs.map(x=>({value:x,label:x}))
const specializationOptions=taxonomy.specializations.map(x=>({value:x.id,label:x.name}))
const gradeOptions=[...taxonomy.grades].sort((a,b)=>a.order-b.order).map(x=>({value:x.id,label:x.name}))
const errorText=(error:unknown)=>{const e=error as Partial<ApiError>;return e.detail||e.title||(error instanceof Error?error.message:'Не удалось выполнить запрос')}
function Shell({children}:{children:React.ReactNode}){return <AppShell role="employer">{children}</AppShell>}
function Empty({children}:{children:React.ReactNode}){return <div className="rounded-xl border bg-white p-10 text-center text-gray-500">{children}</div>}

export function Company(){return <Shell><div className="max-w-3xl space-y-6"><h1 className="text-3xl font-bold">Профиль компании</h1><Card><CardContent className="p-6 space-y-4"><p className="text-gray-600">Профиль и статус доверия загружаются через API компании.</p><Link className="text-primary-accent" to="/employer/dashboard">Вернуться в кабинет</Link></CardContent></Card></div></Shell>}

export function Need() {
  const nav = useNavigate()
  const create = useCreateNeed()
  const [text, setText] = useState('')
  const [title, setTitle] = useState('Backend Developer')
  const [spec, setSpec] = useState(specializationOptions[0]?.value || '')
  const [gradeMin, setGradeMin] = useState(gradeOptions[0]?.value || '')
  const [gradeMax, setGradeMax] = useState(gradeOptions[0]?.value || '')
  const [min, setMin] = useState('')
  const [max, setMax] = useState('')
  
  const valid = !!text && !!title && !!spec && !!gradeMin && !!gradeMax && Number(min) > 0 && Number(max) >= Number(min)
  
  const submit = () => create.mutate({
    title,
    description: text,
    specialization_id: spec,
    grade_min_id: gradeMin,
    grade_max_id: gradeMax,
    must_have_skills: [],
    nice_to_have_skills: [],
    salary_min: Number(min),
    salary_max: Number(max)
  }, {
    onSuccess: r => { sessionStorage.setItem('employer_need_id', r.id) }
  })
  
  const parsed = create.data
  const source = ((parsed?.parsed_data as Record<string, unknown>)?.source || {}) as Record<string, unknown>
  const parsedData = (parsed?.parsed_data || {}) as Record<string, unknown>
  const extracted = (Array.isArray(parsedData.extracted_skills) ? parsedData.extracted_skills : []) as string[]
  
  // Map specialization - use the user-selected value since API returns DB UUID
  const getSpecializationName = (): string => {
    // User selected specialization in the form - use that
    if (spec) {
      const specObj = taxonomy.specializations.find(s => s.id === spec)
      return specObj ? specObj.name : spec
    }
    // Fallback: API might return specialization code
    if (source.specialization) {
      const specObj = taxonomy.specializations.find(s => s.id === String(source.specialization))
      if (specObj) return specObj.name
    }
    return 'Не извлечено'
  }
  
  // Map grade range - use the user-selected values since API returns DB UUIDs
  const getGradeRange = (): string => {
    // User selected grades in the form - use those
    if (gradeMin && gradeMax) {
      const minGrade = taxonomy.grades.find(g => g.id === gradeMin)
      const maxGrade = taxonomy.grades.find(g => g.id === gradeMax)
      
      if (minGrade && maxGrade) {
        return `${minGrade.name} — ${maxGrade.name}`
      }
    }
    
    // Fallback: try to parse from API if it returned codes
    const gradeRange = source.grade_range as { min?: string; max?: string } | undefined
    if (gradeRange?.min || gradeRange?.max) {
      const minGrade = gradeRange.min ? taxonomy.grades.find(g => g.id === gradeRange.min) : null
      const maxGrade = gradeRange.max ? taxonomy.grades.find(g => g.id === gradeRange.max) : null
      
      if (minGrade && maxGrade) {
        return `${minGrade.name} — ${maxGrade.name}`
      }
      if (minGrade) return minGrade.name
      if (maxGrade) return maxGrade.name
    }
    
    return 'Не извлечено'
  }
  
  const rows: Array<[string, string]> = [
    ['Специализация', getSpecializationName()],
    ['Грейд', getGradeRange()],
    ['Роль', source.role || source.team_role ? String(source.role || source.team_role) : 'Не распознаётся автоматически'],
    ['Формат', source.work_format ? String(source.work_format) : 'Не распознаётся автоматически'],
    ['Домен', source.domain ? String(source.domain) : 'Не распознаётся автоматически']
  ]
  
  return (
    <Shell>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Опишите потребность</h1>
          <p className="text-sm text-gray-600">Потребность — это запрос на подбор: по ней строится ранжированная подборка и отправляются приглашения. Вакансия для этого не обязательна.</p>
          <p className="text-gray-600 mt-2">API разберёт свободный текст и вернёт структуру.</p>
        </div>
        <Card>
          <CardContent className="p-6 space-y-4">
            <Input label="Название потребности" value={title} onChange={e => setTitle(e.target.value)} />
            <Textarea label="Описание потребности" value={text} onChange={e => setText(e.target.value)} rows={4} />
            <div className="grid sm:grid-cols-3 gap-4">
              <Select label="Специализация *" value={spec} onChange={e => setSpec(e.target.value)} options={specializationOptions} />
              <Select label="Грейд от *" value={gradeMin} onChange={e => setGradeMin(e.target.value)} options={gradeOptions} />
              <Select label="Грейд до *" value={gradeMax} onChange={e => setGradeMax(e.target.value)} options={gradeOptions} />
            </div>
            <div className="grid sm:grid-cols-2 gap-4">
              <Input label="Зарплата от, ₽ *" value={min} onChange={e => setMin(e.target.value)} type="number" />
              <Input label="Зарплата до, ₽ *" value={max} onChange={e => setMax(e.target.value)} type="number" />
            </div>
            {(!valid || create.isError) && <p className="text-sm text-red-600">{create.isError ? errorText(create.error) : 'Опишите задачу и укажите корректную обязательную вилку.'}</p>}
            <Button loading={create.isPending} disabled={!valid} onClick={submit}>Разобрать потребность</Button>
          </CardContent>
        </Card>
        {parsed && (
          <Card>
            <CardContent className="p-6">
              <h2 className="text-xl font-bold">Мы поняли так — проверьте поля</h2>
              <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 mt-4">
                {rows.map(([label, value]) => (
                  <div className="border rounded-lg p-4" key={label}>
                    <div className="text-xs text-gray-500 mb-2">{label}</div>
                    <input className="font-semibold w-full bg-transparent" defaultValue={String(value || 'Не извлечено')} />
                    <p className="text-xs text-primary-accent mt-1">Поле можно исправить</p>
                  </div>
                ))}
              </div>
              {!!(source.must_have_skills || source.nice_to_have_skills) && (
                <div className="mt-5 border rounded-lg p-4">
                  <b>Требуемые навыки</b>
                  {Array.isArray(source.must_have_skills) && source.must_have_skills.length > 0 && (
                    <div className="mt-3">
                      <p className="text-xs text-gray-600">Must-have:</p>
                      <p className="font-semibold">{(source.must_have_skills as string[]).join(', ')}</p>
                    </div>
                  )}
                  {Array.isArray(source.nice_to_have_skills) && source.nice_to_have_skills.length > 0 && (
                    <div className="mt-2">
                      <p className="text-xs text-gray-600">Nice-to-have:</p>
                      <p className="font-semibold">{(source.nice_to_have_skills as string[]).join(', ')}</p>
                    </div>
                  )}
                </div>
              )}
              {extracted.length > 0 && (
                <div className="mt-5 rounded-lg bg-purple-50 p-4">
                  <b>Распознанные навыки</b>
                  <p className="mt-2">{extracted.join(' · ')}</p>
                </div>
              )}
              <Button className="mt-5" onClick={() => nav(`/employer/categories?need=${parsed.id}`)}>Рекомендованные категории →</Button>
            </CardContent>
          </Card>
        )}
      </div>
    </Shell>
  )
}

export function Categories(){const nav=useNavigate();const[sp]=useSearchParams();const id=sp.get('need')||sessionStorage.getItem('employer_need_id');const q=useRecommendedCategories(id);const raw=q.data;const rows=((raw&&'categories' in (raw as object)?(raw as {categories?:unknown[]}).categories:raw)||[]) as Array<Record<string,unknown>>;return <Shell><div className="space-y-6"><h1 className="text-3xl font-bold">Рекомендованные категории</h1>{q.isPending?<p>Загружаем категории…</p>:q.isError?<Empty>{errorText(q.error)}</Empty>:rows.length===0?<Empty>API не вернул подходящих категорий.</Empty>:<div className="grid md:grid-cols-3 gap-4">{rows.map((r,i)=><Card key={String(r.id||i)}><CardContent className="p-5"><h2 className="font-bold">{String(r.name||r.category||'Категория')}</h2><p className="text-2xl font-bold mt-3">{String(r.candidate_count||r.count||0)} кандидатов</p><p>Медиана: {String(r.median_salary||r.salary_median||'—')} ₽</p><Button className="mt-4" onClick={()=>nav(`/employer/shortlist?need=${id}`)}>Открыть подборку</Button></CardContent></Card>)}</div>}</div></Shell>}

export function Shortlist() {
  const [sp] = useSearchParams()
  const id = sp.get('need') || sessionStorage.getItem('employer_need_id')
  const q = useShortlist(id)
  const nav = useNavigate()
  const [frozen, setFrozen] = useState<string[]>([])
  if (!id) return <Shell><h1 className="text-3xl font-bold">Подборка под потребность</h1><Empty>Выберите потребность.<Link to="/employer/need">Создать потребность →</Link></Empty></Shell>
  return <Shell><div className="space-y-5">
    <h1 className="text-3xl font-bold">Подборка под потребность</h1>
    {q.isPending ? <p>Строим подборку по базе…</p> : q.isError ? <Empty>{errorText(q.error)}</Empty> : !q.data?.items.length ? <Empty>Подборка пуста. Уточните потребность.</Empty> : q.data.items.map(item => {
      const candidate = item.candidate
      const explanation = item.explanation
      const confirmed = candidate.is_confirmed
      const label = confirmed === true ? '✓ Грейд подтверждён' : confirmed === false ? 'Предварительный' : 'Статус грейда не указан'
      const highlights = explanation.fsp_highlights ?? candidate.fsp_highlights ?? []
      return <Card key={candidate.id}><CardContent className="p-5">
        <div className="flex justify-between gap-4">
          <div><h2 className="text-xl font-bold">{candidate.pseudonym || 'Анонимный кандидат'}</h2><Badge variant={confirmed ? 'confirmed' : 'preliminary'}>{label} · {candidate.grade}</Badge></div>
          <div><Button size="sm" onClick={() => nav(`/employer/invite/${candidate.id}`)}>Пригласить</Button><Button size="sm" variant="ghost" onClick={() => setFrozen(ids => [...ids, candidate.id])}>{frozen.includes(candidate.id) ? '★ Закреплён' : '☆ Закрепить'}</Button></div>
        </div>
        <div className="bg-gray-50 rounded p-4 mt-4">
          <b>Почему в подборке · {Math.round(item.match_score)} из 100</b>
          <ul className="text-sm mt-2 space-y-1">
            <li>✓ Совпали: {explanation.skills_matched?.join(', ') || '—'}</li>
            <li>⚠ Не покрыто: {explanation.skills_missing?.join(', ') || 'нет'}</li>
            <li>🏆 ФСП: {highlights.join(', ') || 'нет данных'}</li>
            <li>◷ Свежесть: {explanation.freshness === undefined ? '—' : explanation.freshness}</li>
            {explanation.category_rank !== undefined && <li>↗ Место: {explanation.category_rank}</li>}
          </ul>
          {item.counterfactual && <p className="text-sm mt-2 text-purple-800">💡 {item.counterfactual}</p>}
        </div>
        <p className="text-xs text-gray-500 mt-3">API не раскрывает ФИО, контакты и место работы до принятия приглашения.</p>
      </CardContent></Card>
    })}
  </div></Shell>
}

export function Search(){const[query,setQuery]=useState('');const[sort,setSort]=useState('relevance');const[active,setActive]=useState(false);const q=useSearchCandidates({skills:query,sort_by:sort},{enabled:active});const raw=q.data as Record<string,unknown>|undefined;const rows=((raw?.data||raw?.items||(Array.isArray(q.data)?q.data:[])) as Record<string,unknown>[]);return <Shell><div className="space-y-6"><h1 className="text-3xl font-bold">Поиск кандидатов</h1><div className="flex gap-3"><Input label="Навык или специализация" value={query} onChange={e=>setQuery(e.target.value)}/><Select label="Сортировать" value={sort} onChange={e=>setSort(e.target.value)} options={opts(['relevance','profile_strength'])}/><Button className="mt-6" onClick={()=>setActive(true)}>Найти</Button></div>{q.isError?<Empty>{errorText(q.error)}</Empty>:rows.map((r,i)=><Card key={String(r.candidate_id||i)}><CardContent className="p-4"><b>{String(r.pseudonym||'Анонимный кандидат')}</b><p className="text-sm text-gray-600">Псевдоним: виден работодателю до принятия приглашения</p><p className="text-sm">Стек кандидата: {Array.isArray(r.skills)?r.skills.join(', '):'—'}</p><Button size="sm" className="mt-3" onClick={()=>window.location.assign(`/employer/invite/${String(r.id||r.candidate_id)}`)}>Пригласить кандидата</Button></CardContent></Card>)}</div></Shell>}

export function Invite(){const{candidateId}=useParams();const send=useCreateInvitation();const[offer,setOffer]=useState('');const[subject,setSubject]=useState('Приглашение в команду');const[company,setCompany]=useState('');const[person,setPerson]=useState('');const[contact,setContact]=useState('');const[min,setMin]=useState('');const[max,setMax]=useState('');const submit=(e:FormEvent)=>{e.preventDefault();send.mutate({candidate_id:candidateId,subject,message:offer,salary_min:Number(min),salary_max:Number(max),company_name:company,contact_person:person,contact_method:contact,need_id:sessionStorage.getItem('employer_need_id')||undefined})};return <Shell><div className="max-w-3xl space-y-6"><h1 className="text-3xl font-bold">Приглашение · {candidateId}</h1>{send.data?<Card><CardContent className="p-8 text-center"><Badge variant="confirmed">Статус API: {send.data.status}</Badge><p className="mt-3">Контакты откроются после принятия кандидатом.</p><Link to="/employer/invitations" className="text-primary-accent">К приглашениям →</Link></CardContent></Card>:<form onSubmit={submit}><Card><CardContent className="p-6 space-y-4"><Input label="Тема" value={subject} onChange={e=>setSubject(e.target.value)}/><Input label="Компания *" value={company} onChange={e=>setCompany(e.target.value)}/><Input label="Контактное лицо *" value={person} onChange={e=>setPerson(e.target.value)}/><Input label="Контактный способ *" value={contact} onChange={e=>setContact(e.target.value)}/><Textarea label="Описание предложения" value={offer} onChange={e=>setOffer(e.target.value)}/><div className="grid sm:grid-cols-2 gap-4"><Input label="Вилка от, ₽ *" value={min} onChange={e=>setMin(e.target.value)} type="number"/><Input label="Вилка до, ₽ *" value={max} onChange={e=>setMax(e.target.value)} type="number"/></div>{send.isError&&<p className="text-red-600">{errorText(send.error)}</p>}<Button type="submit" loading={send.isPending} disabled={!offer||!company||!person||!contact||!min||Number(max)<Number(min)}>Отправить приглашение</Button></CardContent></Card></form>}</div></Shell>}

export function Invitations() {
  const q = useSentInvitations()
  const withdraw = useWithdrawInvitation()
  const hire = useHireInvitation()
  const [historyId, setHistoryId] = useState<string | null>(null)
  const history = useInvitationHistory(historyId)
  const labels: Record<Invitation['status'], string> = {sent: 'отправлено', viewed: 'просмотрено', accepted: 'принято', declined: 'отклонено', expired: 'истекло', hired: 'нанят', withdrawn: 'отозвано'}
  const refresh = () => { void q.refetch() }
  return <Shell><div className="space-y-6">
    <h1 className="text-3xl font-bold">Мои приглашения</h1>
    {q.isPending ? <p>Загружаем приглашения…</p> : q.isError ? <Empty>{errorText(q.error)}</Empty> : !q.data?.length ? <Empty>Вы ещё никого не приглашали.</Empty> : <div className="overflow-x-auto bg-white rounded-xl border"><table className="w-full text-sm"><tbody>{q.data.map(invitation => {
      const revealed = invitation.status === 'accepted' || invitation.status === 'hired'
      const contacts = revealed ? invitation.candidate_contacts : null
      const name = revealed ? invitation.candidate_fio : invitation.candidate_pseudonym
      return <tr className="border-b" key={invitation.id}>
        <td className="p-4">{name || `#${invitation.candidate_id.slice(0, 4).toUpperCase()}`}</td>
        <td className="p-4">{invitation.salary_min}–{invitation.salary_max} ₽</td>
        <td><Badge variant={revealed ? 'confirmed' : 'status'}>{labels[invitation.status]}</Badge></td>
        <td className="p-4">{revealed ? [contacts?.email, contacts?.phone].filter(Boolean).join(' · ') || 'Контакты не указаны' : 'Контакты скрыты до принятия'}</td>
        <td className="p-4 flex gap-2">
          <Button size="sm" variant="ghost" onClick={() => setHistoryId(invitation.id)}>История</Button>
          {(invitation.status === 'sent' || invitation.status === 'viewed') && <Button size="sm" variant="danger" loading={withdraw.isPending} onClick={() => withdraw.mutate(invitation.id, {onSuccess: refresh})}>Отозвать</Button>}
          {invitation.status === 'accepted' && <Button size="sm" onClick={() => hire.mutate(invitation.id, {onSuccess: refresh})}>Отметить найм</Button>}
        </td>
      </tr>
    })}</tbody></table></div>}
    {historyId && <Card><CardContent className="p-5"><h2 className="font-bold">История статусов</h2>{history.isLoading ? <p>Загружаем…</p> : history.data?.map((event, index) => <p key={index} className="text-sm mt-2">{String(event.from_status || 'создано')} → {String(event.to_status)} · {String(event.created_at || '')}</p>)}</CardContent></Card>}
  </div></Shell>
}

export function Vacancies(){const q=useVacancies();const create=useCreateVacancy();const update=useUpdateVacancy();const[editing,setEditing]=useState<Record<string,unknown>|null>(null);const[title,setTitle]=useState('');const[description,setDescription]=useState('');const[spec,setSpec]=useState(taxonomy.specializations[0]?.id||'');const[gmin,setGmin]=useState(taxonomy.grades[1]?.id||'');const[gmax,setGmax]=useState(taxonomy.grades[2]?.id||'');const[min,setMin]=useState('');const[max,setMax]=useState('');const submit=(e:FormEvent)=>{e.preventDefault();const payload={title,description,specialization_id:spec,grade_min_id:gmin,grade_max_id:gmax,salary_min:Number(min),salary_max:Number(max),requirements:{},status:'published'};if(editing&&editing.id)update.mutate({id:String(editing.id),data:payload},{onSuccess:()=>{setEditing(null);q.refetch()}});else if(editing)create.mutate(payload,{onSuccess:()=>{setEditing(null);q.refetch()}});else create.mutate(payload,{onSuccess:()=>{setTitle('');setDescription('');q.refetch()}})};const rows=(q.data||[]) as Record<string,unknown>[];return <Shell><div className="space-y-6"><div className="flex justify-between"><div><h1 className="text-3xl font-bold">Ваши опубликованные вакансии ({rows.length})</h1><p className="text-gray-600">Это вакансии вашей компании. Удаления нет в API — для архива используйте статус.</p></div><Button onClick={()=>setEditing({})}>Создать вакансию</Button></div>{editing&&<form onSubmit={submit}><Card><CardContent className="p-5 space-y-3"><Input label="Название" value={title} onChange={e=>setTitle(e.target.value)} required/><Textarea label="Описание" value={description} onChange={e=>setDescription(e.target.value)} required/><div className="grid md:grid-cols-3 gap-3"><Select label="Специализация" value={spec} onChange={e=>setSpec(e.target.value)} options={specializationOptions}/><Select label="Грейд от" value={gmin} onChange={e=>setGmin(e.target.value)} options={gradeOptions}/><Select label="Грейд до" value={gmax} onChange={e=>setGmax(e.target.value)} options={gradeOptions}/></div><div className="grid grid-cols-2 gap-3"><Input label="ЗП от *" type="number" value={min} onChange={e=>setMin(e.target.value)} required/><Input label="ЗП до *" type="number" value={max} onChange={e=>setMax(e.target.value)} required/></div>{(create.isError||update.isError)&&<p className="text-red-600">{errorText(create.error||update.error)}</p>}<Button type="submit" loading={create.isPending||update.isPending} disabled={!min||!max||Number(max)<Number(min)}>Сохранить</Button></CardContent></Card></form>}{q.isError?<Empty>{errorText(q.error)}</Empty>:rows.length===0?<Empty>Опубликованных вакансий пока нет.</Empty>:rows.map((r,i)=><Card key={String(r.id||i)}><CardContent className="p-5"><b>{String(r.title)}</b><p>{String(r.salary_min)}–{String(r.salary_max)} ₽</p><Button size="sm" className="mt-3" variant="ghost" onClick={()=>{setEditing(r);setTitle(String(r.title||''));setDescription(String(r.description||''));setMin(String(r.salary_min||''));setMax(String(r.salary_max||''))}}>Редактировать</Button></CardContent></Card>)}</div></Shell>}

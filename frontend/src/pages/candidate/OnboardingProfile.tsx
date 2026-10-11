import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppShell from '@/app/AppShell'
import { Badge, Button, Card, CardContent, Input, Select } from '@/design/components'
import { useCandidateProfile, useUpdateCandidateProfile } from '@/api'
import uiCopy from '../../../../content/ui-copy.ru.json'
import skillsData from '../../../../content/skills.json'
import taxonomy from '../../../../content/taxonomy.json'

const copy = uiCopy.screens['candidate.onboarding.profile']
const common = uiCopy.common

export default function OnboardingProfile() {
  const navigate = useNavigate()
  const profile = useCandidateProfile()
  const update = useUpdateCandidateProfile()
  
  const [experience, setExperience] = useState('')
  const [skillSearch, setSkillSearch] = useState('')
  const [selectedSkills, setSelectedSkills] = useState<string[]>([])
  const [teamRole, setTeamRole] = useState('')
  const [workFormat, setWorkFormat] = useState('')
  const [industry, setIndustry] = useState('')
  const [specialization, setSpecialization] = useState('')
  const [claimedGrade, setClaimedGrade] = useState('')
  const [apiSkillNames, setApiSkillNames] = useState<Record<string, string>>({})
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  
  const allSkills = skillsData.skills
  const filtered = skillSearch
    ? allSkills.filter(
        (s) =>
          s.name.toLowerCase().includes(skillSearch.toLowerCase()) ||
          s.aliases.some((a) => a.toLowerCase().includes(skillSearch.toLowerCase()))
      ).slice(0, 10)
    : []
  
  const gradeOptions = [...taxonomy.grades]
    .sort((a, b) => a.order - b.order)
    .map((x) => ({ value: x.id, label: x.name }))
  
  useEffect(() => {
    const p = profile.data
    if (p) {
      setExperience(p.years_of_experience == null ? '' : String(p.years_of_experience))
      setClaimedGrade(p.claimed_grade || '')
      
      const skillItems = p.skills || []
      const skillIds = skillItems
        .map((item: unknown) =>
          typeof item === 'string'
            ? item
            : typeof item === 'object' && item !== null
            ? String(
                (item as { skill_id?: string; name?: string }).skill_id ||
                  (item as { name?: string }).name ||
                  ''
              )
            : String(item)
        )
        .filter(Boolean)
      setSelectedSkills(skillIds)
      
      const namesMap: Record<string, string> = {}
      skillItems.forEach((item: unknown) => {
        if (typeof item === 'object' && item !== null && 'skill_id' in item && 'name' in item) {
          const x = item as { skill_id: string; name: string }
          namesMap[x.skill_id] = x.name
        }
      })
      setApiSkillNames(namesMap)
      
      setTeamRole(p.team_role || '')
      setWorkFormat(p.work_format || '')
      setIndustry(p.industry || '')
      setSpecialization(p.specialization_id || '')
    }
  }, [profile.data])
  
  const specializations = taxonomy.specializations.filter(
    (x) => !industry || x.industry_id === industry
  )
  
  const submit = () => {
    setError('')
    setSuccess('')
    if (!selectedSkills.length) {
      setError(copy.errors.skills)
      return
    }
    update.mutate(
      {
        experience_years: experience ? parseInt(experience) : undefined,
        skills: selectedSkills,
        team_role: teamRole || undefined,
        work_format: workFormat || undefined,
        industry: industry || undefined,
        specialization_id: specialization || undefined,
        claimed_grade: claimedGrade || undefined,
      } as any,
      {
        onSuccess: () => setSuccess('Профиль сохранён сервером'),
        onError: (e) => setError(`Не удалось сохранить профиль: ${e.message}`),
      }
    )
  }
  
  const name = (id: string) =>
    apiSkillNames[id] ||
    allSkills.find((s) => s.id === id)?.name ||
    allSkills.find((s) => s.name === id)?.name ||
    id
  
  return (
    <AppShell role="candidate">
      <div className="min-h-screen bg-gray-50 py-4">
        <Card>
          <CardContent>
            <div className="flex justify-between">
              <div>
                <h1 className="text-2xl font-bold">Профиль кандидата</h1>
                <p className="text-gray-600 mb-6">
                  Заполните отрасль, специализацию, стек, опыт, роль и формат работы.
                </p>
              </div>
              {profile.data && <Badge variant="confirmed">Профиль загружен</Badge>}
            </div>
            {profile.isLoading ? (
              <p>Загружаем профиль…</p>
            ) : (
              <div className="space-y-6">
                <Select
                  label="Отрасль"
                  value={industry}
                  onChange={(e) => {
                    setIndustry(e.target.value)
                    setSpecialization('')
                  }}
                  options={[
                    { value: '', label: 'Выберите отрасль…' },
                    ...taxonomy.industries.map((x) => ({ value: x.id, label: x.name })),
                  ]}
                />
                <Select
                  label="Специализация"
                  value={specialization}
                  onChange={(e) => setSpecialization(e.target.value)}
                  options={[
                    { value: '', label: 'Выберите специализацию…' },
                    ...specializations.map((x) => ({ value: x.id, label: x.name })),
                  ]}
                />
                <Select
                  label="Заявленный грейд"
                  value={claimedGrade}
                  onChange={(e) => setClaimedGrade(e.target.value)}
                  options={[
                    { value: '', label: 'Выберите грейд…' },
                    ...gradeOptions,
                  ]}
                />
                <Input
                  type="number"
                  label={copy.experience}
                  value={experience}
                  onChange={(e) => setExperience(e.target.value)}
                  min="0"
                />
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    {copy.skills}
                  </label>
                  <Input
                    value={skillSearch}
                    onChange={(e) => setSkillSearch(e.target.value)}
                    placeholder="Начните печатать: Python, React…"
                  />
                  {filtered.length > 0 && (
                    <div className="border rounded bg-white">
                      {filtered.map((skill) => (
                        <button
                          type="button"
                          key={skill.id}
                          onClick={() => {
                            if (!selectedSkills.includes(skill.id))
                              setSelectedSkills([...selectedSkills, skill.id])
                            setSkillSearch('')
                          }}
                          className="block w-full text-left px-4 py-2"
                        >
                          {skill.name}
                        </button>
                      ))}
                    </div>
                  )}
                  <div className="flex flex-wrap gap-2 mt-3">
                    {selectedSkills.map((id) => (
                      <span key={id} className="px-3 py-1 bg-secondary-light text-white rounded-full">
                        {name(id)}{' '}
                        <button
                          type="button"
                          onClick={() => setSelectedSkills(selectedSkills.filter((x) => x !== id))}
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                </div>
                <Select
                  label={copy.role}
                  value={teamRole}
                  onChange={(e) => setTeamRole(e.target.value)}
                  options={[
                    { value: '', label: 'Выберите…' },
                    { value: 'individual', label: 'Индивидуальный разработчик' },
                    { value: 'team_member', label: 'Член команды' },
                    { value: 'team_lead', label: 'Тимлид' },
                  ]}
                />
                <Select
                  label={copy.format}
                  value={workFormat}
                  onChange={(e) => setWorkFormat(e.target.value)}
                  options={[
                    { value: '', label: 'Выберите…' },
                    { value: 'office', label: 'Офис' },
                    { value: 'remote', label: 'Удалённо' },
                    { value: 'hybrid', label: 'Гибрид' },
                  ]}
                />
                {error && <p className="text-red-600">{error}</p>}
                {success && <p className="text-green-600">{success}</p>}
              </div>
            )}
            <div className="mt-8 flex gap-3">
              <Button variant="ghost" onClick={() => navigate('/candidate/onboarding/grade')}>
                {common.back}
              </Button>
              <Button variant="primary" className="flex-1" onClick={submit} loading={update.isPending}>
                {copy.cta}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  )
}

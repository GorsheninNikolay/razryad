import { SelectHTMLAttributes, forwardRef, useId } from 'react'
import { cn } from '@/lib/utils'
export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> { label?: string; error?: string; options: Array<{ value: string; label: string }> }
const Select = forwardRef<HTMLSelectElement, SelectProps>(({className,label,error,options,id:providedId,...props},ref)=>{const generatedId=useId();const id=providedId||generatedId;const errorId=`${id}-error`;return <div className="w-full">{label&&<label htmlFor={id} className="block text-sm font-medium text-gray-700 mb-1">{label}</label>}<select id={id} aria-describedby={error?errorId:undefined} aria-invalid={error?true:undefined} className={cn('w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-accent focus:border-primary-accent bg-white',error&&'border-red-500 focus:ring-red-500 focus:border-red-500',className)} ref={ref} {...props}>{options.map(option=><option key={option.value} value={option.value}>{option.label}</option>)}</select>{error&&<p id={errorId} className="mt-1 text-sm text-red-600">{error}</p>}</div>})
Select.displayName='Select'
export default Select

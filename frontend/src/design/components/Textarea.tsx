import { TextareaHTMLAttributes, forwardRef, useId } from 'react'
import { cn } from '@/lib/utils'
export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> { label?: string; error?: string }
const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(({className,label,error,id:providedId,...props},ref)=>{const generatedId=useId();const id=providedId||generatedId;const errorId=`${id}-error`;return <div className="w-full">{label&&<label htmlFor={id} className="block text-sm font-medium text-gray-700 mb-1">{label}</label>}<textarea id={id} aria-describedby={error?errorId:undefined} aria-invalid={error?true:undefined} className={cn('w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-accent focus:border-primary-accent resize-y',error&&'border-red-500 focus:ring-red-500 focus:border-red-500',className)} ref={ref} {...props}/>{error&&<p id={errorId} className="mt-1 text-sm text-red-600">{error}</p>}</div>})
Textarea.displayName='Textarea'
export default Textarea

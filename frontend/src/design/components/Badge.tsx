import React from 'react'
import { cn } from '@/lib/utils'

export interface BadgeProps {
  children: React.ReactNode
  variant?: 'grade' | 'status' | 'confirmed' | 'preliminary' | 'default'
  className?: string
}

export default function Badge({ children, variant = 'default', className }: BadgeProps) {
  const variants = {
    grade: 'bg-secondary-light text-white',
    status: 'bg-blue-100 text-blue-800',
    confirmed: 'bg-green-100 text-green-800 border border-green-300',
    preliminary: 'bg-yellow-100 text-yellow-800 border border-yellow-300',
    default: 'bg-gray-100 text-gray-800',
  }

  return (
    <span
      className={cn(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
        variants[variant],
        className
      )}
    >
      {children}
    </span>
  )
}

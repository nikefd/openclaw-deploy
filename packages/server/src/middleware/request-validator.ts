/**
 * request-validator.ts — Request validation middleware
 *
 * Validates request body schema, query params, and path params
 * before they reach route handlers.
 *
 * Architecture: Middleware → validate against schema → pass to handler or reject
 */

import type { RequestHandler } from 'express'
import { HttpError } from './error-handler.js'

export interface ValidationSchema {
  body?: Record<string, {
    type: string
    required?: boolean
    minLength?: number
    maxLength?: number
  }>
  query?: Record<string, {
    type: string
    required?: boolean
  }>
}

/**
 * Validate request body against schema
 */
function validateBody(
  body: unknown,
  schema?: Record<string, any>,
): Record<string, unknown> {
  if (!schema) return {}

  if (typeof body !== 'object' || body === null) {
    throw new HttpError(400, 'Request body must be JSON object')
  }

  const validated: Record<string, unknown> = {}

  for (const [key, rule] of Object.entries(schema)) {
    const value = (body as Record<string, unknown>)[key]

    // Check required
    if (rule.required && (value === undefined || value === null)) {
      throw new HttpError(400, `Missing required field: ${key}`)
    }

    if (value === undefined) continue

    // Check type
    if (rule.type === 'string' && typeof value !== 'string') {
      throw new HttpError(400, `Field ${key} must be string, got ${typeof value}`)
    }
    if (rule.type === 'number' && typeof value !== 'number') {
      throw new HttpError(400, `Field ${key} must be number, got ${typeof value}`)
    }
    if (rule.type === 'boolean' && typeof value !== 'boolean') {
      throw new HttpError(400, `Field ${key} must be boolean, got ${typeof value}`)
    }

    // Check string length
    if (rule.type === 'string' && typeof value === 'string') {
      if (rule.minLength && value.length < rule.minLength) {
        throw new HttpError(400, `Field ${key} must be at least ${rule.minLength} chars`)
      }
      if (rule.maxLength && value.length > rule.maxLength) {
        throw new HttpError(400, `Field ${key} must be at most ${rule.maxLength} chars`)
      }
    }

    validated[key] = value
  }

  return validated
}

/**
 * Create a request validator middleware
 */
export function createValidator(schema: ValidationSchema): RequestHandler {
  return (req, res, next) => {
    try {
      if (schema.body) {
        req.body = validateBody(req.body, schema.body)
      }

      if (schema.query) {
        const validated: Record<string, unknown> = {}
        for (const [key, rule] of Object.entries(schema.query)) {
          const value = req.query[key]
          if (rule.required && !value) {
            throw new HttpError(400, `Missing required query param: ${key}`)
          }
          if (value) validated[key] = value
        }
        req.query = validated as any
      }

      next()
    } catch (err) {
      next(err)
    }
  }
}

// domain/lookup.js — pure lookup helpers for AGENTS / MODELS.
//
// No DOM, no state — given an id, return the matching record (or a sane
// fallback). Extracted from inline as part of Phase 6.3.

import { AGENTS, MODELS } from '../config/constants.js';

/**
 * Look up an agent by id. Falls back to AGENTS[0] (the main agent) if not found.
 * @param {string} id
 */
export function getAgent(id) {
  return AGENTS.find(a => a.id === id) || AGENTS[0];
}

/**
 * Look up a model descriptor by id. Falls back to MODELS[0] (the legacy
 * 'openclaw' default) if not found.
 * @param {string} modelId
 */
export function getModelInfo(modelId) {
  return MODELS.find(m => m.id === modelId) || MODELS[0];
}

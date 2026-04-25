// backendFactory.js — select which backend to use.
// Migration to Hermes: add HermesBackend.js, import it here, switch one line.

import { OpenClawBackend } from './OpenClawBackend.js';

let instance = null;

export function getBackend() {
  if (!instance) instance = new OpenClawBackend();
  return instance;
}

// For tests / future feature flags:
export function setBackend(b) { instance = b; }

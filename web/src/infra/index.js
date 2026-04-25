// infra/index.js — the single entry point for the infrastructure layer.
// Application/UI code imports from here, not from sub-files directly.

import { config, urls, resolveWireModel } from './config.js';
import { getBackend, setBackend } from './backend/backendFactory.js';
import { ChatBackend } from './backend/ChatBackend.js';
import { OpenClawBackend } from './backend/OpenClawBackend.js';
import { localStore, prefs } from './storage/localStore.js';
import { chatStore } from './storage/chatStore.js';
import { perfLog } from './telemetry.js';
import * as chatDomain from '../domain/chat.js';
import * as uiMarkdown from '../ui/markdown.js';
import * as uiMessageActions from '../ui/messageActions.js';

export {
  config, urls, resolveWireModel,
  getBackend, setBackend,
  ChatBackend, OpenClawBackend,
  localStore, prefs,
  chatStore,
  perfLog,
  chatDomain,
  uiMarkdown,
  uiMessageActions,
};

// Developer convenience: expose on window for console probing.
// Remove once Phase 4 is done and everything goes through explicit imports.
if (typeof window !== 'undefined') {
  window.__oc = Object.freeze({
    config, urls, resolveWireModel,
    backend: getBackend(),
    prefs, chatStore, perfLog,
    domain: { chat: chatDomain },
    ui: { markdown: uiMarkdown, messageActions: uiMessageActions },
    version: 'phase-4',
  });
}

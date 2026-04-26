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
import * as uiTts from '../ui/tts.js';
import * as uiFileHelpers from '../ui/fileHelpers.js';
import * as uiSkillsPanel from '../ui/skillsPanel.js';
import * as uiSearchHelpers from '../ui/searchHelpers.js';
import * as uiMemoryPanel from '../ui/memoryPanel.js';
import * as uiDemoCodes from '../ui/demoCodes.js';
import * as uiNodesPanel from '../ui/nodesPanel.js';
import * as uiModelDropdown from '../ui/modelDropdown.js';
import * as uiWelcome from '../ui/welcome.js';
import * as uiChatSidebar from '../ui/chatSidebar.js';
import * as uiTasksDashboard from '../ui/tasksDashboard.js';
import * as uiFileViewer from '../ui/fileViewer.js';
import * as uiExpertTeams from '../ui/expertTeams.js';
import * as uiMentionPopup from '../ui/mentionPopup.js';
import * as uiFileBreadcrumb from '../ui/fileBreadcrumb.js';
import * as uiMessageRenderer from '../ui/messageRenderer.js';
import * as uiStreamHandler from '../ui/streamHandler.js';
import * as uiStreamRecovery from '../ui/streamRecovery.js';
import * as uiStreamFinalize from '../ui/streamFinalize.js';
import * as uiStreamPerf from '../ui/streamPerf.js';
import * as uiStreamPollLoop from '../ui/streamPollLoop.js';

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
  uiTts,
  uiFileHelpers,
  uiSkillsPanel,
  uiSearchHelpers,
  uiMemoryPanel,
  uiDemoCodes,
  uiNodesPanel,
  uiModelDropdown,
  uiWelcome,
  uiChatSidebar,
  uiTasksDashboard,
  uiFileViewer,
  uiExpertTeams,
  uiMentionPopup,
  uiFileBreadcrumb,
  uiMessageRenderer,
  uiStreamHandler,
  uiStreamRecovery,
  uiStreamFinalize,
  uiStreamPerf,
  uiStreamPollLoop,
};

// Developer convenience: expose on window for console probing.
// Remove once Phase 4 is done and everything goes through explicit imports.
if (typeof window !== 'undefined') {
  window.__oc = Object.freeze({
    config, urls, resolveWireModel,
    backend: getBackend(),
    prefs, chatStore, perfLog,
    domain: { chat: chatDomain },
    ui: { markdown: uiMarkdown, messageActions: uiMessageActions, tts: uiTts, fileHelpers: uiFileHelpers, skillsPanel: uiSkillsPanel, searchHelpers: uiSearchHelpers, memoryPanel: uiMemoryPanel, demoCodes: uiDemoCodes, nodesPanel: uiNodesPanel, modelDropdown: uiModelDropdown, welcome: uiWelcome, chatSidebar: uiChatSidebar, tasksDashboard: uiTasksDashboard, fileViewer: uiFileViewer, expertTeams: uiExpertTeams, mentionPopup: uiMentionPopup, fileBreadcrumb: uiFileBreadcrumb, messageRenderer: uiMessageRenderer, streamHandler: uiStreamHandler, streamRecovery: uiStreamRecovery, streamFinalize: uiStreamFinalize, streamPerf: uiStreamPerf, streamPollLoop: uiStreamPollLoop },
    version: 'phase-4',
  });
}

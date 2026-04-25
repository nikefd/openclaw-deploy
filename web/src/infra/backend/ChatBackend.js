// ChatBackend — the contract every backend (OpenClaw / Hermes / …) must implement.
//
// Clean-architecture rule: UI and application layers depend only on this
// interface, never on any concrete implementation. To migrate backends,
// write a new class that extends ChatBackend and swap it in infra/backendFactory.
//
// All methods return Promises. Streaming uses AsyncIterables of deltas so the
// application layer doesn't need to know about SSE / WebSocket / fetch specifics.

/**
 * @typedef {Object} ChatMessage
 * @property {'user'|'assistant'|'system'} role
 * @property {string} content
 */

/**
 * @typedef {Object} StreamDelta
 * @property {'text'|'done'|'error'} type
 * @property {string} [text]       present when type === 'text'
 * @property {string} [error]      present when type === 'error'
 * @property {Object} [meta]       optional metadata (tokens, finish_reason, ...)
 */

/**
 * @typedef {Object} SendOptions
 * @property {string} chatId
 * @property {string} modelId       e.g. 'github-copilot/claude-opus-4.7'
 * @property {string} agentId       'main' means no agent override
 * @property {ChatMessage[]} messages
 * @property {AbortSignal} [signal]
 */

export class ChatBackend {
  /** Unique backend name for logging / telemetry. */
  get name() { throw new Error('not implemented'); }

  /**
   * Stream an assistant reply.
   * @param {SendOptions} opts
   * @returns {AsyncIterable<StreamDelta>}
   */
  async *stream(opts) {   // eslint-disable-line require-yield
    throw new Error('not implemented');
  }

  /**
   * Load server-side chat history for a chat id.
   * Used for recovery after page reload.
   * @param {string} chatId
   * @returns {Promise<ChatMessage[]>}
   */
  async loadHistory(chatId) { throw new Error('not implemented'); }

  /**
   * Persist a chat (whole object) to the server. Called by storage layer only;
   * UI code should not call this directly.
   * @param {Object} chat
   */
  async saveChat(chat) { throw new Error('not implemented'); }

  /**
   * Load all chats for the current user.
   * @returns {Promise<Object[]>}
   */
  async loadAllChats() { throw new Error('not implemented'); }

  /**
   * Delete a chat by id.
   * @param {string} chatId
   */
  async deleteChat(chatId) { throw new Error('not implemented'); }
}

// ui/welcome.js — pure HTML builder for the empty-chat welcome screen.
//
// Side-effect free: caller passes the active agent + a list of mention-able
// agents and gets back the HTML string to drop into messagesEl.innerHTML.

function escHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// JS-string escape for values landing inside onclick='...("VALUE")'
function escJsSingle(s) {
  return String(s == null ? '' : s)
    .replace(/\\/g, '\\\\')
    .replace(/'/g, "\\'");
}

/**
 * Build the welcome screen HTML.
 *
 * @param {{emoji?:string,name?:string,desc?:string}} agent  the active agent (e.g. 'main')
 * @param {Array<{emoji?:string,mention?:string}>} mentionableAgents  agents that have a `.mention` set
 * @returns {string}
 */
export function welcomeHtml(agent, mentionableAgents) {
  const a = agent || {};
  const emoji = escHtml(a.emoji);
  const name = escHtml(a.name);
  const desc = escHtml(a.desc);

  const mentions = (Array.isArray(mentionableAgents) ? mentionableAgents : [])
    .filter(x => x && x.mention)
    .map(x => {
      const safeMentionForJs = escHtml(escJsSingle(x.mention));
      const safeMentionForText = escHtml(x.mention);
      const safeEmoji = escHtml(x.emoji);
      return `<span onclick="insertMention('${safeMentionForJs}')">${safeEmoji} ${safeMentionForText}</span>`;
    })
    .join('');

  const mentionsBlock = mentions
    ? `<p style="font-size:13px;color:var(--text-sec);margin-top:12px">输入 @ 切换角色</p><div class="agents-hint">${mentions}</div>`
    : '';

  return `<div class="welcome"><div class="logo">${emoji}</div><h2>${name}</h2><p>${desc}</p>${mentionsBlock}</div>`;
}

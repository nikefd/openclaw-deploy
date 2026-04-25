// ui/modelDropdown.js — pure HTML builder for the model picker dropdown.
//
// Side-effect free: caller passes models + currentModelId, gets HTML string.

function escHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Build the dropdown menu HTML.
 *
 * @param {Array<{id:string,name:string,emoji:string,desc:string,cost:string}>} models
 * @param {string} currentModelId
 * @returns {string}
 */
export function modelDropdownHtml(models, currentModelId) {
  if (!Array.isArray(models) || !models.length) return '';
  return models.map(m => {
    const active = m.id === currentModelId ? ' active' : '';
    // m.id goes into onclick='setCurrentModel("...")'. We single-quote
    // the JS string and HTML-escape the id to defuse both injection
    // vectors. Backslashes also escaped to keep the string literal sane.
    const idForJs = String(m.id || '')
      .replace(/\\/g, '\\\\')
      .replace(/'/g, "\\'");
    return (
      `<div class="model-option${active}" onclick="setCurrentModel('${escHtml(idForJs)}')">` +
        `<span>${escHtml(m.emoji)}</span>` +
        `<div style="flex:1">` +
          `<div>${escHtml(m.name)}</div>` +
          `<div style="font-size:10px;color:var(--text-sec)">${escHtml(m.desc)}</div>` +
        `</div>` +
        `<span class="cost">${escHtml(m.cost)}</span>` +
      `</div>`
    );
  }).join('');
}

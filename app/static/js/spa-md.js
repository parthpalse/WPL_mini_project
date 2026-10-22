/* Minimal, XSS-safe Markdown renderer for assistant chat bubbles in the prebuilt SPA.
 * The SPA calls window.__beMd(text) and injects the returned HTML. All input is
 * HTML-escaped first, so only the tags produced below can ever reach the DOM. */
(function () {
  'use strict';

  function esc(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function inline(s) {
    s = esc(s);
    s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
    s = s.replace(/\*\*([^*]+?)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/(^|[^*\w])\*(?!\s)([^*]+?)\*(?![*\w])/g, '$1<em>$2</em>');
    s = s.replace(/(^|[^\w])_(?!\s)([^_]+?)_(?![\w])/g, '$1<em>$2</em>');
    return s;
  }

  function cells(line) {
    return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(function (c) { return c.trim(); });
  }

  var BULLET = /^\s*(?:[-*•]|•)\s+(.*)$/;
  var NUMBERED = /^\s*\d+[.)]\s+(.*)$/;
  var HEADING = /^\s*#{1,6}\s+(.*)$/;
  var TABLE_SEP = /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/;

  window.__beMd = function (text) {
    var lines = String(text == null ? '' : text).replace(/\r\n?/g, '\n').split('\n');
    var out = [], i = 0, para = [];

    function flush() {
      if (para.length) { out.push('<p>' + para.map(inline).join('<br>') + '</p>'); para = []; }
    }

    while (i < lines.length) {
      var line = lines[i], m;
      if (!line.trim()) { flush(); i++; continue; }

      if (line.indexOf('|') !== -1 && i + 1 < lines.length && TABLE_SEP.test(lines[i + 1]) && lines[i + 1].indexOf('-') !== -1) {
        flush();
        var head = cells(line), rows = [];
        i += 2;
        while (i < lines.length && lines[i].indexOf('|') !== -1 && lines[i].trim()) { rows.push(cells(lines[i])); i++; }
        out.push('<div class="be-md-scroll"><table><thead><tr>' + head.map(function (c) { return '<th>' + inline(c) + '</th>'; }).join('') +
          '</tr></thead><tbody>' + rows.map(function (r) {
            return '<tr>' + r.map(function (c) { return '<td>' + inline(c) + '</td>'; }).join('') + '</tr>';
          }).join('') + '</tbody></table></div>');
        continue;
      }

      if ((m = HEADING.exec(line))) { flush(); out.push('<p><strong>' + inline(m[1]) + '</strong></p>'); i++; continue; }

      if (BULLET.test(line) || NUMBERED.test(line)) {
        flush();
        var ordered = NUMBERED.test(line), items = [];
        while (i < lines.length && (m = (ordered ? NUMBERED : BULLET).exec(lines[i]))) { items.push('<li>' + inline(m[1]) + '</li>'); i++; }
        out.push((ordered ? '<ol>' : '<ul>') + items.join('') + (ordered ? '</ol>' : '</ul>'));
        continue;
      }

      para.push(line.trim());
      i++;
    }
    flush();
    return out.join('');
  };

  var css = document.createElement('style');
  css.textContent =
    '.be-md{white-space:normal;word-break:break-word}' +
    '.be-md p{margin:.45em 0}.be-md>:first-child{margin-top:0}.be-md>:last-child{margin-bottom:0}' +
    '.be-md ul,.be-md ol{margin:.45em 0;padding-left:1.25em}.be-md ul{list-style:disc}.be-md ol{list-style:decimal}' +
    '.be-md li{margin:.2em 0}.be-md code{font-family:ui-monospace,monospace;font-size:.9em;background:rgba(0,0,0,.08);padding:0 .25em}' +
    '.be-md-scroll{overflow-x:auto;margin:.45em 0}.be-md table{border-collapse:collapse;font-size:.85em}' +
    '.be-md th,.be-md td{border:1px solid currentColor;padding:.2em .5em;text-align:left}';
  (document.head || document.documentElement).appendChild(css);
})();

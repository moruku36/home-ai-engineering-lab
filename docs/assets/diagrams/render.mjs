// Render every src/*.mmd to <name>.svg with Pele (pinned in package.json).
import fs from 'node:fs';
import { render } from 'pele';
const srcDir = new URL('./src/', import.meta.url);
const options = { fontFamily: 'sans-serif', fontSize: 16, responsive: false, autoDirection: false };
// Pele's documented light-theme fallbacks, resolved so plain <img> viewers show the same colors.
const defaults = { '--_bg':'#fff', '--_fg':'#1f1f1f', '--_m':'#6e6e6e', '--_l':'#1f1f1f', '--_s':'#f3f3f3', '--_a':'#e6e6e6', '--_b':'#8a8a8a', '--_c':'#5b7bd5', '--_r':'4px', '--_fm':'monospace' };
const only = process.argv[2];
for (const f of fs.readdirSync(srcDir).filter(n => n.endsWith('.mmd') && (!only || n.startsWith(only))).sort()) {
  const result = render(fs.readFileSync(new URL(f, srcDir), 'utf8'), options);
  let svg = result.svg.replace(/var\((--[\w-]+)(?:,([^)]*))?\)/g, (full, n, fb) => defaults[n] ?? fb ?? full);
  // opaque white background so dark-mode viewers keep the text readable
  svg = svg.replace(/(<svg[^>]*>)/, '$1<rect width="100%" height="100%" fill="#fff"/>');
  fs.writeFileSync(new URL(f.replace(/\.mmd$/, '.svg'), import.meta.url), svg);
  console.log(f.padEnd(34), result.type.padEnd(10), result.width + 'x' + result.height);
}

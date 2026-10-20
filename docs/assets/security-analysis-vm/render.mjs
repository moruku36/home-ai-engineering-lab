import fs from 'node:fs';
import { render } from 'pele';
const source = fs.readFileSync(new URL('./source.mmd', import.meta.url), 'utf8');
const options = { fontFamily: 'sans-serif', fontSize: 16, responsive: false, autoDirection: false };
const result = render(source, options);
fs.writeFileSync(new URL('./architecture.raw.svg', import.meta.url), result.svg);
// Resolve Pele's documented light-theme fallbacks for SVG-only image consumers.
const defaults = { '--_bg':'#fff', '--_fg':'#1f1f1f', '--_m':'#6e6e6e', '--_l':'#1f1f1f', '--_s':'#f3f3f3', '--_a':'#e6e6e6', '--_b':'#8a8a8a', '--_c':'#5b7bd5', '--_r':'4px', '--_fm':'monospace' };
const portableSvg = result.svg.replace(/var\((--[\w-]+)(?:,([^)]*))?\)/g, (full, name, fallback) => defaults[name] ?? fallback ?? full);
fs.writeFileSync(new URL('./architecture.svg', import.meta.url), portableSvg);
console.log(JSON.stringify({renderer:'pele', version:'1.6.0', options, type:result.type, width:result.width, height:result.height, svgBytes:Buffer.byteLength(result.svg)}, null, 2));

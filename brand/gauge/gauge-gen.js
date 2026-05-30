// PollenWatch categorical gauge generator (vanilla, returns SVG strings).
// Data model: none(0) / low(1) / high(2) / mixed / unknown / nodata.
// 3 honest segments green->amber->red. Needle points at a SEGMENT CENTER
// (not a continuous value). Mixed + missing states get distinct treatments.

const G = {
  green: '#3DAE5A', amber: '#F2A516', red: '#E0492E',
  slate: '#33414F', gold: '#E8920C', goldDeep: '#C9760A',
  petals: ['#F2B705', '#EC7A1C', '#E0492E', '#D94F87', '#7FB23E'],
  petalCenter: '#F6D45E',
  gray: '#AEB7C0', grayTrack: '#D7DCE2', grayFaint: '#E6E9ED', muted: '#8B96A1',
};
const SEGCOL = [G.green, G.amber, G.red];
const CENTERS = [-52, 0, 52];

const CX = 60, CY = 60, R = 44, W = 11, H = 78;
const pt = (cx, cy, r, deg) => {
  const a = (deg - 90) * Math.PI / 180;
  return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
};
const f = (n) => Math.round(n * 100) / 100;

function arc(a0, a1, col, w, op = 1, dash = null) {
  const [x0, y0] = pt(CX, CY, R, a0);
  const [x1, y1] = pt(CX, CY, R, a1);
  const large = (a1 - a0) > 180 ? 1 : 0;
  const d = dash ? ` stroke-dasharray="${dash}"` : '';
  return `<path d="M${f(x0)} ${f(y0)} A${R} ${R} 0 ${large} 1 ${f(x1)} ${f(y1)}" stroke="${col}" stroke-width="${w}" fill="none" stroke-linecap="round" opacity="${op}"${d}/>`;
}

// three segments; activeIdx gets `activeW`, others `baseW` at `inactiveOp`
function segments(activeIdx, baseW, activeW, inactiveOp) {
  const bounds = [[-78, -28], [-24, 24], [28, 78]];
  return bounds.map((b, i) => {
    const isA = i === activeIdx;
    return arc(b[0], b[1], SEGCOL[i], isA ? activeW : baseW, (activeIdx == null || isA) ? 1 : inactiveOp);
  }).join('');
}

function grayArc(style) {
  // style: 'dash' (unknown) | 'faint' (nodata)
  if (style === 'dash') return arc(-78, 78, G.gray, W, 0.9, '1.5 5');
  return arc(-78, 78, G.grayFaint, W, 1);
}

function needle(deg, w = 4.5, col = G.slate) {
  const [nx, ny] = pt(CX, CY, R - 7, deg);
  return `<path d="M${CX} ${CY} L${f(nx)} ${f(ny)}" stroke="${col}" stroke-width="${w}" stroke-linecap="round"/>`;
}
function hubDot(col = G.slate, r = 4) {
  return `<circle cx="${CX}" cy="${CY}" r="${r}" fill="${col}"/>`;
}
function hubHollow(col = G.gray) {
  return `<circle cx="${CX}" cy="${CY}" r="4.5" fill="#fff" stroke="${col}" stroke-width="2"/>`;
}
function rimDot(deg, col) {
  const [x, y] = pt(CX, CY, R, deg);
  return `<circle cx="${f(x)}" cy="${f(y)}" r="6" fill="#fff"/><circle cx="${f(x)}" cy="${f(y)}" r="4.2" fill="${col}"/>`;
}

function bloom(op, centerCol) {
  const petalR = 13, rx = 6, ry = 8.8, n = 6, cr = 5.5;
  let p = '';
  for (let i = 0; i < n; i++) {
    const ang = i * (360 / n);
    const [px, py] = pt(CX, CY, petalR, ang);
    const col = (op === 'gray') ? G.gray : G.petals[i % G.petals.length];
    p += `<ellipse cx="${f(px)}" cy="${f(py)}" rx="${rx}" ry="${ry}" transform="rotate(${f(ang)} ${f(px)} ${f(py)})" fill="${col}"/>`;
  }
  const o = (op === 'gray') ? 0.3 : op;
  const center = `<circle cx="${CX}" cy="${CY}" r="${cr}" fill="${centerCol || ((op === 'gray') ? G.gray : G.petalCenter)}"/>`;
  return `<g opacity="${o}"><g>${p}</g>${center}</g>`;
}

function grain(cx, cy, bodyR, spikeLen, n, col, op = 1) {
  let s = '';
  for (let i = 0; i < n; i++) {
    const ang = (360 / n) * i;
    const [tx, ty] = pt(cx, cy, bodyR + spikeLen, ang);
    const [b1x, b1y] = pt(cx, cy, bodyR - 0.4, ang - 360 / n / 2.4);
    const [b2x, b2y] = pt(cx, cy, bodyR - 0.4, ang + 360 / n / 2.4);
    s += `M${f(b1x)} ${f(b1y)} L${f(tx)} ${f(ty)} L${f(b2x)} ${f(b2y)} Z`;
  }
  return `<g fill="${col}" opacity="${op}"><path d="${s}"/><circle cx="${cx}" cy="${cy}" r="${bodyR}"/></g>`;
}
function pollen(col, op, count = 5) {
  const list = [
    [CX + 27, CY + 4, 3.2, 2.2, 9], [CX + 18, CY + 22, 2.7, 1.9, 8],
    [CX, CY + 30, 2.8, 2.0, 8], [CX - 18, CY + 22, 2.7, 1.9, 8],
    [CX - 27, CY + 4, 3.2, 2.2, 9],
  ];
  // balanced subsets so "few" still looks intentional, not broken
  const PICK = { 0: [], 2: [1, 3], 3: [0, 2, 4], 5: [0, 1, 2, 3, 4] };
  const idx = PICK[count] || PICK[5];
  return idx.map(i => { const g = list[i]; return grain(g[0], g[1], g[2], g[3], g[4], col, op); }).join('');
}
// grains per level: none = nothing in the air, more pollen = worse
const GRAINS_FOR = { 0: 0, 1: 3, 2: 5 };

function slash() {
  // diagonal "absent" slash across the dial
  return `<path d="M30 86 L90 34" stroke="${G.muted}" stroke-width="3" stroke-linecap="round" opacity="0.85"/>`;
}

// mixed: small slate ticks at all three segment centers on the rim + hollow hub
function mixedTicks() {
  return CENTERS.map(d => {
    const [x, y] = pt(CX, CY, R, d);
    return `<circle cx="${f(x)}" cy="${f(y)}" r="3.4" fill="${G.slate}"/>`;
  }).join('');
}
// mixed alt: dashed neutral overlay along the whole rim + "not-equal" hub badge
function mixedOverlay() {
  return arc(-78, 78, G.slate, 3, 0.85, '2 4.5');
}
function neqBadge() {
  return `<g stroke="${G.slate}" stroke-width="2" stroke-linecap="round">
    <line x1="${CX-5}" y1="${CY-2}" x2="${CX+5}" y2="${CY-2}"/>
    <line x1="${CX-5}" y1="${CY+2.5}" x2="${CX+5}" y2="${CY+2.5}"/>
    <line x1="${CX+4}" y1="${CY-5}" x2="${CX-4}" y2="${CY+5.5}"/></g>`;
}

const SVG = (inner) => `<svg viewBox="0 0 120 92" xmlns="http://www.w3.org/2000/svg">${inner}</svg>`;

// ---- composers ----
// direction: 1 = needle + full segments (active thicker)
//            2 = lit segment (inactive dimmed) + rim dot, no needle
//            3 = needle + hub & bloom-center take the active color
function known(direction, activeIdx) {
  const deg = CENTERS[activeIdx];
  const col = SEGCOL[activeIdx];
  if (direction === 1) {
    return SVG(segments(activeIdx, W, W + 3, 1) + bloom(0.6) + pollen(G.gold, 1) + needle(deg) + hubDot());
  }
  if (direction === 2) {
    return SVG(segments(activeIdx, W, W + 2, 0.22) + bloom(0.6) + pollen(G.gold, 1) + rimDot(deg, col) + hubDot(G.slate, 3));
  }
  // direction 3
  return SVG(segments(activeIdx, W, W + 3, 1) + bloom(0.6, col) + pollen(G.gold, 1) + needle(deg, 3.6) + hubDot(col, 4.5));
}

// FINAL design — Dir 3 (status hub) + grains scaled by level + mixed Option A.
function pwGauge(state) {
  if (state === 'mixed') {
    return SVG(segments(null, W, W, 1) + bloom(0.6) + pollen(G.gold, 1, 5) + mixedTicks() + hubHollow(G.slate));
  }
  if (state === 'unknown' || state === 'nodata') return missing(state);
  const idx = { none: 0, low: 1, high: 2 }[state];
  const col = SEGCOL[idx];
  return SVG(
    segments(idx, W, W + 3, 1) +
    bloom(0.6, col) +
    pollen(G.gold, 1, GRAINS_FOR[idx]) +
    needle(CENTERS[idx], 3.6) +
    hubDot(col, 4.5)
  );
}

function mixed(variant) {
  if (variant === 2) {
    return SVG(segments(null, W, W, 1) + bloom(0.6) + pollen(G.gold, 1) + mixedOverlay() + `<circle cx="${CX}" cy="${CY}" r="8" fill="#fff"/>` + neqBadge());
  }
  return SVG(segments(null, W, W, 1) + bloom(0.6) + pollen(G.gold, 1) + mixedTicks() + hubHollow(G.slate));
}

function missing(kind) {
  if (kind === 'unknown') {
    return SVG(grayArc('dash') + bloom('gray') + hubHollow(G.gray));
  }
  // nodata
  return SVG(grayArc('faint') + bloom('gray') + slash() + hubHollow(G.gray));
}

window.PWGauge = { known, mixed, missing, pwGauge, G };

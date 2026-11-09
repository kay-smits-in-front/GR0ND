/* Penseel: schilderachtige tekenhulp voor het 0-zicht (sfeer van Terra Nil: warme, korrelige grond,
   gras, bomen, heuvels). Alles is deterministisch: dezelfde plek geeft altijd hetzelfde beeld.
   Hoort bij kaart.js en gebruikt zx, zy, zuVan en zicht daaruit. Alleen vormgeving, geen data. */

function hasj(a, b = 0, c = 0) {
  let h = (Math.floor(a) * 374761393 + Math.floor(b) * 668265263 + Math.floor(c) * 2147483647) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}

function zichtbaarBereik() {
  const [u0, u1] = [zuVan(-20), zuVan(zicht.w + 20)];
  const d0 = Math.max(0, (-20 - zicht.hy) / zicht.pm);
  const d1 = Math.min(DIEPTE_M, (zicht.h + 20 - zicht.hy) / zicht.pm);
  return { u0, u1, d0, d1 };
}

/* Korrel en stenen in de laag waarvan het pad nu actief is (clip met het huidige pad). */
function penseelKorrel(ctx, laagIndex) {
  const { u0, u1, d0, d1 } = zichtbaarBereik();
  const cel = Math.max(0.4, Math.sqrt(((u1 - u0) * (d1 - d0)) / 14000));
  ctx.save();
  ctx.clip();
  for (let i = Math.floor(u0 / cel); i <= u1 / cel; i++) {
    for (let j = Math.floor(d0 / cel); j <= d1 / cel; j++) {
      const k = hasj(i, j, laagIndex);
      const x = zx((i + hasj(i, j, 91)) * cel);
      const y = zy((j + hasj(i, j, 92)) * cel);
      if (k < 0.3) {
        ctx.fillStyle = k < 0.15 ? "rgba(0,0,0,0.13)" : "rgba(255,238,200,0.11)";
        const r = Math.max(1.2, cel * zicht.pm * (0.1 + k * 0.4));
        ctx.fillRect(x, y, r * 1.8, r);
      } else if (k > 0.985) {
        penseelSteen(ctx, x, y, Math.max(3, cel * zicht.pm * (0.35 + hasj(i, j, 93) * 0.5)));
      }
    }
  }
  ctx.restore();
}

function penseelSteen(ctx, x, y, r) {
  ctx.beginPath();
  ctx.ellipse(x, y, r, r * 0.68, 0, 0, Math.PI * 2);
  ctx.fillStyle = "rgba(150,150,145,0.55)";
  ctx.fill();
  ctx.beginPath();
  ctx.ellipse(x - r * 0.15, y - r * 0.2, r * 0.6, r * 0.35, 0, 0, Math.PI * 2);
  ctx.fillStyle = "rgba(235,235,225,0.28)";
  ctx.fill();
  ctx.strokeStyle = "rgba(20,18,14,0.45)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.ellipse(x, y, r, r * 0.68, 0, 0, Math.PI * 2);
  ctx.stroke();
}

/* Lichte rand boven en donkere rand onder elke laaggrens geeft de lagen volume. */
function penseelLaaggrens(ctx, us, pad) {
  const lijn = (verschuif, kleur) => {
    ctx.strokeStyle = kleur;
    ctx.beginPath();
    us.forEach((u, i) => (i ? ctx.lineTo(zx(u), zy(pad[i]) + verschuif) : ctx.moveTo(zx(u), zy(pad[i]) + verschuif)));
    ctx.stroke();
  };
  ctx.lineWidth = 2;
  lijn(-1.5, "rgba(255, 238, 200, 0.16)");
  lijn(1.5, "rgba(0, 0, 0, 0.32)");
}

function tekenHemel(ctx) {
  const horizon = Math.max(zy(0), 1);
  const lucht = ctx.createLinearGradient(0, 0, 0, horizon);
  lucht.addColorStop(0, "#0b1822");
  lucht.addColorStop(0.55, "#17333d");
  lucht.addColorStop(1, "#3f6f62");
  ctx.fillStyle = lucht;
  ctx.fillRect(0, 0, zicht.w, zicht.h);
  const gloed = ctx.createRadialGradient(zicht.w * 0.82, horizon, 0, zicht.w * 0.82, horizon, zicht.w * 0.5);
  gloed.addColorStop(0, "rgba(232, 168, 96, 0.30)");
  gloed.addColorStop(1, "rgba(232, 168, 96, 0)");
  ctx.fillStyle = gloed;
  ctx.fillRect(0, 0, zicht.w, horizon);
}

/* Twee rijen heuvels op afstand; ze schuiven langzamer mee dan de voorgrond. */
function tekenHeuvels(ctx) {
  const horizon = zy(0);
  const rijen = [[0.35, 7, "rgba(36, 74, 70, 0.9)", 31], [0.6, 4, "rgba(31, 66, 56, 0.95)", 77]];
  for (const [parallax, hoogte, kleur, zaad] of rijen) {
    ctx.beginPath();
    ctx.moveTo(0, horizon);
    for (let sx = 0; sx <= zicht.w + 8; sx += 8) {
      const u = (sx - zicht.w / 2) / zicht.pm + zicht.uc * parallax;
      const golf = Math.sin(u * 0.045 + zaad) * 0.5 + Math.sin(u * 0.13 + zaad * 2) * 0.25 + 0.75;
      ctx.lineTo(sx, horizon - golf * hoogte * zicht.pm * 0.55);
    }
    ctx.lineTo(zicht.w, horizon);
    ctx.closePath();
    ctx.fillStyle = kleur;
    ctx.fill();
  }
}

function penseelGras(ctx, g) {
  const { u0, u1 } = zichtbaarBereik();
  const horizon = zy(0);
  const dik = Math.max(5, 0.28 * zicht.pm);
  const band = ctx.createLinearGradient(0, horizon - 2, 0, horizon + dik);
  band.addColorStop(0, "#7fb85a");
  band.addColorStop(0.45, "#4f8c3c");
  band.addColorStop(1, "#33602b");
  ctx.fillStyle = band;
  ctx.fillRect(0, horizon - 2, zicht.w, dik + 2);
  const stap = 0.32;
  for (let i = Math.floor(u0 / stap); i <= u1 / stap; i++) {
    const u = (i + hasj(i, 5)) * stap;
    if (g.sloten.some((s) => Math.abs(u - s.u_midden) < s.breedte_boven / 2 + 0.2)) continue;
    const hoogte = Math.max(3, (0.1 + hasj(i, 6) * 0.3) * zicht.pm);
    const x = zx(u);
    ctx.fillStyle = hasj(i, 7) < 0.5 ? "#8cc664" : "#5a9a44";
    ctx.beginPath();
    ctx.moveTo(x - 1.5, horizon);
    ctx.lineTo(x + (hasj(i, 8) - 0.5) * 3, horizon - hoogte);
    ctx.lineTo(x + 1.5, horizon);
    ctx.fill();
  }
}

function penseelSchaduw(ctx, x, y, breedte) {
  ctx.beginPath();
  ctx.ellipse(x, y, breedte / 2, Math.max(2, breedte * 0.07), 0, 0, Math.PI * 2);
  ctx.fillStyle = "rgba(10, 24, 18, 0.35)";
  ctx.fill();
}

function penseelDenneboom(ctx, x, grond, hoogte, tint) {
  const h = hoogte * zicht.pm;
  const b = h * 0.34;
  ctx.fillStyle = "#4a3426";
  ctx.fillRect(x - b * 0.06, grond - h * 0.16, b * 0.12, h * 0.16);
  const trappen = 4;
  for (let t = 0; t < trappen; t++) {
    const onder = grond - h * 0.1 - (t * h * 0.84) / trappen;
    const top = onder - (h * 0.84) / trappen - h * 0.1;
    const halve = (b * (trappen - t * 0.72)) / trappen;
    ctx.beginPath();
    ctx.moveTo(x - halve, onder);
    ctx.lineTo(x, top);
    ctx.lineTo(x + halve, onder);
    ctx.closePath();
    ctx.fillStyle = tint[0];
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(x, top);
    ctx.lineTo(x + halve, onder);
    ctx.lineTo(x + halve * 0.15, onder);
    ctx.closePath();
    ctx.fillStyle = tint[1];
    ctx.fill();
  }
}

function penseelLoofboom(ctx, x, grond, hoogte, zaad, tint) {
  const h = hoogte * zicht.pm;
  ctx.fillStyle = "#4a3426";
  ctx.fillRect(x - h * 0.035, grond - h * 0.45, h * 0.07, h * 0.45);
  for (const [dx, dy, r, kleur] of [[-0.16, 0.58, 0.2, tint[0]], [0.16, 0.6, 0.2, tint[0]], [0, 0.78, 0.26, tint[0]], [0.07, 0.8, 0.18, tint[1]], [-0.08, 0.68, 0.12, tint[1]]]) {
    ctx.beginPath();
    ctx.arc(x + dx * h * (0.9 + hasj(zaad, 3) * 0.2), grond - dy * h, r * h, 0, Math.PI * 2);
    ctx.fillStyle = kleur;
    ctx.fill();
  }
}

function penseelVrij(g, u) {
  const buiten = (a, b, marge) => u < a - marge || u > b + marge;
  return (
    g.huizen.every((h) => buiten(h.u0, h.u1, 2.5)) &&
    g.wegen.every((w) => buiten(w.teen_l, w.teen_r, 1.5)) &&
    g.sloten.every((s) => buiten(s.u_midden - s.breedte_boven / 2, s.u_midden + s.breedte_boven / 2, 1.5)) &&
    g.lantaarns.every((l) => Math.abs(u - l.u) > 1.5)
  );
}

/* Bomen op vaste plekken; ze wisselen mee met de voorbeeldbovengrond (elke 100 m). */
function penseelBomen(ctx, g, zaad) {
  const { u0, u1 } = zichtbaarBereik();
  const horizon = zy(0);
  const stap = 6;
  const groen = [["#2c5a3a", "#3c7548"], ["#3a6e3a", "#528a4a"], ["#6b7f35", "#8a9c45"]];
  for (let i = Math.floor(u0 / stap) - 2; i <= u1 / stap + 2; i++) {
    if (hasj(i, zaad, 11) > 0.42) continue;
    const u = (i + 0.2 + hasj(i, zaad, 12) * 0.6) * stap;
    if (!penseelVrij(g, u)) continue;
    const hoogte = 4.5 + hasj(i, zaad, 13) * 4.5;
    const tint = groen[Math.floor(hasj(i, zaad, 14) * 3)];
    const x = zx(u);
    penseelSchaduw(ctx, x, horizon + 2, hoogte * zicht.pm * 0.5);
    if (hasj(i, zaad, 15) < 0.55) penseelDenneboom(ctx, x, horizon, hoogte, tint);
    else penseelLoofboom(ctx, x, horizon, hoogte * 0.85, i, tint);
  }
}

"use strict";

/* GR0ND kaartpagina: overzichtskaart (RD) en 0-zicht (doorsnede loodrecht op het tracé).
   Schaal in beide richtingen gelijk, dus alles staat in verhouding. Grond en bovengrond zijn voorbeelddata. */

const $ = (id) => document.getElementById(id);

const DIEPTE_M = 50;
const OVERZICHT_INFO = "Kantelen en draaien: sleep met de rechtermuisknop. Grond en leidingen in het 0-zicht zijn voorbeelddata.";
const SKY_ONDER = "#1a1f22";

const staat = {
  weergave: "overzicht",
  nl: null,
  a: null,
  b: null,
  aLL: null,
  bLL: null,
  zet: null,
  s: 0,
  profiel: null,
  typen: {},
  bestaand: [],
  nieuwe: [],
  posities: {},
  meldingen: [],
  checkstatus: {},
  gereed: {},
  gereedschap: "selecteer",
  geselecteerd: null,
  sleep: null,
  cursor: null,
  controleNr: 0,
  teller: 0,
};

/* ---------- hulpfuncties ---------- */

const nl = (getal, cijfers = 2) => getal.toFixed(cijfers).replace(".", ",");

function bewaarGereed() {
  try {
    localStorage.setItem("gr0nd_checklist", JSON.stringify(staat.gereed));
  } catch {}
}

function leesGereed() {
  try {
    return JSON.parse(localStorage.getItem("gr0nd_checklist")) || {};
  } catch {
    return {};
  }
}

function toon(tekst) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = tekst;
  $("toasts").append(toast);
  setTimeout(() => toast.remove(), 4500);
}

async function api(pad, opties) {
  const antwoord = await fetch(pad, opties);
  if (antwoord.status === 401) {
    location.href = "/login";
    throw new Error("Niet ingelogd");
  }
  if (!antwoord.ok) {
    let tekst = "Er ging iets mis. Probeer het opnieuw.";
    try {
      const inhoud = await antwoord.json();
      if (typeof inhoud.detail === "string") tekst = inhoud.detail;
    } catch {}
    throw new Error(tekst);
  }
  return antwoord.json();
}

function trace() {
  if (!staat.a || !staat.b) return null;
  return { ax: staat.a[0], ay: staat.a[1], bx: staat.b[0], by: staat.b[1] };
}

function traceLengte() {
  const t = trace();
  return t ? Math.hypot(t.bx - t.ax, t.by - t.ay) : 0;
}

function maatCanvas(canvas) {
  const dpr = window.devicePixelRatio || 1;
  const vak = canvas.getBoundingClientRect();
  const breedte = Math.max(1, Math.round(vak.width * dpr));
  const hoogte = Math.max(1, Math.round(vak.height * dpr));
  if (canvas.width !== breedte || canvas.height !== hoogte) {
    canvas.width = breedte;
    canvas.height = hoogte;
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, w: vak.width, h: vak.height };
}

function aanwijzer(canvas, gebeurtenis) {
  const vak = canvas.getBoundingClientRect();
  return [gebeurtenis.clientX - vak.left, gebeurtenis.clientY - vak.top];
}

/* ---------- overzichtskaart (MapLibre met PDOK-lagen) ---------- */

let kaartObj = null;
const markers = {};
const gebied = { punten: [], tekenen: false, klaar: false };
const leegGeo = () => ({ type: "FeatureCollection", features: [] });

function registreerTegelprotocol() {
  // PDOK-WMTS verwacht soms een tegelmatrix met voorloopnul ("07"); we proberen beide.
  maplibregl.addProtocol("pdok", async (params, afbreken) => {
    const adres = params.url.replace("pdok://", "https://");
    const matrix = /tilematrix=(\d+)/.exec(adres)[1];
    for (const waarde of [matrix.padStart(2, "0"), matrix]) {
      const antwoord = await fetch(adres.replace(/tilematrix=\d+/, `tilematrix=${waarde}`), {
        signal: afbreken.signal,
      });
      if (antwoord.ok && (antwoord.headers.get("content-type") || "").startsWith("image/")) {
        return { data: await antwoord.arrayBuffer() };
      }
    }
    throw new Error("Tegel niet beschikbaar");
  });
}

function maakStijl(lagen) {
  const bronnen = {};
  const kaartlagen = lagen.map((laag) => {
    bronnen[laag.id] = {
      type: "raster",
      tiles: [laag.tegels],
      tileSize: 256,
      maxzoom: laag.max_zoom,
      attribution: laag.bron,
    };
    return {
      id: laag.id,
      type: "raster",
      source: laag.id,
      layout: { visibility: laag.standaard ? "visible" : "none" },
    };
  });
  return {
    version: 8,
    sources: bronnen,
    layers: [{ id: "achtergrondkleur", type: "background", paint: { "background-color": "#0e1216" } }, ...kaartlagen],
  };
}

function voegTekenlagenToe() {
  kaartObj.addSource("gebied", { type: "geojson", data: leegGeo() });
  kaartObj.addSource("trace", { type: "geojson", data: leegGeo() });
  kaartObj.addLayer({
    id: "gebied-vlak", type: "fill", source: "gebied", filter: ["==", "$type", "Polygon"],
    paint: { "fill-color": "#d4a572", "fill-opacity": 0.2 },
  });
  kaartObj.addLayer({
    id: "gebied-lijn", type: "line", source: "gebied", filter: ["!=", "$type", "Point"],
    paint: { "line-color": "#d4a572", "line-width": 2.5 },
  });
  kaartObj.addLayer({
    id: "gebied-punten", type: "circle", source: "gebied", filter: ["==", "$type", "Point"],
    paint: { "circle-radius": 4, "circle-color": "#1a140d", "circle-stroke-color": "#d4a572", "circle-stroke-width": 2 },
  });
  kaartObj.addLayer({
    id: "trace-lijn", type: "line", source: "trace",
    paint: { "line-color": "#ffffff", "line-width": 3, "line-dasharray": [2, 1.5] },
  });
}

function oppervlakM2(punten) {
  const [lon0, lat0] = punten[0];
  const naarM = ([lon, lat]) => [(lon - lon0) * 111320 * Math.cos((lat0 * Math.PI) / 180), (lat - lat0) * 110540];
  const xy = punten.map(naarM);
  let som = 0;
  xy.forEach(([x, y], i) => {
    const [x2, y2] = xy[(i + 1) % xy.length];
    som += x * y2 - x2 * y;
  });
  return Math.abs(som) / 2;
}

function toonOppervlak(m2) {
  return m2 >= 1e6 ? `${nl(m2 / 1e6)} km²` : m2 >= 1e4 ? `${nl(m2 / 1e4, 1)} ha` : `${nl(m2, 0)} m²`;
}

function gebiedBijwerken() {
  const p = gebied.punten;
  const features = p.map((c) => ({ type: "Feature", properties: {}, geometry: { type: "Point", coordinates: c } }));
  if (p.length >= 2) {
    const geometrie = gebied.klaar
      ? { type: "Polygon", coordinates: [[...p, p[0]]] }
      : { type: "LineString", coordinates: p };
    features.push({ type: "Feature", properties: {}, geometry: geometrie });
  }
  kaartObj.getSource("gebied").setData({ type: "FeatureCollection", features });
  const info = $("gebied-info");
  if (gebied.klaar) info.textContent = `Gebied van ${toonOppervlak(oppervlakM2(p))}, ${p.length} hoekpunten.`;
  else if (gebied.tekenen) info.textContent = `${p.length} punten. Dubbelklik om af te ronden.`;
  else info.textContent = "Klik punten op de kaart. Dubbelklik om af te ronden.";
  $("teken-gebied").setAttribute("aria-pressed", gebied.tekenen);
  $("wis-gebied").disabled = p.length === 0;
  updateCursor();
}

function updateCursor() {
  kaartObj.getCanvas().style.cursor = staat.zet || gebied.tekenen ? "crosshair" : "";
}

function startGebied() {
  gebied.punten = [];
  gebied.klaar = false;
  gebied.tekenen = !gebied.tekenen;
  staat.zet = null;
  if (gebied.tekenen) kaartObj.doubleClickZoom.disable();
  else kaartObj.doubleClickZoom.enable();
  traceVeranderd();
  gebiedBijwerken();
}

function rondGebiedAf() {
  if (gebied.punten.length > 2) gebied.punten.pop();
  gebied.klaar = gebied.punten.length >= 3;
  gebied.tekenen = false;
  setTimeout(() => kaartObj.doubleClickZoom.enable(), 300);
  gebiedBijwerken();
}

function wisGebied() {
  gebied.punten = [];
  gebied.tekenen = false;
  gebied.klaar = false;
  kaartObj.doubleClickZoom.enable();
  gebiedBijwerken();
}

function maakMarker(letter) {
  const element = document.createElement("div");
  element.className = "marker-punt";
  element.textContent = letter;
  return new maplibregl.Marker({ element });
}

function tekenTrace() {
  for (const [letter, punt] of [["A", staat.aLL], ["B", staat.bLL]]) {
    markers[letter] ??= maakMarker(letter);
    if (punt) markers[letter].setLngLat(punt).addTo(kaartObj);
    else markers[letter].remove();
  }
  const lijn = staat.aLL && staat.bLL
    ? [{ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: [staat.aLL, staat.bLL] } }]
    : [];
  kaartObj.getSource("trace").setData({ type: "FeatureCollection", features: lijn });
}

async function zetPunt(lngLat) {
  const letter = staat.zet;
  try {
    const rd = await api(`/api/rd?lon=${lngLat.lng}&lat=${lngLat.lat}`);
    const [punt, ll] = [[rd.x, rd.y], [lngLat.lng, lngLat.lat]];
    if (letter === "A") [staat.a, staat.aLL] = [punt, ll];
    else [staat.b, staat.bLL] = [punt, ll];
    staat.zet = letter === "A" && !staat.b ? "B" : null;
    traceVeranderd();
  } catch (fout) {
    toon(fout.message);
  }
}

function traceVeranderd() {
  staat.nieuwe = [];
  staat.profiel = null;
  const t = trace();
  const info = $("trace-info");
  if (t) {
    const lengte = traceLengte();
    info.textContent = `Rechte lijn van ${lengte >= 1000 ? nl(lengte / 1000) + " km" : nl(lengte, 0) + " m"}. Een tracé met bochten volgt.`;
  } else {
    info.textContent = staat.a ? "Zet nu punt B." : "Klik een knop en dan op de kaart.";
  }
  $("open-zicht").disabled = !t;
  $("tab-zicht").disabled = !t;
  for (const [id, letter] of [["zet-a", "A"], ["zet-b", "B"]]) $(id).setAttribute("aria-pressed", staat.zet === letter);
  if (kaartObj?.getSource("trace")) {
    tekenTrace();
    updateCursor();
  }
}

function bouwLagenpaneel(catalogus) {
  const maak = (laag, soort) => {
    const label = document.createElement("label");
    const keuze = document.createElement("input");
    keuze.type = soort;
    keuze.name = soort === "radio" ? "achtergrond" : laag.id;
    keuze.checked = laag.standaard;
    keuze.addEventListener("change", () => {
      if (soort === "radio") {
        for (const andere of catalogus.lagen.filter((l) => l.groep === "achtergrond")) {
          kaartObj.setLayoutProperty(andere.id, "visibility", andere.id === laag.id ? "visible" : "none");
        }
      } else {
        kaartObj.setLayoutProperty(laag.id, "visibility", keuze.checked ? "visible" : "none");
      }
    });
    label.append(keuze, laag.naam);
    return label;
  };
  for (const laag of catalogus.lagen) {
    $(laag.groep === "achtergrond" ? "achtergronden" : "lagen").append(maak(laag, laag.groep === "achtergrond" ? "radio" : "checkbox"));
  }
  for (const item of catalogus.volgt) {
    const li = document.createElement("li");
    li.textContent = item.naam;
    li.title = item.reden;
    $("lagen-volgt").append(li);
  }
}

function bindZoeken() {
  const invoer = $("zoek-invoer");
  const lijst = $("zoek-lijst");
  let timer = null;
  let nummer = 0;
  const sluit = () => {
    lijst.hidden = true;
    lijst.replaceChildren();
  };
  const kies = async (resultaat) => {
    sluit();
    try {
      const plek = await api(`/api/zoek/locatie?id=${encodeURIComponent(resultaat.id)}`);
      invoer.value = plek.naam;
      kaartObj.flyTo({
        center: [plek.lon, plek.lat], zoom: plek.zoom, pitch: plek.zoom >= 15 ? 50 : kaartObj.getPitch(), duration: 2500,
      });
    } catch (fout) {
      toon(fout.message);
    }
  };
  invoer.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      const volgnummer = ++nummer;
      const tekst = invoer.value.trim();
      if (tekst.length < 2) return sluit();
      try {
        const resultaten = await api(`/api/zoek?q=${encodeURIComponent(tekst)}`);
        if (volgnummer !== nummer) return;
        lijst.replaceChildren();
        for (const r of resultaten) {
          const li = document.createElement("li");
          const knop = document.createElement("button");
          knop.type = "button";
          knop.textContent = r.naam;
          knop.addEventListener("click", () => kies(r));
          li.append(knop);
          lijst.append(li);
        }
        lijst.hidden = resultaten.length === 0;
      } catch (fout) {
        toon(fout.message);
      }
    }, 250);
  });
  $("zoek-form").addEventListener("submit", (e) => {
    e.preventDefault();
    lijst.querySelector("button")?.click();
  });
  invoer.addEventListener("keydown", (e) => e.key === "Escape" && sluit());
  document.addEventListener("click", (e) => !$("zoek-form").contains(e.target) && sluit());
}

function bindOverzicht() {
  for (const [id, letter] of [["zet-a", "A"], ["zet-b", "B"]]) {
    $(id).addEventListener("click", () => {
      staat.zet = staat.zet === letter ? null : letter;
      if (gebied.tekenen) startGebied();
      traceVeranderd();
    });
  }
  $("teken-gebied").addEventListener("click", startGebied);
  $("wis-gebied").addEventListener("click", wisGebied);
  $("open-zicht").addEventListener("click", openZicht);
  bindZoeken();
}

function bindKaart() {
  kaartObj.on("click", (e) => {
    if (staat.zet) zetPunt(e.lngLat);
    else if (gebied.tekenen) {
      gebied.punten.push([e.lngLat.lng, e.lngLat.lat]);
      gebiedBijwerken();
    }
  });
  kaartObj.on("dblclick", () => gebied.tekenen && rondGebiedAf());
  kaartObj.on("mousemove", (e) => {
    $("status").textContent = `${nl(e.lngLat.lat, 5)} N, ${nl(e.lngLat.lng, 5)} O · kantel ${nl(kaartObj.getPitch(), 0)}°`;
  });
}

async function startKaart() {
  registreerTegelprotocol();
  const catalogus = await api("/api/lagen");
  kaartObj = new maplibregl.Map({
    container: "kaart",
    style: maakStijl(catalogus.lagen),
    center: [5.29, 52.13],
    zoom: 7,
    minZoom: 6,
    maxZoom: 20,
    maxPitch: 80,
    renderWorldCopies: false,
    maxBounds: [[2.0, 50.3], [8.4, 54.0]],
    attributionControl: { compact: true },
  });
  kaartObj.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
  kaartObj.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");
  bouwLagenpaneel(catalogus);
  await new Promise((klaar) => kaartObj.on("load", klaar));
  voegTekenlagenToe();
  bindKaart();
}

/* ---------- 0-zicht ---------- */

const zicht = { uc: 0, hy: 0, pm: 16, w: 1, h: 1 };

const zx = (u) => zicht.w / 2 + (u - zicht.uc) * zicht.pm;
const zy = (diepte) => zicht.hy + diepte * zicht.pm;
const zuVan = (sx) => zicht.uc + (sx - zicht.w / 2) / zicht.pm;
const zdVan = (sy) => (sy - zicht.hy) / zicht.pm;

function herstelZicht() {
  zicht.pm = Math.max(4, zicht.w / 66);
  zicht.uc = 0;
  zicht.hy = zicht.h / 2;
}

function beperkZicht() {
  zicht.uc = Math.min(32, Math.max(-32, zicht.uc));
  const laag = zicht.h - DIEPTE_M * zicht.pm - 20;
  zicht.hy = Math.min(zicht.h - 40, Math.max(Math.min(laag, zicht.h / 2), zicht.hy));
}

function leidingenLijst() {
  return [...staat.bestaand, ...staat.nieuwe];
}

function positie(leiding) {
  if (staat.sleep?.id === leiding.id) return [leiding.u, leiding.diepte];
  const p = staat.posities[leiding.id];
  return p ? [p.u, p.diepte] : [leiding.u, leiding.diepte];
}

const straalVan = (leiding) => staat.typen[leiding.type_id].diameter_m / 2;
const SOORT_VOLGORDE = { leiding: 0, buis: 1, kabel: 2 };

function tekenvolgorde() {
  return leidingenLijst().sort((p, q) => SOORT_VOLGORDE[staat.typen[p.type_id].soort] - SOORT_VOLGORDE[staat.typen[q.type_id].soort]);
}

function raak(sx, sy) {
  for (const leiding of tekenvolgorde().reverse()) {
    const [u, d] = positie(leiding);
    const afstand = Math.hypot(sx - zx(u), sy - zy(d));
    if (afstand <= Math.max(straalVan(leiding) * zicht.pm, 7)) return leiding;
  }
  return null;
}

function tekenLagen(ctx, p) {
  const v = p.venster;
  const aantal = Math.round((v.u_max - v.u_min) / v.stap) + 1;
  const us = [-500, ...Array.from({ length: aantal }, (_, i) => v.u_min + i * v.stap), 500];
  const uitbreiden = (waarden) => [waarden[0], ...waarden, waarden[waarden.length - 1]];
  let boven = us.map(() => 0);
  for (const laag of p.lagen) {
    const onder = uitbreiden(laag.onderkant);
    if (onder.some((d, i) => d - boven[i] > 0.001)) {
      ctx.beginPath();
      us.forEach((u, i) => (i ? ctx.lineTo(zx(u), zy(boven[i])) : ctx.moveTo(zx(u), zy(boven[i]))));
      for (let i = us.length - 1; i >= 0; i--) ctx.lineTo(zx(us[i]), zy(onder[i]));
      ctx.closePath();
      ctx.fillStyle = laag.kleur;
      ctx.fill();
    }
    laag.pad = onder;
    boven = onder;
  }
  const verloop = ctx.createLinearGradient(0, zy(0), 0, zy(DIEPTE_M));
  verloop.addColorStop(0, "rgba(0,0,0,0)");
  verloop.addColorStop(1, "rgba(0,0,0,0.62)");
  ctx.fillStyle = verloop;
  ctx.fillRect(0, zy(0), zicht.w, DIEPTE_M * zicht.pm);
  ctx.fillStyle = "rgba(70, 110, 140, 0.24)";
  ctx.fillRect(0, zy(p.grondwater), zicht.w, (DIEPTE_M - p.grondwater) * zicht.pm);
  ctx.strokeStyle = "rgba(0,0,0,0.35)";
  ctx.lineWidth = 1;
  for (const laag of p.lagen.slice(0, -1)) {
    ctx.beginPath();
    us.forEach((u, i) => (i ? ctx.lineTo(zx(u), zy(laag.pad[i])) : ctx.moveTo(zx(u), zy(laag.pad[i]))));
    ctx.stroke();
  }
  tekenLaaglabels(ctx, p, us);
  ctx.setLineDash([6, 4]);
  ctx.strokeStyle = "rgba(140, 190, 230, 0.85)";
  ctx.beginPath();
  ctx.moveTo(0, zy(p.grondwater));
  ctx.lineTo(zicht.w, zy(p.grondwater));
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = "rgba(140, 190, 230, 0.95)";
  ctx.font = "11px system-ui, sans-serif";
  ctx.textAlign = "right";
  ctx.fillText(`grondwater ${nl(p.grondwater, 1)} m`, zicht.w - 10, zy(p.grondwater) - 4);
}

function tekenLaaglabels(ctx, p, us) {
  const u = zuVan(76);
  const index = us.findIndex((waarde) => waarde >= u);
  if (index < 0) return;
  ctx.font = "11px system-ui, sans-serif";
  ctx.textAlign = "left";
  ctx.fillStyle = "rgba(255,255,255,0.72)";
  let boven = 0;
  for (const laag of p.lagen) {
    const onder = laag.pad[index];
    const hoogte = (onder - boven) * zicht.pm;
    const midden = zy((onder + boven) / 2);
    if (hoogte > 18 && midden > 8 && midden < zicht.h - 8) ctx.fillText(laag.naam, 56, midden + 4);
    boven = onder;
  }
}

function tekenSloot(ctx, sloot) {
  const m = sloot.u_midden;
  const bb = sloot.breedte_boven / 2;
  const bo = sloot.breedte_bodem / 2;
  const trapezium = (diepte) => bb + ((bo - bb) * diepte) / sloot.diepte;
  ctx.beginPath();
  ctx.moveTo(zx(m - bb), zy(0));
  ctx.lineTo(zx(m - bo), zy(sloot.diepte));
  ctx.lineTo(zx(m + bo), zy(sloot.diepte));
  ctx.lineTo(zx(m + bb), zy(0));
  ctx.closePath();
  ctx.fillStyle = SKY_ONDER;
  ctx.fill();
  const water = trapezium(sloot.waterpeil);
  ctx.save();
  ctx.beginPath();
  ctx.moveTo(zx(m - water), zy(sloot.waterpeil));
  ctx.lineTo(zx(m - bo), zy(sloot.diepte));
  ctx.lineTo(zx(m + bo), zy(sloot.diepte));
  ctx.lineTo(zx(m + water), zy(sloot.waterpeil));
  ctx.closePath();
  ctx.fillStyle = "rgba(70, 120, 160, 0.85)";
  ctx.fill();
  ctx.clip();
  ctx.strokeStyle = "rgba(200, 225, 245, 0.55)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let x = zx(m - bb) - 80; x < zx(m + bb) + 80; x += 7) {
    ctx.moveTo(x, zy(sloot.diepte) + 30);
    ctx.lineTo(x + 60, zy(sloot.waterpeil) - 30);
  }
  ctx.stroke();
  ctx.restore();
}

function tekenBovengrond(ctx, g) {
  const horizon = zy(0);
  const { weg, huis, lantaarn } = g;
  ctx.beginPath();
  ctx.moveTo(zx(weg.teen_l), horizon);
  ctx.lineTo(zx(weg.kruin0), horizon - weg.hoogte * zicht.pm);
  ctx.lineTo(zx(weg.kruin1), horizon - weg.hoogte * zicht.pm);
  ctx.lineTo(zx(weg.teen_r), horizon);
  ctx.closePath();
  ctx.fillStyle = "#6a5844";
  ctx.fill();
  ctx.fillStyle = "#26272a";
  ctx.fillRect(zx(weg.kruin0), horizon - (weg.hoogte + weg.asfalt) * zicht.pm, (weg.kruin1 - weg.kruin0) * zicht.pm, weg.asfalt * zicht.pm);
  const wegtop = weg.hoogte + weg.asfalt;
  ctx.fillStyle = "#2a2c30";
  ctx.fillRect(zx(lantaarn.u) - 0.06 * zicht.pm, horizon - (wegtop + lantaarn.hoogte) * zicht.pm, 0.12 * zicht.pm, lantaarn.hoogte * zicht.pm);
  ctx.fillRect(zx(lantaarn.u) - 1.1 * zicht.pm, horizon - (wegtop + lantaarn.hoogte) * zicht.pm, 1.2 * zicht.pm, 0.1 * zicht.pm);
  ctx.fillStyle = "#e8d9a8";
  ctx.fillRect(zx(lantaarn.u) - 1.1 * zicht.pm, horizon - (wegtop + lantaarn.hoogte - 0.1) * zicht.pm, 0.5 * zicht.pm, 0.1 * zicht.pm);

  ctx.fillStyle = "#9a9a94";
  for (const gevel of [huis.u0, huis.u1]) {
    ctx.fillRect(zx(gevel - huis.fundering_breedte / 2), horizon, huis.fundering_breedte * zicht.pm, huis.fundering_diepte * zicht.pm);
  }
  const breedte = (huis.u1 - huis.u0) * zicht.pm;
  ctx.fillStyle = "#7a5a48";
  ctx.fillRect(zx(huis.u0), horizon - huis.goot * zicht.pm, breedte, huis.goot * zicht.pm);
  ctx.beginPath();
  ctx.moveTo(zx(huis.u0 - 0.4), horizon - huis.goot * zicht.pm);
  ctx.lineTo(zx((huis.u0 + huis.u1) / 2), horizon - huis.nok * zicht.pm);
  ctx.lineTo(zx(huis.u1 + 0.4), horizon - huis.goot * zicht.pm);
  ctx.closePath();
  ctx.fillStyle = "#3b3532";
  ctx.fill();
  ctx.fillStyle = "#c9d2d8";
  for (const [u, onder, hoogte] of [[huis.u0 + 1.2, 1.0, 1.3], [huis.u1 - 2.4, 1.0, 1.3], [huis.u0 + 1.2, 3.4, 1.3], [huis.u1 - 2.4, 3.4, 1.3]]) {
    ctx.fillRect(zx(u), horizon - (onder + hoogte) * zicht.pm, 1.2 * zicht.pm, hoogte * zicht.pm);
  }
}

function tekenLeiding(ctx, leiding) {
  const type = staat.typen[leiding.type_id];
  const [u, d] = positie(leiding);
  const x = zx(u);
  const y = zy(d);
  const straal = type.diameter_m / 2 * zicht.pm;
  const fout = staat.meldingen.some((m) => m.niveau === "fout" && m.leiding_ids.includes(leiding.id));
  if (straal < 5) {
    ctx.strokeStyle = fout ? "#ff6b66" : "rgba(238, 230, 217, 0.7)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(x, y, 5, 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.beginPath();
  ctx.arc(x, y, Math.max(straal, 0.8), 0, Math.PI * 2);
  if (type.soort === "buis") {
    ctx.strokeStyle = type.kleur;
    ctx.lineWidth = Math.max(1.5, 0.012 * zicht.pm);
    ctx.fillStyle = "rgba(20, 22, 25, 0.55)";
    ctx.fill();
    ctx.stroke();
  } else {
    ctx.fillStyle = type.kleur;
    ctx.fill();
    ctx.strokeStyle = "rgba(238, 230, 217, 0.5)";
    ctx.lineWidth = 1;
    ctx.stroke();
  }
  if (type.kern && straal > 6) {
    ctx.beginPath();
    ctx.arc(x, y, straal * 0.55, 0, Math.PI * 2);
    ctx.fillStyle = type.kern;
    ctx.fill();
  }
  if (leiding.nieuw || fout || staat.geselecteerd === leiding.id) {
    ctx.beginPath();
    ctx.arc(x, y, Math.max(straal, 3) + 3, 0, Math.PI * 2);
    ctx.setLineDash(leiding.nieuw ? [3, 3] : []);
    ctx.strokeStyle = fout ? "#ff6b66" : staat.geselecteerd === leiding.id ? "#ffffff" : "#d4a572";
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.setLineDash([]);
  }
}

function kiesStap(pm, minimum) {
  return [0.1, 0.2, 0.5, 1, 2, 5, 10, 20].find((stap) => stap * pm >= minimum) ?? 20;
}

function tekenLinialen(ctx) {
  ctx.font = "11px system-ui, sans-serif";
  ctx.fillStyle = "rgba(14, 18, 22, 0.72)";
  ctx.fillRect(0, 0, 44, zicht.h);
  ctx.fillRect(0, 0, zicht.w, 20);
  ctx.fillStyle = "#eee6d9";
  ctx.strokeStyle = "rgba(238, 230, 217, 0.6)";
  ctx.textAlign = "right";
  const stapD = kiesStap(zicht.pm, 36);
  for (let d = 0; d <= DIEPTE_M + 1e-9; d += stapD) {
    const y = zy(d);
    if (y < 24 || y > zicht.h - 4) continue;
    ctx.beginPath();
    ctx.moveTo(36, y);
    ctx.lineTo(44, y);
    ctx.stroke();
    ctx.fillText(`${nl(d, stapD < 1 ? 1 : 0)} m`, 33, y + 4);
  }
  ctx.textAlign = "center";
  const stapU = kiesStap(zicht.pm, 60);
  const begin = Math.ceil(zuVan(70) / stapU) * stapU;
  for (let u = begin; zx(u) < zicht.w; u += stapU) {
    ctx.beginPath();
    ctx.moveTo(zx(u), 12);
    ctx.lineTo(zx(u), 20);
    ctx.stroke();
    ctx.fillText(`${nl(u, stapU < 1 ? 1 : 0)} m`, zx(u), 10);
  }
  ctx.textAlign = "left";
  ctx.fillText("diepte", 6, 14);
}

function tekenSpook(ctx) {
  const type = staat.typen[staat.gereedschap];
  if (!type || !staat.cursor || staat.sleep) return;
  const [sx, sy] = staat.cursor;
  ctx.beginPath();
  ctx.arc(sx, sy, Math.max(type.diameter_m / 2 * zicht.pm, 4), 0, Math.PI * 2);
  ctx.strokeStyle = "#d4a572";
  ctx.setLineDash([3, 3]);
  ctx.stroke();
  ctx.setLineDash([]);
}

function tekenZicht() {
  const { ctx, w, h } = maatCanvas($("zicht"));
  zicht.w = w;
  zicht.h = h;
  const p = staat.profiel;
  if (!p) return;
  beperkZicht();
  const lucht = ctx.createLinearGradient(0, 0, 0, Math.max(zy(0), 1));
  lucht.addColorStop(0, "#0e1216");
  lucht.addColorStop(1, SKY_ONDER);
  ctx.fillStyle = lucht;
  ctx.fillRect(0, 0, w, h);
  tekenLagen(ctx, p);
  tekenSloot(ctx, p.bovengrond.sloot);
  tekenBovengrond(ctx, p.bovengrond);
  ctx.strokeStyle = "rgba(238, 230, 217, 0.5)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, zy(0));
  ctx.lineTo(w, zy(0));
  ctx.stroke();
  for (const leiding of tekenvolgorde()) tekenLeiding(ctx, leiding);
  tekenSpook(ctx);
  tekenLinialen(ctx);
}

/* ---------- 0-zicht: gegevens, checks en checklist ---------- */

async function laadProfiel(s) {
  const t = trace();
  const vraag = new URLSearchParams({ ...t, s });
  const profiel = await api(`/api/profiel?${vraag}`);
  staat.s = s;
  staat.profiel = profiel;
  staat.typen = Object.fromEntries(profiel.bibliotheek.map((type) => [type.id, type]));
  staat.bestaand = profiel.leidingen;
  staat.posities = profiel.posities;
}

async function controleer() {
  const nummer = ++staat.controleNr;
  const lijst = leidingenLijst().map((l) => ({
    id: l.id, type_id: l.type_id, u: l.u, diepte: l.diepte, nieuw: Boolean(l.nieuw), buis_id: l.buis_id ?? null,
  }));
  try {
    const antwoord = await api("/api/controle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...trace(), s: staat.s, leidingen: lijst }),
    });
    if (nummer !== staat.controleNr) return;
    staat.meldingen = antwoord.meldingen;
    staat.posities = antwoord.posities;
    staat.checkstatus = antwoord.checklist;
  } catch (fout) {
    toon(fout.message);
  }
  tekenZicht();
  toonMeldingen();
  toonChecklist();
}

function toonMeldingen() {
  const doos = $("meldingen");
  doos.replaceChildren();
  const unieke = [...new Map(staat.meldingen.map((m) => [m.code + m.tekst, m])).values()];
  const kaarten = unieke.length
    ? unieke
    : [{ niveau: "goed", tekst: staat.nieuwe.length ? "Geen problemen gevonden." : "Kies een leiding bij Tools en klik in de grond." }];
  for (const m of kaarten) {
    const kaart = document.createElement("div");
    kaart.className = `melding ${m.niveau}`;
    kaart.textContent = m.tekst;
    doos.append(kaart);
  }
  $("vlak").classList.toggle("fout", staat.meldingen.some((m) => m.niveau === "fout"));
}

function toonChecklist() {
  const punten = staat.profiel?.checklist ?? [];
  const lijst = $("checklist");
  lijst.replaceChildren();
  let klaar = 0;
  for (const punt of punten) {
    const item = document.createElement("li");
    const tekst = document.createElement("span");
    tekst.innerHTML = "";
    tekst.append(punt.tekst);
    const bron = document.createElement("small");
    bron.textContent = punt.bron;
    tekst.append(bron);
    if (punt.auto.length) {
      const status = staat.checkstatus[punt.id] ?? "open";
      const stip = document.createElement("span");
      stip.className = `stip ${status}`;
      stip.title = { open: "Nog niet getoetst", ok: "Voldoet", fout: "Voldoet niet" }[status];
      item.append(stip, tekst);
      if (status === "ok") klaar++;
    } else {
      const vink = document.createElement("input");
      vink.type = "checkbox";
      vink.checked = Boolean(staat.gereed[punt.id]);
      vink.setAttribute("aria-label", punt.tekst);
      vink.addEventListener("change", () => {
        staat.gereed[punt.id] = vink.checked;
        bewaarGereed();
        toonChecklist();
      });
      item.append(vink, tekst);
      if (vink.checked) klaar++;
    }
    lijst.append(item);
  }
  $("checklist-teller").textContent = `${klaar} van ${punten.length}`;
}

function bouwTools() {
  const doos = $("tools");
  doos.replaceChildren();
  const knop = (id, naam, kleur) => {
    const b = document.createElement("button");
    b.type = "button";
    b.dataset.id = id;
    if (kleur) {
      const bol = document.createElement("i");
      bol.style.background = kleur;
      b.append(bol);
    }
    b.append(naam);
    b.addEventListener("click", () => kiesGereedschap(id));
    return b;
  };
  doos.append(knop("selecteer", "Selecteren"), knop("verwijder", "Verwijderen"));
  const groepen = [["kabel", "Kabels"], ["buis", "Buizen"]];
  for (const [soort, titel] of groepen) {
    const kop = document.createElement("h3");
    kop.textContent = titel;
    doos.append(kop);
    for (const type of Object.values(staat.typen).filter((t) => t.soort === soort && t.plaatsbaar)) {
      const korteNaam = soort === "kabel" ? `${type.naam.match(/\d+ mm²/)[0]}` : `Ø ${Math.round(type.diameter_m * 1000)} mm`;
      const b = knop(type.id, korteNaam, soort === "kabel" ? type.kern : type.kleur);
      b.title = `${type.naam} · Ø ${Math.round(type.diameter_m * 1000)} mm`;
      doos.append(b);
    }
  }
  kiesGereedschap("selecteer");
}

function kiesGereedschap(id) {
  staat.gereedschap = id;
  for (const b of $("tools").querySelectorAll("button")) b.classList.toggle("actief", b.dataset.id === id);
  $("zicht").style.cursor = id === "selecteer" ? "default" : "crosshair";
  tekenZicht();
}

/* ---------- 0-zicht: bewerken ---------- */

const snap = (waarde) => Math.round(waarde * 20) / 20;

function bepaalBuis(leiding) {
  if (staat.typen[leiding.type_id].soort !== "kabel") return null;
  const [u, d] = positie(leiding);
  const buis = leidingenLijst().find((l) => {
    if (l.id === leiding.id || staat.typen[l.type_id].soort !== "buis") return false;
    const [bu, bd] = positie(l);
    return Math.hypot(u - bu, d - bd) < straalVan(l);
  });
  return buis?.id ?? null;
}

function plaats(sx, sy) {
  const type = staat.typen[staat.gereedschap];
  const leiding = {
    id: `nieuw-${++staat.teller}`, type_id: type.id, u: snap(zuVan(sx)), diepte: Math.max(0, snap(zdVan(sy))),
    nieuw: true, buis_id: null,
  };
  leiding.buis_id = bepaalBuis(leiding);
  staat.nieuwe.push(leiding);
  staat.geselecteerd = leiding.id;
  controleer();
}

function verwijder(id) {
  staat.nieuwe = staat.nieuwe.filter((l) => l.id !== id && l.buis_id !== id);
  if (staat.geselecteerd === id) staat.geselecteerd = null;
  controleer();
}

function statusTekst(sx, sy) {
  const leiding = raak(sx, sy);
  if (leiding) {
    const type = staat.typen[leiding.type_id];
    const [u, d] = positie(leiding);
    const wie = leiding.nieuw ? "nieuw" : "bestaand";
    return `${type.naam} (${wie}) · Ø ${Math.round(type.diameter_m * 1000)} mm · u ${nl(u)} m · diepte ${nl(d)} m`;
  }
  return `u ${nl(zuVan(sx))} m · ${zdVan(sy) >= 0 ? "diepte" : "hoogte"} ${nl(Math.abs(zdVan(sy)))} m`;
}

function bindZicht() {
  const canvas = $("zicht");
  let actie = null;
  let wacht = null;
  canvas.addEventListener("pointerdown", (e) => {
    canvas.setPointerCapture(e.pointerId);
    const [sx, sy] = aanwijzer(canvas, e);
    const leiding = raak(sx, sy);
    actie = { sx, sy, bewogen: false, soort: "pan", leiding };
    if (staat.gereedschap === "selecteer") {
      staat.geselecteerd = leiding?.id ?? null;
      if (leiding?.nieuw) {
        actie.soort = "sleep";
        staat.sleep = { id: leiding.id };
      }
    } else {
      actie.soort = "klik";
    }
    tekenZicht();
  });
  canvas.addEventListener("pointermove", (e) => {
    const [sx, sy] = aanwijzer(canvas, e);
    staat.cursor = [sx, sy];
    $("status").textContent = statusTekst(sx, sy);
    if (actie) {
      if (Math.hypot(sx - actie.sx, sy - actie.sy) > 4) actie.bewogen = true;
      if (actie.soort === "sleep") {
        const leiding = actie.leiding;
        leiding.u = snap(zuVan(sx));
        leiding.diepte = Math.max(0, snap(zdVan(sy)));
        leiding.buis_id = bepaalBuis(leiding);
        clearTimeout(wacht);
        wacht = setTimeout(controleer, 60);
      } else if (actie.bewogen) {
        zicht.uc -= (sx - actie.sx) / zicht.pm;
        zicht.hy += sy - actie.sy;
        actie.sx = sx;
        actie.sy = sy;
      }
    }
    tekenZicht();
  });
  canvas.addEventListener("pointerup", (e) => {
    const [sx, sy] = aanwijzer(canvas, e);
    if (actie?.soort === "sleep") {
      staat.sleep = null;
      controleer();
    } else if (actie && !actie.bewogen && staat.gereedschap === "verwijder") {
      if (actie.leiding?.nieuw) verwijder(actie.leiding.id);
      else if (actie.leiding) toon("Bestaande leidingen kunnen niet worden verwijderd.");
    } else if (actie && !actie.bewogen && staat.typen[staat.gereedschap]) {
      plaats(sx, sy);
    }
    actie = null;
    tekenZicht();
  });
  canvas.addEventListener("pointerleave", () => {
    staat.cursor = null;
    tekenZicht();
  });
  canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    const [sx, sy] = aanwijzer(canvas, e);
    const u = zuVan(sx);
    const d = zdVan(sy);
    zicht.pm = Math.min(600, Math.max(4, zicht.pm * Math.exp(-e.deltaY * 0.0015)));
    zicht.uc = u - (sx - zicht.w / 2) / zicht.pm;
    zicht.hy = sy - d * zicht.pm;
    tekenZicht();
  }, { passive: false });
  window.addEventListener("keydown", (e) => {
    if (staat.weergave !== "zicht" || e.target.tagName === "INPUT") return;
    if (e.key === "Escape") kiesGereedschap("selecteer");
    const leiding = staat.nieuwe.find((l) => l.id === staat.geselecteerd);
    if ((e.key === "Delete" || e.key === "Backspace") && leiding) verwijder(leiding.id);
  });
  $("herstel").addEventListener("click", () => {
    herstelZicht();
    tekenZicht();
  });
  let vertraging = null;
  $("positie-schuif").addEventListener("input", (e) => {
    $("positie-waarde").textContent = `${e.target.value} m`;
    clearTimeout(vertraging);
    vertraging = setTimeout(async () => {
      try {
        await laadProfiel(Number(e.target.value));
        await controleer();
        toonInfo();
      } catch (fout) {
        toon(fout.message);
      }
    }, 150);
  });
}

function toonInfo() {
  const p = staat.profiel;
  $("balk-info").textContent =
    `${p.zone} · grondwater ${nl(p.grondwater, 1)} m onder maaiveld · je kijkt langs het tracé naar A (azimut ${nl(p.trace.azimut, 0)}°) · voorbeelddata`;
}

/* ---------- weergave wisselen ---------- */

async function openZicht() {
  if (!trace()) return;
  try {
    const lengte = traceLengte();
    await laadProfiel(Math.round(lengte / 2 / 10) * 10);
    const schuif = $("positie-schuif");
    schuif.max = Math.floor(lengte);
    schuif.value = staat.s;
    $("positie-waarde").textContent = `${staat.s} m`;
  } catch (fout) {
    toon(fout.message);
    return;
  }
  zetWeergave("zicht");
  bouwTools();
  herstelZicht();
  toonInfo();
  await controleer();
}

function zetWeergave(naam) {
  staat.weergave = naam;
  const zichtActief = naam === "zicht";
  $("kaart").hidden = zichtActief;
  $("zoek-form").hidden = zichtActief;
  $("zicht").hidden = !zichtActief;
  $("paneel-overzicht").hidden = zichtActief;
  $("paneel-zicht").hidden = !zichtActief;
  $("positie").hidden = !zichtActief;
  $("tab-overzicht").setAttribute("aria-pressed", !zichtActief);
  $("tab-zicht").setAttribute("aria-pressed", zichtActief);
  $("status").textContent = "";
  $("meldingen").replaceChildren();
  $("vlak").classList.remove("fout");
  if (!zichtActief) {
    $("balk-info").textContent = OVERZICHT_INFO;
    kaartObj?.resize();
  }
}

async function start() {
  staat.gereed = leesGereed();
  bindOverzicht();
  bindZicht();
  $("tab-overzicht").addEventListener("click", () => zetWeergave("overzicht"));
  $("tab-zicht").addEventListener("click", openZicht);
  new ResizeObserver(() => (staat.weergave === "zicht" ? tekenZicht() : kaartObj?.resize())).observe($("vlak"));
  $("balk-info").textContent = OVERZICHT_INFO;
  try {
    await startKaart();
  } catch (fout) {
    toon(fout.message);
  }
}

start();

"use strict";

/* GR0ND kaartpagina: overzichtskaart (MapLibre met PDOK-lagen) en het 3D-blok van het projectgebied. */

const $ = (id) => document.getElementById(id);

const OVERZICHT_INFO = "Kantelen en draaien: sleep met de rechtermuisknop. Teken een gebied en open het 3D-blok.";

const staat = {
  weergave: "overzicht",
  trace: { ll: [], rd: [], tekenen: false },
};

/* ---------- hulpfuncties ---------- */

const nl = (getal, cijfers = 2) => getal.toFixed(cijfers).replace(".", ",");

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
  const t = staat.trace;
  return !t.tekenen && t.rd.length >= 2 ? { punten: t.rd } : null;
}

function traceLengte() {
  const rd = staat.trace.rd;
  return rd.slice(1).reduce((som, p, i) => som + Math.hypot(p[0] - rd[i][0], p[1] - rd[i][1]), 0);
}

/* ---------- overzichtskaart (MapLibre met PDOK-lagen) ---------- */

let kaartObj = null;
const markers = {};
const gebied = { punten: [], tekenen: false, klaar: false };
const leegGeo = () => ({ type: "FeatureCollection", features: [] });

const LEGE_TEGEL = Uint8Array.from(
  atob("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="),
  (c) => c.charCodeAt(0),
).buffer;
const WERELD_M = 40075016.68;

function tegelGrens(adres) {
  const bbox = /bbox=([-\d.]+),([-\d.]+),([-\d.]+),([-\d.]+)/.exec(adres);
  if (bbox) return bbox.slice(1, 5).map(Number);
  const z = Number(/tilematrix=(\d+)/.exec(adres)[1]);
  const x = Number(/tilecol=(\d+)/.exec(adres)[1]);
  const y = Number(/tilerow=(\d+)/.exec(adres)[1]);
  const maat = WERELD_M / 2 ** z;
  const x0 = -WERELD_M / 2 + x * maat;
  const y1 = WERELD_M / 2 - y * maat;
  return [x0, y1 - maat, x0 + maat, y1];
}

function buitenProject(adres) {
  const g = projecten.grens3857;
  if (!g) return false;
  const [x0, y0, x1, y1] = tegelGrens(adres);
  return x1 < g[0] || x0 > g[2] || y1 < g[1] || y0 > g[3];
}

function registreerTegelprotocol() {
  // Buiten het open project halen we geen tegels op: de kaart is daar toch donker.
  // PDOK-WMTS verwacht soms een tegelmatrix met voorloopnul ("07"); we proberen beide.
  maplibregl.addProtocol("pdok", async (params, afbreken) => {
    const adres = params.url.replace("pdok://", "https://");
    if (buitenProject(adres)) return { data: LEGE_TEGEL };
    const matrix = /tilematrix=(\d+)/.exec(adres)?.[1];
    const versies = matrix ? [matrix.padStart(2, "0"), matrix] : [null];
    for (const waarde of versies) {
      const url = waarde === null ? adres : adres.replace(/tilematrix=\d+/, `tilematrix=${waarde}`);
      const antwoord = await fetch(url, { signal: afbreken.signal });
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
    id: "trace-lijn", type: "line", source: "trace", filter: ["!=", "$type", "Point"],
    paint: { "line-color": "#ffffff", "line-width": 3, "line-dasharray": [2, 1.5] },
  });
  kaartObj.addLayer({
    id: "trace-punten", type: "circle", source: "trace", filter: ["==", "$type", "Point"],
    paint: { "circle-radius": 5, "circle-color": "#ffffff", "circle-stroke-color": "#1a140d", "circle-stroke-width": 2 },
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
  $("tab-blok").disabled = !gebied.klaar;
  const info = $("gebied-info");
  if (gebied.klaar) info.textContent = `Gebied van ${toonOppervlak(oppervlakM2(p))}, ${p.length} hoekpunten.`;
  else if (gebied.tekenen) info.textContent = `${p.length} punten. Dubbelklik om af te ronden.`;
  else info.textContent = "Klik punten op de kaart. Dubbelklik om af te ronden.";
  $("teken-gebied").setAttribute("aria-pressed", gebied.tekenen);
  $("wis-gebied").disabled = p.length === 0;
  if (typeof bewaarKnopBijwerken === "function") bewaarKnopBijwerken();
  updateCursor();
}

function updateCursor() {
  kaartObj.getCanvas().style.cursor = staat.trace.tekenen || gebied.tekenen ? "crosshair" : "";
}

function startGebied() {
  gebied.punten = [];
  gebied.klaar = false;
  gebied.tekenen = !gebied.tekenen;
  if (gebied.tekenen && staat.trace.tekenen) wisTrace();
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
  const ll = staat.trace.ll;
  const eind = ll.length > 1 ? ll.at(-1) : null;
  for (const [letter, punt] of [["A", ll[0]], ["B", eind]]) {
    markers[letter] ??= maakMarker(letter);
    if (punt) markers[letter].setLngLat(punt).addTo(kaartObj);
    else markers[letter].remove();
  }
  const features = ll.slice(1, -1).map((c) => ({ type: "Feature", properties: {}, geometry: { type: "Point", coordinates: c } }));
  if (ll.length >= 2) features.push({ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: ll } });
  kaartObj.getSource("trace").setData({ type: "FeatureCollection", features });
}

function voegTracepunt(lngLat) {
  staat.trace.ll.push([lngLat.lng, lngLat.lat]);
  staat.trace.rd = [];
  traceVeranderd();
}

async function rondTraceAf() {
  const t = staat.trace;
  if (t.ll.length < 2) return toon("Zet minstens twee punten voor een tracé.");
  try {
    const paren = t.ll.map(([lon, lat]) => `${lon},${lat}`).join(";");
    t.rd = (await api(`/api/rd?punten=${encodeURIComponent(paren)}`)).punten;
    t.tekenen = false;
  } catch (fout) {
    return toon(fout.message);
  }
  traceVeranderd();
}

function startTrace() {
  const t = staat.trace;
  t.tekenen = !t.tekenen;
  if (t.tekenen) {
    t.rd = [];
    if (gebied.tekenen) startGebied();
    kaartObj.doubleClickZoom.disable();
  } else {
    kaartObj.doubleClickZoom.enable();
  }
  traceVeranderd();
}

function laatstePuntWeg() {
  const t = staat.trace;
  t.ll.pop();
  t.rd = [];
  t.tekenen = true;
  kaartObj.doubleClickZoom.disable();
  traceVeranderd();
}

function wisTrace() {
  staat.trace = { ll: [], rd: [], tekenen: false };
  kaartObj?.doubleClickZoom.enable();
  traceVeranderd();
}

function traceVeranderd() {
  const t = staat.trace;
  const klaar = Boolean(trace());
  const lengte = traceLengte();
  if (klaar) {
    const tekst = lengte >= 1000 ? `${nl(lengte / 1000)} km` : `${nl(lengte, 0)} m`;
    $("trace-info").textContent = `Tracé van ${tekst} met ${t.rd.length - 2} bochten.`;
  } else if (t.tekenen) {
    $("trace-info").textContent = `${t.ll.length} punten. Klik verder, dubbelklik of kies Klaar.`;
  } else {
    $("trace-info").textContent = "Kies Teken tracé en klik de route op de kaart, ook met bochten.";
  }
  $("teken-trace").setAttribute("aria-pressed", t.tekenen);
  $("klaar-trace").disabled = !(t.tekenen && t.ll.length >= 2);
  $("laatste-punt").disabled = t.ll.length === 0;
  $("wis-trace").disabled = t.ll.length === 0;
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
  $("teken-trace").addEventListener("click", startTrace);
  $("klaar-trace").addEventListener("click", rondTraceAf);
  $("laatste-punt").addEventListener("click", laatstePuntWeg);
  $("wis-trace").addEventListener("click", wisTrace);
  $("teken-gebied").addEventListener("click", startGebied);
  $("wis-gebied").addEventListener("click", wisGebied);
  bindZoeken();
}

function bindKaart() {
  kaartObj.on("click", (e) => {
    if (staat.trace.tekenen) voegTracepunt(e.lngLat);
    else if (gebied.tekenen) {
      gebied.punten.push([e.lngLat.lng, e.lngLat.lat]);
      gebiedBijwerken();
    }
  });
  kaartObj.on("dblclick", () => {
    if (staat.trace.tekenen) {
      staat.trace.ll.pop();
      rondTraceAf();
    } else if (gebied.tekenen) rondGebiedAf();
  });
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
  voegProjectlagenToe();
  bindKaart();
  bindProjecten();
  await laadProjecten();
}

/* ---------- weergave wisselen ---------- */

function zetWeergave(naam) {
  staat.weergave = naam;
  if (naam !== "blok") {
    blokWeergave?.stop();
    blokWeergave?.annuleerKeuze();
  }
  const blokActief = naam === "blok";
  const overzichtActief = naam === "overzicht";
  $("kaart").hidden = !overzichtActief;
  $("zoek-form").hidden = !overzichtActief;
  $("blok").hidden = !blokActief;
  $("blok-gereedschap").hidden = !blokActief;
  if (!blokActief) $("blok-legenda").hidden = true;
  $("paneel-overzicht").hidden = !overzichtActief;
  $("tab-overzicht").setAttribute("aria-pressed", overzichtActief);
  $("tab-blok").setAttribute("aria-pressed", blokActief);
  $("status").textContent = "";
  if (overzichtActief) {
    $("balk-info").textContent = OVERZICHT_INFO;
    kaartObj?.resize();
  }
}

let blokWeergave = null;

function wachtOpBlokModule() {
  if (window.BlokWeergave) return Promise.resolve();
  return new Promise((klaar) => window.addEventListener("blok-gereed", klaar, { once: true }));
}

async function gebiedInRd() {
  const paren = gebied.punten.map(([lon, lat]) => `${lon},${lat}`).join(";");
  const { punten } = await api(`/api/rd?punten=${encodeURIComponent(paren)}`);
  const xs = punten.map((p) => p[0]);
  const ys = punten.map((p) => p[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

const blokStaat = { heel: null, kiezen: false };
const MIN_STUK_M = 20;

const ECHT_MAX_M = 600; // groter dan dit laden we de PDOK 3D-tiles niet: eerst een stuk uitsnijden

async function haalBlok(bbox) {
  const [x0, y0, x1, y1] = bbox;
  const vraag = `x0=${x0}&y0=${y0}&x1=${x1}&y1=${y1}`;
  const breedte = Math.round(x1 - x0);
  const diepte = Math.round(y1 - y0);
  const echt = Math.max(breedte, diepte) <= ECHT_MAX_M;
  $("balk-info").textContent = "Echte grond (GeoTOP) en netten worden opgehaald…";
  const [data, ondergrond, netten] = await Promise.all([
    api(`/api/blok?${vraag}&n=64`),
    api(`/api/ondergrond?${vraag}`).catch((fout) => (toon(`${fout.message} Wanden: voorbeelddata.`), null)),
    // shortcut: netten alleen in een echt blok (≤ ECHT_MAX_M); groter wordt te zwaar als buizen
    echt ? api(`/api/netten?${vraag}`).catch((fout) => (toon(fout.message), null)) : null,
  ]);
  const schaal = blokWeergave.toon(data, echt, ondergrond);
  if (netten) blokWeergave.zetNetten(netten);
  blokWeergave.zetOndergronds($("blok-onder").getAttribute("aria-pressed") === "true");
  toonBlokLegenda(ondergrond, netten);
  const grond = ondergrond ? "Grond: GeoTOP (TNO)." : "Grond: voorbeelddata.";
  const maat = `3D-blok ${nl(breedte, 0)} × ${nl(diepte, 0)} m. ${grond}`;
  if (echt) {
    const toonInfo = (tekst) => ($("balk-info").textContent = `${maat} ${tekst}`);
    blokWeergave.laadOmgeving(undefined, toonInfo);
    toonInfo("PDOK 3D (gebouwen, terrein) wordt geladen…");
  } else {
    const over = schaal > 1.05 ? ` Hoogte ${nl(schaal, 0)}× overdreven.` : "";
    $("balk-info").textContent = `${maat}${over} Snijd een stuk uit van maximaal ${ECHT_MAX_M} m voor gebouwen en kabels.`;
  }
  blokTraceToevoegen();
}

function legendaRegel(kleur, tekst) {
  const regel = document.createElement("li");
  const vak = document.createElement("span");
  vak.className = "legenda-kleur";
  vak.style.background = kleur;
  regel.append(vak, tekst);
  return regel;
}

/* Legenda met alleen wat in beeld is: grondsoorten op de wanden en de soorten netten. */
function toonBlokLegenda(ondergrond, netten) {
  const legenda = $("blok-legenda");
  legenda.replaceChildren();
  if (ondergrond) {
    const codes = new Set(Object.values(ondergrond.zijden).flatMap((z) => z.kolommen.flatMap((k) => k.lithok)));
    const lijst = document.createElement("ul");
    for (const k of ondergrond.klassen) if (codes.has(k.code)) lijst.append(legendaRegel(k.kleur, k.naam));
    legenda.append(Object.assign(document.createElement("h3"), { textContent: "Grond (GeoTOP)" }), lijst);
  }
  if (netten) {
    const aanwezig = new Set(netten.lagen.filter((l) => l.lijnen.length).map((l) => l.soort));
    const lijst = document.createElement("ul");
    for (const s of netten.soorten) {
      if (aanwezig.has(s.id)) lijst.append(legendaRegel(s.kleur, `${s.naam}, ca. ${nl(s.diepte_m, 1)} m diep`));
    }
    if (!aanwezig.size) lijst.append(legendaRegel("transparent", "Geen open netdata in dit gebied"));
    const bronnen = [...new Set(netten.lagen.filter((l) => l.lijnen.length).map((l) => l.beheerder))].join(", ");
    const bron = Object.assign(document.createElement("p"), { className: "zacht", textContent: `${bronnen ? `Bron: ${bronnen}. ` : ""}${netten.let_op}` });
    legenda.append(Object.assign(document.createElement("h3"), { textContent: "Kabels en leidingen" }), lijst, bron);
  }
  legenda.append(Object.assign(document.createElement("p"), { className: "zacht", textContent: "Lopen: WASD, omhoog/omlaag: E/Q, sneller: Shift." }));
  legenda.hidden = false;
}

const LEIDING_DIEPTE_M = 1.2;

function blokTraceToevoegen() {
  const lengte = blokWeergave.zetTrace(staat.trace.rd, LEIDING_DIEPTE_M);
  const heeft = lengte > 0;
  for (const id of ["blok-volg", "blok-loop", "blok-positie", "blok-meter"]) $(id).hidden = !heeft;
  $("blok-positie").max = Math.floor(lengte);
  $("blok-positie").value = 0;
  $("blok-volg").setAttribute("aria-pressed", false);
  $("blok-loop").setAttribute("aria-pressed", false);
  $("blok-meter").textContent = "";
}

function blokPositieTonen(afstand) {
  $("blok-positie").value = afstand;
  $("blok-meter").textContent = `${nl(afstand, 0)} m`;
}

function blokVolgenZetten(aan) {
  blokWeergave.zetVolgen(aan);
  $("blok-volg").setAttribute("aria-pressed", aan);
  if (aan) blokWeergave.ga(Number($("blok-positie").value));
  if (!aan) {
    blokWeergave.speel(false);
    $("blok-loop").setAttribute("aria-pressed", false);
  }
}

function bindBlokTrace() {
  $("blok-volg").addEventListener("click", () => blokVolgenZetten($("blok-volg").getAttribute("aria-pressed") !== "true"));
  $("blok-positie").addEventListener("input", () => {
    blokVolgenZetten(true);
    blokWeergave.ga(Number($("blok-positie").value));
    blokPositieTonen(Number($("blok-positie").value));
  });
  $("blok-loop").addEventListener("click", () => {
    const aan = $("blok-loop").getAttribute("aria-pressed") !== "true";
    if (aan) blokVolgenZetten(true);
    $("blok-loop").setAttribute("aria-pressed", aan);
    blokWeergave.speel(aan, 10, blokPositieTonen);
  });
}

function blokKiezenZetten(aan) {
  blokStaat.kiezen = aan;
  $("blok-snijd").setAttribute("aria-pressed", aan);
  $("blok-info").textContent = aan ? "Sleep een rechthoek op het gras." : "Draaien: slepen. Zoomen: scrollen.";
}

async function snijStukUit(bbox) {
  blokKiezenZetten(false);
  const [x0, y0, x1, y1] = bbox;
  if (x1 - x0 < MIN_STUK_M || y1 - y0 < MIN_STUK_M) return toon(`Kies een stuk van minstens ${MIN_STUK_M} m.`);
  try {
    await haalBlok(bbox);
    $("blok-heel").disabled = false;
  } catch (fout) {
    toon(fout.message);
  }
}

function bindBlok() {
  bindBlokTrace();
  $("tab-blok").addEventListener("click", openBlok);
  $("blok-onder").addEventListener("click", () => {
    const aan = $("blok-onder").getAttribute("aria-pressed") !== "true";
    $("blok-onder").setAttribute("aria-pressed", aan);
    blokWeergave?.zetOndergronds(aan);
  });
  $("blok-snijd").addEventListener("click", () => {
    if (blokStaat.kiezen) {
      blokWeergave.annuleerKeuze();
      return blokKiezenZetten(false);
    }
    blokKiezenZetten(true);
    blokWeergave.kiesStuk(snijStukUit);
  });
  $("blok-heel").addEventListener("click", async () => {
    $("blok-heel").disabled = true;
    await haalBlok(blokStaat.heel);
  });
}

async function openBlok() {
  if (!gebied.klaar) return toon("Teken eerst een gebied.");
  try {
    await wachtOpBlokModule();
    blokStaat.heel = await gebiedInRd();
    zetWeergave("blok");
    blokWeergave ??= new window.BlokWeergave($("blok"));
    blokKiezenZetten(false);
    $("blok-heel").disabled = true;
    await haalBlok(blokStaat.heel);
  } catch (fout) {
    toon(fout.message);
  }
}

async function start() {
  bindOverzicht();
  $("tab-overzicht").addEventListener("click", () => zetWeergave("overzicht"));
  bindBlok();
  new ResizeObserver(() => kaartObj?.resize()).observe($("vlak"));
  $("balk-info").textContent = OVERZICHT_INFO;
  try {
    await startKaart();
  } catch (fout) {
    toon(fout.message);
  }
}

start();

/* ---------- menubalk: uitklappende panelen ---------- */

function sluitMenus(behalve = null) {
  for (const menu of document.querySelectorAll(".menu")) {
    if (menu === behalve) continue;
    menu.querySelector(".uitklap").hidden = true;
    menu.querySelector("button").setAttribute("aria-expanded", "false");
  }
}

function bindMenus() {
  for (const menu of document.querySelectorAll(".menu")) {
    const knop = menu.querySelector("button");
    const paneel = menu.querySelector(".uitklap");
    knop.addEventListener("click", () => {
      sluitMenus(menu);
      paneel.hidden = !paneel.hidden;
      knop.setAttribute("aria-expanded", String(!paneel.hidden));
    });
  }
  document.addEventListener("pointerdown", (e) => {
    if (!e.target.closest(".menu")) sluitMenus();
  });
  document.addEventListener("keydown", (e) => e.key === "Escape" && sluitMenus());
}

/* ---------- projecten ---------- */

const NEDERLAND_GRENS = [[2.0, 50.3], [8.4, 54.0]];
const projecten = { lijst: [], open: null, grens3857: null, data: null };
const DATA_KLEUREN = { natuur: "#7fb069", erfgoed: "#b07fd0", grondwater: "#4aa3df" };

function middenVan(ring) {
  const lon = ring.reduce((som, p) => som + p[0], 0) / ring.length;
  const lat = ring.reduce((som, p) => som + p[1], 0) / ring.length;
  return [lon, lat];
}

function grensVan(ring) {
  const lons = ring.map((p) => p[0]);
  const lats = ring.map((p) => p[1]);
  return [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]];
}

function projectFeatures(lijst) {
  return lijst.flatMap((p) => {
    const eigenschappen = { id: p.id, naam: p.naam };
    return [
      { type: "Feature", properties: eigenschappen, geometry: { type: "Polygon", coordinates: [[...p.gebied, p.gebied[0]]] } },
      { type: "Feature", properties: eigenschappen, geometry: { type: "Point", coordinates: middenVan(p.gebied) } },
    ];
  });
}

function voegProjectlagenToe() {
  kaartObj.addSource("projecten", { type: "geojson", data: leegGeo() });
  kaartObj.addSource("masker", { type: "geojson", data: leegGeo() });
  kaartObj.addSource("projectdata", { type: "geojson", data: leegGeo() });
  const onder = "gebied-vlak";
  kaartObj.addLayer({
    id: "masker", type: "fill", source: "masker",
    paint: { "fill-color": "#0e1216", "fill-opacity": 0.94 },
  }, onder);
  kaartObj.addLayer({
    id: "projecten-vlak", type: "fill", source: "projecten", minzoom: 9, filter: ["==", "$type", "Polygon"],
    paint: { "fill-color": "#e5ddc7", "fill-opacity": 0.18 },
  }, onder);
  kaartObj.addLayer({
    id: "projecten-rand", type: "line", source: "projecten", minzoom: 9, filter: ["==", "$type", "Polygon"],
    paint: { "line-color": "#e5ddc7", "line-width": 2 },
  }, onder);
  const kleur = ["match", ["get", "categorie"], ...Object.entries(DATA_KLEUREN).flat(), "#e5ddc7"];
  kaartObj.addLayer({
    id: "data-vlak", type: "fill", source: "projectdata", filter: ["==", "$type", "Polygon"],
    paint: { "fill-color": kleur, "fill-opacity": 0.3 },
  }, onder);
  kaartObj.addLayer({
    id: "data-lijn", type: "line", source: "projectdata", filter: ["!=", "$type", "Point"],
    paint: { "line-color": kleur, "line-width": 1.5 },
  }, onder);
  kaartObj.addLayer({
    id: "data-punt", type: "circle", source: "projectdata", filter: ["==", "$type", "Point"],
    paint: { "circle-radius": 4, "circle-color": kleur, "circle-stroke-color": "#0e1216", "circle-stroke-width": 1 },
  }, onder);
  kaartObj.addLayer({
    id: "projecten-punt", type: "circle", source: "projecten", maxzoom: 9, filter: ["==", "$type", "Point"],
    paint: { "circle-radius": 7, "circle-color": "#d4a572", "circle-stroke-color": "#1a140d", "circle-stroke-width": 2 },
  }, onder);
}

async function laadProjecten() {
  try {
    projecten.lijst = await api("/api/projecten");
  } catch (fout) {
    return toon(fout.message);
  }
  toonProjecten();
}

function toonProjecten() {
  kmlKnopBijwerken();
  const zichtbaar = projecten.open ? [] : projecten.lijst;
  kaartObj.getSource("projecten").setData({ type: "FeatureCollection", features: projectFeatures(zichtbaar) });
  const lijst = $("project-lijst");
  lijst.replaceChildren();
  for (const p of projecten.lijst) {
    const rij = document.createElement("li");
    const open = document.createElement("button");
    open.type = "button";
    open.textContent = p.naam;
    open.classList.toggle("actief-project", projecten.open?.id === p.id);
    open.addEventListener("click", () => openProject(p));
    const weg = document.createElement("button");
    weg.type = "button";
    weg.textContent = "Verwijder";
    weg.addEventListener("click", () => verwijderProject(p));
    rij.append(open, weg);
    lijst.append(rij);
  }
  $("sluit-project").disabled = !projecten.open;
  bewaarKnopBijwerken();
}

function bewaarKnopBijwerken() {
  $("bewaar-project").disabled = !(gebied.klaar && $("project-naam").value.trim());
  $("bewaar-project").textContent = projecten.open ? "Werk project bij" : "Bewaar project";
  $("project-info").textContent = projecten.open
    ? `Project "${projecten.open.naam}" is open. Alleen dit gebied wordt getoond.`
    : gebied.klaar ? "Geef een naam en bewaar het gebied." : "Teken eerst een gebied (maximaal 10 × 10 km).";
}

function projectInvoer() {
  return {
    naam: $("project-naam").value.trim(),
    gebied: gebied.punten.filter((c, i, alle) => i === 0 || c.join() !== alle[i - 1].join()),
    trace: staat.trace.ll,
  };
}

async function bewaarProject() {
  const open = projecten.open;
  try {
    const opgeslagen = await api(open ? `/api/projecten/${open.id}` : "/api/projecten", {
      method: open ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(projectInvoer()),
    });
    projecten.lijst = open
      ? projecten.lijst.map((p) => (p.id === opgeslagen.id ? opgeslagen : p))
      : [...projecten.lijst, opgeslagen];
    toon(`Project "${opgeslagen.naam}" bewaard.`);
    openProject(opgeslagen);
  } catch (fout) {
    toon(fout.message);
  }
}

async function verwijderProject(p) {
  try {
    await api(`/api/projecten/${p.id}`, { method: "DELETE" });
  } catch (fout) {
    return toon(fout.message);
  }
  projecten.lijst = projecten.lijst.filter((x) => x.id !== p.id);
  if (projecten.open?.id === p.id) sluitProject();
  else toonProjecten();
}

function maskerRond(ring) {
  const wereld = [[-180, -85], [180, -85], [180, 85], [-180, 85], [-180, -85]];
  return {
    type: "FeatureCollection",
    features: [{ type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [wereld, [...ring, ring[0]].reverse()] } }],
  };
}

async function herstelTrace(ll) {
  staat.trace.ll = ll.map((p) => [...p]);
  staat.trace.tekenen = false;
  if (ll.length >= 2) await rondTraceAf();
  else {
    staat.trace.rd = [];
    traceVeranderd();
  }
}

async function openProject(p) {
  projecten.open = p;
  $("project-naam").value = p.naam;
  gebied.punten = p.gebied.map((c) => [...c]);
  gebied.klaar = true;
  gebied.tekenen = false;
  gebiedBijwerken();
  kaartObj.getSource("masker").setData(maskerRond(p.gebied));
  const grens = grensVan(p.gebied);
  const ruimte = Math.max(grens[1][0] - grens[0][0], grens[1][1] - grens[0][1]) * 0.15;
  projecten.grens3857 = [...naarMercator(grens[0][0] - ruimte, grens[0][1] - ruimte), ...naarMercator(grens[1][0] + ruimte, grens[1][1] + ruimte)];
  kaartObj.setMaxBounds([[grens[0][0] - ruimte, grens[0][1] - ruimte], [grens[1][0] + ruimte, grens[1][1] + ruimte]]);
  kaartObj.fitBounds(grens, { padding: 60, duration: 800 });
  await herstelTrace(p.trace);
  toonProjecten();
  laadProjectdata(false);
}

function kmlKnopBijwerken() {
  const knop = $("exporteer-kml");
  knop.hidden = !projecten.open;
  if (projecten.open) knop.href = `/api/projecten/${projecten.open.id}/kml`;
}

function sluitProject() {
  projecten.open = null;
  projecten.grens3857 = null;
  wisProjectdata();
  kaartObj.getSource("masker").setData(leegGeo());
  kaartObj.setMaxBounds(NEDERLAND_GRENS);
  kaartObj.fitBounds(NEDERLAND_GRENS, { padding: 20, duration: 800 });
  wisGebied();
  wisTrace();
  $("project-naam").value = "";
  toonProjecten();
}

function bindProjecten() {
  $("bewaar-project").addEventListener("click", bewaarProject);
  $("sluit-project").addEventListener("click", sluitProject);
  $("project-naam").addEventListener("input", bewaarKnopBijwerken);
  $("ververs-data").addEventListener("click", () => laadProjectdata(true));
  for (const laag of ["projecten-vlak", "projecten-punt"]) {
    kaartObj.on("click", laag, (e) => {
      if (staat.trace.tekenen || gebied.tekenen) return;
      const p = projecten.lijst.find((x) => x.id === e.features[0].properties.id);
      if (p) openProject(p);
    });
    kaartObj.on("mouseenter", laag, () => (kaartObj.getCanvas().style.cursor = "pointer"));
    kaartObj.on("mouseleave", laag, updateCursor);
  }
}

function naarMercator(lon, lat) {
  const x = (lon * WERELD_M) / 360;
  const y = (Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360)) / Math.PI) * (WERELD_M / 2);
  return [x, y];
}

/* ---------- projectdata: alleen voor het open projectgebied ---------- */

function wisProjectdata() {
  projecten.data = null;
  kaartObj.getSource("projectdata").setData(leegGeo());
  $("projectdata").hidden = true;
}

function lijstVullen(lijst, regels) {
  lijst.replaceChildren(
    ...regels.map((tekst) => Object.assign(document.createElement("li"), { textContent: tekst })),
  );
}

function bronFilter() {
  const aan = [...document.querySelectorAll("#data-bronnen input:checked")].map((i) => i.value);
  for (const laag of ["data-vlak", "data-lijn", "data-punt"]) {
    const soort = laag === "data-vlak" ? "Polygon" : laag === "data-punt" ? "Point" : null;
    const basis = soort ? ["==", ["geometry-type"], soort] : ["!=", ["geometry-type"], "Point"];
    kaartObj.setFilter(laag, ["all", basis, ["in", ["get", "bron"], ["literal", aan]]]);
  }
}

function toonBronnen(data) {
  const doos = $("data-bronnen");
  doos.replaceChildren();
  for (const bron of data.bronnen) {
    const label = document.createElement("label");
    const vinkje = Object.assign(document.createElement("input"), { type: "checkbox", value: bron.id });
    vinkje.checked = bron.aantal > 0;
    vinkje.disabled = bron.aantal === 0;
    vinkje.addEventListener("change", bronFilter);
    const stip = Object.assign(document.createElement("i"), { className: "bron-stip" });
    stip.style.background = DATA_KLEUREN[bron.categorie] || "#e5ddc7";
    const tekst = bron.status === "fout" ? `${bron.naam}: niet bereikbaar` : `${bron.naam} (${bron.aantal})`;
    label.append(vinkje, stip, tekst);
    label.title = bron.fout || "";
    doos.append(label);
  }
}

async function laadProjectdata(vernieuw) {
  const project = projecten.open;
  if (!project) return;
  $("projectdata").hidden = false;
  $("data-bronnen").textContent = "Data ophalen…";
  try {
    const data = await api(`/api/projecten/${project.id}/data${vernieuw ? "?vernieuw=true" : ""}`);
    if (projecten.open?.id !== project.id) return;
    projecten.data = data;
    kaartObj.getSource("projectdata").setData({ type: "FeatureCollection", features: data.features });
    toonBronnen(data);
    bronFilter();
    lijstVullen($("data-punten"), data.aandachtspunten.map((p) => `${p.titel}: ${p.tekst}`));
    lijstVullen($("data-volgt"), data.nog_te_koppelen);
  } catch (fout) {
    $("data-bronnen").textContent = "";
    toon(fout.message);
  }
}

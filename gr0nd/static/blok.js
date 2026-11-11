/* 3D-blok van een projectgebied: echte grond (GeoTOP) op de wanden, echte netten (open data) in de grond,
   PDOK 3D (terrein, gebouwen) erop. Zonder GeoTOP vallen de wanden terug op voorbeelddata van /api/blok.
   Kijken: slepen, zoomen: scrollen, lopen: WASD, omhoog/omlaag: E/Q, sneller: Shift. */
import * as THREE from "three";
import { OrbitControls } from "three/addons/OrbitControls.js";
import { DRACOLoader } from "three/addons/loaders/DRACOLoader.js";
import { MeshoptDecoder } from "three/addons/libs/meshopt_decoder.module.js";
import { GLTFExtensionsPlugin, TilesRenderer, WGS84_ELLIPSOID } from "/static/vendor/3d-tiles-renderer.js";

const PDOK_3D = "https://api.pdok.nl/kadaster/3d-basisvoorziening/ogc/v1/collections";
export const OMGEVING_BRONNEN = {
  terreinen: `${PDOK_3D}/terreinen/3dtiles?f=json`,
  gebouwen: `${PDOK_3D}/gebouwen/3dtiles?f=json`,
};

const ZIJDEN_SCHADUW = { zuid: 0.92, oost: 0.74, noord: 0.6, west: 0.8 };

const LUCHT = { boven: "#4f86c6", horizon: "#dce8ee" };
const ONDER = "#1d140c"; // achtergrond en nevel onder de grond

/* Achtergrond met kleurverloop van zenit naar horizon. */
function maakLucht() {
  const doek = document.createElement("canvas");
  doek.width = 2;
  doek.height = 256;
  const ctx = doek.getContext("2d");
  const verloop = ctx.createLinearGradient(0, 0, 0, 256);
  verloop.addColorStop(0, LUCHT.boven);
  verloop.addColorStop(1, LUCHT.horizon);
  ctx.fillStyle = verloop;
  ctx.fillRect(0, 0, 2, 256);
  const textuur = new THREE.CanvasTexture(doek);
  textuur.colorSpace = THREE.SRGBColorSpace;
  return textuur;
}

/* Vaste korrel per voxel (0,94 tot 1,06), zodat grondlagen niet vlak ogen. */
const korrel = (a, b) => 0.94 + 0.12 * (Math.abs(Math.sin(a * 12.9898 + b * 78.233) * 43758.5453) % 1);

function mengKleur(hex, factor) {
  const kleur = new THREE.Color(hex);
  return kleur.multiplyScalar(factor);
}

/* Verticale overdrijving zodat 50 m diep zichtbaar is naast een gebied van kilometers breed. */
export function overdrijving(breedte, diepte) {
  const gewenst = Math.max(breedte, 1) * 0.17;
  return Math.min(60, Math.max(1, gewenst / diepte));
}

function zijdePlek(data, naam) {
  const n = data.n;
  const [x0, y0, x1, y1] = data.gebied;
  const langs = (i) => i / (n - 1);
  return {
    zuid: (i) => ({ k: i, x: x0 + (x1 - x0) * langs(i), y: y0 }),
    noord: (i) => ({ k: (n - 1) * n + i, x: x0 + (x1 - x0) * langs(i), y: y1 }),
    west: (i) => ({ k: i * n, x: x0, y: y0 + (y1 - y0) * langs(i) }),
    oost: (i) => ({ k: i * n + n - 1, x: x1, y: y0 + (y1 - y0) * langs(i) }),
  }[naam];
}

/* Elke laag is een eigen strook met eigen hoekpunten, zodat de lagen scherp van elkaar scheiden. */
function bouwZijde(data, naam, schaalZ) {
  const plek = zijdePlek(data, naam);
  const posities = [];
  const kleuren = [];
  const index = [];
  const hoekpunt = (p, diepte, laag) => {
    posities.push(p.x, -diepte * schaalZ, -p.y);
    const kleur = mengKleur(laag.kleur, (1 - 0.42 * (diepte / data.diepte)) * ZIJDEN_SCHADUW[naam]);
    kleuren.push(kleur.r, kleur.g, kleur.b);
    return posities.length / 3 - 1;
  };
  const grens = (laagNr, k) => (laagNr === 0 ? 0 : data.onderkant[laagNr - 1][k]);
  for (let i = 0; i < data.n - 1; i++) {
    const [p, q] = [plek(i), plek(i + 1)];
    data.lagen.forEach((laag, nr) => {
      const a = hoekpunt(p, grens(nr, p.k), laag);
      const b = hoekpunt(p, data.onderkant[nr][p.k], laag);
      const c = hoekpunt(q, grens(nr, q.k), laag);
      const d = hoekpunt(q, data.onderkant[nr][q.k], laag);
      index.push(a, b, c, c, b, d);
    });
  }
  const geometrie = new THREE.BufferGeometry();
  geometrie.setAttribute("position", new THREE.Float32BufferAttribute(posities, 3));
  geometrie.setAttribute("color", new THREE.Float32BufferAttribute(kleuren, 3));
  geometrie.setIndex(index);
  return new THREE.Mesh(geometrie, new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.DoubleSide }));
}

/* Wand uit GeoTOP-kolommen: per voxel van 0,5 m een rechthoek in de kleur van de grondsoort. */
function bouwVoxelWand(og, naam, gebied, [cx, cy], schaalZ) {
  const [x0, y0, x1, y1] = gebied;
  const langsX = naam === "zuid" || naam === "noord";
  const [a0, a1] = langsX ? [x0, x1] : [y0, y1];
  const vast = { zuid: y0, noord: y1, west: x0, oost: x1 }[naam];
  const punt = (l, h) => (langsX ? [l - cx, h, -(vast - cy)] : [vast - cx, h, -(l - cy)]);
  const kleurVan = Object.fromEntries(og.klassen.map((k) => [k.code, k.kleur]));
  const posities = [];
  const kleuren = [];
  const zijde = og.zijden[naam];
  zijde.posities.forEach((pos, i) => {
    const kolom = zijde.kolommen[i];
    const [l0, l1] = [Math.max(a0, pos - og.half), Math.min(a1, pos + og.half)];
    if (kolom.maaiveld === null || l1 <= l0) return;
    kolom.lithok.forEach((code, j) => {
      if (code === -127) return;
      const boven = (kolom.maaiveld - j * og.stap_z - og.referentie_nap) * schaalZ;
      const onder = boven - og.stap_z * schaalZ;
      const kleur = mengKleur(kleurVan[code] ?? "#777777", ZIJDEN_SCHADUW[naam] * korrel(pos, j));
      for (const [l, h] of [[l0, boven], [l0, onder], [l1, boven], [l1, boven], [l0, onder], [l1, onder]]) {
        posities.push(...punt(l, h));
        kleuren.push(kleur.r, kleur.g, kleur.b);
      }
    });
  });
  const geometrie = new THREE.BufferGeometry();
  geometrie.setAttribute("position", new THREE.Float32BufferAttribute(posities, 3));
  geometrie.setAttribute("color", new THREE.Float32BufferAttribute(kleuren, 3));
  return new THREE.Mesh(geometrie, new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.DoubleSide }));
}

/* Echte kabels en leidingen als buizen op hun indicatieve diepte, gekleurd per soort. */
function bouwNetten(netten, [cx, cy], schaalZ, straal) {
  const soorten = Object.fromEntries(netten.soorten.map((s) => [s.id, s]));
  const groep = new THREE.Group();
  for (const laag of netten.lagen) {
    const soort = soorten[laag.soort];
    const materiaal = new THREE.MeshStandardMaterial({ color: soort.kleur, emissive: soort.kleur, emissiveIntensity: 0.35 });
    for (const lijn of laag.lijnen) {
      if (lijn.length < 2) continue;
      const punten = lijn.map(([x, y]) => new THREE.Vector3(x - cx, -soort.diepte_m * schaalZ, -(y - cy)));
      const buis = bouwBuis(punten, straal, soort.kleur);
      buis.material.dispose();
      buis.material = materiaal;
      groep.add(buis);
    }
  }
  return groep;
}

/* Doorschijnende grond tussen de wanden, zodat kabels zichtbaar in de grond liggen. */
function bouwGrondvolume(gebiedLokaal, dikte) {
  const [x0, z0, x1, z1] = gebiedLokaal;
  const volume = new THREE.Mesh(
    new THREE.BoxGeometry(x1 - x0, dikte, z1 - z0),
    new THREE.MeshBasicMaterial({ color: "#7a5a36", transparent: true, opacity: 0.28, depthWrite: false, side: THREE.DoubleSide }),
  );
  volume.position.set((x0 + x1) / 2, -dikte / 2 - 0.05, (z0 + z1) / 2);
  return volume;
}

function bouwBovenvlak(data) {
  const [x0, y0, x1, y1] = data.gebied;
  const doek = document.createElement("canvas");
  doek.width = doek.height = 512;
  const ctx = doek.getContext("2d");
  const verloop = ctx.createLinearGradient(0, 0, 512, 512);
  verloop.addColorStop(0, "#6aa04a");
  verloop.addColorStop(1, "#4f8c3c");
  ctx.fillStyle = verloop;
  ctx.fillRect(0, 0, 512, 512);
  let zaad = 7;
  const toeval = () => ((zaad = (zaad * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < 5000; i++) {
    ctx.fillStyle = toeval() < 0.5 ? "rgba(255,240,170,0.10)" : "rgba(10,40,20,0.12)";
    ctx.fillRect(toeval() * 512, toeval() * 512, 2 + toeval() * 6, 2 + toeval() * 4);
  }
  const textuur = new THREE.CanvasTexture(doek);
  textuur.colorSpace = THREE.SRGBColorSpace;
  const vlak = new THREE.Mesh(
    new THREE.PlaneGeometry(x1 - x0, y1 - y0),
    new THREE.MeshBasicMaterial({ map: textuur }),
  );
  vlak.rotation.x = -Math.PI / 2;
  vlak.position.set((x0 + x1) / 2, 0.02, -(y0 + y1) / 2);
  return vlak;
}

function padLengtes(punten) {
  const lengtes = [0];
  for (let i = 1; i < punten.length; i++) lengtes.push(lengtes[i - 1] + punten[i].distanceTo(punten[i - 1]));
  return lengtes;
}

/* Buis door de punten van een lijn; elk knikpunt is een hoekpunt van de buis. */
function bouwBuis(punten, straal, kleur) {
  const pad = new THREE.CurvePath();
  for (let i = 1; i < punten.length; i++) pad.add(new THREE.LineCurve3(punten[i - 1], punten[i]));
  const geometrie = new THREE.TubeGeometry(pad, Math.max(8, punten.length * 6), straal, 8, false);
  return new THREE.Mesh(geometrie, new THREE.MeshBasicMaterial({ color: kleur }));
}

/* Doorschijnend gordijn tussen het tracé aan de oppervlakte en de leiding in de grond. */
function bouwGordijn(boven, onder, kleur = "#e8a860") {
  const posities = [];
  const index = [];
  boven.forEach((p, i) => {
    posities.push(p.x, p.y, p.z, onder[i].x, onder[i].y, onder[i].z);
    if (i) index.push(2 * i - 2, 2 * i - 1, 2 * i, 2 * i, 2 * i - 1, 2 * i + 1);
  });
  const geometrie = new THREE.BufferGeometry();
  geometrie.setAttribute("position", new THREE.Float32BufferAttribute(posities, 3));
  geometrie.setIndex(index);
  const materiaal = new THREE.MeshBasicMaterial({
    color: kleur,
    transparent: true,
    opacity: 0.3,
    side: THREE.DoubleSide,
    depthWrite: false,
  });
  return new THREE.Mesh(geometrie, materiaal);
}

/* Matrix die ECEF (3D Tiles) naar de blokscène brengt: eerst lokaal ENU bij het midden, dan de hoek tussen
   RD-noord en ware noord eruit draaien. Scène: x = RD-oost, y = omhoog, z = -RD-noord. */
export function ecefNaarScene(lonGraden, latGraden, convergentieGraden) {
  const enu = WGS84_ELLIPSOID.getEastNorthUpFrame(
    THREE.MathUtils.degToRad(latGraden),
    THREE.MathUtils.degToRad(lonGraden),
    0,
    new THREE.Matrix4(),
  );
  const g = THREE.MathUtils.degToRad(convergentieGraden);
  const [c, sn] = [Math.cos(g), Math.sin(g)];
  const enuNaarScene = new THREE.Matrix4().set(c, -sn, 0, 0, 0, 0, 1, 0, -sn, -c, 0, 0, 0, 0, 0, 1);
  return enuNaarScene.multiply(enu.invert());
}

function maakTegels(url, matrix, dracoLoader, camera, renderer, errorTarget) {
  const tegels = new TilesRenderer(url);
  tegels.registerPlugin(new GLTFExtensionsPlugin({ dracoLoader, meshoptDecoder: MeshoptDecoder }));
  tegels.group.matrixAutoUpdate = false;
  tegels.group.matrix.copy(matrix);
  tegels.group.matrixWorldNeedsUpdate = true;
  tegels.errorTarget = errorTarget;
  tegels.setCamera(camera);
  tegels.setResolutionFromRenderer(camera, renderer);
  return tegels;
}

export class BlokWeergave {
  constructor(houder) {
    this.houder = houder;
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.lucht = maakLucht();
    houder.append(this.renderer.domElement);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(32, 1, 1, 1e6);
    this.scene.add(new THREE.HemisphereLight("#dfeaff", "#6b5a45", 1.6));
    this.zon = new THREE.DirectionalLight("#fff1d6", 2.6);
    this.zon.castShadow = true;
    this.zon.shadow.mapSize.set(2048, 2048);
    this.scene.add(this.zon, this.zon.target);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.maxPolarAngle = Math.PI * 0.47;
    this.blok = null;
    this.actief = false;
    this.verschuiving = [0, 0];
    this.selectie = null;
    this.bindSelectie();
    this.toetsen = new Set();
    addEventListener("keydown", (e) => {
      if (this.actief && !e.target.closest?.("input, textarea, select")) this.toetsen.add(e.code);
    });
    addEventListener("keyup", (e) => this.toetsen.delete(e.code));
    addEventListener("blur", () => this.toetsen.clear());
    new ResizeObserver(() => this.pasMaatAan()).observe(houder);
  }

  toon(data, echt = false, ondergrond = null) {
    this.leegmaken();
    const [gx0, gy0, gx1, gy1] = data.gebied;
    const [cx, cy] = [(gx0 + gx1) / 2, (gy0 + gy1) / 2];
    this.verschuiving = [cx, cy];
    this.gebiedLokaal = [gx0 - cx, -(gy1 - cy), gx1 - cx, -(gy0 - cy)];
    data = { ...data, gebied: [gx0 - cx, gy0 - cy, gx1 - cx, gy1 - cy] };
    const [x0, y0, x1, y1] = data.gebied;
    const breedte = Math.max(x1 - x0, y1 - y0);
    this.breedte = breedte;
    this.echt = echt;
    this.midden = data.midden;
    this.schaalZ = echt ? 1 : overdrijving(breedte, data.diepte);
    this.blok = new THREE.Group();
    for (const naam of Object.keys(ZIJDEN_SCHADUW)) {
      this.blok.add(
        ondergrond
          ? bouwVoxelWand(ondergrond, naam, [gx0, gy0, gx1, gy1], this.verschuiving, this.schaalZ)
          : bouwZijde(data, naam, this.schaalZ),
      );
    }
    if (ondergrond) {
      const lagen = Math.max(...Object.values(ondergrond.zijden).flatMap((z) => z.kolommen.map((k) => k.lithok.length)));
      this.blok.add(bouwGrondvolume(this.gebiedLokaal, lagen * ondergrond.stap_z * this.schaalZ));
    }
    this.bovenvlak = bouwBovenvlak(data);
    this.blok.add(this.bovenvlak);
    this.scene.add(this.blok);
    this.zetZon(breedte);
    this.zetSfeer();
    const midden = new THREE.Vector3((x0 + x1) / 2, (-data.diepte * this.schaalZ) / 2.4, -(y0 + y1) / 2);
    const afstand = breedte * 2.3;
    const hoek = (30 * Math.PI) / 180;
    this.camera.position.set(
      midden.x + afstand * Math.cos(hoek) * Math.SQRT1_2,
      midden.y + afstand * Math.sin(hoek),
      midden.z + afstand * Math.cos(hoek) * Math.SQRT1_2,
    );
    this.controls.target.copy(midden);
    this.camera.near = breedte / 500;
    this.camera.far = breedte * 20;
    this.camera.updateProjectionMatrix();
    this.pasMaatAan();
    const wasActief = this.actief;
    this.actief = true;
    if (!wasActief) this.lus();
    return this.schaalZ;
  }

  /* Selecteren van een rechthoek op het bovenvlak. `klaar` krijgt de RD-omhullende [x0, y0, x1, y1]. */
  kiesStuk(klaar) {
    this.selectie = { klaar, start: null, vlak: null };
    this.controls.enabled = false;
    this.renderer.domElement.style.cursor = "crosshair";
  }

  annuleerKeuze() {
    if (this.selectie?.vlak) this.scene.remove(this.selectie.vlak);
    this.selectie = null;
    this.controls.enabled = true;
    this.renderer.domElement.style.cursor = "";
  }

  grondPunt(gebeurtenis) {
    const rect = this.renderer.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2(
      ((gebeurtenis.clientX - rect.left) / rect.width) * 2 - 1,
      -((gebeurtenis.clientY - rect.top) / rect.height) * 2 + 1,
    );
    const straal = new THREE.Raycaster();
    straal.setFromCamera(ndc, this.camera);
    const punt = new THREE.Vector3();
    if (!straal.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), 0), punt)) return null;
    return { x: punt.x, y: -punt.z };
  }

  tekenKeuze(a, b) {
    const sel = this.selectie;
    if (!sel.vlak) {
      sel.vlak = new THREE.Mesh(
        new THREE.PlaneGeometry(1, 1),
        new THREE.MeshBasicMaterial({ color: "#e8a860", transparent: true, opacity: 0.4, depthTest: false }),
      );
      sel.vlak.rotation.x = -Math.PI / 2;
      sel.vlak.renderOrder = 5;
      this.scene.add(sel.vlak);
    }
    sel.vlak.scale.set(Math.max(Math.abs(b.x - a.x), 1), Math.max(Math.abs(b.y - a.y), 1), 1);
    sel.vlak.position.set((a.x + b.x) / 2, 0.5, -(a.y + b.y) / 2);
  }

  bindSelectie() {
    const doek = this.renderer.domElement;
    let neer = null;
    doek.addEventListener("pointerdown", (e) => (neer = [e.clientX, e.clientY]));
    doek.addEventListener("pointerup", (e) => {
      const klik = neer && Math.hypot(e.clientX - neer[0], e.clientY - neer[1]) < 5;
      const punt = klik && this.tekenen && this.grondPunt(e);
      if (punt) this.voegTekenpuntToe(punt);
    });
    doek.addEventListener("dblclick", () => this.rondTekenenAf());
    addEventListener("keydown", (e) => {
      if (!this.tekenen) return;
      if (e.key === "Enter") this.rondTekenenAf();
      if (e.key === "Escape") this.stopTekenen();
    });
    doek.addEventListener("pointerdown", (e) => {
      if (!this.selectie) return;
      this.selectie.start = this.grondPunt(e);
      doek.setPointerCapture(e.pointerId);
    });
    doek.addEventListener("pointermove", (e) => {
      const punt = this.selectie?.start && this.grondPunt(e);
      if (punt) this.tekenKeuze(this.selectie.start, punt);
    });
    doek.addEventListener("pointerup", (e) => {
      const sel = this.selectie;
      const eind = sel?.start && this.grondPunt(e);
      if (!eind) return;
      const [a, b] = [sel.start, eind];
      this.annuleerKeuze();
      const [cx, cy] = this.verschuiving;
      sel.klaar([Math.min(a.x, b.x) + cx, Math.min(a.y, b.y) + cy, Math.max(a.x, b.x) + cx, Math.max(a.y, b.y) + cy]);
    });
  }

  /* Tracé met de nieuwe leiding volgens het profiel van /api/aanleg ([x, y, diepte] in RD) en de kruisingen.
     Ontgraven: bruine sleufwand; boring: oranje gordijn. Kruising: groene of rode bol op de bestaande kabel. */
  zetAanleg(aanleg) {
    this.wisTrace();
    if (!this.blok || aanleg.profiel.length < 2) return 0;
    const [cx, cy] = this.verschuiving;
    const straal = this.echt ? 0.15 : Math.max(this.breedte * 0.0004, 0.3);
    const naarScene = (x, y, d) => new THREE.Vector3(x - cx, -d * this.schaalZ, -(y - cy));
    const maaiveld = aanleg.profiel.map(([x, y]) => naarScene(x, y, -straal / this.schaalZ));
    const leiding = aanleg.profiel.map(([x, y, d]) => naarScene(x, y, d));
    const ontgraven = aanleg.wijze === "ontgraven";
    this.trace = new THREE.Group();
    this.trace.add(bouwBuis(maaiveld, straal, "#ffb454"), bouwBuis(leiding, straal * 1.6, "#ff5a3c"));
    this.trace.add(bouwGordijn(maaiveld, leiding, ontgraven ? "#8a5a2b" : "#e8a860"));
    const bol = new THREE.SphereGeometry(Math.max(straal * 4, this.breedte * 0.005), 16, 12);
    for (const k of aanleg.kruisingen) {
      const kleur = k.ok ? "#3ddc84" : "#ff3b3b";
      const teken = new THREE.Mesh(bol, new THREE.MeshBasicMaterial({ color: kleur, depthTest: false, transparent: true }));
      teken.position.copy(naarScene(k.x, k.y, k.kabel_diepte));
      teken.renderOrder = 6;
      this.trace.add(teken);
    }
    this.scene.add(this.trace);
    this.pad = { punten: maaiveld, lengtes: padLengtes(maaiveld) };
    return this.pad.lengtes.at(-1);
  }

  /* Tracé tekenen in 3D: klik punten op het maaiveld, dubbelklik of Enter om af te ronden, Esc om te stoppen.
     `klaar` krijgt de RD-punten. */
  tekenTrace(klaar) {
    this.annuleerKeuze();
    this.tekenen = { klaar, punten: [], voorbeeld: null };
    this.renderer.domElement.style.cursor = "crosshair";
  }

  stopTekenen() {
    if (this.tekenen?.voorbeeld) this.scene.remove(this.tekenen.voorbeeld);
    this.tekenen = null;
    this.renderer.domElement.style.cursor = "";
  }

  voegTekenpuntToe(punt) {
    const t = this.tekenen;
    t.punten.push(punt);
    if (t.voorbeeld) this.scene.remove(t.voorbeeld);
    if (t.punten.length < 2) return;
    const straal = this.echt ? 0.3 : Math.max(this.breedte * 0.0008, 0.6);
    t.voorbeeld = bouwBuis(t.punten.map((p) => new THREE.Vector3(p.x, straal, -p.y)), straal, "#ffb454");
    this.scene.add(t.voorbeeld);
  }

  rondTekenenAf() {
    const t = this.tekenen;
    if (!t) return;
    const [cx, cy] = this.verschuiving;
    // een dubbelklik zet het laatste punt twee keer: punten dichter dan 0,5 m bij de vorige vallen weg
    const punten = t.punten.filter((p, i) => !i || Math.hypot(p.x - t.punten[i - 1].x, p.y - t.punten[i - 1].y) > 0.5);
    const rd = punten.map((p) => [p.x + cx, p.y + cy]);
    this.stopTekenen();
    if (rd.length >= 2) t.klaar(rd);
  }

  wisTrace() {
    if (!this.trace) return;
    this.scene.remove(this.trace);
    this.trace.traverse((o) => {
      o.geometry?.dispose();
      o.material?.dispose();
    });
    this.trace = null;
    this.pad = null;
    this.zetVolgen(false);
  }

  /* Punt en looprichting op afstand s langs het tracé. */
  plekOp(s) {
    const { punten, lengtes } = this.pad;
    const nr = Math.min(Math.max(lengtes.findIndex((l) => l >= s) - 1, 0), punten.length - 2);
    const [a, b] = [punten[nr], punten[nr + 1]];
    const t = Math.min(Math.max((s - lengtes[nr]) / Math.max(lengtes[nr + 1] - lengtes[nr], 1e-6), 0), 1);
    return { punt: a.clone().lerp(b, t), richting: b.clone().sub(a).setY(0).normalize() };
  }

  /* Camera achter het punt op afstand s, kijkend langs het tracé (zoals lopen in een spel). */
  zetPositie(s) {
    if (!this.pad || !this.volgen) return;
    const { punt, richting } = this.plekOp(s);
    const achter = Math.max(25, this.breedte * 0.03);
    this.camera.position.copy(punt).addScaledVector(richting, -achter).setY(achter * 0.4);
    this.controls.target.copy(punt).addScaledVector(richting, achter * 1.5).setY(0);
    this.camera.lookAt(this.controls.target);
  }

  zetVolgen(aan) {
    if (aan && !this.pad) return;
    if (aan && !this.volgen) this.overzicht = { positie: this.camera.position.clone(), doel: this.controls.target.clone() };
    if (!aan && this.volgen && this.overzicht) {
      this.camera.position.copy(this.overzicht.positie);
      this.controls.target.copy(this.overzicht.doel);
    }
    this.volgen = aan;
    this.controls.enabled = !aan && !this.selectie;
    if (!aan) this.speelt = false;
  }

  ga(afstand) {
    this.afstand = afstand;
    this.zetPositie(afstand);
  }

  /* Automatisch lopen met `snelheid` m/s; `bijwerk(s)` krijgt de nieuwe afstand. */
  speel(aan, snelheid, bijwerk) {
    this.speelt = aan && !!this.pad;
    if (this.speelt && this.afstand >= this.pad.lengtes.at(-1)) this.afstand = 0;
    this.snelheid = snelheid;
    this.bijwerk = bijwerk;
    this.laatste = performance.now();
  }

  zetNetten(netten) {
    this.wisNetten();
    if (!this.blok) return;
    const straal = this.echt ? 0.2 : Math.max(this.breedte * 0.0005, 0.3);
    this.netten = bouwNetten(netten, this.verschuiving, this.schaalZ, straal);
    this.scene.add(this.netten);
  }

  wisNetten() {
    if (!this.netten) return;
    this.scene.remove(this.netten);
    this.netten.traverse((o) => {
      o.geometry?.dispose();
      o.material?.dispose();
    });
    this.netten = null;
  }

  /* Zon schuin uit het zuidwesten; het schaduwvak dekt het hele blok. */
  zetZon(breedte) {
    const rand = breedte * 0.75;
    this.zon.position.set(-breedte * 0.6, breedte * 0.9, breedte * 0.5);
    this.zon.target.position.set(0, 0, 0);
    Object.assign(this.zon.shadow.camera, { left: -rand, right: rand, top: rand, bottom: -rand, near: 1, far: breedte * 3 });
    this.zon.shadow.camera.updateProjectionMatrix();
    this.zon.shadow.bias = -0.0005;
  }

  /* Boven: lucht en nevel aan de horizon. Onder de grond: donker en aards, nevel dichtbij. */
  zetSfeer() {
    const b = this.breedte ?? 1000;
    this.scene.background = this.ondergronds ? new THREE.Color(ONDER) : this.lucht;
    this.scene.fog = this.ondergronds
      ? new THREE.Fog(ONDER, b * 2.5, b * 8)
      : new THREE.Fog(LUCHT.horizon, b * 2.5, b * 9);
  }

  /* Onder de grond kijken: terrein en grasvlak weg, camera mag onder het maaiveld. Gebouwen blijven staan. */
  zetOndergronds(aan) {
    this.ondergronds = aan;
    this.zetSfeer();
    if (this.tegels?.[0]) this.tegels[0].group.visible = !aan;
    if (this.bovenvlak) this.bovenvlak.visible = !aan && !this.hoogteGekalibreerd;
    this.controls.maxPolarAngle = aan ? Math.PI : Math.PI * 0.47;
  }

  /* Lopen zoals in een spel: WASD langs de grond in de kijkrichting, E/Q omhoog en omlaag. */
  beweeg(seconden) {
    if (!this.toetsen.size || this.volgen) return;
    const t = this.toetsen;
    const vooruit = (t.has("KeyW") || t.has("ArrowUp")) - (t.has("KeyS") || t.has("ArrowDown"));
    const opzij = (t.has("KeyD") || t.has("ArrowRight")) - (t.has("KeyA") || t.has("ArrowLeft"));
    const omhoog = t.has("KeyE") - t.has("KeyQ");
    if (!vooruit && !opzij && !omhoog) return;
    const kijk = new THREE.Vector3();
    this.camera.getWorldDirection(kijk).setY(0).normalize();
    const rechts = new THREE.Vector3().crossVectors(kijk, this.camera.up).normalize();
    const snelheid = Math.max(8, this.breedte * 0.15) * (t.has("ShiftLeft") || t.has("ShiftRight") ? 4 : 1);
    const stap = kijk.multiplyScalar(vooruit).add(rechts.multiplyScalar(opzij)).setY(omhoog);
    stap.multiplyScalar(snelheid * seconden);
    this.camera.position.add(stap);
    this.controls.target.add(stap);
  }

  /* Echte omgeving: PDOK 3D Tiles (terrein en gebouwen), afgeknipt tot het blok. Alleen voor kleine gebieden. */
  laadOmgeving(bronnen = OMGEVING_BRONNEN, melding = () => {}) {
    this.wisOmgeving();
    this.melding = melding;
    if (!this.blok || !this.midden) return;
    const [x0, y0, x1, y1] = this.gebiedLokaal; // y0 en y1 zijn hier z-grenzen van de scène
    this.renderer.localClippingEnabled = false;
    const rand = 0.1; // net buiten de wanden, anders flikkeren die op het afknipvlak
    this.renderer.clippingPlanes = [
      new THREE.Plane(new THREE.Vector3(1, 0, 0), -x0 + rand),
      new THREE.Plane(new THREE.Vector3(-1, 0, 0), x1 + rand),
      new THREE.Plane(new THREE.Vector3(0, 0, 1), -y0 + rand),
      new THREE.Plane(new THREE.Vector3(0, 0, -1), y1 + rand),
    ];
    const matrix = ecefNaarScene(this.midden.lon, this.midden.lat, this.midden.convergentie);
    this.dracoLoader ??= new DRACOLoader().setDecoderPath("/static/vendor/draco/");
    this.omgeving = new THREE.Group();
    this.tegels = Object.entries(bronnen).map(([naam, url]) => {
      const tegels = maakTegels(url, matrix, this.dracoLoader, this.camera, this.renderer, 8);
      tegels.addEventListener("load-model", ({ scene }) =>
        scene.traverse((o) => {
          if (o.isMesh) o.castShadow = o.receiveShadow = true;
        }),
      );
      tegels.addEventListener("load-error", (e) => {
        console.warn(`PDOK ${naam}:`, e.error?.message ?? e);
        this.melding(`PDOK 3D ${naam} laden mislukt: ${e.error?.message ?? "onbekende fout"}. Open het blok opnieuw om het nog eens te proberen.`);
      });
      this.omgeving.add(tegels.group);
      return tegels;
    });
    this.scene.add(this.omgeving);
  }

  /* Zodra terrein er is: verberg het nepvlak en breng het maaiveld op y = 0 (hoogtes in de tiles zijn ellipsoïdisch).
     Wordt per beeld geprobeerd tot er terrein onder het midden zit. */
  kalibreerHoogte() {
    this.omgeving.updateMatrixWorld(true);
    const straal = new THREE.Raycaster(new THREE.Vector3(0, 5000, 0), new THREE.Vector3(0, -1, 0));
    const treffer = straal.intersectObject(this.tegels[0].group, true)[0];
    if (!treffer) return;
    this.omgeving.position.y -= treffer.point.y;
    this.hoogteGekalibreerd = true;
    if (this.bovenvlak) this.bovenvlak.visible = false;
    if (this.ondergronds) this.tegels[0].group.visible = false;
    this.melding("PDOK 3D-terrein geladen. Gebouwen laden mee.");
  }

  wisOmgeving() {
    this.tegels?.forEach((t) => t.dispose());
    if (this.omgeving) this.scene.remove(this.omgeving);
    this.tegels = null;
    this.omgeving = null;
    this.hoogteGekalibreerd = false;
    this.renderer.clippingPlanes = [];
  }

  leegmaken() {
    this.stopTekenen();
    this.wisOmgeving();
    this.wisNetten();
    this.wisTrace();
    this.annuleerKeuze();
    if (!this.blok) return;
    this.scene.remove(this.blok);
    this.blok.traverse((o) => {
      o.geometry?.dispose();
      o.material?.map?.dispose();
      o.material?.dispose();
    });
    this.blok = null;
  }

  stop() {
    this.actief = false;
  }

  pasMaatAan() {
    const { clientWidth: b, clientHeight: h } = this.houder;
    if (!b || !h) return;
    this.renderer.setSize(b, h);
    this.camera.aspect = b / h;
    this.camera.updateProjectionMatrix();
  }

  loopStap() {
    const nu = performance.now();
    const lengte = this.pad.lengtes.at(-1);
    this.afstand = Math.min((this.afstand ?? 0) + (this.snelheid * (nu - this.laatste)) / 1000, lengte);
    this.laatste = nu;
    this.zetPositie(this.afstand);
    this.bijwerk?.(this.afstand);
    if (this.afstand >= lengte) this.speelt = false;
  }

  lus() {
    if (!this.actief) return;
    const nu = performance.now();
    this.beweeg(Math.min((nu - (this.vorigBeeld ?? nu)) / 1000, 0.1));
    this.vorigBeeld = nu;
    if (this.speelt) this.loopStap();
    this.controls.update();
    this.camera.updateMatrixWorld();
    this.tegels?.forEach((t) => t.update());
    if (this.tegels && !this.hoogteGekalibreerd) this.kalibreerHoogte();
    this.renderer.render(this.scene, this.camera);
    requestAnimationFrame(() => this.lus());
  }
}

window.BlokWeergave = BlokWeergave;
window.dispatchEvent(new Event("blok-gereed"));

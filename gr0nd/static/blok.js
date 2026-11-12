/* 3D-wereld van een projectgebied, in de vorm van het getekende gebied en op ware grootte.
   Maaiveld: AHN-hoogte met PDOK-luchtfoto. Gebouwen: 3D BAG (echte omtrek en hoogte) in Terra Nil-stijl.
   Bomen: BGT. Grond langs de rand: GeoTOP. Kabels: open data netbeheerders (diepte indicatief).
   Scène: x = RD-oost, y = NAP min referentie (omhoog), z = -RD-noord; oorsprong in het midden van het gebied.
   Kijken: slepen, zoomen: scrollen, lopen: WASD, omhoog/omlaag: E/Q, sneller: Shift. */
import * as THREE from "three";
import { OrbitControls } from "three/addons/OrbitControls.js";

const LUCHT = { boven: "#4f86c6", horizon: "#dce8ee" };
const ONDER = "#1d140c"; // achtergrond onder de grond
const MUREN = ["#efe6d8", "#e8dccb", "#f2ece2", "#e3d6c3", "#ece3d3"];
const DAKEN_SCHUIN = ["#b5533c", "#a2483a", "#5b5f66", "#7a4a35"];
const DAK_PLAT = "#cfc8bb";
const KROONKLEUREN = ["#4f8a3c", "#5c9a44", "#3f7a35", "#6aa64f"];
const LUCHTFOTO = "https://service.pdok.nl/hwh/luchtfotorgb/wms/v1_0";
const BLOKJE_M = 0.5; // grondblokjes bij het graven, zoals de voxels van GeoTOP
const MAX_BLOKJES = 40000;
const AANLEG_SPEELDUUR_MS = 24000; // de hele aanleg in beeld, de klok toont de echte werkuren
const GROND = { humus: "#5a3d24", zand: ["#c8a466", "#b8955a", "#d1b07a"], open: "#2e2015", dicht: "#d8c08a" };
const LUCHTFOTO_TEGEL_PX = 2048; // grootste afbeelding die PDOK per verzoek levert

/* Vaste pseudo-toevalswaarde tussen 0 en 1, zodat de wereld er elke keer hetzelfde uitziet. */
const hasj = (a, b = 0) => Math.abs(Math.sin(a * 12.9898 + b * 78.233) * 43758.5453) % 1;
const kies = (lijst, a, b) => lijst[Math.floor(hasj(a, b) * lijst.length)];

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

function laadAfbeelding(url) {
  return new Promise((klaar, fout) => {
    const beeld = new Image();
    beeld.crossOrigin = "anonymous";
    beeld.onload = () => klaar(beeld);
    beeld.onerror = () => fout(new Error("Luchtfoto laden mislukt."));
    beeld.src = url;
  });
}

/* Luchtfoto van het gebied als één textuur: 1 tegel tot 1,5 km, anders 2 × 2 tegels van 2048 px. */
export async function laadLuchtfoto([x0, y0, x1, y1]) {
  const aantal = Math.max(x1 - x0, y1 - y0) > 1500 ? 2 : 1;
  const px = LUCHTFOTO_TEGEL_PX;
  const doek = document.createElement("canvas");
  doek.width = doek.height = px * aantal;
  const ctx = doek.getContext("2d");
  const [bx, by] = [(x1 - x0) / aantal, (y1 - y0) / aantal];
  const taken = [];
  for (let i = 0; i < aantal; i++) {
    for (let j = 0; j < aantal; j++) {
      const bbox = [x0 + i * bx, y0 + j * by, x0 + (i + 1) * bx, y0 + (j + 1) * by].map((v) => v.toFixed(2)).join(",");
      // PDOK geeft een wit beeld als de pixelverhouding niet gelijk is aan die van de bbox
      const [b, h] = bx >= by ? [px, Math.round((px * by) / bx)] : [Math.round((px * bx) / by), px];
      const url = `${LUCHTFOTO}?service=WMS&request=GetMap&version=1.3.0&layers=Actueel_orthoHR&styles=&crs=EPSG:28992&bbox=${bbox}&width=${b}&height=${h}&format=image/jpeg`;
      taken.push(laadAfbeelding(url).then((beeld) => ctx.drawImage(beeld, i * px, (aantal - 1 - j) * px, px, px)));
    }
  }
  await Promise.all(taken);
  const textuur = new THREE.CanvasTexture(doek);
  textuur.colorSpace = THREE.SRGBColorSpace;
  textuur.anisotropy = 8;
  return textuur;
}

/* Wit binnen de projectvorm, zwart erbuiten: snijdt het maaiveld precies op de vorm af. */
function maakMasker(ring, [x0, y0, x1, y1]) {
  const doek = document.createElement("canvas");
  doek.width = doek.height = 2048;
  const ctx = doek.getContext("2d");
  ctx.fillStyle = "#000";
  ctx.fillRect(0, 0, 2048, 2048);
  ctx.fillStyle = "#fff";
  ctx.beginPath();
  ring.forEach(([x, y], i) => ctx[i ? "lineTo" : "moveTo"](((x - x0) / (x1 - x0)) * 2048, (1 - (y - y0) / (y1 - y0)) * 2048));
  ctx.fill();
  return new THREE.CanvasTexture(doek);
}

function vulGeometrie(posities, kleuren, index = null) {
  const geometrie = new THREE.BufferGeometry();
  geometrie.setAttribute("position", new THREE.Float32BufferAttribute(posities, 3));
  if (kleuren) geometrie.setAttribute("color", new THREE.Float32BufferAttribute(kleuren, 3));
  if (index) geometrie.setIndex(index);
  return geometrie;
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
  return new THREE.Mesh(geometrie, new THREE.MeshStandardMaterial({ color: kleur, emissive: kleur, emissiveIntensity: 0.35 }));
}

/* Doorschijnend gordijn tussen het tracé aan de oppervlakte en de leiding in de grond. */
function bouwGordijn(boven, onder, kleur) {
  const posities = [];
  const index = [];
  boven.forEach((p, i) => {
    posities.push(p.x, p.y, p.z, onder[i].x, onder[i].y, onder[i].z);
    if (i) index.push(2 * i - 2, 2 * i - 1, 2 * i, 2 * i, 2 * i - 1, 2 * i + 1);
  });
  const materiaal = new THREE.MeshBasicMaterial({ color: kleur, transparent: true, opacity: 0.3, side: THREE.DoubleSide, depthWrite: false });
  return new THREE.Mesh(vulGeometrie(posities, null, index), materiaal);
}

/* Punten om de `stap` langs het profiel ([x, y, diepte] in RD): plek, diepte, afstand en de normaal (haaks). */
function bemonster(profiel, stap) {
  const uit = [];
  let s = 0;
  for (let i = 1; i < profiel.length; i++) {
    const [[x0, y0, d0], [x1, y1, d1]] = [profiel[i - 1], profiel[i]];
    const lengte = Math.hypot(x1 - x0, y1 - y0);
    if (lengte < 1e-6) continue;
    const [nx, ny] = [-(y1 - y0) / lengte, (x1 - x0) / lengte];
    for (let a = uit.length ? stap - (s % stap || stap) : 0; a < lengte; a += stap) {
      const t = a / lengte;
      uit.push({ x: x0 + t * (x1 - x0), y: y0 + t * (y1 - y0), d: d0 + t * (d1 - d0), s: s + a, nx, ny });
    }
    s += lengte;
  }
  return uit;
}

/* Strook langs de punten met de gegeven breedte, net boven het maaiveld; volgorde langs het tracé. */
function bouwStrook(punten, breedte, hoogte, naarScene, kleur) {
  const posities = [];
  const index = [];
  punten.forEach((p, i) => {
    for (const kant of [-0.5, 0.5]) {
      const [x, y] = [p.x + p.nx * breedte * kant, p.y + p.ny * breedte * kant];
      posities.push(...naarScene(x, y, hoogte(x, y) + 0.06).toArray());
    }
    if (i) index.push(2 * i - 2, 2 * i - 1, 2 * i, 2 * i, 2 * i - 1, 2 * i + 1);
  });
  return new THREE.Mesh(vulGeometrie(posities, null, index), new THREE.MeshBasicMaterial({ color: kleur, side: THREE.DoubleSide }));
}

export class BlokWeergave {
  constructor(houder) {
    this.houder = houder;
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    houder.append(this.renderer.domElement);
    this.scene = new THREE.Scene();
    this.lucht = maakLucht();
    this.camera = new THREE.PerspectiveCamera(40, 1, 1, 1e6);
    this.scene.add(new THREE.HemisphereLight("#e6f0ff", "#6b5a45", 1.4));
    this.zon = new THREE.DirectionalLight("#fff1d6", 2.6);
    this.zon.castShadow = true;
    this.zon.shadow.mapSize.set(4096, 4096);
    this.scene.add(this.zon, this.zon.target);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    // besturing zoals een online kaart: links schuiven, rechts draaien, scrollen zoomt naar de muis
    Object.assign(this.controls, {
      enableDamping: true,
      maxPolarAngle: Math.PI * 0.49,
      screenSpacePanning: false,
      zoomToCursor: true,
      zoomSpeed: 1.6,
      minDistance: 3,
      mouseButtons: { LEFT: THREE.MOUSE.PAN, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.ROTATE },
      touches: { ONE: THREE.TOUCH.PAN, TWO: THREE.TOUCH.DOLLY_ROTATE },
    });
    this.wereld = null;
    this.actief = false;
    this.doorzicht = 0;
    this.toetsen = new Set();
    addEventListener("keydown", (e) => {
      if (this.actief && !e.target.closest?.("input, textarea, select")) this.toetsen.add(e.code);
    });
    addEventListener("keyup", (e) => this.toetsen.delete(e.code));
    addEventListener("blur", () => this.toetsen.clear());
    this.bindMuis();
    new ResizeObserver(() => this.pasMaatAan()).observe(houder);
  }

  /* ---------- wereld opbouwen ---------- */

  /* Bouw de wereld uit /api/wereld en de luchtfoto. Geeft de breedte in meters. */
  toon(w, luchtfoto) {
    this.leegmaken();
    const [x0, y0, x1, y1] = w.gebied;
    this.w = w;
    this.midden = [(x0 + x1) / 2, (y0 + y1) / 2];
    this.breedte = Math.max(x1 - x0, y1 - y0);
    this.wereld = new THREE.Group();
    this.maaiveld = this.bouwMaaiveld(w, luchtfoto);
    this.gebouwen = this.bouwGebouwen(w.gebouwen);
    this.wereld.add(this.maaiveld, this.bouwGrondrand(w), this.bouwBodem(w), this.gebouwen, this.bouwBomen(w.bomen));
    this.scene.add(this.wereld);
    this.zetZon();
    this.zetDoorzicht(this.doorzicht);
    this.camera.near = 0.5;
    this.camera.far = this.breedte * 20;
    this.camera.updateProjectionMatrix();
    this.overzicht();
    this.pasMaatAan();
    const wasActief = this.actief;
    this.actief = true;
    if (!wasActief) this.lus();
    return this.breedte;
  }

  naarScene(x, y, nap) {
    return new THREE.Vector3(x - this.midden[0], nap - this.w.referentie_nap, -(y - this.midden[1]));
  }

  /* NAP-hoogte van het maaiveld op (x, y), bilineair uit het AHN-raster. */
  hoogte(x, y) {
    const { n, hoogtes } = this.w.maaiveld;
    const [x0, y0, x1, y1] = this.w.gebied;
    const fx = Math.min(Math.max(((x - x0) / (x1 - x0)) * (n - 1), 0), n - 1.001);
    const fy = Math.min(Math.max(((y - y0) / (y1 - y0)) * (n - 1), 0), n - 1.001);
    const [i, j] = [Math.floor(fy), Math.floor(fx)];
    const [ty, tx] = [fy - i, fx - j];
    const h = (r, k) => hoogtes[r * n + k];
    return (h(i, j) * (1 - tx) + h(i, j + 1) * tx) * (1 - ty) + (h(i + 1, j) * (1 - tx) + h(i + 1, j + 1) * tx) * ty;
  }

  bouwMaaiveld(w, luchtfoto) {
    const { n, hoogtes } = w.maaiveld;
    const [x0, y0, x1, y1] = w.gebied;
    const posities = [];
    const uv = [];
    const index = [];
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        const [x, y] = [x0 + ((x1 - x0) * j) / (n - 1), y0 + ((y1 - y0) * i) / (n - 1)];
        posities.push(...this.naarScene(x, y, hoogtes[i * n + j]).toArray());
        uv.push(j / (n - 1), i / (n - 1));
        if (i && j) index.push((i - 1) * n + j - 1, (i - 1) * n + j, i * n + j - 1, i * n + j - 1, (i - 1) * n + j, i * n + j);
      }
    }
    const geometrie = vulGeometrie(posities, null, index);
    geometrie.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
    geometrie.computeVertexNormals();
    // een luchtfoto heeft zijn eigen licht en schaduw: onbelicht tonen, anders wordt hij overbelicht wit
    const opties = { alphaMap: maakMasker(w.ring, w.gebied), alphaTest: 0.5, side: THREE.DoubleSide };
    const materiaal = luchtfoto
      ? new THREE.MeshBasicMaterial({ map: luchtfoto, ...opties })
      : new THREE.MeshStandardMaterial({ color: "#7fa25a", roughness: 0.95, ...opties });
    const mesh = new THREE.Mesh(geometrie, materiaal);
    mesh.receiveShadow = true;
    return mesh;
  }

  /* Grondwand langs de projectgrens: per randpunt een kolom GeoTOP-voxels van 0,5 m onder het maaiveld. */
  bouwGrondrand(w) {
    const kleurVan = Object.fromEntries(w.klassen.map((k) => [k.code, new THREE.Color(k.kleur)]));
    const posities = [];
    const kleuren = [];
    for (let r = 1; r < w.rand.length; r++) {
      const [a, b] = [w.rand[r - 1], w.rand[r]];
      a.lithok.forEach((code, k) => {
        if (code === -127) return;
        const kleur = (kleurVan[code] ?? new THREE.Color("#777")).clone().multiplyScalar(0.92 + 0.12 * hasj(a.x, k));
        const [boA, onA] = [a.maaiveld - k * w.stap_z, a.maaiveld - (k + 1) * w.stap_z];
        const [boB, onB] = [b.maaiveld - k * w.stap_z, b.maaiveld - (k + 1) * w.stap_z];
        for (const [p, h] of [[a, boA], [a, onA], [b, boB], [b, boB], [a, onA], [b, onB]]) {
          posities.push(...this.naarScene(p.x, p.y, h).toArray());
          kleuren.push(kleur.r, kleur.g, kleur.b);
        }
      });
    }
    return new THREE.Mesh(vulGeometrie(posities, kleuren), new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.DoubleSide }));
  }

  /* Donkere onderkant in de vorm van het gebied. */
  bouwBodem(w) {
    const laagste = Math.min(...w.rand.map((p) => p.maaiveld - p.lithok.length * w.stap_z));
    const vorm = new THREE.Shape(w.ring.map(([x, y]) => new THREE.Vector2(x - this.midden[0], y - this.midden[1])));
    const bodem = new THREE.Mesh(new THREE.ShapeGeometry(vorm), new THREE.MeshBasicMaterial({ color: "#2a1d12", side: THREE.DoubleSide }));
    bodem.rotation.x = -Math.PI / 2;
    bodem.position.y = laagste - w.referentie_nap;
    return bodem;
  }

  /* Alle gebouwen als één geometrie: muren in zachte tinten, platte of schuine daken in dakkleur. */
  bouwGebouwen(panden) {
    const posities = [];
    const kleuren = [];
    const voeg = (punt, kleur) => {
      posities.push(punt.x, punt.y, punt.z);
      kleuren.push(kleur.r, kleur.g, kleur.b);
    };
    panden.forEach((pand, nr) => {
      const voet = Math.min(pand.voet, ...pand.rand.map(([x, y]) => this.hoogte(x, y))) - 0.3;
      const muur = new THREE.Color(kies(MUREN, nr));
      const dak = new THREE.Color(pand.schuin ? kies(DAKEN_SCHUIN, nr, 1) : DAK_PLAT);
      const onder = pand.rand.map(([x, y]) => this.naarScene(x, y, voet));
      const boven = pand.rand.map(([x, y]) => this.naarScene(x, y, pand.dak));
      for (let i = 0; i < onder.length; i++) {
        const k = (i + 1) % onder.length;
        const tint = muur.clone().multiplyScalar(0.85 + 0.15 * hasj(i, nr));
        for (const p of [onder[i], onder[k], boven[i], boven[i], onder[k], boven[k]]) voeg(p, tint);
      }
      const vlak = pand.rand.map(([x, y]) => new THREE.Vector2(x, y));
      for (const [a, b, c] of THREE.ShapeUtils.triangulateShape(vlak, [])) for (const i of [a, c, b]) voeg(boven[i], dak);
    });
    const geometrie = vulGeometrie(posities, kleuren);
    geometrie.computeVertexNormals();
    const mesh = new THREE.Mesh(geometrie, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.85, side: THREE.DoubleSide }));
    mesh.castShadow = mesh.receiveShadow = true;
    return mesh;
  }

  /* Gestileerde bomen: stam en ronde kroon, maat en kleur verschillen per boom. */
  bouwBomen(punten) {
    const groep = new THREE.Group();
    if (!punten.length) return groep;
    const stammen = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.25, 0.35, 1, 6), new THREE.MeshStandardMaterial({ color: "#6b4a2b" }), punten.length);
    const kronen = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1, 0), new THREE.MeshStandardMaterial({ roughness: 0.9, flatShading: true }), punten.length);
    const m = new THREE.Matrix4();
    const rust = new THREE.Quaternion();
    punten.forEach(([x, y], i) => {
      const grootte = 0.7 + 0.6 * hasj(x, y);
      const voet = this.naarScene(x, y, this.hoogte(x, y));
      m.compose(voet.clone().setY(voet.y + 1.5 * grootte), rust, new THREE.Vector3(grootte, 3 * grootte, grootte));
      stammen.setMatrixAt(i, m);
      m.compose(voet.clone().setY(voet.y + 4.2 * grootte), rust, new THREE.Vector3(2.6, 2.3, 2.6).multiplyScalar(grootte));
      kronen.setMatrixAt(i, m);
      kronen.setColorAt(i, new THREE.Color(kies(KROONKLEUREN, x, y)));
    });
    stammen.castShadow = kronen.castShadow = true;
    groep.add(stammen, kronen);
    return groep;
  }

  /* ---------- camera, licht en sfeer ---------- */

  overzicht() {
    this.zetLopen(false);
    const afstand = this.breedte * 0.9;
    this.camera.position.set(afstand * 0.55, afstand * 0.6, afstand * 0.75);
    this.controls.target.set(0, 0, 0);
    this.controls.maxDistance = this.breedte * 2.5;
  }

  /* Het draaipunt ligt altijd op het maaiveld, ook na schuiven: draaien voelt dan als om een plek op de grond. */
  houdDoelOpMaaiveld() {
    if (!this.w || this.lopen || this.volgen || this.vlucht) return;
    const doel = this.controls.target;
    const grond = this.hoogte(doel.x + this.midden[0], -doel.z + this.midden[1]) - this.w.referentie_nap;
    const verschil = grond - doel.y;
    if (Math.abs(verschil) < 0.01) return;
    doel.y += verschil;
    this.camera.position.y += verschil;
  }

  /* Vlieg in 0,7 s naar een punt op het maaiveld (dubbelklik), op een kwart van de huidige afstand. */
  vliegNaar(punt) {
    const afstand = Math.max(this.camera.position.distanceTo(this.controls.target) * 0.25, 25);
    const richting = this.camera.position.clone().sub(this.controls.target).normalize();
    this.vlucht = {
      begin: performance.now(),
      van: [this.camera.position.clone(), this.controls.target.clone()],
      naar: [punt.clone().addScaledVector(richting, afstand), punt.clone()],
    };
  }

  vliegStap(nu) {
    const v = this.vlucht;
    const t = Math.min((nu - v.begin) / 700, 1);
    const zacht = t * t * (3 - 2 * t);
    this.camera.position.lerpVectors(v.van[0], v.naar[0], zacht);
    this.controls.target.lerpVectors(v.van[1], v.naar[1], zacht);
    if (t >= 1) this.vlucht = null;
  }

  /* Lopen op ooghoogte: de muis kijkt rond (slepen), WASD loopt, je volgt het maaiveld. */
  zetLopen(aan) {
    if (aan === !!this.lopen || (aan && !this.w)) return;
    if (aan) {
      const kijk = this.controls.target.clone().sub(this.camera.position).setY(0).normalize();
      this.lopen = { yaw: Math.atan2(-kijk.x, -kijk.z), pitch: -0.05 };
      this.camera.position.copy(this.controls.target);
      this.zetOoghoogte();
    } else {
      const vooruit = new THREE.Vector3(0, 0, -1).applyEuler(this.camera.rotation).setY(0).normalize();
      this.controls.target.copy(this.camera.position).addScaledVector(vooruit, 30);
      this.camera.position.addScaledVector(vooruit, -10).setY(this.camera.position.y + 25);
      this.lopen = null;
    }
    this.controls.enabled = !aan && !this.selectie;
  }

  zetOoghoogte() {
    const p = this.camera.position;
    p.y = this.hoogte(p.x + this.midden[0], -p.z + this.midden[1]) - this.w.referentie_nap + 1.7;
    this.camera.rotation.set(this.lopen.pitch, this.lopen.yaw, 0, "YXZ");
  }

  kijkRond(dx, dy) {
    this.lopen.yaw -= dx * 0.004;
    this.lopen.pitch = Math.min(Math.max(this.lopen.pitch - dy * 0.004, -1.4), 1.4);
    this.zetOoghoogte();
  }

  zetZon() {
    const b = this.breedte;
    const rand = b * 0.75;
    this.zon.position.set(-b * 0.6, b * 0.9, b * 0.5);
    Object.assign(this.zon.shadow.camera, { left: -rand, right: rand, top: rand, bottom: -rand, near: 1, far: b * 3 });
    this.zon.shadow.camera.updateProjectionMatrix();
    this.zon.shadow.bias = -0.0004;
  }

  zetSfeer() {
    const b = this.breedte ?? 1000;
    const onder = this.doorzicht >= 0.5 && this.camera.position.y < 0;
    if (onder === this.onder && this.scene.fog) return;
    this.onder = onder;
    this.scene.background = onder ? new THREE.Color(ONDER) : this.lucht;
    this.scene.fog = new THREE.Fog(onder ? ONDER : LUCHT.horizon, b * 2.5, b * 9);
  }

  /* Doorzicht 0 (dicht) tot 1: maaiveld en gebouwen worden doorzichtig, je ziet grond en kabels eronder.
     Je blijft zien waar wegen, water en huizen liggen. Vanaf 0,5 mag de camera onder het maaiveld. */
  zetDoorzicht(waarde) {
    this.doorzicht = waarde;
    for (const [mesh, factor] of [[this.maaiveld, 0.8], [this.gebouwen, 1.3]]) {
      if (!mesh) continue;
      mesh.material.transparent = waarde > 0;
      mesh.material.opacity = Math.max(0.08, 1 - waarde * factor);
      mesh.material.depthWrite = waarde < 0.3;
      mesh.material.needsUpdate = true;
    }
    this.controls.maxPolarAngle = waarde >= 0.5 ? Math.PI : Math.PI * 0.49;
    this.zetSfeer();
  }

  /* Lopen zoals in een spel: WASD langs de grond in de kijkrichting, E/Q omhoog en omlaag.
     Hoe hoger je bent, hoe sneller je gaat. */
  beweeg(seconden) {
    if (!this.toetsen.size || this.volgen) return;
    const t = this.toetsen;
    const vooruit = (t.has("KeyW") || t.has("ArrowUp")) - (t.has("KeyS") || t.has("ArrowDown"));
    const opzij = (t.has("KeyD") || t.has("ArrowRight")) - (t.has("KeyA") || t.has("ArrowLeft"));
    const omhoog = t.has("KeyE") - t.has("KeyQ");
    if (!vooruit && !opzij && !omhoog) return;
    if (this.lopen) {
      const snelheid = (t.has("ShiftLeft") || t.has("ShiftRight") ? 12 : 4) * seconden;
      const voor = new THREE.Vector3(-Math.sin(this.lopen.yaw), 0, -Math.cos(this.lopen.yaw));
      const rechts = new THREE.Vector3(-voor.z, 0, voor.x);
      this.camera.position.addScaledVector(voor, vooruit * snelheid).addScaledVector(rechts, opzij * snelheid);
      return this.zetOoghoogte();
    }
    const kijk = new THREE.Vector3();
    this.camera.getWorldDirection(kijk).setY(0).normalize();
    const rechts = new THREE.Vector3().crossVectors(kijk, this.camera.up).normalize();
    const hoogteBoven = Math.max(Math.abs(this.camera.position.y), 2);
    const snel = t.has("ShiftLeft") || t.has("ShiftRight") ? 4 : 1;
    const snelheid = Math.min(Math.max(hoogteBoven * 1.5, 6), this.breedte * 0.3) * snel;
    const stap = kijk.multiplyScalar(vooruit).add(rechts.multiplyScalar(opzij)).setY(omhoog * 0.6);
    stap.multiplyScalar(snelheid * seconden);
    this.camera.position.add(stap);
    this.controls.target.add(stap);
  }

  /* ---------- muis: punt op het maaiveld, stuk kiezen, tracé tekenen ---------- */

  maaiveldPunt(gebeurtenis) {
    if (!this.maaiveld) return null;
    const rect = this.renderer.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2(((gebeurtenis.clientX - rect.left) / rect.width) * 2 - 1, -((gebeurtenis.clientY - rect.top) / rect.height) * 2 + 1);
    const straal = new THREE.Raycaster();
    straal.setFromCamera(ndc, this.camera);
    const treffer = straal.intersectObject(this.maaiveld)[0];
    if (!treffer) return null;
    return { x: treffer.point.x + this.midden[0], y: -treffer.point.z + this.midden[1], punt: treffer.point };
  }

  /* Rechthoek kiezen op het maaiveld. `klaar` krijgt de RD-omhullende [x0, y0, x1, y1]. */
  kiesStuk(klaar) {
    this.stopTekenen();
    this.selectie = { klaar, start: null, vlak: null };
    this.controls.enabled = false;
    this.renderer.domElement.style.cursor = "crosshair";
  }

  annuleerKeuze() {
    if (this.selectie?.vlak) this.scene.remove(this.selectie.vlak);
    this.selectie = null;
    this.controls.enabled = !this.volgen;
    this.renderer.domElement.style.cursor = "";
  }

  tekenKeuze(a, b) {
    const sel = this.selectie;
    if (!sel.vlak) {
      sel.vlak = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ color: "#e8a860", transparent: true, opacity: 0.4, depthTest: false }));
      sel.vlak.rotation.x = -Math.PI / 2;
      sel.vlak.renderOrder = 5;
      this.scene.add(sel.vlak);
    }
    sel.vlak.scale.set(Math.max(Math.abs(b.x - a.x), 1), Math.max(Math.abs(b.y - a.y), 1), 1);
    sel.vlak.position.copy(this.naarScene((a.x + b.x) / 2, (a.y + b.y) / 2, this.hoogte(a.x, a.y) + 1));
  }

  bindMuis() {
    const doek = this.renderer.domElement;
    let neer = null;
    doek.addEventListener("pointerdown", (e) => {
      neer = [e.clientX, e.clientY];
      if (!this.selectie) return;
      this.selectie.start = this.maaiveldPunt(e);
      doek.setPointerCapture(e.pointerId);
    });
    doek.addEventListener("pointermove", (e) => {
      if (this.lopen && e.buttons) return this.kijkRond(e.movementX, e.movementY);
      const punt = this.selectie?.start && this.maaiveldPunt(e);
      if (punt) this.tekenKeuze(this.selectie.start, punt);
    });
    doek.addEventListener("pointerup", (e) => {
      const klik = neer && Math.hypot(e.clientX - neer[0], e.clientY - neer[1]) < 5;
      if (klik && this.tekenen) {
        const punt = this.maaiveldPunt(e);
        if (punt) this.voegTekenpuntToe(punt);
        return;
      }
      const sel = this.selectie;
      const eind = sel?.start && this.maaiveldPunt(e);
      if (!eind) return;
      const a = sel.start;
      this.annuleerKeuze();
      sel.klaar([Math.min(a.x, eind.x), Math.min(a.y, eind.y), Math.max(a.x, eind.x), Math.max(a.y, eind.y)]);
    });
    doek.addEventListener("dblclick", (e) => {
      if (this.tekenen) return this.rondTekenenAf();
      const punt = !this.lopen && this.maaiveldPunt(e);
      if (punt) this.vliegNaar(punt.punt);
    });
    doek.addEventListener("contextmenu", (e) => e.preventDefault());
    addEventListener("keydown", (e) => {
      if (!this.tekenen) return;
      if (e.key === "Enter") this.rondTekenenAf();
      if (e.key === "Escape") this.stopTekenen();
    });
  }

  /* Tracé tekenen: klik punten op het maaiveld, dubbelklik of Enter om af te ronden, Esc om te stoppen. */
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
    t.voorbeeld = bouwBuis(t.punten.map((p) => p.punt.clone().setY(p.punt.y + 0.4)), 0.4, "#ffb454");
    this.scene.add(t.voorbeeld);
  }

  rondTekenenAf() {
    const t = this.tekenen;
    if (!t) return;
    // een dubbelklik zet het laatste punt twee keer: punten dichter dan 0,5 m bij de vorige vallen weg
    const punten = t.punten.filter((p, i) => !i || Math.hypot(p.x - t.punten[i - 1].x, p.y - t.punten[i - 1].y) > 0.5);
    this.stopTekenen();
    if (punten.length >= 2) t.klaar(punten.map((p) => [p.x, p.y]));
  }

  /* ---------- kabels en het nieuwe tracé ---------- */

  /* Bestaande kabels als buizen op hun indicatieve diepte onder het echte maaiveld. */
  zetNetten(netten) {
    this.wisGroep("netten");
    if (!this.wereld) return;
    const soorten = Object.fromEntries(netten.soorten.map((s) => [s.id, s]));
    const groep = new THREE.Group();
    for (const laag of netten.lagen) {
      const soort = soorten[laag.soort];
      for (const lijn of laag.lijnen) {
        if (lijn.length < 2) continue;
        const punten = lijn.map(([x, y]) => this.naarScene(x, y, this.hoogte(x, y) - soort.diepte_m));
        groep.add(bouwBuis(punten, 0.25, soort.kleur));
      }
    }
    this.netten = groep;
    this.scene.add(groep);
  }

  /* Nieuw tracé volgens het profiel van /api/aanleg ([x, y, diepte] in RD) met kruisingen.
     Ontgraven: bruine sleufwand; boring: oranje gordijn. Kruising: groene of rode bol op de bestaande kabel. */
  zetAanleg(aanleg) {
    this.wisTrace();
    if (!this.wereld || aanleg.profiel.length < 2) return 0;
    const maaiveld = aanleg.profiel.map(([x, y]) => this.naarScene(x, y, this.hoogte(x, y) + 0.2));
    const leiding = aanleg.profiel.map(([x, y, d]) => this.naarScene(x, y, this.hoogte(x, y) - d));
    this.trace = new THREE.Group();
    this.trace.add(bouwBuis(maaiveld, 0.3, "#ffb454"), bouwBuis(leiding, 0.35, "#ff5a3c"));
    this.trace.add(bouwGordijn(maaiveld, leiding, aanleg.wijze === "ontgraven" ? "#8a5a2b" : "#e8a860"));
    const bol = new THREE.SphereGeometry(Math.max(1.2, this.breedte * 0.003), 16, 12);
    for (const k of aanleg.kruisingen) {
      const teken = new THREE.Mesh(bol, new THREE.MeshBasicMaterial({ color: k.ok ? "#3ddc84" : "#ff3b3b", depthTest: false, transparent: true }));
      teken.position.copy(this.naarScene(k.x, k.y, this.hoogte(k.x, k.y) - k.kabel_diepte));
      teken.renderOrder = 6;
      this.trace.add(teken);
    }
    this.scene.add(this.trace);
    this.pad = { punten: maaiveld, lengtes: padLengtes(maaiveld) };
    return this.pad.lengtes.at(-1);
  }

  wisGroep(naam) {
    const groep = this[naam];
    if (!groep) return;
    this.scene.remove(groep);
    groep.traverse((o) => {
      o.geometry?.dispose();
      o.material?.map?.dispose();
      o.material?.alphaMap?.dispose();
      o.material?.dispose?.();
    });
    this[naam] = null;
  }

  wisTrace() {
    this.animatie = null;
    this.wisGroep("werk");
    this.wisGroep("trace");
    this.pad = null;
    this.zetVolgen(false);
  }

  /* ---------- aanleg in beeld: graven of boren ---------- */

  /* Speel de aanleg af. `bijwerk(fractie, fase)` krijgt de voortgang (0 tot 1) en de naam van de fase. */
  speelAanleg(aanleg, bijwerk) {
    this.wisGroep("werk");
    this.werk = new THREE.Group();
    this.scene.add(this.werk);
    const lengte = aanleg.lengte;
    const bouw = aanleg.wijze === "boring" ? this.bouwBoring(aanleg) : this.bouwSleuf(aanleg);
    if (this.trace) this.trace.visible = false;
    this.animatie = { begin: performance.now(), lengte, bijwerk, ...bouw };
  }

  /* Sleuf: grondblokjes van 0,5 m die naar een hoop naast de sleuf gaan en er later weer in. */
  bouwSleuf(aanleg) {
    const breedte = aanleg.sleuf_breedte;
    const kolommen = Math.max(1, Math.round(breedte / BLOKJE_M));
    const lagen = Math.max(1, Math.ceil((aanleg.diepte + 0.1) / BLOKJE_M));
    let stap = BLOKJE_M;
    // shortcut: bij een heel lang tracé worden de blokjes per stap groter weergegeven, anders te zwaar
    while ((aanleg.lengte / stap) * kolommen * lagen > MAX_BLOKJES) stap *= 2;
    const punten = bemonster(aanleg.profiel, stap);
    const aantal = punten.length * kolommen * lagen;
    const blokjes = new THREE.InstancedMesh(new THREE.BoxGeometry(BLOKJE_M, BLOKJE_M, BLOKJE_M), new THREE.MeshStandardMaterial({ roughness: 1 }), aantal);
    const reis = [];
    punten.forEach((p, k) => {
      const maaiveld = this.hoogte(p.x, p.y);
      for (let laag = 0; laag < lagen; laag++) {
        for (let kol = 0; kol < kolommen; kol++) {
          const dwars = (kol - (kolommen - 1) / 2) * BLOKJE_M;
          const q = laag * kolommen + kol;
          const opzij = breedte / 2 + 0.4 + (q % 3) * BLOKJE_M;
          const van = this.naarScene(p.x + p.nx * dwars, p.y + p.ny * dwars, maaiveld - 0.25 - laag * BLOKJE_M);
          const naar = this.naarScene(p.x + p.nx * opzij, p.y + p.ny * opzij, this.hoogte(p.x + p.nx * opzij, p.y + p.ny * opzij) + 0.25 + Math.floor(q / 3) * BLOKJE_M);
          const nr = reis.length;
          blokjes.setColorAt(nr, new THREE.Color(laag === 0 ? GROND.humus : kies(GROND.zand, k, q)));
          reis.push({ s: p.s, van, naar });
        }
      }
    });
    blokjes.castShadow = true;
    const open = bouwStrook(punten, breedte, (x, y) => this.hoogte(x, y), (x, y, h) => this.naarScene(x, y, h), GROND.open);
    const dicht = bouwStrook(punten, breedte, (x, y) => this.hoogte(x, y), (x, y, h) => this.naarScene(x, y, h), GROND.dicht);
    const kabel = bouwBuis(aanleg.profiel.map(([x, y, d]) => this.naarScene(x, y, this.hoogte(x, y) - d)), 0.2, "#ff5a3c");
    this.werk.add(blokjes, open, dicht, kabel);
    return { soort: "sleuf", blokjes, reis, open, dicht, kabel, punten: punten.length };
  }

  /* Boring: bouwputten bij intrede en uittrede, een boorkop door de grond en daarna de ingetrokken leiding. */
  bouwBoring(aanleg) {
    const pad = aanleg.profiel.map(([x, y, d]) => this.naarScene(x, y, this.hoogte(x, y) - d));
    const put = new THREE.MeshStandardMaterial({ color: GROND.open });
    for (const [x, y] of [aanleg.profiel[0], aanleg.profiel.at(-1)]) {
      const kuil = new THREE.Mesh(new THREE.BoxGeometry(3, 1.6, 2), put);
      kuil.position.copy(this.naarScene(x, y, this.hoogte(x, y) - 0.75));
      this.werk.add(kuil);
    }
    const boorgat = bouwBuis(pad, 0.3, "#6d5a45");
    const leiding = bouwBuis(pad, 0.22, "#ff5a3c");
    const kop = new THREE.Mesh(new THREE.ConeGeometry(0.6, 2, 12).rotateX(Math.PI / 2), new THREE.MeshStandardMaterial({ color: "#ffd23f", emissive: "#ffd23f", emissiveIntensity: 0.6 }));
    this.werk.add(boorgat, leiding, kop);
    return { soort: "boring", boorgat, leiding, kop, pad: { punten: pad, lengtes: padLengtes(pad) } };
  }

  /* Eén beeld van de animatie. Sleuf: 60% graven en kabel leggen, 40% dichtgooien. Boring: 70% boren, 30% intrekken. */
  animeer(nu) {
    const a = this.animatie;
    const f = Math.min((nu - a.begin) / AANLEG_SPEELDUUR_MS, 1);
    if (a.soort === "sleuf") this.animeerSleuf(a, f);
    else this.animeerBoring(a, f);
    if (f >= 1) this.animatie = null;
  }

  animeerSleuf(a, f) {
    const voor = a.lengte * Math.min(f / 0.6, 1); // graaffront
    const achter = a.lengte * Math.max((f - 0.6) / 0.4, 0); // dichtgooien
    const m = new THREE.Matrix4();
    const plek = new THREE.Vector3();
    const weg = new THREE.Matrix4().makeScale(0, 0, 0);
    a.reis.forEach((r, i) => {
      const heen = Math.min(Math.max((voor - r.s) / 3, 0), 1); // over 3 m graaffront vliegt een blokje naar de hoop
      const terug = Math.min(Math.max((achter - r.s) / 3, 0), 1);
      if (heen === 0 || terug === 1) return a.blokjes.setMatrixAt(i, weg);
      const t = terug > 0 ? 1 - terug : heen;
      plek.lerpVectors(r.van, r.naar, t).setY(plek.y + 1.5 * Math.sin(Math.PI * t));
      a.blokjes.setMatrixAt(i, m.makeTranslation(plek.x, plek.y, plek.z));
    });
    a.blokjes.instanceMatrix.needsUpdate = true;
    const stroken = a.punten - 1;
    const [i0, i1] = [Math.floor((achter / a.lengte) * stroken), Math.floor((voor / a.lengte) * stroken)];
    a.open.geometry.setDrawRange(i0 * 6, Math.max(0, i1 - i0) * 6);
    a.dicht.geometry.setDrawRange(0, i0 * 6);
    a.kabel.geometry.setDrawRange(0, Math.floor(a.kabel.geometry.index.count * Math.max(0, voor - 5) / a.lengte / 3) * 3);
    a.bijwerk?.(f, f < 0.6 ? "Graven en kabel leggen" : f < 1 ? "Dichtgooien" : "Klaar");
  }

  animeerBoring(a, f) {
    const boor = Math.min(f / 0.7, 1);
    const trek = Math.max((f - 0.7) / 0.3, 0);
    const lengte = a.pad.lengtes.at(-1);
    const vorig = this.pad;
    this.pad = a.pad;
    const { punt, richting } = this.plekOp(lengte * boor);
    this.pad = vorig;
    a.kop.position.copy(punt);
    a.kop.lookAt(punt.clone().add(richting.lengthSq() ? richting : new THREE.Vector3(1, 0, 0)));
    a.kop.visible = boor < 1;
    a.boorgat.geometry.setDrawRange(0, Math.floor((a.boorgat.geometry.index.count * boor) / 3) * 3);
    a.leiding.geometry.setDrawRange(0, Math.floor((a.leiding.geometry.index.count * trek) / 3) * 3);
    a.bijwerk?.(f, f < 0.7 ? "Boren" : f < 1 ? "Leiding intrekken" : "Klaar");
  }

  /* ---------- langs het tracé lopen ---------- */

  plekOp(s) {
    const { punten, lengtes } = this.pad;
    const nr = Math.min(Math.max(lengtes.findIndex((l) => l >= s) - 1, 0), punten.length - 2);
    const [a, b] = [punten[nr], punten[nr + 1]];
    const t = Math.min(Math.max((s - lengtes[nr]) / Math.max(lengtes[nr + 1] - lengtes[nr], 1e-6), 0), 1);
    return { punt: a.clone().lerp(b, t), richting: b.clone().sub(a).setY(0).normalize() };
  }

  /* Camera op ooghoogte achter het punt op afstand s, kijkend langs het tracé. */
  zetPositie(s) {
    if (!this.pad || !this.volgen) return;
    const { punt, richting } = this.plekOp(s);
    this.camera.position.copy(punt).addScaledVector(richting, -12).setY(punt.y + 5);
    this.controls.target.copy(punt).addScaledVector(richting, 20);
    this.camera.lookAt(this.controls.target);
  }

  zetVolgen(aan) {
    if (aan && !this.pad) return;
    if (aan) this.zetLopen(false);
    if (aan && !this.volgen) this.terug = { positie: this.camera.position.clone(), doel: this.controls.target.clone() };
    if (!aan && this.volgen && this.terug) {
      this.camera.position.copy(this.terug.positie);
      this.controls.target.copy(this.terug.doel);
    }
    this.volgen = aan;
    this.controls.enabled = !aan && !this.selectie;
    if (!aan) this.speelt = false;
  }

  ga(afstand) {
    this.afstand = afstand;
    this.zetPositie(afstand);
  }

  speel(aan, snelheid, bijwerk) {
    this.speelt = aan && !!this.pad;
    if (this.speelt && this.afstand >= this.pad.lengtes.at(-1)) this.afstand = 0;
    this.snelheid = snelheid;
    this.bijwerk = bijwerk;
    this.laatste = performance.now();
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

  /* ---------- levensloop ---------- */

  leegmaken() {
    this.stopTekenen();
    this.annuleerKeuze();
    this.wisTrace();
    this.wisGroep("netten");
    this.wisGroep("wereld");
    this.maaiveld = this.gebouwen = null;
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

  lus() {
    if (!this.actief) return;
    const nu = performance.now();
    this.beweeg(Math.min((nu - (this.vorigBeeld ?? nu)) / 1000, 0.1));
    this.vorigBeeld = nu;
    if (this.speelt) this.loopStap();
    if (this.animatie) this.animeer(nu);
    if (this.vlucht) this.vliegStap(nu);
    if (!this.lopen) {
      this.houdDoelOpMaaiveld();
      this.controls.update();
    }
    this.zetSfeer();
    this.renderer.render(this.scene, this.camera);
    requestAnimationFrame(() => this.lus());
  }
}

window.BlokWeergave = BlokWeergave;
window.laadLuchtfoto = laadLuchtfoto;
window.dispatchEvent(new Event("blok-gereed"));

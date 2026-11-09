/* 3D-blok van een projectgebied: bovenvlak met de bodemlagen als doorsnede aan de vier zijkanten.
   Gladde, geschilderde stijl (vaste kleuren, zachte schaduw per zijde), geen blokjes.
   Bodemlagen komen van /api/blok en zijn voorbeelddata. Draaien: slepen, zoomen: scrollen. */
import * as THREE from "three";
import { OrbitControls } from "three/addons/OrbitControls.js";

const ZIJDEN_SCHADUW = { zuid: 0.92, oost: 0.74, noord: 0.6, west: 0.8 };

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

export class BlokWeergave {
  constructor(houder) {
    this.houder = houder;
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    houder.append(this.renderer.domElement);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(32, 1, 1, 1e6);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.maxPolarAngle = Math.PI * 0.47;
    this.blok = null;
    this.actief = false;
    this.verschuiving = [0, 0];
    this.selectie = null;
    this.bindSelectie();
    new ResizeObserver(() => this.pasMaatAan()).observe(houder);
  }

  toon(data) {
    this.leegmaken();
    const [gx0, gy0, gx1, gy1] = data.gebied;
    const [cx, cy] = [(gx0 + gx1) / 2, (gy0 + gy1) / 2];
    this.verschuiving = [cx, cy];
    data = { ...data, gebied: [gx0 - cx, gy0 - cy, gx1 - cx, gy1 - cy] };
    const [x0, y0, x1, y1] = data.gebied;
    const breedte = Math.max(x1 - x0, y1 - y0);
    this.schaalZ = overdrijving(breedte, data.diepte);
    this.blok = new THREE.Group();
    for (const naam of Object.keys(ZIJDEN_SCHADUW)) this.blok.add(bouwZijde(data, naam, this.schaalZ));
    this.blok.add(bouwBovenvlak(data));
    this.scene.add(this.blok);
    this.scene.background = new THREE.Color("#12303a");
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

  leegmaken() {
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

  lus() {
    if (!this.actief) return;
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
    requestAnimationFrame(() => this.lus());
  }
}

window.BlokWeergave = BlokWeergave;
window.dispatchEvent(new Event("blok-gereed"));

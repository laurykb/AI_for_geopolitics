/** Laury — la mascotte 3D, guide de la visite (portage fidèle de proto_9 l.1651-1714).
 *
 * Chibi assemblé en primitives three (aucun sprite ni modèle chargé), contour
 * « autocollant » blanc par coques inversées (BackSide), palette du SVG maître. Le
 * geste : le bras droit levé OFFRE le petit monde — LA texture du globe du jeu — dans
 * sa main. La scène `globe-stage.tsx` la crée une fois et l'anime dans sa boucle
 * (compagnon-caméra) ; ici, aucune dépendance à React ni au temps. */

import * as THREE from "three";

export type MascotHandle = {
  /** Racine positionnée chaque frame près de la caméra (masquée par défaut). */
  g: THREE.Group;
  /** Le gréement animé (bob/roll d'inactivité). */
  rig: THREE.Group;
  head: THREE.Mesh;
  /** Bras droit levé (le geste d'offrande) — porte le petit monde. */
  armR: THREE.Group;
  /** Le petit monde dans la main : mappé sur LA texture du globe. */
  mini: THREE.Mesh<THREE.SphereGeometry, THREE.MeshBasicMaterial>;
  halo: THREE.Mesh<THREE.TorusGeometry, THREE.MeshBasicMaterial>;
  spark: THREE.Mesh;
};

/** Construit Laury et l'ajoute à la scène (masquée). `texture` = la texture du globe
 * (le petit monde offert). */
export function createMascot(scene: THREE.Scene, texture: THREE.Texture): MascotHandle {
  const g = new THREE.Group();
  const rig = new THREE.Group();
  g.add(rig);

  const M = {
    skin: new THREE.MeshStandardMaterial({ color: "#a7693d", roughness: 0.62, metalness: 0.04 }),
    black: new THREE.MeshStandardMaterial({ color: "#131317", roughness: 0.5, metalness: 0.12 }),
    hair: new THREE.MeshStandardMaterial({ color: "#1c0f08", roughness: 0.75 }),
    tee: new THREE.MeshStandardMaterial({ color: "#f4f2ea", roughness: 0.72 }),
    gum: new THREE.MeshStandardMaterial({ color: "#d9d6cb", roughness: 0.85 }),
    eye: new THREE.MeshBasicMaterial({ color: "#3a2313" }),
  };
  const OUT = new THREE.MeshBasicMaterial({ color: "#ffffff", side: THREE.BackSide });

  const put = <T extends THREE.Object3D>(m: T, x: number, y: number, z: number, p: THREE.Object3D = rig): T => {
    m.position.set(x, y, z);
    p.add(m);
    return m;
  };
  // Contour « autocollant » : une coque inversée qui réutilise la géométrie, agrandie.
  const hull = (m: THREE.Mesh, s = 1.08): THREE.Mesh => {
    const o = new THREE.Mesh(m.geometry, OUT);
    o.position.copy(m.position);
    o.rotation.copy(m.rotation);
    o.scale.copy(m.scale).multiplyScalar(s);
    m.parent!.add(o);
    return o;
  };

  const head = put(new THREE.Mesh(new THREE.SphereGeometry(0.021, 22, 18), M.skin), 0, 0.052, 0);
  head.scale.set(1, 0.95, 0.96);
  for (const s of [-1, 1]) {
    // yeux hublots bruns + reflets
    put(new THREE.Mesh(new THREE.SphereGeometry(0.0052, 10, 10), M.eye), s * 0.0082, 0.051, 0.0175);
    put(
      new THREE.Mesh(new THREE.SphereGeometry(0.0016, 6, 6), new THREE.MeshBasicMaterial({ color: "#ffffff" })),
      s * 0.0065,
      0.0535,
      0.0215,
    );
  }
  for (let i = 0; i < 8; i++) {
    // boucles en grappes de billes
    const a = Math.PI * 0.15 + i * ((Math.PI * 0.7) / 7);
    put(
      new THREE.Mesh(new THREE.SphereGeometry(0.0045, 8, 8), M.hair),
      Math.cos(a) * 0.019,
      0.045 + Math.sin(i * 2.1) * 0.003,
      -0.006 - Math.sin(a) * 0.012,
    );
  }
  const cap = put(
    new THREE.Mesh(new THREE.SphereGeometry(0.0215, 20, 14, 0, Math.PI * 2, 0, Math.PI * 0.52), M.black),
    0,
    0.0585,
    -0.001,
  );
  const visor = put(
    new THREE.Mesh(new THREE.CylinderGeometry(0.019, 0.019, 0.0028, 18, 1, false, -0.62, 1.24), M.black),
    0,
    0.0585,
    0.006,
  );
  visor.scale.set(1, 0.55, 1.35);
  const torso = put(new THREE.Mesh(new THREE.CylinderGeometry(0.0125, 0.0155, 0.024, 14), M.tee), 0, 0.026, 0);
  const strap = put(new THREE.Mesh(new THREE.BoxGeometry(0.0035, 0.026, 0.003), M.black), -0.004, 0.027, 0.0128);
  strap.rotation.z = 0.55;
  put(new THREE.Mesh(new THREE.BoxGeometry(0.011, 0.007, 0.005), M.black), -0.0125, 0.017, 0.006); // sacoche
  const armL = put(new THREE.Mesh(new THREE.CylinderGeometry(0.0032, 0.003, 0.017, 8), M.tee), -0.014, 0.028, 0);
  armL.rotation.z = 0.28;
  put(new THREE.Mesh(new THREE.SphereGeometry(0.0036, 8, 8), M.skin), -0.0175, 0.019, 0);

  // bras droit levé — LE geste : offrir le petit monde
  const armR = new THREE.Group();
  armR.position.set(0.013, 0.033, 0.002);
  rig.add(armR);
  const upperR = new THREE.Mesh(new THREE.CylinderGeometry(0.0032, 0.003, 0.016, 8), M.tee);
  upperR.position.set(0.004, 0.007, 0.004);
  upperR.rotation.z = -0.9;
  upperR.rotation.x = -0.35;
  armR.add(upperR);
  const handR = new THREE.Mesh(new THREE.SphereGeometry(0.0038, 8, 8), M.skin);
  handR.position.set(0.011, 0.013, 0.008);
  armR.add(handR);
  const mini = new THREE.Mesh(
    new THREE.SphereGeometry(0.0085, 18, 14),
    new THREE.MeshBasicMaterial({ map: texture }), // le monde du jeu, dans sa main
  );
  mini.position.set(0.011, 0.0255, 0.008);
  armR.add(mini);
  const halo = new THREE.Mesh(
    new THREE.TorusGeometry(0.0122, 0.0006, 8, 36),
    new THREE.MeshBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.75 }),
  );
  halo.position.copy(mini.position);
  halo.rotation.x = Math.PI / 2.6;
  armR.add(halo);
  const spark = new THREE.Mesh(
    new THREE.OctahedronGeometry(0.0016, 0),
    new THREE.MeshBasicMaterial({ color: 0xeab308 }),
  );
  armR.add(spark);

  for (const s of [-1, 1]) {
    // jambes + sneakers (semelle gomme)
    put(new THREE.Mesh(new THREE.CylinderGeometry(0.004, 0.0045, 0.015, 10), M.black), s * 0.006, 0.0075, 0);
    put(new THREE.Mesh(new THREE.BoxGeometry(0.0085, 0.004, 0.0125), M.tee), s * 0.006, 0.0005, 0.002);
    put(new THREE.Mesh(new THREE.BoxGeometry(0.009, 0.0016, 0.013), M.gum), s * 0.006, -0.0022, 0.002);
  }

  hull(head, 1.07);
  hull(cap, 1.07);
  hull(torso, 1.08);

  g.visible = false;
  g.scale.setScalar(0.68);
  scene.add(g);

  return { g, rig, head, armR, mini, halo, spark };
}

/** Le ciel du globe réaliste (spec planète-réaliste A3/A4/A6) — sphères
 * séparées composées autour de la Terre : nuages (alpha = luminance),
 * atmosphère (fresnel BackSide teinté par le soleil), lune texturée,
 * champ d'étoiles en fond. Three pur, testable en node ; le rendu, le
 * soleil animé et le morph 2D⇄3D restent pilotés par `globe-stage.tsx`.
 * Les nuages et l'atmosphère se fondent quand le monde s'aplatit (`uFlat`). */

import * as THREE from "three";

export function makeClouds(tex: THREE.Texture): THREE.Mesh {
  tex.colorSpace = THREE.SRGBColorSpace;
  const m = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false,
    uniforms: {
      uMap: { value: tex },
      uSun: { value: new THREE.Vector3(1, 0.15, 0.4).normalize() },
      uFlat: { value: 0 },
    },
    vertexShader: `varying vec2 vUv; varying vec3 vN; void main(){ vUv=uv;
      vN=normalize(mat3(modelMatrix)*normalize(position));
      gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
    fragmentShader: `uniform sampler2D uMap; uniform vec3 uSun; uniform float uFlat;
      varying vec2 vUv; varying vec3 vN;
      void main(){ vec3 c=texture2D(uMap,vUv).rgb; float a=dot(c,vec3(0.333));
        // Nuages éclairés par le soleil : blancs le jour, sombres (mais présents) la nuit.
        float lit=smoothstep(-0.2, 0.3, dot(normalize(vN), normalize(uSun)));
        gl_FragColor=vec4(vec3(0.10+0.90*lit), a*0.9*(1.0-uFlat)); }`,
  });
  return new THREE.Mesh(new THREE.SphereGeometry(1.003, 96, 64), m);
}

export function makeAtmosphere(): { mesh: THREE.Mesh; setSun: (d: THREE.Vector3) => void; setFlat: (k: number) => void } {
  const mat = new THREE.ShaderMaterial({
    side: THREE.BackSide, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false,
    uniforms: { uSun: { value: new THREE.Vector3(1, 0.15, 0.4).normalize() }, uFlat: { value: 0 } },
    vertexShader: `varying vec3 vN; varying vec3 vW; void main(){
      vN=normalize(mat3(modelMatrix)*normal); vW=normalize(mat3(modelMatrix)*position);
      gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
    fragmentShader: `varying vec3 vN; varying vec3 vW; uniform vec3 uSun; uniform float uFlat;
      void main(){
        float d=dot(vN,vec3(0.,0.,1.));
        float rim=pow(0.72-d,3.2);
        float outer=smoothstep(0.42,0.72,0.72-d);            // ~1 au limbe extrême
        float sd=clamp(dot(normalize(vW),normalize(uSun))*0.5+0.5,0.0,1.0);
        // Rougeâtre au bord extrême ET côté ombre ; bleu ciel à l'intérieur / côté soleil
        // (halo two-tone des rendus photo three.js).
        float red=clamp(outer*0.75 + (1.0-sd)*0.55, 0.0, 1.0);
        vec3 col=mix(vec3(0.36,0.65,1.0), vec3(0.9,0.35,0.12), red);
        gl_FragColor=vec4(col*rim*1.55*(1.0-uFlat),1.0);
      }`,
  });
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(1.055, 72, 48), mat);
  return {
    mesh,
    setSun: (d) => (mat.uniforms.uSun.value as THREE.Vector3).copy(d).normalize(),
    setFlat: (k) => (mat.uniforms.uFlat.value = k),
  };
}

export function makeMoon(tex: THREE.Texture): THREE.Mesh {
  tex.colorSpace = THREE.SRGBColorSpace;
  const mesh = new THREE.Mesh(
    new THREE.SphereGeometry(0.34, 48, 32),
    new THREE.MeshStandardMaterial({ map: tex, roughness: 1, metalness: 0 }),
  );
  mesh.position.set(-4.6, 2.4, -6.5);
  return mesh;
}

export function makeStarfield(tex: THREE.Texture): THREE.Mesh {
  tex.colorSpace = THREE.SRGBColorSpace;
  return new THREE.Mesh(
    new THREE.SphereGeometry(50, 48, 32),
    new THREE.MeshBasicMaterial({ map: tex, side: THREE.BackSide, depthWrite: false }),
  );
}

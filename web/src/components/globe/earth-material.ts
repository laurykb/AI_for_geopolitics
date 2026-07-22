/** Matériau Terre réaliste (spec planète réaliste A2) : un ShaderMaterial qui
 * mélange jour/nuit selon le soleil, ajoute un spéculaire océan, compose la
 * surcouche gameplay (bordures/liseré/cicatrices) par-dessus — et PRÉSERVE
 * verbatim le morph vertex sphère⇄carte (`mix(position, flatPos, uFlat)`) du
 * globe peint. On ne change que le fragment ; le vertex déplie vers le même
 * plan équirectangulaire que `morph.ts` (FLAT_W×FLAT_H). */

import * as THREE from "three";

export type EarthMaterial = {
  material: THREE.ShaderMaterial;
  setSun: (dir: THREE.Vector3) => void;
  setFlat: (k: number) => void;
};

export function createEarthMaterial(opts: {
  day: THREE.Texture;
  night: THREE.Texture;
  overlay: THREE.Texture;
  flatW: number;
  flatH: number;
}): EarthMaterial {
  const { day, night, overlay, flatW, flatH } = opts;
  day.colorSpace = THREE.SRGBColorSpace;
  night.colorSpace = THREE.SRGBColorSpace;
  const material = new THREE.ShaderMaterial({
    uniforms: {
      uDay: { value: day },
      uNight: { value: night },
      uOverlay: { value: overlay },
      uSun: { value: new THREE.Vector3(1, 0.15, 0.4).normalize() },
      uFlat: { value: 0 },
    },
    vertexShader: `
      uniform float uFlat;
      varying vec2 vUv; varying vec3 vNormalW;
      void main(){
        vUv = uv;
        vNormalW = normalize(mat3(modelMatrix) * normalize(position)); // normale sphere stable
        vec3 flatPos = vec3((uv.x-0.5)*${flatW.toFixed(6)}, (uv.y-0.5)*${flatH.toFixed(6)}, 0.0);
        vec3 p = mix(position, flatPos, uFlat);           // MORPH VERBATIM
        gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
      }`,
    fragmentShader: `
      uniform sampler2D uDay; uniform sampler2D uNight; uniform sampler2D uOverlay;
      uniform vec3 uSun; uniform float uFlat;
      varying vec2 vUv; varying vec3 vNormalW;
      void main(){
        vec3 day = texture2D(uDay, vUv).rgb;
        vec3 night = texture2D(uNight, vUv).rgb;
        float sd = dot(normalize(vNormalW), normalize(uSun));
        // Terminateur adouci : la face nuit reste lisible, la transition jour/nuit large.
        float dayMix = smoothstep(-0.25, 0.35, sd);
        dayMix = mix(dayMix, 1.0, uFlat);                 // carte = plein jour
        vec3 col = mix(night, day, dayMix);
        col += day * 0.06;                                // ambiant : dévoile la face nuit
        col *= 1.45;                                      // rehausse global (moins foncé)
        float lum = dot(day, vec3(0.299,0.587,0.114));
        float ocean = smoothstep(0.24, 0.08, lum) * step(day.r, day.b);
        vec3 h = normalize(uSun + vec3(0.0,0.0,1.0));
        float spec = pow(max(dot(normalize(vNormalW), h), 0.0), 48.0) * ocean * dayMix * (1.0 - uFlat);
        col += vec3(0.95,0.97,1.0) * spec * 3.0;          // reflet solaire sur l'océan (glint)
        // Tonemap filmique (ACES approx) : contraste + hautes lumières douces façon three.js.
        col = clamp((col * (2.51 * col + 0.03)) / (col * (2.43 * col + 0.59) + 0.14), 0.0, 1.0);
        vec4 ov = texture2D(uOverlay, vUv);
        col = mix(col, ov.rgb, ov.a);                     // surcouche gameplay (au-dessus du tonemap)
        gl_FragColor = vec4(col, 1.0);
      }`,
  });
  return {
    material,
    setSun: (dir) => (material.uniforms.uSun.value as THREE.Vector3).copy(dir).normalize(),
    setFlat: (k) => (material.uniforms.uFlat.value = k),
  };
}

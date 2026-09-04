import * as THREE from "three";

/**
 * Genera texturas de resplandor radial procedurales en canvas para evitar assets externos.
 */
export function createGlowTexture(
  size = 256,
  innerColor = "rgba(255,255,255,1.0)",
  outerColor = "rgba(255,255,255,0.0)"
): THREE.CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    const half = size / 2;
    const grad = ctx.createRadialGradient(half, half, 0, half, half, half);
    grad.addColorStop(0, innerColor);
    grad.addColorStop(
      0.3,
      innerColor.replace(/[\d.]+\)$/, "0.5)")
    );
    grad.addColorStop(1, outerColor);
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, size, size);
  }
  const tex = new THREE.CanvasTexture(canvas);
  tex.needsUpdate = true;
  return tex;
}

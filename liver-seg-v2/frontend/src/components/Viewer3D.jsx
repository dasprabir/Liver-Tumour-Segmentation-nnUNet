// src/components/Viewer3D.jsx
// Fix: defer Three.js initialisation until the container has a
// non-zero clientHeight. Uses ResizeObserver to detect when the
// container is actually sized before creating the renderer.

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import "./Viewer3D.css";

function buildGeometry(meshData) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute(
        "position",
        new THREE.BufferAttribute(new Float32Array(meshData.vertices.flat()), 3)
    );
    geometry.setIndex(
        new THREE.BufferAttribute(new Uint32Array(meshData.faces.flat()), 1)
    );
    geometry.computeVertexNormals();
    geometry.computeBoundingSphere();
    return geometry;
}

function createLighting(scene) {
    scene.add(new THREE.AmbientLight(0xfff0e8, 0.5));
    const key = new THREE.DirectionalLight(0xffffff, 1.2);
    key.position.set(2, 4, 3);
    key.castShadow = true;
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xd0e8ff, 0.4);
    fill.position.set(-3, 1, -2);
    scene.add(fill);
    const rim = new THREE.DirectionalLight(0xffffff, 0.3);
    rim.position.set(0, -2, -4);
    scene.add(rim);
}

function liverMat(opacity) {
    return new THREE.MeshPhongMaterial({
        color:       new THREE.Color(0x0e7c7b),
        emissive:    new THREE.Color(0x012e2e),
        specular:    new THREE.Color(0x66ffff),
        shininess:   45,
        transparent: true,
        opacity,
        side:        THREE.DoubleSide,
        depthWrite:  false,
    });
}

function tumorMat() {
    return new THREE.MeshPhongMaterial({
        color:    new THREE.Color(0xff2020),
        emissive: new THREE.Color(0x6b0000),
        specular: new THREE.Color(0xff8888),
        shininess: 70,
        side: THREE.DoubleSide,
    });
}

export default function Viewer3D({ liverMesh, tumorMesh }) {
    const containerRef = useRef(null);
    const rendererRef  = useRef(null);
    const frameRef     = useRef(null);
    const liverMatRef  = useRef(null);
    const tumorMatRef  = useRef(null);
    const liverMeshRef = useRef(null);
    const tumorMeshRef = useRef(null);
    const controlsRef  = useRef(null);
    const initDoneRef  = useRef(false);

    const [wireframe,    setWireframe]    = useState(false);
    const [liverOpacity, setLiverOpacity] = useState(0.78);
    const [showLiver,    setShowLiver]    = useState(true);
    const [showTumor,    setShowTumor]    = useState(true);
    const [autoRotate,   setAutoRotate]   = useState(true);

    useEffect(() => {
        const container = containerRef.current;
        if (!container) return;

        let cleanup = null;

        // Wait until container has a non-zero size before init
        const ro = new ResizeObserver((entries) => {
            const entry = entries[0];
            const { width, height } = entry.contentRect;

            if (width > 0 && height > 0 && !initDoneRef.current) {
                initDoneRef.current = true;
                cleanup = initScene(container, width, height);
                // Keep the ResizeObserver alive for resize handling
            } else if (initDoneRef.current && rendererRef.current) {
                // Handle resize after init
                const camera = rendererRef.current.userData?.camera;
                if (camera) {
                    camera.aspect = width / height;
                    camera.updateProjectionMatrix();
                    rendererRef.current.setSize(width, height);
                }
            }
        });

        ro.observe(container);

        return () => {
            ro.disconnect();
            if (cleanup) cleanup();
        };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [liverMesh, tumorMesh]);

    function initScene(container, W, H) {
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x080b12);

        const camera = new THREE.PerspectiveCamera(40, W / H, 0.01, 50);
        camera.position.set(0, 0.2, 3.2);

        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.setSize(W, H);
        renderer.shadowMap.enabled     = true;
        renderer.shadowMap.type        = THREE.PCFSoftShadowMap;
        renderer.toneMapping           = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure   = 1.0;
        // Store camera reference for resize handler
        renderer.userData.camera = camera;
        container.appendChild(renderer.domElement);
        rendererRef.current = renderer;

        const controls = new OrbitControls(camera, renderer.domElement);
        controls.enableDamping   = true;
        controls.dampingFactor   = 0.06;
        controls.autoRotate      = autoRotate;
        controls.autoRotateSpeed = 0.5;
        controls.minDistance     = 0.5;
        controls.maxDistance     = 8;
        controlsRef.current = controls;

        createLighting(scene);

        const grid = new THREE.GridHelper(4, 24, 0x111827, 0x111827);
        grid.position.y = -1.2;
        scene.add(grid);

        if (liverMesh) {
            const geo = buildGeometry(liverMesh);
            const mat = liverMat(liverOpacity);
            liverMatRef.current = mat;
            const mesh = new THREE.Mesh(geo, mat);
            mesh.castShadow = mesh.receiveShadow = true;
            liverMeshRef.current = mesh;
            scene.add(mesh);

            const glowMat = new THREE.MeshPhongMaterial({
                color: new THREE.Color(0x0e9e9c),
                transparent: true, opacity: 0.05,
                side: THREE.BackSide, depthWrite: false,
            });
            const glow = new THREE.Mesh(geo.clone(), glowMat);
            glow.scale.setScalar(1.02);
            scene.add(glow);
        }

        if (tumorMesh) {
            const geo = buildGeometry(tumorMesh);
            const mat = tumorMat();
            tumorMatRef.current = mat;
            const mesh = new THREE.Mesh(geo, mat);
            mesh.castShadow = mesh.receiveShadow = true;
            tumorMeshRef.current = mesh;
            scene.add(mesh);
        }

        scene.add(new THREE.AxesHelper(0.35));

        const animate = () => {
            frameRef.current = requestAnimationFrame(animate);
            controls.update();
            renderer.render(scene, camera);
        };
        animate();

        return () => {
            cancelAnimationFrame(frameRef.current);
            renderer.dispose();
            initDoneRef.current = false;
            if (container.contains(renderer.domElement))
                container.removeChild(renderer.domElement);
        };
    }

    // Live control updates
    useEffect(() => {
        if (controlsRef.current) controlsRef.current.autoRotate = autoRotate;
    }, [autoRotate]);

    useEffect(() => {
        [liverMatRef, tumorMatRef].forEach(r => {
            if (r.current) { r.current.wireframe = wireframe; r.current.needsUpdate = true; }
        });
    }, [wireframe]);

    useEffect(() => {
        if (liverMatRef.current) liverMatRef.current.opacity = liverOpacity;
    }, [liverOpacity]);

    useEffect(() => {
        if (liverMeshRef.current) liverMeshRef.current.visible = showLiver;
    }, [showLiver]);

    useEffect(() => {
        if (tumorMeshRef.current) tumorMeshRef.current.visible = showTumor;
    }, [showTumor]);

    const liverStats = liverMesh
        ? `${liverMesh.vertex_count.toLocaleString()} verts · ${liverMesh.face_count.toLocaleString()} faces`
        : "—";
    const tumorStats = tumorMesh
        ? `${tumorMesh.vertex_count.toLocaleString()} verts · ${tumorMesh.face_count.toLocaleString()} faces`
        : "Not detected";

    return (
        <div className="v3d-root">
            <div className="v3d-canvas" ref={containerRef} />

            <div className="v3d-legend">
                <div className="v3d-legend-item">
                    <span className="v3d-swatch v3d-swatch-liver" />Liver
                </div>
                <div className="v3d-legend-item">
                    <span className="v3d-swatch v3d-swatch-tumor" />Tumour
                </div>
            </div>

            <div className="v3d-controls">
                <div className="v3d-ctrl-group">
                    <label className="v3d-toggle">
                        <input type="checkbox" checked={showLiver}
                            onChange={e => setShowLiver(e.target.checked)} />
                        <span className="v3d-dot v3d-dot-liver" />
                        Liver
                    </label>
                    <div className="v3d-opacity-row">
                        <input type="range" min={0.1} max={0.95} step={0.05}
                            value={liverOpacity} disabled={!showLiver}
                            onChange={e => setLiverOpacity(parseFloat(e.target.value))}
                            className="v3d-slider" title="Liver opacity" />
                        <span className="v3d-slider-val">{Math.round(liverOpacity * 100)}%</span>
                    </div>
                </div>

                <div className="v3d-divider" />

                <label className="v3d-toggle">
                    <input type="checkbox" checked={showTumor}
                        onChange={e => setShowTumor(e.target.checked)} />
                    <span className="v3d-dot v3d-dot-tumor" />
                    Tumour
                </label>

                <div className="v3d-divider" />

                <label className="v3d-toggle">
                    <input type="checkbox" checked={wireframe}
                        onChange={e => setWireframe(e.target.checked)} />
                    <span className="v3d-dot v3d-dot-wire" />
                    Wireframe
                </label>

                <div className="v3d-divider" />

                <label className="v3d-toggle">
                    <input type="checkbox" checked={autoRotate}
                        onChange={e => setAutoRotate(e.target.checked)} />
                    <span className="v3d-dot v3d-dot-rotate" />
                    Rotate
                </label>

                <div className="v3d-divider" />

                <div className="v3d-stats">
                    <span className="v3d-stat liver-color">
                        ● Liver&nbsp;<span className="v3d-stat-val">{liverStats}</span>
                    </span>
                    <span className="v3d-stat tumor-color">
                        ● Tumour&nbsp;<span className="v3d-stat-val">{tumorStats}</span>
                    </span>
                </div>

                <div className="v3d-hint">Drag · Scroll · Right-drag to pan</div>
            </div>
        </div>
    );
}

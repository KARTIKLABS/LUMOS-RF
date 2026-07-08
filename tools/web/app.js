// LUMOS RF 3D Web UI Client
// Handles SSE streaming and Three.js 3D WebGL rendering

let scene, camera, renderer, controls;
let roomBox, gridHelper;
let nodeMeshes = {};
let targetMesh;
let trailLine;
let trailPoints = [];
const MAX_TRAIL_POINTS = 100;

// Configuration options
let roomBounds = { x_min: 0, x_max: 5, y_min: 0, y_max: 5, z_min: 0, z_max: 3 };
let nodeConfigs = {};

// UI elements
const engineStatus = document.getElementById('engine-status');
const activeAnchorsCount = document.getElementById('active-anchors-count');
const posXText = document.getElementById('pos-x');
const posYText = document.getElementById('pos-y');
const posZText = document.getElementById('pos-z');
const nodesContainer = document.getElementById('nodes-container');
const clearTrailBtn = document.getElementById('clear-trail-btn');
const loader = document.getElementById('loader');

// Initialize the application
window.addEventListener('load', async () => {
    // 1. Fetch system configuration
    await fetchConfig();
    
    // 2. Initialize 3D Canvas
    init3D();
    
    // 3. Connect to the Live SSE Data Stream
    connectSSE();
    
    // Hide loader
    if (loader) {
        loader.style.opacity = 0;
        setTimeout(() => loader.style.display = 'none', 500);
    }
});

// Fetch system configuration
async function fetchConfig() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();
        
        roomBounds = config.room_bounds;
        nodeConfigs = config.nodes;
    } catch (e) {
        console.error('Failed to load configuration API. Using local defaults.', e);
    }
}

// Set up Three.js 3D environment
function init3D() {
    const container = document.getElementById('threejs-container');
    const width = container.clientWidth;
    const height = container.clientHeight;
    
    // Create Scene
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x04050a);
    // Add fog for deep-field aesthetic
    scene.fog = new THREE.FogExp2(0x04050a, 0.04);
    
    // Setup Camera
    camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    // Position camera looking down on the room
    const centerX = (roomBounds.x_max + roomBounds.x_min) / 2;
    const centerY = (roomBounds.y_max + roomBounds.y_min) / 2;
    const maxDim = Math.max(roomBounds.x_max, roomBounds.y_max, roomBounds.z_max);
    camera.position.set(centerX + maxDim * 1.5, roomBounds.z_max + maxDim * 1.2, centerY + maxDim * 1.5);
    
    // WebGL Renderer
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.shadowMap.enabled = true;
    container.appendChild(renderer.domElement);
    
    // Camera Controls
    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.maxPolarAngle = Math.PI / 2 - 0.05; // Don't let user look below floor
    controls.target.set(centerX, (roomBounds.z_max - roomBounds.z_min) / 2, centerY);
    controls.update();
    
    // Add Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.25);
    scene.add(ambientLight);
    
    const dirLight = new THREE.DirectionalLight(0xffffff, 0.7);
    dirLight.position.set(20, 40, 20);
    dirLight.castShadow = true;
    scene.add(dirLight);
    
    const pointLight = new THREE.PointLight(0x00e5ff, 1.2, 30);
    pointLight.position.set(centerX, roomBounds.z_max, centerY);
    scene.add(pointLight);
    
    // Build Room boundaries wireframe
    const roomWidth = roomBounds.x_max - roomBounds.x_min;
    const roomDepth = roomBounds.y_max - roomBounds.y_min;
    const roomHeight = roomBounds.z_max - roomBounds.z_min;
    
    const roomGeom = new THREE.BoxGeometry(roomWidth, roomHeight, roomDepth);
    const edges = new THREE.EdgesGeometry(roomGeom);
    const lineMat = new THREE.LineBasicMaterial({ color: 0x3a3f58, linewidth: 2 });
    roomBox = new THREE.LineSegments(edges, lineMat);
    // Align bottom center
    roomBox.position.set(centerX, roomHeight / 2, centerY);
    scene.add(roomBox);
    
    // Grid floor
    gridHelper = new THREE.GridHelper(Math.max(roomWidth, roomDepth) * 2, 20, 0x00e5ff, 0x1f2335);
    gridHelper.position.y = 0;
    scene.add(gridHelper);
    
    // Create Anchor Node Meshes
    const nodeGeom = new THREE.SphereGeometry(0.18, 32, 32);
    
    Object.keys(nodeConfigs).forEach((nid) => {
        const conf = nodeConfigs[nid];
        
        // Node color represents anchor
        const nodeMat = new THREE.MeshPhongMaterial({
            color: 0x00ff66,
            emissive: 0x005511,
            shininess: 100,
            specular: 0xffffff
        });
        
        const mesh = new THREE.Mesh(nodeGeom, nodeMat);
        mesh.position.set(conf.x, conf.z, conf.y); // Coordinate mapping: Unity-style (x, z, y) -> Three (x, y, z)
        scene.add(mesh);
        nodeMeshes[nid] = mesh;
        
        // Add small coordinate rings around node base
        const ringGeom = new THREE.RingGeometry(0.01, 0.3, 32);
        const ringMat = new THREE.MeshBasicMaterial({ color: 0x00ff66, side: THREE.DoubleSide, opacity: 0.15, transparent: true });
        const ring = new THREE.Mesh(ringGeom, ringMat);
        ring.rotation.x = Math.PI / 2;
        ring.position.set(conf.x, 0.01, conf.y);
        scene.add(ring);
    });
    
    // Create Transmitter mesh in center
    const txGeom = new THREE.CylinderGeometry(0.05, 0.05, 0.6, 16);
    const txMat = new THREE.MeshPhongMaterial({ color: 0x00e5ff, emissive: 0x003366 });
    const txMesh = new THREE.Mesh(txGeom, txMat);
    txMesh.position.set(centerX, 0.3, centerY);
    scene.add(txMesh);
    
    const txRingGeom = new THREE.RingGeometry(0.01, 0.5, 32);
    const txRingMat = new THREE.MeshBasicMaterial({ color: 0x00e5ff, side: THREE.DoubleSide, opacity: 0.2, transparent: true });
    const txRing = new THREE.Mesh(txRingGeom, txRingMat);
    txRing.rotation.x = Math.PI / 2;
    txRing.position.set(centerX, 0.01, centerY);
    scene.add(txRing);
    
    // Create Target Tracking mesh (Person)
    const targetGeom = new THREE.SphereGeometry(0.28, 32, 32);
    const targetMat = new THREE.MeshPhongMaterial({
        color: 0xff9900,
        emissive: 0xff4400,
        shininess: 120,
        transparent: true,
        opacity: 0.0 // Invisible until tracked
    });
    targetMesh = new THREE.Mesh(targetGeom, targetMat);
    scene.add(targetMesh);
    
    // Create Target trajectory line
    const trailMat = new THREE.LineBasicMaterial({
        color: 0xff007f,
        linewidth: 3,
        transparent: true,
        opacity: 0.8
    });
    const trailGeom = new THREE.BufferGeometry();
    trailLine = new THREE.Line(trailGeom, trailMat);
    scene.add(trailLine);
    
    // Handle Window resizing
    window.addEventListener('resize', onWindowResize);
    
    // Start Render Loop
    animate();
}

// 3D Render Loop
function animate(time) {
    requestAnimationFrame(animate);
    
    // Slow rotation of room helper when idle
    // roomBox.rotation.y += 0.0002;
    
    // Target pulse animation
    if (targetMesh && targetMesh.material.opacity > 0) {
        const pulse = 1.0 + 0.15 * Math.sin(Date.now() * 0.005);
        targetMesh.scale.set(pulse, pulse, pulse);
        targetMesh.material.emissive.setHSL(0.05 + 0.02 * Math.sin(Date.now() * 0.005), 1.0, 0.5);
    }
    
    controls.update();
    renderer.render(scene, camera);
}

// Resize handler
function onWindowResize() {
    const container = document.getElementById('threejs-container');
    const width = container.clientWidth;
    const height = container.clientHeight;
    
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
}

// Connect to Server-Sent Events (SSE)
function connectSSE() {
    const eventSource = new EventSource('/api/stream');
    
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateUI(data);
    };
    
    eventSource.onerror = (err) => {
        console.error('SSE Connection failed. Reconnecting...', err);
        engineStatus.textContent = "OFFLINE";
        engineStatus.className = "value badge badge-red";
    };
}

// Update DOM elements and Three.js scene
function updateUI(data) {
    const nodes = data.nodes;
    const target = data.target;
    
    // 1. Update overall status badges
    const numActiveNodes = Object.keys(nodes).length;
    activeAnchorsCount.textContent = numActiveNodes;
    
    if (target.active) {
        engineStatus.textContent = "TRACKING";
        engineStatus.className = "value badge badge-green";
        
        // Update Coordinates
        posXText.textContent = target.x_smooth.toFixed(2);
        posYText.textContent = target.y_smooth.toFixed(2);
        posZText.textContent = target.z_smooth.toFixed(2);
        
        // Show/move target in Three.js
        targetMesh.position.set(target.x_smooth, target.z_smooth, target.y_smooth); // Map back: (x, z_smooth, y_smooth)
        targetMesh.material.opacity = 0.95;
        
        // Add coordinates to trail line
        const newPos = new THREE.Vector3(target.x_smooth, target.z_smooth, target.y_smooth);
        
        // Avoid adding identical points in sequence
        if (trailPoints.length === 0 || trailPoints[trailPoints.length - 1].distanceTo(newPos) > 0.05) {
            trailPoints.push(newPos);
            if (trailPoints.length > MAX_TRAIL_POINTS) {
                trailPoints.shift();
            }
            
            // Rebuild trail geometry
            trailLine.geometry.setFromPoints(trailPoints);
        }
    } else {
        engineStatus.textContent = "CALIBRATING";
        engineStatus.className = "value badge badge-red";
        
        posXText.textContent = "--.--";
        posYText.textContent = "--.--";
        posZText.textContent = "--.--";
        
        if (targetMesh) {
            targetMesh.material.opacity = 0.05; // Fade out target
        }
    }
    
    // 2. Render Node Cards in Sidebar
    nodesContainer.innerHTML = '';
    
    if (numActiveNodes === 0) {
        nodesContainer.innerHTML = '<div class="empty-state">Waiting for UDP streams...</div>';
        return;
    }
    
    Object.keys(nodes).forEach((nid) => {
        const nd = nodes[nid];
        const conf = nodeConfigs[nid] || { x: 0, y: 0, z: 0 };
        
        const card = document.createElement('div');
        card.className = 'node-card glass';
        
        // Determine activity level css
        const lvlLower = nd.level.toLowerCase();
        let levelClass = `node-level-badge level-${lvlLower}`;
        
        card.innerHTML = `
            <div class="node-header">
                <span class="node-title">${nid.toUpperCase()}</span>
                <span class="${levelClass}">${nd.level}</span>
            </div>
            <div class="node-info-grid">
                <div class="node-info-item">
                    <span class="lbl">RSSI</span>
                    <span class="val">${nd.rssi} dBm</span>
                </div>
                <div class="node-info-item">
                    <span class="lbl">Variance</span>
                    <span class="val">${nd.variance.toFixed(3)}</span>
                </div>
                <div class="node-info-item">
                    <span class="lbl">Pos (X,Y)</span>
                    <span class="val">${conf.x.toFixed(1)}, ${conf.y.toFixed(1)}m</span>
                </div>
                <div class="node-info-item">
                    <span class="lbl">Pos (Z)</span>
                    <span class="val">${conf.z.toFixed(1)}m</span>
                </div>
            </div>
        `;
        
        nodesContainer.appendChild(card);
        
        // Update anchor node color based on activity in Three.js
        if (nodeMeshes[nid]) {
            const material = nodeMeshes[nid].material;
            if (nd.level === 'HEAVY') {
                material.color.setHex(0xff007f);
                material.emissive.setHex(0x550011);
            } else if (nd.level === 'MODERATE') {
                material.color.setHex(0xff9900);
                material.emissive.setHex(0x553300);
            } else if (nd.level === 'SLIGHT') {
                material.color.setHex(0xffff00);
                material.emissive.setHex(0x555500);
            } else {
                material.color.setHex(0x00ff66);
                material.emissive.setHex(0x005511);
            }
        }
    });
}

// Clear Trajectory Trail button handler
clearTrailBtn.addEventListener('click', () => {
    trailPoints = [];
    if (trailLine) {
        trailLine.geometry.setFromPoints([]);
    }
});

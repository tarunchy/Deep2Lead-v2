/* globe_viz.js — WebGL aurora globe via Three.js */
window.GlobeViz = (function () {
  "use strict";

  let _scene, _camera, _renderer, _globe, _atmos, _clock;
  let _rings = [], _ringTimer = 0;
  let _state = "idle", _animId = null, _ready = false;
  let _uTime = 0, _curSpeed = 0.35, _curIntensity = 0.35;
  let _targetSpeed = 0.35, _targetIntensity = 0.35;
  let _uniforms = null, _atmosUniforms = null;

  const PARAMS = {
    idle:      { speed: 0.35, intensity: 0.35, c1: [0.0, 0.75, 0.45], c2: [0.25, 0.0,  0.65], ring: 0x00cc88 },
    listening: { speed: 0.55, intensity: 0.55, c1: [0.9,  0.5,  0.0],  c2: [0.9,  0.1,  0.15], ring: 0xff8800 },
    thinking:  { speed: 1.5,  intensity: 0.75, c1: [0.0,  0.5,  0.95], c2: [0.5,  0.0,  0.85], ring: 0x4499ff },
    speaking:  { speed: 2.2,  intensity: 1.0,  c1: [0.0,  0.95, 0.5],  c2: [0.0,  0.35, 0.95], ring: 0x00ffaa },
  };

  // ── Shaders ───────────────────────────────────────────────────
  const VERT = `
    varying vec3 vN; varying vec2 vUv;
    void main(){ vN=normalize(normalMatrix*normal); vUv=uv;
      gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }`;

  const FRAG = `
    precision highp float;
    uniform float uTime; uniform float uSpeed; uniform float uIntensity;
    uniform vec3 uC1; uniform vec3 uC2;
    varying vec3 vN; varying vec2 vUv;
    float h(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
    float n(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.0-2.0*f);
      return mix(mix(h(i),h(i+vec2(1,0)),f.x),mix(h(i+vec2(0,1)),h(i+vec2(1,1)),f.x),f.y);}
    float fbm(vec2 p){float v=0.0,a=0.5;
      for(int i=0;i<5;i++){v+=n(p)*a;p=p*2.1+vec2(1.3,0.7);a*=0.5;}return v;}
    void main(){
      vec3 col=vec3(0.02,0.05,0.14);
      col+=vec3(0.02,0.04,0.07)*smoothstep(0.45,0.62,fbm(vUv*4.0));
      col+=vec3(0.85,0.8,0.45)*step(0.83,n(vUv*42.0))*smoothstep(0.25,0.75,sin(vUv.y*3.14159))*0.14;
      float polar=clamp(smoothstep(0.58,0.79,vUv.y)+smoothstep(0.42,0.21,vUv.y),0.0,1.0);
      float t=uTime*uSpeed*0.25;
      vec2 auv=vUv*vec2(4.0,2.5)+vec2(t*0.6,t*0.15);
      float a1=smoothstep(0.36,0.68,fbm(auv))*polar*uIntensity;
      float a2=smoothstep(0.44,0.72,fbm(auv*1.3+vec2(3.1,1.7)))*polar*uIntensity*0.55;
      float blend=sin(vUv.x*6.2831+t*0.8)*0.5+0.5;
      col+=mix(uC1,uC2,blend)*a1;
      col+=mix(uC2,uC1,blend)*a2;
      float rim=1.0-abs(dot(normalize(vN),vec3(0,0,1)));
      col+=mix(uC1,vec3(0.05,0.2,0.6),0.6)*pow(rim,2.2)*0.7;
      col+=vec3(0.3,0.4,0.7)*pow(max(dot(vN,normalize(vec3(1.5,1.0,2.0))),0.0),14.0)*0.12;
      gl_FragColor=vec4(col,1.0);}`;

  const VERT_A = `varying vec3 vN;
    void main(){vN=normalize(normalMatrix*normal);
      gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`;
  const FRAG_A = `precision mediump float;
    uniform float uIntensity; uniform vec3 uC1; varying vec3 vN;
    void main(){float r=1.0-abs(dot(normalize(vN),vec3(0,0,1)));
      gl_FragColor=vec4(uC1*1.3,pow(r,1.8)*0.55*uIntensity);}`;

  // ── Init ──────────────────────────────────────────────────────
  function _init(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !window.THREE) return;
    const THREE = window.THREE;
    const W = canvas.clientWidth || 380, H = canvas.clientHeight || 380;

    _clock = new THREE.Clock();

    _scene    = new THREE.Scene();
    _camera   = new THREE.PerspectiveCamera(45, W / H, 0.1, 100);
    _camera.position.set(0, 0, 2.6);

    _renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    _renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    _renderer.setSize(W, H);
    _renderer.setClearColor(0x000000, 0);

    // Stars
    const starGeo = new THREE.BufferGeometry();
    const starPos = new Float32Array(3000);
    for (let i = 0; i < 3000; i++) {
      const r = 8 + Math.random() * 10;
      const th = Math.random() * Math.PI * 2;
      const ph = Math.acos(2 * Math.random() - 1);
      starPos[i*3]   = r * Math.sin(ph) * Math.cos(th);
      starPos[i*3+1] = r * Math.sin(ph) * Math.sin(th);
      starPos[i*3+2] = r * Math.cos(ph);
    }
    starGeo.setAttribute("position", new THREE.BufferAttribute(starPos, 3));
    const starMat = new THREE.PointsMaterial({ color: 0xffffff, size: 0.04, transparent: true, opacity: 0.7 });
    _scene.add(new THREE.Points(starGeo, starMat));

    // Globe
    const p = PARAMS.idle;
    _uniforms = {
      uTime:      { value: 0 },
      uSpeed:     { value: p.speed },
      uIntensity: { value: p.intensity },
      uC1:        { value: new THREE.Vector3(...p.c1) },
      uC2:        { value: new THREE.Vector3(...p.c2) },
    };
    _globe = new THREE.Mesh(
      new THREE.SphereGeometry(1.0, 64, 64),
      new THREE.ShaderMaterial({ vertexShader: VERT, fragmentShader: FRAG, uniforms: _uniforms })
    );
    _scene.add(_globe);

    // Atmosphere
    _atmosUniforms = {
      uIntensity: { value: p.intensity },
      uC1:        { value: new THREE.Vector3(...p.c1) },
    };
    _atmos = new THREE.Mesh(
      new THREE.SphereGeometry(1.18, 64, 64),
      new THREE.ShaderMaterial({
        vertexShader: VERT_A, fragmentShader: FRAG_A,
        uniforms: _atmosUniforms,
        transparent: true, side: THREE.FrontSide, depthWrite: false,
        blending: THREE.AdditiveBlending,
      })
    );
    _scene.add(_atmos);

    _ready = true;
    _animate();
  }

  // ── Animation loop ────────────────────────────────────────────
  function _animate() {
    _animId = requestAnimationFrame(_animate);
    const delta = _clock.getDelta();
    _uTime += delta;

    // Lerp towards target params
    _curSpeed     += ((_targetSpeed     - _curSpeed)     * Math.min(delta * 3, 1));
    _curIntensity += ((_targetIntensity - _curIntensity) * Math.min(delta * 2, 1));

    if (_uniforms) {
      _uniforms.uTime.value      = _uTime;
      _uniforms.uSpeed.value     = _curSpeed;
      _uniforms.uIntensity.value = _curIntensity;
      const p = PARAMS[_state] || PARAMS.idle;
      _uniforms.uC1.value.set(...p.c1);
      _uniforms.uC2.value.set(...p.c2);
    }
    if (_atmosUniforms) {
      _atmosUniforms.uIntensity.value = _curIntensity;
      const p = PARAMS[_state] || PARAMS.idle;
      _atmosUniforms.uC1.value.set(...p.c1);
    }

    // Globe rotation
    if (_globe) {
      _globe.rotation.y += delta * (0.12 + _curSpeed * 0.05);
      _atmos.rotation.y = _globe.rotation.y * 0.8;
    }

    // Rings (listening / speaking)
    if (_state === "listening" || _state === "speaking") {
      _ringTimer += delta;
      if (_ringTimer > (_state === "listening" ? 0.42 : 0.28)) {
        _spawnRing(PARAMS[_state].ring);
        _ringTimer = 0;
      }
    } else {
      _ringTimer = 0;
    }
    _updateRings(delta);

    _renderer.render(_scene, _camera);
  }

  // ── Rings ─────────────────────────────────────────────────────
  function _spawnRing(color) {
    const THREE = window.THREE;
    const geo = new THREE.RingGeometry(1.08, 1.18, 64);
    const mat = new THREE.MeshBasicMaterial({
      color, transparent: true, opacity: 0.65,
      side: THREE.DoubleSide, depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const ring = new THREE.Mesh(geo, mat);
    ring.userData.s = 1.0; ring.userData.o = 0.65;
    ring.lookAt(0, 0, 5);
    _rings.push(ring);
    _scene.add(ring);
  }

  function _updateRings(delta) {
    const dead = [];
    for (const r of _rings) {
      r.userData.s += delta * 1.3;
      r.userData.o -= delta * 0.85;
      r.scale.setScalar(r.userData.s);
      r.material.opacity = Math.max(0, r.userData.o);
      if (r.userData.o <= 0) dead.push(r);
    }
    for (const r of dead) {
      _scene.remove(r); r.geometry.dispose(); r.material.dispose();
      _rings.splice(_rings.indexOf(r), 1);
    }
  }

  // ── Public API ────────────────────────────────────────────────
  return {
    load(canvasId, callback) {
      if (window.THREE) { _init(canvasId); callback && callback(); return; }
      const s = document.createElement("script");
      s.src = "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js";
      s.onload = () => { _init(canvasId); callback && callback(); };
      s.onerror = () => { console.warn("Three.js CDN failed"); };
      document.head.appendChild(s);
    },
    setState(state) {
      if (!PARAMS[state]) return;
      _state = state;
      _targetSpeed     = PARAMS[state].speed;
      _targetIntensity = PARAMS[state].intensity;
    },
    resize() {
      if (!_renderer || !_camera) return;
      const canvas = _renderer.domElement;
      const W = canvas.clientWidth, H = canvas.clientHeight;
      if (!W || !H) return;
      _camera.aspect = W / H;
      _camera.updateProjectionMatrix();
      _renderer.setSize(W, H);
    },
    destroy() {
      if (_animId) cancelAnimationFrame(_animId);
      _renderer?.dispose();
      _ready = false;
    },
  };
})();

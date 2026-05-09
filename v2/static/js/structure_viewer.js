/* 3Dmol.js protein structure viewer helper */
(function () {
  "use strict";

  let _viewer = null;

  function ensureLib(callback) {
    if (window.$3Dmol) { callback(); return; }
    const script = document.createElement("script");
    script.src = "https://3Dmol.org/build/3Dmol-min.js";
    script.onload = callback;
    document.head.appendChild(script);
  }

  window.StructureViewer = {
    init: function (containerId, options = {}) {
      ensureLib(() => {
        const el = document.getElementById(containerId);
        if (!el) return;
        el.innerHTML = "";
        _viewer = $3Dmol.createViewer(el, {
          backgroundColor: options.bg || "#0a0f17",
          antialias: true,
        });
      });
    },

    loadPdbUrl: async function (pdbUrl, style = "cartoon") {
      ensureLib(async () => {
        const label = document.getElementById("viewerLoadingLabel");
        if (label) label.textContent = "Loading structure…";
        try {
          const r = await fetch(pdbUrl);
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          const pdbText = await r.text();
          StructureViewer.loadPdbText(pdbText, style);
        } catch (e) {
          if (label) label.textContent = "Failed to load structure.";
          console.error("Structure load error:", e);
        }
      });
    },

    loadPdbText: function (pdbText, style = "cartoon") {
      ensureLib(() => {
        if (!_viewer) return;
        _viewer.clear();
        _viewer.addModel(pdbText, "pdb");
        if (style === "cartoon") {
          _viewer.setStyle({}, { cartoon: { colorscheme: "ssJmol" } });
        } else if (style === "stick") {
          _viewer.setStyle({}, { stick: {}, sphere: { radius: 0.3 } });
        } else if (style === "confidence") {
          // Color by B-factor (pLDDT for AlphaFold)
          _viewer.setStyle({}, { cartoon: { colorscheme: { prop: "b", gradient: "roygb", min: 50, max: 100 } } });
        }
        _viewer.zoomTo();
        _viewer.render();
        const label = document.getElementById("viewerLoadingLabel");
        if (label) label.style.display = "none";
      });
    },

    loadDockingPose: function (proteinPdb, ligandPdbqt) {
      ensureLib(() => {
        if (!_viewer) return;
        _viewer.clear();
        _viewer.addModel(proteinPdb, "pdb");
        _viewer.setStyle({}, { cartoon: { color: "#58a6ff", opacity: 0.5 } });
        if (ligandPdbqt) {
          _viewer.addModel(ligandPdbqt, "pdbqt");
          _viewer.setStyle({ hetflag: true }, { stick: { colorscheme: "Jmol" }, sphere: { radius: 0.25 } });
          _viewer.zoomTo({ hetflag: true });
        } else {
          _viewer.zoomTo();
        }
        _viewer.render();
      });
    },

    setStyle: function (style) {
      if (!_viewer) return;
      _viewer.setStyle({}, style === "stick"
        ? { stick: {}, sphere: { radius: 0.3 } }
        : style === "confidence"
          ? { cartoon: { colorscheme: { prop: "b", gradient: "roygb", min: 50, max: 100 } } }
          : { cartoon: { colorscheme: "ssJmol" } }
      );
      _viewer.render();
    },

    highlight: function (residue) {
      if (!_viewer) return;
      _viewer.addSurface($3Dmol.SurfaceType.VDW, { opacity: 0.7, color: "#ffa657" }, { resi: residue });
      _viewer.render();
    },

    clearSurfaces: function () {
      if (!_viewer) { return; }
      _viewer.removeAllSurfaces();
      _viewer.render();
    },
  };
})();

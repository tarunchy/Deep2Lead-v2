document.addEventListener("DOMContentLoaded", () => {
  const joinBtn = document.getElementById("joinBtn");
  const annotationArea = document.getElementById("annotationArea");
  const saveBtn = document.getElementById("saveAnnotationBtn");

  joinBtn.addEventListener("click", async () => {
    const res = await fetch(`/api/v3/game/session/${SESSION_ID}/join-analyst`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
    });
    if (res.ok) {
      joinBtn.style.display = "none";
      annotationArea.style.display = "block";
    } else {
      const d = await res.json();
      alert(d.error || "Could not join session");
    }
  });

  saveBtn.addEventListener("click", async () => {
    const text = document.getElementById("annotationInput").value.trim();
    if (!text) return;
    const res = await fetch(`/api/v3/game/session/${SESSION_ID}/annotate`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({note: text, saved_at: new Date().toISOString()}),
    });
    if (res.ok) {
      saveBtn.textContent = "Saved!";
      setTimeout(() => { saveBtn.textContent = "Save Annotation"; }, 2000);
    } else {
      const d = await res.json();
      alert(d.error || "Save failed");
    }
  });
});

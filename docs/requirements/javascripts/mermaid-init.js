function normalizeMermaidLabel(value) {
  return (value || "").replace(/\s+/g, "").trim().toLowerCase();
}

function normalizeMermaidLabelLoose(value) {
  return normalizeMermaidLabel(value).replace(/[^a-z0-9]/g, "");
}

function normalizeMermaidLayout() {
  document.querySelectorAll(".sql-landscape-er .mermaid").forEach((diagram) => {
    diagram.style.setProperty("display", "block", "important");
    diagram.style.setProperty("width", "max-content", "important");
    diagram.style.setProperty("max-width", "none", "important");
    diagram.style.setProperty("position", "static", "important");

    const svg = diagram.querySelector("svg");
    if (!svg) {
      return;
    }

    svg.style.setProperty("display", "block", "important");
    svg.style.setProperty("max-width", "none", "important");
    svg.style.setProperty("position", "static", "important");
    svg.style.setProperty("overflow", "visible", "important");
  });
}

function applyAcidErStatusColors() {
  const palette = {
    exists: { fill: "#eff6ff", stroke: "#2563eb" },
    extend: { fill: "#ecfdf3", stroke: "#059669" },
    implement: { fill: "#fff7ed", stroke: "#ea580c" },
  };

  document.querySelectorAll(".acid-er-card").forEach((card) => {
    const data = card.querySelector(".acid-er-status-data");
    const svg = card.querySelector("svg");
    if (!data || !svg) {
      return;
    }

    let statuses = {};
    try {
      statuses = JSON.parse(data.textContent || "{}");
    } catch {
      return;
    }

    const statusByLabel = new Map();
    Object.entries(statuses).forEach(([label, status]) => {
      if (!label || !status) {
        return;
      }
      statusByLabel.set(normalizeMermaidLabel(label), status);
      statusByLabel.set(normalizeMermaidLabelLoose(label), status);
    });

    svg.querySelectorAll("g").forEach((group) => {
      const directTexts = Array.from(group.children).filter((child) => child.tagName.toLowerCase() === "text");
      const textElements = directTexts.length ? directTexts : Array.from(group.querySelectorAll("text"));
      const texts = textElements
        .map((text) => text.textContent || "")
        .map((text) => text.trim())
        .filter(Boolean);
      if (!texts.length || texts.length > 60) {
        return;
      }

      let status = "";
      for (const label of texts) {
        status =
          statusByLabel.get(normalizeMermaidLabel(label)) ||
          statusByLabel.get(normalizeMermaidLabelLoose(label)) ||
          "";
        if (status) {
          break;
        }
      }

      const colors = palette[status];
      if (!colors) {
        return;
      }

      const shapes = Array.from(group.querySelectorAll("rect, polygon, path")).filter((shape) => {
        const stroke = (shape.getAttribute("stroke") || "").toLowerCase();
        const fill = (shape.getAttribute("fill") || "").toLowerCase();
        return stroke !== "none" || fill === "#fff" || fill === "#ffffff" || fill === "white" || fill === "";
      });
      if (!shapes.length) {
        return;
      }

      shapes.forEach((shape) => {
        shape.style.setProperty("fill", colors.fill, "important");
        shape.style.setProperty("stroke", colors.stroke, "important");
        shape.style.setProperty("stroke-width", "2px", "important");
      });
      group.classList.add(`acid-er-entity-${status}`);
    });

    card.classList.add("acid-er-colored");
  });
}

async function runMermaid() {
  if (!window.mermaid) {
    return;
  }

  window.mermaid.initialize({
    startOnLoad: false,
    securityLevel: "loose",
    theme: "base",
    themeVariables: {
      primaryColor: "#ffffff",
      primaryBorderColor: "#3858a6",
      primaryTextColor: "#17202a",
      lineColor: "#64748b",
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    },
    er: {
      useMaxWidth: false,
    },
  });

  try {
    if (window.mermaid.run) {
      await window.mermaid.run({ querySelector: ".mermaid" });
    } else {
      window.mermaid.init(undefined, document.querySelectorAll(".mermaid"));
    }
  } finally {
    normalizeMermaidLayout();
    applyAcidErStatusColors();
    window.setTimeout(() => {
      normalizeMermaidLayout();
      applyAcidErStatusColors();
    }, 250);
  }
}

if (typeof document$ !== "undefined") {
  document$.subscribe(runMermaid);
} else {
  document.addEventListener("DOMContentLoaded", runMermaid);
}

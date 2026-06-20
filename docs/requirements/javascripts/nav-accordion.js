(function () {
  const selector = ".md-tabs .rm-tabs-menu";

  function menus() {
    return Array.from(document.querySelectorAll(selector));
  }

  function closeOthers(current) {
    menus().forEach((menu) => {
      if (menu !== current) {
        menu.open = false;
      }
    });
  }

  function setupNavAccordion() {
    menus().forEach((menu) => {
      if (menu.dataset.rmAccordionReady === "true") {
        return;
      }

      menu.dataset.rmAccordionReady = "true";
      const summary = menu.querySelector("summary");
      if (summary) {
        summary.setAttribute("aria-expanded", menu.open ? "true" : "false");
      }
      menu.addEventListener("toggle", () => {
        if (summary) {
          summary.setAttribute("aria-expanded", menu.open ? "true" : "false");
        }
        if (menu.open) {
          closeOthers(menu);
        }
      });
      menu.addEventListener("mouseenter", () => closeOthers(menu));
    });
  }

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".md-tabs")) {
      closeOthers(null);
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeOthers(null);
    }
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setupNavAccordion);
  } else {
    setupNavAccordion();
  }

  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(setupNavAccordion);
  }
})();

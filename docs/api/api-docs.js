/* Pinned browser distributions; no build step or npm installation is needed. */
const assets = {
  rest: {
    css: "https://unpkg.com/swagger-ui-dist@5.33.0/swagger-ui.css",
    js: "https://unpkg.com/swagger-ui-dist@5.33.0/swagger-ui-bundle.js",
  },
  events: {
    css: "https://unpkg.com/@asyncapi/react-component@3.1.0/styles/default.min.css",
    js: "https://unpkg.com/@asyncapi/react-component@3.1.0/browser/standalone/index.js",
  },
};

const loading = new Map();

function loadScript(url) {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = url;
    script.onload = resolve;
    script.onerror = () => reject(new Error("Не удалось загрузить средство просмотра из CDN."));
    document.head.append(script);
  });
}

async function render(kind) {
  const status = document.getElementById(`${kind}-status`);
  try {
    const style = document.createElement("link");
    style.rel = "stylesheet";
    style.href = assets[kind].css;
    document.head.append(style);
    await loadScript(assets[kind].js);
    if (kind === "rest") {
      SwaggerUIBundle({
        url: "./openapi.json",
        dom_id: "#swagger-ui",
        docExpansion: "list",
        defaultModelsExpandDepth: -1,
        displayOperationId: true,
        filter: true,
        supportedSubmitMethods: [],
        tryItOutEnabled: false,
        persistAuthorization: false,
        validatorUrl: null,
      });
    } else {
      AsyncApiStandalone.render({
        schema: { url: new URL("./asyncapi.json", window.location.href).href },
        config: { show: { sidebar: false } },
      }, document.getElementById("asyncapi"));
    }
    status.hidden = true;
  } catch (error) {
    status.classList.add("error");
    status.textContent = `${error.message} Исходные JSON-контракты доступны по ссылкам вверху страницы.`;
  }
}

function select() {
  const kind = window.location.hash === "#events" ? "events" : "rest";
  for (const candidate of ["rest", "events"]) {
    document.getElementById(`${candidate}-section`).hidden = candidate !== kind;
    const link = document.getElementById(`${candidate}-link`);
    if (candidate === kind) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  if (!loading.has(kind)) loading.set(kind, render(kind));
}

window.addEventListener("hashchange", select);
select();

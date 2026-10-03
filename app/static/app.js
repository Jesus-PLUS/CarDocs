const TOKEN_KEY = "cardocs_token";
const USER_KEY = "cardocs_user";

const $ = (sel) => document.querySelector(sel);
const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const session = {
  token: () => localStorage.getItem(TOKEN_KEY),
  user: () => JSON.parse(localStorage.getItem(USER_KEY) || "null"),
  save(data) {
    localStorage.setItem(TOKEN_KEY, data.token);
    localStorage.setItem(USER_KEY, JSON.stringify(data.user));
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },
};

function logout() {
  session.clear();
  location.href = "/login";
}

async function api(path, { method = "GET", json, form } = {}) {
  const headers = {};
  if (session.token()) headers.Authorization = `Bearer ${session.token()}`;
  let body;
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (form) {
    body = form;
  }
  const res = await fetch(`/api${path}`, { method, headers, body });
  if (res.status === 401 && session.token()) {
    logout();
    throw new Error("Sesión expirada");
  }
  if (!res.ok) {
    let detail = `Error ${res.status}`;
    try {
      detail = (await res.json()).detail || detail;
    } catch {}
    throw new Error(detail);
  }
  return res.status === 204 ? null : res;
}
const apiJson = async (path, opts) => (await api(path, opts)).json();

function showError(msg) {
  $("#error").textContent = msg || "";
}

function requireSession() {
  if (!session.token()) {
    location.href = "/login";
    return null;
  }
  const user = session.user();
  $("#who").textContent = `${user.email} · ${user.role}`;
  $("#logout").addEventListener("click", logout);
  return user;
}

const fmtDate = (d) => (d ? d.split("-").reverse().join("/") : "—");
const fmtSize = (n) => (n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);
const STATUS_LABEL = { vigente: "Vigente", vencido: "Vencido", sin_fecha: "Sin fecha" };
const TYPE_LABEL = { factura: "Factura", poliza: "Póliza", verificacion: "Verificación", foto: "Foto", otro: "Otro" };

/* ---------- login / register ---------- */

function initAuthForm(kind) {
  if (session.token()) {
    location.href = "/garage";
    return;
  }
  $("#auth-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    showError("");
    const f = e.target;
    const json = { email: f.email.value, password: f.password.value };
    if (kind === "register") json.role = f.role.value;
    try {
      session.save(await apiJson(`/auth/${kind}`, { method: "POST", json }));
      location.href = "/garage";
    } catch (err) {
      showError(err.message);
    }
  });
}

/* ---------- garage ---------- */

async function initGarage() {
  const user = requireSession();
  if (!user) return;
  const isOwner = user.role === "dueño";
  $("#title").textContent = isOwner ? "Mi garage" : "Autos autorizados";
  $("#new-car").classList.toggle("hidden", !isOwner);
  try {
    const cars = await apiJson("/vehicles");
    const totalExpired = cars.reduce((n, c) => n + c.expired_count, 0);
    const badge = $("#expired-total");
    badge.textContent = `${totalExpired} vencido${totalExpired === 1 ? "" : "s"}`;
    badge.className = `badge ${totalExpired ? "vencido" : "vigente"}`;
    $("#cars").innerHTML =
      cars
        .map(
          (c) => `<a class="card car" href="/vehicles/${c.id}">
            <div class="plates">${esc(c.plates)}</div>
            <div>${esc(c.brand)} ${esc(c.model)} · ${esc(c.year)}</div>
            <div class="muted">${c.document_count} documento${c.document_count === 1 ? "" : "s"}
              ${c.expired_count ? `<span class="badge vencido">${c.expired_count} vencido${c.expired_count === 1 ? "" : "s"}</span>` : ""}</div>
          </a>`
        )
        .join("") ||
      `<p class="muted">${isOwner ? "Aún no tienes autos. Agrega el primero." : "Ningún dueño te ha autorizado todavía."}</p>`;
  } catch (err) {
    showError(err.message);
  }
}

/* ---------- new vehicle ---------- */

function initNewVehicle() {
  const user = requireSession();
  if (!user) return;
  if (user.role !== "dueño") {
    location.href = "/garage";
    return;
  }
  $("#vehicle-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    showError("");
    const f = e.target;
    try {
      const car = await apiJson("/vehicles", {
        method: "POST",
        json: { plates: f.plates.value, brand: f.brand.value, model: f.model.value, year: Number(f.year.value) },
      });
      location.href = `/vehicles/${car.id}`;
    } catch (err) {
      showError(err.message);
    }
  });
}

/* ---------- vehicle detail ---------- */

async function initVehicle() {
  const user = requireSession();
  if (!user) return;
  const isOwner = user.role === "dueño";
  const id = location.pathname.split("/").pop();
  document.querySelectorAll(".owner-only").forEach((el) => el.classList.toggle("hidden", !isOwner));

  async function load() {
    const type = $("#filter-type").value;
    const car = await apiJson(`/vehicles/${id}${type ? `?doc_type=${encodeURIComponent(type)}` : ""}`);
    $("#car-title").textContent = `${car.brand} ${car.model} ${car.year}`;
    $("#car-plates").textContent = car.plates;
    const f = $("#edit-form");
    if (isOwner && !f.dataset.filled) {
      f.plates.value = car.plates;
      f.brand.value = car.brand;
      f.model.value = car.model;
      f.year.value = car.year;
      f.dataset.filled = "1";
    }
    $("#docs-body").innerHTML =
      car.documents
        .map(
          (d) => `<tr>
            <td>${esc(TYPE_LABEL[d.doc_type] || d.doc_type)}</td>
            <td>${esc(d.original_name)} <span class="muted">(${fmtSize(d.size_bytes)})</span></td>
            <td>${fmtDate(d.issued_on)}</td>
            <td>${fmtDate(d.expires_on)}</td>
            <td><span class="badge ${d.status}">${STATUS_LABEL[d.status]}</span></td>
            <td class="actions">
              <button class="secondary small" data-download="${d.id}" data-name="${esc(d.original_name)}">Descargar</button>
              ${isOwner ? `<button class="danger small" data-delete="${d.id}">Borrar</button>` : ""}
            </td>
          </tr>`
        )
        .join("") || `<tr><td colspan="6" class="muted">Sin documentos.</td></tr>`;
    if (isOwner) {
      $("#shares").innerHTML =
        car.shares
          .map(
            (s) => `<li><span>${esc(s.email)}</span>
              <button class="danger small" data-unshare="${s.user_id}">Revocar</button></li>`
          )
          .join("") || `<li class="muted">Ningún taller autorizado.</li>`;
    }
  }

  const run = async (fn) => {
    showError("");
    try {
      await fn();
    } catch (err) {
      showError(err.message);
    }
  };

  $("#filter-type").addEventListener("change", () => run(load));

  $("#docs-body").addEventListener("click", (e) => {
    const dl = e.target.closest("[data-download]");
    const del = e.target.closest("[data-delete]");
    if (dl) {
      run(async () => {
        const blob = await (await api(`/documents/${dl.dataset.download}/download`)).blob();
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = dl.dataset.name;
        a.click();
        URL.revokeObjectURL(a.href);
      });
    } else if (del && confirm("¿Borrar este documento? Se elimina también el archivo.")) {
      run(async () => {
        await api(`/documents/${del.dataset.delete}`, { method: "DELETE" });
        await load();
      });
    }
  });

  if (isOwner) {
    $("#upload-form").addEventListener("submit", (e) => {
      e.preventDefault();
      run(async () => {
        await api(`/vehicles/${id}/documents`, { method: "POST", form: new FormData(e.target) });
        e.target.reset();
        await load();
      });
    });

    $("#share-form").addEventListener("submit", (e) => {
      e.preventDefault();
      run(async () => {
        await api(`/vehicles/${id}/shares`, { method: "POST", json: { email: e.target.email.value } });
        e.target.reset();
        await load();
      });
    });

    $("#shares").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-unshare]");
      if (btn)
        run(async () => {
          await api(`/vehicles/${id}/shares/${btn.dataset.unshare}`, { method: "DELETE" });
          await load();
        });
    });

    $("#edit-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const f = e.target;
      run(async () => {
        await api(`/vehicles/${id}`, {
          method: "PUT",
          json: { plates: f.plates.value, brand: f.brand.value, model: f.model.value, year: Number(f.year.value) },
        });
        await load();
      });
    });

    $("#delete-car").addEventListener("click", () => {
      if (!confirm("¿Eliminar este auto con todos sus documentos y autorizaciones?")) return;
      run(async () => {
        await api(`/vehicles/${id}`, { method: "DELETE" });
        location.href = "/garage";
      });
    });
  }

  run(load);
}

const pages = {
  login: () => initAuthForm("login"),
  register: () => initAuthForm("register"),
  garage: initGarage,
  "vehicle-new": initNewVehicle,
  vehicle: initVehicle,
};
pages[document.body.dataset.page]?.();

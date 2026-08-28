import { html, reactive } from "/assets/vendor/arrow-core.js"
import { isGalaxyTunnel } from "/assets/js/utils.js"
import { Modal } from "/assets/components/modal.js";

const state = reactive({
  loading: true,
  error: null,
  routes: [],
  selectedRoute: null,
  showPreservedOnly: false,
  progress: 0,
  total: 0,
  showDeleteAllModal: false,
  isDeletingAll: false,
  truncated: false,
})

const MAX_RENDERED_ROUTES = 250
const ROUTE_FLUSH_INTERVAL_MS = 120

let routesAbortController = null
let routesRequestToken = 0
let pendingRoutes = []
let flushTimerId = null
let seenRouteNames = new Set()

function formatRouteDate(dateString) {
  if (!dateString) {
    return "알 수 없는 날짜"
  }

  const date = new Date(dateString)
  if (isNaN(date.getTime())) {
    return dateString
  }
  const dateLabel = date.toLocaleDateString("ko-KR", { year: "numeric", month: "long", day: "numeric" })
  const timeLabel = date.toLocaleTimeString("ko-KR", { hour: "numeric", minute: "2-digit" })
  return `${dateLabel} - ${timeLabel}`
}

function resetRouteStreamState() {
  pendingRoutes = []
  if (flushTimerId !== null) {
    clearTimeout(flushTimerId)
    flushTimerId = null
  }
  seenRouteNames = new Set()
}

function flushPendingRoutes() {
  if (pendingRoutes.length === 0) return

  const availableSlots = Math.max(MAX_RENDERED_ROUTES - state.routes.length, 0)
  if (availableSlots <= 0) {
    pendingRoutes = []
    state.truncated = true
    return
  }

  const toAppend = pendingRoutes.slice(0, availableSlots)
  pendingRoutes = []
  if (toAppend.length > 0) {
    state.routes = [...state.routes, ...toAppend]
  }
  if (state.routes.length >= MAX_RENDERED_ROUTES) {
    state.truncated = true
  }
}

function enqueueRoutes(rawRoutes) {
  if (!Array.isArray(rawRoutes) || rawRoutes.length === 0) return

  const nextRoutes = []
  for (const route of rawRoutes) {
    const name = String(route?.name || "")
    if (!name || seenRouteNames.has(name)) continue
    seenRouteNames.add(name)
    nextRoutes.push({
      ...route,
      timestamp: formatRouteDate(route.timestamp),
    })
  }

  if (nextRoutes.length === 0) return
  pendingRoutes.push(...nextRoutes)

  if (flushTimerId === null) {
    flushTimerId = setTimeout(() => {
      flushTimerId = null
      flushPendingRoutes()
    }, ROUTE_FLUSH_INTERVAL_MS)
  }
}

async function fetchRoutes() {
  const requestToken = ++routesRequestToken
  if (routesAbortController) {
    routesAbortController.abort()
  }
  const controller = new AbortController()
  routesAbortController = controller

  try {
    const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const response = await fetch(`/api/routes?timezone=${encodeURIComponent(userTimezone)}`, {
      signal: controller.signal,
    });
    if (!response.ok) throw new Error();

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      if (requestToken !== routesRequestToken) return

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split(/\r?\n\r?\n/);
      buffer = lines.pop();

      for (const line of lines) {
        if (line.startsWith("data:")) {
          try {
            const payload = line.substring(5).trim()
            if (!payload) continue
            const data = JSON.parse(payload);
            if (data.progress !== undefined && data.total !== undefined) {
              state.progress = data.progress;
              state.total = data.total;
            }
            if (data.routes) {
              enqueueRoutes(data.routes)
            }
          } catch (e) {
            console.error("Failed to parse JSON:", e);
          }
        }
      }
    }
    flushPendingRoutes()
  } catch (error) {
    if (error?.name !== "AbortError") {
      state.error = "주행 영상을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요."
    }
  } finally {
    if (requestToken === routesRequestToken) {
      flushPendingRoutes()
      state.loading = false
      if (routesAbortController === controller) {
        routesAbortController = null
      }
    }
  }
}

function refresh() {
  state.loading = true
  state.error = null
  state.routes = []
  state.progress = 0
  state.total = 0
  state.truncated = false
  resetRouteStreamState()
  fetchRoutes()
}

refresh()

let overlay = null

function openDialog(htmlStr) {
  const o = document.createElement("div")
  o.className = "dialog-overlay"
  o.innerHTML = htmlStr
  document.body.appendChild(o)
  return o
}

function closeDialog(o) {
  if (o) o.remove()
}

async function deleteRoute(route) {
  const dlg = openDialog(`
    <div class="dialog-box">
      <p>“${route.timestamp}” 주행 영상을 삭제하시겠습니까?</p>
      <div class="dialog-buttons">
        <button class="btn btn-cancel" ...>취소</button>
        <button class="btn btn-danger btn-del" ...>삭제</button>
      </div>
    </div>`)
  dlg.querySelector(".btn-cancel").onclick = () => closeDialog(dlg)
  dlg.querySelector(".btn-del").onclick = async () => {
    const res = await fetch(`/api/routes/${route.name}`, { method: "DELETE" })
    if (res.ok) {
      state.routes = state.routes.filter(r => r.name !== route.name)
      closeDialog(dlg)
      closeOverlay()
      refresh()
      showSnackbar("주행 영상이 삭제되었습니다!")
    } else {
      showSnackbar("삭제하지 못했습니다...", "error")
    }
  }
}

async function resetRouteName(route, dlg) {
  const res = await fetch(`/api/routes/reset_name`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: route.name })
  });
  if (res.ok) {
    const { timestamp } = await res.json();
    closeDialog(dlg);
    const routeInList = state.routes.find(r => r.name === route.name);
    if (routeInList) {
      routeInList.timestamp = formatRouteDate(timestamp);
    }
    route.timestamp = formatRouteDate(timestamp);
    const overlayTitleSpan = overlay.querySelector(".media-player-title span");
    if (overlayTitleSpan) {
      overlayTitleSpan.textContent = formatRouteDate(timestamp);
    }
    showSnackbar("주행 이름이 초기화되었습니다!");
  } else {
    showSnackbar("주행 이름을 초기화하지 못했습니다...", "error");
  }
}

async function renameRoute(route) {
  const dlg = openDialog(`
    <div class="dialog-box">
      <p>“${route.timestamp}” 이름 변경</p>
      <input class="rn-input" value="${route.timestamp}" />
      <div class="dialog-buttons">
        <button class="btn-cancel">취소</button>
        <button class="btn-reset">초기화</button>
        <button class="btn-save">저장</button>
      </div>
    </div>`);
  dlg.querySelector(".btn-cancel").onclick = () => closeDialog(dlg);
  dlg.querySelector(".btn-reset").onclick = () => resetRouteName(route, dlg);
  dlg.querySelector(".btn-save").onclick = async () => {
    const newName = dlg.querySelector(".rn-input").value.trim();
    if (!newName) return;
    const res = await fetch(`/api/routes/rename`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ old: route.name, new: newName })
    });
    if (res.ok) {
      closeDialog(dlg);
      const routeInList = state.routes.find(r => r.name === route.name);
      if (routeInList) {
        routeInList.timestamp = newName;
      }
      route.timestamp = newName;
      const overlayTitleSpan = overlay.querySelector(".media-player-title span");
      if (overlayTitleSpan) {
        overlayTitleSpan.textContent = newName;
      }
      showSnackbar("주행 이름이 변경되었습니다!");
    } else {
      showSnackbar("이름을 변경하지 못했습니다...", "error");
    }
  };
}

async function openOverlay(route) {
  if (overlay) return;

  overlay = document.createElement("div");
  overlay.className = "media-player-overlay";
  overlay.innerHTML = `
    <div class="media-player-content">
      <div class="media-player-title">
        <span>${route.timestamp}</span>
        <i class="bi bi-pencil-fill action-rename-icon"></i>
      </div>
      <video controls autoplay muted>
        <source src="/thumbnails/${route.name}--0/preview.png" type="video/mp4">
      </video>
      <div class="button-row">
        <button class="close-button action-close">닫기</button>
        <button class="close-button camera-button active" data-camera="forward">전방</button>
        <button class="close-button camera-button" data-camera="wide">광각</button>
        <button class="close-button camera-button" data-camera="driver">운전자</button>
        <button class="close-button action-download">다운로드</button>
        <button class="close-button action-delete">삭제</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);

  overlay.addEventListener("click", e => {
    if (e.target === overlay) closeOverlay();
  });
  overlay.querySelector(".action-rename-icon").onclick = () => renameRoute(route);
  overlay.querySelector(".action-close").onclick = closeOverlay;
  overlay.querySelector(".action-delete").onclick = () => deleteRoute(route);

  const vid = overlay.querySelector("video");
  const downloadButton = overlay.querySelector(".action-download");

  let segments;
  let current = 0;
  let selectedCamera = "forward";

  downloadButton.onclick = () => {
    const link = document.createElement("a");
    const videoPath = `/video/${route.name}/combined?camera=${selectedCamera}`;
    link.href = videoPath;
    link.download = `${route.timestamp}-${selectedCamera}.mp4`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  (async () => {
    try {
      const response = await fetch(`/api/routes/${route.name}`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      segments = data.segment_urls;

      if (!segments || segments.length === 0) {
        segments = [`/video/${route.name}--0`];
      }
      vid.src = `${segments[0]}?camera=forward`;
      vid.load();
      vid.play();
    } catch (error) {
      showSnackbar("오류: 주행 영상을 불러올 수 없습니다.", "error");
    }
  })();

  vid.addEventListener("ended", () => {
    current++;
    if (current < segments.length) {
      const videoPath = segments[current].includes("?") ? `${segments[current]}&camera=${selectedCamera}` : `${segments[current]}?camera=${selectedCamera}`
      vid.src = videoPath;
      vid.load();
      vid.play();
    }
  });

  overlay.querySelectorAll(".camera-button").forEach(button => {
    button.addEventListener("click", e => {
      overlay.querySelectorAll(".camera-button").forEach(btn => btn.classList.remove("active"));
      e.target.classList.add("active");
      selectedCamera = e.target.dataset.camera;
      vid.src = segments[current].includes("?") ? `${segments[current]}&camera=${selectedCamera}` : `${segments[current]}?camera=${selectedCamera}`;
      vid.load();
      vid.play();
    });
  });
}

function closeOverlay() {
  if (!overlay) return
  overlay.remove()
  overlay = null
  state.selectedRoute = null
}

async function togglePreserved(route, e) {
  e.stopPropagation()
  const newPreservedState = !route.is_preserved
  const method = newPreservedState ? "POST" : "DELETE"
  try {
    const response = await fetch(`/api/routes/${route.name}/preserve`, { method })
    if (response.ok) {
      route.is_preserved = newPreservedState
    } else {
      const errorData = await response.json()
      showSnackbar(errorData.error || "보존 상태를 변경하지 못했습니다...", "error")
    }
  } catch (_) {
    showSnackbar("오류가 발생했습니다...", "error")
  }
}

async function deleteAllRoutes() {
  state.showDeleteAllModal = false
  state.isDeletingAll = true
  try {
    const res = await fetch("/api/routes/delete_all", { method: "DELETE" })
    if (!res.ok) throw new Error()
    await refresh()
    showSnackbar("모든 주행 영상이 삭제되었습니다!")
  } catch {
    showSnackbar("모든 주행 영상을 삭제하는 중 오류가 발생했습니다...", "error")
  } finally {
    state.isDeletingAll = false
  }
}

export function RouteRecordings() {
  if (isGalaxyTunnel()) {
    return html`
      <div class="tunnel-notice">
        <div class="tunnel-notice-icon">🛰️</div>
        <h3 class="tunnel-notice-title">Galaxy에서는 주행 영상을 이용할 수 없습니다</h3>
        <p class="tunnel-notice-body">주행 영상을 불러오려면 장치에 직접 연결해야 합니다.<br>이 기능을 사용하려면 장치의 로컬 네트워크에 연결하세요.</p>
      </div>
    `;
  }

  if (state.selectedRoute && !overlay) openOverlay(state.selectedRoute);

  return html`
    <div class="screen-recordings-wrapper">
      <div class="screen-recordings-widget">
        <div class="screen-recordings-title">주행 영상</div>
        <button
          class="show-preserved-button"
          @click="${() => (state.showPreservedOnly = !state.showPreservedOnly)}"
          disabled="${() => (state.loading && state.routes.length === 0) || false}"
        >          ${() => (state.showPreservedOnly ? "모든 주행 보기" : "보존된 주행만 보기")}
        </button>

        ${() => {
      const routesToShow = state.routes.filter(r => !state.showPreservedOnly || r.is_preserved);

      if (routesToShow.length === 0) {
        if (state.loading && state.total > 0) {
          return html`<p class="screen-recordings-message">주행 처리 중: 전체 ${state.total.toLocaleString("ko-KR")}개 중 ${state.progress.toLocaleString("ko-KR")}개</p>`;
        }
        if (state.loading && !state.isDeletingAll) {
          return html`<p class="screen-recordings-message">불러오는 중...</p>`;
        }
        if (state.isDeletingAll) {
          return html`<p class="screen-recordings-message">주행 영상 삭제 중...</p>`;
        }
        if (state.showPreservedOnly) {
          return html`<p class="screen-recordings-message">보존된 주행이 없습니다...</p>`;
        }
        if (state.error) {
          return html`<p class="screen-recordings-message">${state.error}</p>`;
        }
        return html`<p class="screen-recordings-message">주행 영상을 찾을 수 없습니다...</p>`;
      }

      return html`
            <div class="screen-recordings-grid">
              ${routesToShow.map(
        route => html`
                  <div
                    class="recording-card"
                    @click="${() => {
            state.selectedRoute = route;
          }}"
                  >
                    <div class="preserved-icon" @click="${e => togglePreserved(route, e)}">
                      ${() => html`<i class="bi ${route.is_preserved ? "bi-heart-fill" : "bi-heart"}"></i>`}
                    </div>
                    <div class="recording-preview-container">
                      <img
                        src="${route.png}"
                        class="recording-preview recording-preview-png"
                        style="display:block;"
                        loading="lazy"
                      >
                    </div>
                    <p class="recording-filename">${route.timestamp}</p>
                  </div>
                `
      )}
            </div>
          `;
    }}
        ${() => state.truncated ? html`
          <p class="screen-recordings-message">원활한 화면 표시를 위해 처음 ${MAX_RENDERED_ROUTES.toLocaleString("ko-KR")}개 주행만 표시합니다.</p>
        ` : ""}
        ${() => {
      if (state.routes.length > 0) {
        return html`
              <button
                class="delete-all-button"
                @click="${() => (state.showDeleteAllModal = true)}"
                disabled="${() => state.isDeletingAll || false}"
              >                ${() => (state.isDeletingAll ? "삭제 중..." : "모든 주행 영상 삭제")}
              </button>
            `;
      }
      return "";
    }}
      </div>
      ${() => state.showDeleteAllModal ? Modal({
      title: "전체 삭제 확인",
      message: "모든 주행 영상을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다...",
      onConfirm: deleteAllRoutes,
      onCancel: () => { state.showDeleteAllModal = false; },
      confirmText: "모두 삭제"
    }) : ""}
    </div>
  `;
}

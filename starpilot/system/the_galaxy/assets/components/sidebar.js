import { html } from "/assets/vendor/arrow-core.js";
import { hideSidebar, upperFirst } from "/assets/js/utils.js";

const MENU_ITEMS = {
  home: [
    { name: "홈", link: "/", icon: "bi-house-fill" },
  ],
  recordings: [
    { name: "주행 영상", link: "/dashcam_routes", icon: "bi-camera-reels" },
    { name: "화면 녹화", link: "/screen_recordings", icon: "bi-record-circle" },
  ],
  tools: [
    { name: "설정", link: "/device_settings", icon: "bi-toggle-on" },
    { name: "제한 속도 다운로드", link: "/download_speed_limits", icon: "bi-download" },
    { name: "오류 로그", link: "/manage_error_logs", icon: "bi-exclamation-triangle" },
    { name: "Galaxy", link: "/galaxy", icon: "bi-globe2" },
    { name: "감시 모드", link: "/sentry", icon: "bi-shield-exclamation" },
    { name: "횡방향 튜닝", link: "/tuning", icon: "bi-sign-turn-right" },
    { name: "종방향 제어", link: "/longitudinal_maneuvers", icon: "bi-signpost-split" },
    { name: "지도", link: "/manage_maps", icon: "bi-map" },
    { name: "내비게이션", link: "/set_navigation_destination", icon: "bi-geo-alt-fill" },
    { name: "앱 키", link: "/manage_navigation_keys", icon: "bi-key-fill" },
    { name: "모델 관리", link: "/manage_models", icon: "bi-cpu" },
    { name: "그래프", link: "/plots", icon: "bi-graph-up-arrow" },
    { name: "테스트 환경", link: "/testing_ground", icon: "bi-bezier2" },
    { name: "문제 해결", link: "/troubleshoot", icon: "bi-tools" },
    { name: "V-Adj 사각지대 모니터", link: "/manage_v_asm", icon: "bi-eye" },
    { name: "PiP 측면 카메라", link: "/manage_pip_sidecam", icon: "bi-badge-hd", developerOnly: true },
    { name: "테마 만들기", link: "/theme_maker", icon: "bi-palette-fill" },
    { name: "Tmux 로그", link: "/manage_tmux", icon: "bi-terminal" },
    { name: "백업 및 복원", link: "/manage_toggles", icon: "bi-arrow-repeat" },
    { name: "소프트웨어", link: "/manage_updates", icon: "bi-arrow-up-circle" },
    { name: "차량 기능", link: "/vehicle_features", icon: "bi-car-front" },
  ],
};

const SECTION_NAMES = {
  home: "홈",
  recordings: "녹화",
  tools: "도구",
};

let galaxyDeveloperMode = false;

function matchesPath(currentPath, link) {
  if (link === "/") return currentPath === "/";
  if (link === "/tuning" && currentPath === "/lateral_maneuvers") return true;
  return currentPath === link || currentPath.startsWith(`${link}/`);
}

function buildSectionMarkup(section, links, currentPath) {
  const linksMarkup = links.filter((link) => !link.developerOnly || galaxyDeveloperMode).map((link) => {
    const active = matchesPath(currentPath, link.link) ? "active" : "";
    return `
      <li class="${active}">
        <a class="menu-item-link" href="${link.link}">
          <i class="bi ${link.icon}"></i>
          <span>${upperFirst(link.name)}</span>
        </a>
      </li>
    `;
  }).join("");

  return `
    <div class="sidebar_widget">
      <ul class="menu_section">
        <li>
          <span class="section-title">${SECTION_NAMES[section] ?? upperFirst(section)}</span>
          <ul id="${section}">
            ${linksMarkup}
          </ul>
        </li>
      </ul>
    </div>
  `;
}

async function refreshGalaxyDeveloperMode() {
  try {
    const response = await fetch("/api/params/all", { cache: "no-store" });
    if (!response.ok) return;
    const values = await response.json();
    const next = Boolean(values?.GalaxyDeveloperMode);
    if (next !== galaxyDeveloperMode) {
      galaxyDeveloperMode = next;
      renderSidebarIntoShell();
    }
  } catch (error) {
    console.warn("Unable to determine Galaxy Developer Mode:", error);
  }
}

function bindSidebarHandlers() {
  const menuButton = document.getElementById("menu_button");
  const underlay = document.getElementById("sidebarUnderlay");

  if (!menuButton || !underlay) return;

  if (!window.__theGalaxySidebarMenuBound) {
    window.__theGalaxySidebarMenuBound = true;
    menuButton.addEventListener("click", () => {
      const sidebar = document.getElementById("sidebar");
      const currentUnderlay = document.getElementById("sidebarUnderlay");
      if (!sidebar || !currentUnderlay) return;
      sidebar.classList.toggle("visible");
      currentUnderlay.classList.toggle("hidden");
    });
  }

  underlay.onclick = hideSidebar;

  document.querySelectorAll("#sidebar a.menu-item-link").forEach((anchor) => {
    if (anchor.dataset.boundClick === "1") return;
    anchor.dataset.boundClick = "1";
    anchor.addEventListener("click", (event) => {
      if (event.defaultPrevented) return;
      if (event.button !== 0) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

      event.preventDefault();
      const href = anchor.getAttribute("href") || "/";
      const navigate = window.__theGalaxyNavigate;
      if (typeof navigate === "function") {
        navigate(href);
      } else {
        window.location.assign(href);
      }
      hideSidebar();
      window.scrollTo(0, 0);
    });
  });
}

function renderSidebarIntoShell(currentPath) {
  const shell = document.getElementById("sidebar_shell");
  if (!shell) return;

  const activePath = currentPath || window.location.pathname;
  const sectionsMarkup = Object.entries(MENU_ITEMS)
    .map(([section, links]) => buildSectionMarkup(section, links, activePath))
    .join("");

  shell.innerHTML = `
    <div id="sidebarUnderlay" class="hidden"></div>
    <div id="sidebar" class="sidebar">
      <div>
        <div class="title">
          <img class="logo" src="/assets/images/main_logo.png" alt="Galaxy logo" />
          <div class="title_text sidebar_header">
            <p>Galaxy</p>
          </div>
        </div>
        <hr />
        ${sectionsMarkup}
      </div>
    </div>
  `;

  bindSidebarHandlers();
}

export function Sidebar(currentPath) {
  setTimeout(() => {
    renderSidebarIntoShell(currentPath);
    refreshGalaxyDeveloperMode();
  }, 0);
  return html`<div id="sidebar_shell"></div>`;
}

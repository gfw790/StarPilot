import { html } from "/assets/vendor/arrow-core.js";

const HOME_STATE = {
  status: "loading",
  data: null,
  unit: "miles",
  error: "",
  initialized: false,
  refreshTimer: null,
};

const FAVORITE_COLORS = ["#5ec8c8", "#8b6cc5", "#d4a060", "#e05577", "#6cc56e", "#8aa3ff"];
const TOP_MODEL_LIMIT = 3;

function withTimeout(promise, timeoutMs, label) {
  return new Promise((resolve, reject) => {
    const timerId = setTimeout(() => reject(new Error(`${label} 시간 초과`)), timeoutMs);
    promise.then((value) => {
      clearTimeout(timerId);
      resolve(value);
    }).catch((err) => {
      clearTimeout(timerId);
      reject(err);
    });
  });
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function safeUrl(value) {
  const text = String(value ?? "").trim();
  return text.startsWith("https://github.com/") ? text : "";
}

function numberValue(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function formatInt(value) {
  return Math.round(numberValue(value)).toLocaleString("ko-KR", { maximumFractionDigits: 0 });
}

function formatOneDecimal(value) {
  return numberValue(value).toLocaleString("ko-KR", { maximumFractionDigits: 1 });
}

function formatPercent(value) {
  return `${Math.max(0, Math.min(100, Math.round(numberValue(value))))}%`;
}

function formatDuration(seconds) {
  const total = Math.max(0, Math.round(numberValue(seconds)));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  if (hours > 0) return `${hours}시간 ${minutes}분`;
  return `${minutes}분`;
}

function formatDate(value) {
  if (!value) return "아직 주행 기록 없음";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("ko-KR", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatDriveTimeRange(startValue, endValue) {
  if (!startValue) return "아직 주행 기록 없음";
  const start = new Date(startValue);
  const end = new Date(endValue);
  if (Number.isNaN(start.getTime())) return String(startValue);
  if (Number.isNaN(end.getTime()) || end <= start) return formatDate(startValue);

  const dateLabel = start.toLocaleDateString("ko-KR", { month: "short", day: "numeric" });
  const startTime = start.toLocaleTimeString("ko-KR", { hour: "numeric", minute: "2-digit" });
  const endTime = end.toLocaleTimeString("ko-KR", { hour: "numeric", minute: "2-digit" });
  if (start.toDateString() === end.toDateString()) {
    return `${dateLabel}, ${startTime}-${endTime}`;
  }

  const endDateLabel = end.toLocaleDateString("ko-KR", { month: "short", day: "numeric" });
  return `${dateLabel}, ${startTime}-${endDateLabel}, ${endTime}`;
}

function localizeUnit(unit) {
  return ({ miles: "마일", kilometers: "킬로미터", mph: "mph", kph: "km/h" })[unit] || unit;
}

function localizeDayLabel(label) {
  return ({ Mon: "월", Tue: "화", Wed: "수", Thu: "목", Fri: "금", Sat: "토", Sun: "일" })[label] || label;
}

function localizeDisplayText(value) {
  const text = String(value ?? "");
  const exact = {
    "No drives": "주행 기록 없음",
    "No clean drives": "안전 주행 기록 없음",
    "No undistracted drives": "집중력 저하 없는 주행 기록 없음",
    "Consecutive drive days": "연속 주행",
    "No attention warnings": "주의 경고 없음",
    "Unknown date": "알 수 없는 날짜",
    "Parked": "주차 중",
    "Driving": "주행 중",
    "Yes": "예",
    "No": "아니요",
    "unknown": "알 수 없음",
  };
  if (exact[text]) return exact[text];
  const months = { Jan: 1, Feb: 2, Mar: 3, Apr: 4, May: 5, Jun: 6, Jul: 7, Aug: 8, Sep: 9, Oct: 10, Nov: 11, Dec: 12 };
  const localizedDates = text.replace(/\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d{1,2})(?:, (\d{4}))?/g,
    (_, month, day, year) => `${year ? `${year}년 ` : ""}${months[month]}월 ${day}일`);
  if (localizedDates !== text) {
    const isWeekDetail = /^(miles|kilometers) - week of /.test(text);
    return localizedDates
      .replace(/^(miles|kilometers) - week of /, (_, unit) => `${localizeUnit(unit)} - `)
      .replace(/^(miles|kilometers) - /, (_, unit) => `${localizeUnit(unit)} - `)
      + (isWeekDetail ? "이 포함된 주" : "");
  }
  if (text === "miles" || text === "kilometers") return localizeUnit(text);
  if (/^\d+(?:\.\d+)? hours?$/.test(text)) return text.replace(/ hours?$/, "시간");
  if (/^\d+ days?$/.test(text)) return text.replace(/ days?$/, "일");
  if (/^\d+ drives?$/.test(text)) return text.replace(/ drives?$/, "회");
  if (/^\d+(?:\.\d+)? (miles|kilometers)$/.test(text)) {
    const [, amount, unit] = text.match(/^(\d+(?:\.\d+)?) (miles|kilometers)$/);
    return `${amount} ${localizeUnit(unit)}`;
  }
  return text;
}

function formatBytes(bytes) {
  const value = Math.max(0, numberValue(bytes));
  if (value >= 2 ** 30) return `${formatOneDecimal(value / (2 ** 30))} GB`;
  if (value >= 2 ** 20) return `${formatOneDecimal(value / (2 ** 20))} MB`;
  return `${formatInt(value / 1024)} KB`;
}

function statBlock(title, stats = {}, unit) {
  return `
    <section class="dashboard-card dashboard-summary-card">
      <h2>${escapeHtml(title)}</h2>
      <div class="dashboard-stat-row">
        <div><strong>${formatInt(stats.drives)}회</strong><span>주행</span></div>
        <div><strong>${formatOneDecimal(stats.distance)}</strong><span>${escapeHtml(localizeUnit(stats.unit || unit))}</span></div>
        <div><strong>${formatOneDecimal(stats.hours)}</strong><span>시간</span></div>
      </div>
    </section>
  `;
}

function fallbackDashboard(data, unit) {
  const disk = Array.isArray(data?.diskUsage) ? data.diskUsage[0] : {};
  const usedText = String(disk?.used || "0 GB");
  const sizeText = String(disk?.size || "0 GB");
  return {
    lastDrive: {
      date: "",
      distance: 0,
      duration: 0,
      avgSpeed: 0,
      engagedPercent: 0,
      model: "알 수 없는 모델",
      segmentCount: 0,
      distractedMoments: 0,
      unresponsiveMoments: 0,
      attentionKnown: true,
      distanceUnit: unit,
      speedUnit: unit === "kilometers" ? "kph" : "mph",
    },
    recentDrives: [],
    week: {
      distance: 0,
      duration: 0,
      hours: 0,
      drives: 0,
      engagedPercent: 0,
      dailyDistance: [],
      distanceUnit: unit,
    },
    records: {
      longestDrive: { value: "0", detail: unit },
      mostEngagedDay: { value: "0%", detail: "주행 기록 없음" },
      bestWeek: { value: "0", detail: unit },
      highestStreak: { value: "0일", detail: "주행 기록 없음" },
      longestUndistractedDrive: { value: "0.0시간", detail: "안전 주행 기록 없음" },
      cleanDriveStreak: { value: "0회", detail: "안전 주행 기록 없음" },
    },
    device: { status: "Parked", online: true, uptimeSeconds: null, cpuTempC: null },
    storage: {
      freeBytes: 0,
      usedBytes: 0,
      totalBytes: 0,
      usedPercent: Number.parseFloat(disk?.usedPercentage) || 0,
      legacyText: `${sizeText} 중 ${usedText} 사용`,
      segmentCounts: { standard: 0, highResolution: 0, alternate: 0 },
    },
    favoriteModels: [],
  };
}

function driveStatsReady(drive) {
  return drive?.ignored === true || drive?.attentionKnown !== false;
}

function dashboardPendingDriveCount(dashboard) {
  const recent = Array.isArray(dashboard?.recentDrives) ? dashboard.recentDrives : [];
  return recent.filter(drive => !driveStatsReady(drive)).length;
}

function dashboardShouldAutoRefresh(dashboard) {
  const analysis = dashboard?.analysis || {};
  return Boolean(analysis.running)
    || numberValue(analysis.pendingRoutes) > 0
    || dashboardPendingDriveCount(dashboard) > 0;
}

function clearDashboardRefreshTimer() {
  if (HOME_STATE.refreshTimer) {
    clearTimeout(HOME_STATE.refreshTimer);
    HOME_STATE.refreshTimer = null;
  }
}

function scheduleDashboardRefresh(dashboard) {
  clearDashboardRefreshTimer();
  if (!dashboardShouldAutoRefresh(dashboard)) return;
  HOME_STATE.refreshTimer = setTimeout(() => initializeHome(false), 3500);
}

function renderAnalysisStatus(dashboard) {
  const analysis = dashboard?.analysis || {};
  const pendingRoutes = Math.max(0, Math.round(numberValue(analysis.pendingRoutes)));
  const pendingDrives = dashboardPendingDriveCount(dashboard);
  const count = Math.max(pendingRoutes, pendingDrives);
  if (!analysis.running && count <= 0) return "";

  const runningCount = count || Math.max(1, Math.round(numberValue(analysis.batchSize)));
  const label = analysis.running
    ? `${runningCount}개 주행 분석 중`
    : `${count}개 주행 분석 대기 중`;

  return `
    <div class="dashboard-analysis-status">
      <i class="bi bi-hourglass-split"></i>
      <span>${escapeHtml(label)}</span>
    </div>
  `;
}

function renderLastDrive(drive) {
  const ready = driveStatsReady(drive);
  return `
    <section class="dashboard-card dashboard-last-drive">
      <div class="dashboard-card-kicker"><span></span>최근 주행</div>
      <div class="dashboard-drive-date">${escapeHtml(formatDriveTimeRange(drive.date, drive.endDate))}</div>
      <div class="dashboard-drive-metrics">
        <div><strong>${ready ? formatOneDecimal(drive.distance) : "..."}</strong><span>${ready ? escapeHtml(localizeUnit(drive.distanceUnit || "miles")) : "분석 중"}</span></div>
        <div><strong>${formatDuration(drive.duration)}</strong><span>주행 시간</span></div>
        <div><strong>${ready ? formatInt(drive.avgSpeed) : "..."}</strong><span>${ready ? `평균 ${escapeHtml(localizeUnit(drive.speedUnit || "mph"))}` : "속도"}</span></div>
        <div><strong>${ready ? formatPercent(drive.engagedPercent) : "..."}</strong><span>제어 활성</span></div>
      </div>
      <div class="dashboard-drive-footer">
        <span><i class="bi bi-cpu"></i>${escapeHtml(drive.model || "알 수 없는 모델")}</span>
        ${ready
          ? `<span><i class="bi bi-eye"></i>주의 분산 ${formatInt(drive.distractedMoments)}회</span>
             <span><i class="bi bi-exclamation-triangle"></i>무반응 ${formatInt(drive.unresponsiveMoments)}회</span>`
          : `<span><i class="bi bi-hourglass-split"></i>통계 분석 중</span>`}
      </div>
    </section>
  `;
}

function renderWeekChart(week) {
  const days = Array.isArray(week.dailyDistance) && week.dailyDistance.length
    ? week.dailyDistance
    : ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map(label => ({ label, distance: 0 }));
  const maxDistance = Math.max(1, ...days.map(day => numberValue(day.distance)));
  const bars = days.map(day => {
    const height = Math.max(4, (numberValue(day.distance) / maxDistance) * 100);
    return `
      <div class="dashboard-day">
        <div class="dashboard-day-bar" style="height:${height}%"></div>
        <span>${escapeHtml(localizeDayLabel(day.label))}</span>
      </div>
    `;
  }).join("");

  return `
    <section class="dashboard-card dashboard-week">
      <h2>이번 주</h2>
      <div class="dashboard-week-top">
        <div class="dashboard-donut" style="--value:${Math.max(0, Math.min(100, numberValue(week.engagedPercent)))}">
          <strong>${formatPercent(week.engagedPercent)}</strong>
          <span>제어 활성</span>
        </div>
        <div class="dashboard-week-metrics">
          <div><strong>${formatOneDecimal(week.distance)}</strong><span>${escapeHtml(localizeUnit(week.distanceUnit || "miles"))}</span></div>
          <div><strong>${formatOneDecimal(week.hours)}</strong><span>시간</span></div>
          <div><strong>${formatInt(week.drives)}회</strong><span>주행</span></div>
        </div>
      </div>
      <h3>일별 주행 거리</h3>
      <div class="dashboard-bars">${bars}</div>
    </section>
  `;
}

function recordRow(icon, title, record) {
  return `
    <div class="dashboard-record-row">
      <span><i class="bi ${icon}"></i></span>
      <div>
        <p>${escapeHtml(title)}</p>
        <strong>${escapeHtml(localizeDisplayText(record?.value ?? "0"))}</strong>
        <small>${escapeHtml(localizeDisplayText(record?.detail ?? ""))}</small>
      </div>
    </div>
  `;
}

function renderRecords(records) {
  return `
    <section class="dashboard-card dashboard-records">
      <h2>개인 기록</h2>
      ${recordRow("bi-arrow-right", "최장 주행", records.longestDrive)}
      ${recordRow("bi-check2-circle", "제어 활성률이 가장 높은 날", records.mostEngagedDay)}
      ${recordRow("bi-graph-up-arrow", "최고 주간 기록", records.bestWeek)}
      ${recordRow("bi-lightning-charge", "최장 연속 주행", records.highestStreak)}
      ${recordRow("bi-shield-check", "주의 분산 없는 최장 주행", records.longestUndistractedDrive)}
      ${recordRow("bi-stars", "안전 주행 연속 기록", records.cleanDriveStreak)}
    </section>
  `;
}

function renderRecentDrives(drives) {
  if (!Array.isArray(drives) || drives.length === 0) {
    return `
      <section class="dashboard-card dashboard-recent">
        <h2>최근 주행</h2>
        <div class="dashboard-empty">아직 로컬 주행 기록이 없습니다.</div>
      </section>
    `;
  }

  const rows = drives.map(drive => {
    const ignored = drive?.ignored === true;
    const ready = driveStatsReady(drive);
    const routeNames = Array.isArray(drive?.routeNames) ? drive.routeNames.filter(Boolean) : [];
    return `
    <div class="dashboard-drive-row ${ready ? "" : "is-pending"} ${ignored ? "is-ignored" : ""}">
      <div class="dashboard-drive-main">
        <strong>${escapeHtml(formatDriveTimeRange(drive.date, drive.endDate))}</strong>
        <span>${escapeHtml(drive.model || "알 수 없는 모델")}</span>
      </div>
      <div class="dashboard-drive-details">
        <span>${ignored && drive.attentionKnown === false ? "통계에서 제외됨" : (ready ? `${formatOneDecimal(drive.distance)} ${escapeHtml(localizeUnit(drive.distanceUnit || "miles"))}` : "통계 분석 중")}</span>
        <span>${formatDuration(drive.duration)}</span>
      </div>
      <div class="dashboard-attention">
        ${ignored
          ? `<span><i class="bi bi-eye-slash"></i> 통계에서 제외됨</span>`
          : ready
          ? `<span>주의 분산 ${formatInt(drive.distractedMoments)}회</span><span>무반응 ${formatInt(drive.unresponsiveMoments)}회</span>`
          : `<span>전체 경로 분석 대기 중</span>`}
      </div>
      <div class="dashboard-engaged-cell">
        <div class="dashboard-mini-bar"><span style="width:${ready && !ignored ? Math.max(0, Math.min(100, numberValue(drive.engagedPercent))) : 0}%"></span></div>
        <strong>${ignored ? "제외됨" : (ready ? `제어 활성 ${formatPercent(drive.engagedPercent)}` : "대기 중")}</strong>
      </div>
      ${routeNames.length === 0 ? "" : `
        <div class="dashboard-drive-actions">
          <button
            class="dashboard-drive-stats-action"
            data-action="${ignored ? "include" : "ignore"}"
            data-route-names="${escapeHtml(JSON.stringify(routeNames))}"
            title="${ignored ? "이 주행을 로컬 대시보드 통계에 포함" : "이 주행을 로컬 대시보드 통계에서 제외"}">
            <i class="bi ${ignored ? "bi-arrow-counterclockwise" : "bi-eye-slash"}"></i>
            <span>${ignored ? "주행 통계에 포함" : "주행 통계에서 제외"}</span>
          </button>
        </div>
      `}
    </div>
  `;
  }).join("");

  return `
    <section class="dashboard-card dashboard-recent">
      <h2>최근 주행</h2>
      ${rows}
    </section>
  `;
}

function favoriteChart(models) {
  if (!Array.isArray(models) || models.length === 0) {
    return {
      style: "background: conic-gradient(var(--dashboard-track) 0 100%)",
      rows: `<div class="dashboard-empty">아직 모델 사용 기록이 없습니다.</div>`,
    };
  }

  const topModels = models.slice(0, TOP_MODEL_LIMIT);
  const total = topModels.reduce((sum, model) => sum + Math.max(1, numberValue(model.weight)), 0);
  let start = 0;
  const segments = topModels.map((model, index) => {
    const end = start + (Math.max(1, numberValue(model.weight)) / total) * 100;
    const segment = `${FAVORITE_COLORS[index]} ${start}% ${end}%`;
    start = end;
    return segment;
  });

  const rows = topModels.map((model, index) => `
    <div class="dashboard-model-row">
      <span class="dashboard-swatch" style="background:${FAVORITE_COLORS[index]}"></span>
      <div>
        <strong>${escapeHtml(model.name)}</strong>
        <small>이 모델로 ${formatInt(model.drives)}회 주행</small>
      </div>
    </div>
  `).join("");

  return {
    style: `background: conic-gradient(${segments.join(", ")})`,
    rows,
  };
}

function renderFavoriteModels(models) {
  const chart = favoriteChart(models);
  return `
    <section class="dashboard-card dashboard-models">
      <h2>가장 많이 사용한 모델</h2>
      <div class="dashboard-model-layout">
        <div class="dashboard-favorite-donut" style="${chart.style}"></div>
        <div class="dashboard-model-list">${chart.rows}</div>
      </div>
    </section>
  `;
}

function renderStorage(storage) {
  const usedPercent = Math.max(0, Math.min(100, numberValue(storage.usedPercent)));
  const counts = storage.segmentCounts || {};
  const summary = storage.legacyText
    ? storage.legacyText.replace(/^(.+) used of (.+)$/, "$2 중 $1 사용")
    : `${formatBytes(storage.totalBytes)} 중 ${formatBytes(storage.usedBytes)} 사용`;
  return `
    <section class="dashboard-card dashboard-device-card">
      <h2>저장 공간</h2>
      <p class="dashboard-muted">${escapeHtml(summary)}</p>
      <div class="dashboard-storage-track"><span style="width:${usedPercent}%"></span></div>
      <div class="dashboard-key-values">
        <div><span>주행 영상</span><strong>${formatInt(counts.standard)}개 구간</strong></div>
        <div><span>고해상도 영상</span><strong>${formatInt(counts.highResolution)}개 구간</strong></div>
        <div><span>Konik 영상</span><strong>${formatInt(counts.alternate)}개 구간</strong></div>
        <div><span>여유 공간</span><strong>${formatBytes(storage.freeBytes)}</strong></div>
      </div>
    </section>
  `;
}

function renderVitals(device) {
  const uptime = device.uptimeSeconds == null ? "알 수 없음" : formatDuration(device.uptimeSeconds);
  const cpu = device.cpuTempC == null ? "알 수 없음" : `${formatInt(device.cpuTempC)} °C`;
  const lanIp = device.lanIp || "알 수 없음";
  const networkName = device.networkName || "무선 네트워크 연결 없음";
  return `
    <section class="dashboard-card dashboard-device-card">
      <h2>장치 상태</h2>
      <div class="dashboard-key-values">
        <div><span>상태</span><strong>${escapeHtml(localizeDisplayText(device.status || "Parked"))}</strong></div>
        <div><span>LAN IP</span><strong>${escapeHtml(lanIp)}</strong></div>
        <div><span>네트워크</span><strong>${escapeHtml(networkName)}</strong></div>
        <div><span>가동 시간</span><strong>${escapeHtml(uptime)}</strong></div>
        <div><span>CPU 온도</span><strong>${escapeHtml(cpu)}</strong></div>
      </div>
    </section>
  `;
}

function renderSoftware(info = {}) {
  const changelogUrl = safeUrl(info.changelogUrl);
  const commitUrl = safeUrl(info.commitUrl);
  const commitHref = changelogUrl || commitUrl;
  const fields = [
    { label: "브랜치", value: info.branchName },
    { label: "빌드", value: info.buildEnvironment },
    { label: "커밋", value: info.commitHash, href: commitHref },
    { label: "버전 날짜", value: info.versionDate },
    { label: "포크 관리자", value: info.forkMaintainer },
    { label: "업데이트 가능", value: localizeDisplayText(info.updateAvailable) },
  ];

  return `
    <section class="dashboard-card dashboard-device-card">
      <h2>소프트웨어</h2>
      <div class="dashboard-software-list">
        ${fields.map((field) => `
          <div>
            <span>${escapeHtml(field.label)}</span>
            <strong>${field.href ? `<a href="${escapeHtml(field.href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(field.value ?? "알 수 없음")}</a>` : escapeHtml(field.value ?? "알 수 없음")}</strong>
          </div>
        `).join("")}
      </div>
    </section>
  `;
}

function bindDashboardActions() {
  const refreshButton = document.getElementById("dashboard_refresh");
  if (refreshButton) {
    refreshButton.onclick = () => initializeHome(true);
  }

  document.querySelectorAll(".dashboard-drive-stats-action").forEach((button) => {
    button.onclick = async () => {
      let routeNames = [];
      try {
        routeNames = JSON.parse(button.dataset.routeNames || "[]");
      } catch {
        routeNames = [];
      }
      if (!Array.isArray(routeNames) || routeNames.length === 0) return;

      const action = button.dataset.action === "include" ? "include" : "ignore";
      const confirmed = action === "include" || window.confirm(
        "이 주행의 통계를 제외하시겠습니까?\n\n" +
        "로컬 주간 합계, 기록, 모델 사용량, 제어 활성률 및 주의 상태 연속 기록에 더 이상 반영되지 않습니다."
      );
      if (!confirmed) return;

      button.disabled = true;
      try {
        const response = await fetch(`/api/stats/${action}_drive`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ routeNames }),
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "주행 통계를 변경할 수 없습니다.");
        await initializeHome(false);
      } catch (error) {
        window.alert(error?.message || "주행 통계를 변경할 수 없습니다.");
        button.disabled = false;
      }
    };
  });
}

function renderDashboard(state) {
  const shell = document.getElementById("home_shell");
  if (!shell) return;

  if (state.status === "error") {
    clearDashboardRefreshTimer();
    shell.innerHTML = `
      <div class="dashboard dashboard-narrow">
        <div class="dashboard-error">대시보드를 불러오지 못했습니다: ${escapeHtml(state.error)}</div>
        <button id="dashboard_refresh" class="dashboard-refresh"><i class="bi bi-arrow-clockwise"></i>새로고침</button>
      </div>
    `;
    bindDashboardActions();
    return;
  }

  if (state.status !== "ready" || !state.data) {
    shell.innerHTML = `
      <div class="dashboard dashboard-narrow">
        <div class="dashboard-loading">대시보드 불러오는 중...</div>
      </div>
    `;
    return;
  }

  const data = state.data || {};
  const dashboard = data.dashboard || fallbackDashboard(data, state.unit);
  const driveStats = data.driveStats || {};
  const device = dashboard.device || {};
  const status = device.status || "Parked";
  const onlineText = device.online === false ? "장치 오프라인" : "장치 온라인";

  shell.innerHTML = `
    <main class="dashboard">
      <header class="dashboard-header">
        <div>
          <h1>대시보드</h1>
          <p><span class="dashboard-status-dot"></span><strong>${escapeHtml(localizeDisplayText(status))}</strong> - ${escapeHtml(onlineText)}</p>
        </div>
        <button id="dashboard_refresh" class="dashboard-refresh"><i class="bi bi-arrow-clockwise"></i>새로고침</button>
      </header>

      ${renderLastDrive(dashboard.lastDrive || fallbackDashboard(data, state.unit).lastDrive)}
      ${renderAnalysisStatus(dashboard)}

      <div class="dashboard-section-label"><span></span>나의 주행</div>
      <div class="dashboard-summary-grid">
        ${statBlock("전체 기간", driveStats.all, state.unit)}
        ${statBlock("지난 1주", driveStats.week, state.unit)}
        ${statBlock("StarPilot", driveStats.starpilot, state.unit)}
      </div>

      <div class="dashboard-two-column">
        ${renderWeekChart(dashboard.week || {})}
        ${renderRecords(dashboard.records || {})}
      </div>

      ${renderRecentDrives(dashboard.recentDrives || [])}

      <div class="dashboard-two-column dashboard-model-storage">
        ${renderFavoriteModels(dashboard.favoriteModels || [])}
        ${renderStorage(dashboard.storage || {})}
      </div>

      <div class="dashboard-section-label"><span></span>내 장치</div>
      <div class="dashboard-device-grid">
        ${renderVitals(device)}
        ${renderSoftware(data.softwareInfo || {})}
      </div>
    </main>
  `;

  bindDashboardActions();
  scheduleDashboardRefresh(dashboard);
}

async function initializeHome(force = false) {
  if (force) {
    clearDashboardRefreshTimer();
    HOME_STATE.status = "loading";
    renderDashboard(HOME_STATE);
  }

  try {
    const statsResponse = await withTimeout(fetch("/api/stats"), 5000, "통계 요청");

    if (!statsResponse.ok) throw new Error(`통계 API 오류: ${statsResponse.status}`);

    const statsJson = await withTimeout(statsResponse.json(), 5000, "통계 JSON 처리");
    const payloadUnit = statsJson?.dashboard?.week?.distanceUnit || statsJson?.driveStats?.all?.unit;

    HOME_STATE.data = statsJson;
    HOME_STATE.unit = payloadUnit || HOME_STATE.unit || "miles";
    HOME_STATE.status = "ready";
  } catch (err) {
    HOME_STATE.status = "error";
    HOME_STATE.error = err?.message || String(err);
  }

  renderDashboard(HOME_STATE);
}

export function Home() {
  setTimeout(() => {
    renderDashboard(HOME_STATE);
    if (!HOME_STATE.initialized) {
      HOME_STATE.initialized = true;
      initializeHome();
    }
  }, 0);

  return html`<div id="home_shell"><p>대시보드 불러오는 중...</p></div>`;
}

import { html, reactive } from "/assets/vendor/arrow-core.js"
import { isGalaxyTunnel } from "/assets/js/utils.js"
import { Modal } from "/assets/components/modal.js";

const state = reactive({
  loading: true,
  error: null,
  recordings: [],
  selectedRecording: null,
  showDeleteModal: false,
  recordingToDelete: null,
  showDeleteAllModal: false,
  progress: 0,
  total: 0,
})

function formatScreenRecordingDate(dateString) {
  const date = new Date(dateString);
  const dateLabel = date.toLocaleDateString("ko-KR", { year: "numeric", month: "long", day: "numeric" });
  const timeLabel = date.toLocaleTimeString("ko-KR", { hour: "numeric", minute: "2-digit" });
  return `${dateLabel} - ${timeLabel}`;
}


async function fetchRecordings() {
  try {
    const response = await fetch("/api/screen_recordings/list");
    if (!response.ok) throw new Error("Network response was not ok");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.substring(6));
            if (data.progress !== undefined && data.total !== undefined) {
              state.progress = data.progress;
              state.total = data.total;
            }
            if (data.recordings) {
              state.recordings.push(...data.recordings);
            }
          } catch (e) {
            console.error("Failed to parse JSON:", e);
          }
        }
      }
    }
  } catch (_) {
    state.error = "화면 녹화를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요."
  } finally {
    state.loading = false
  }
}

fetchRecordings()

function refresh() {
  state.loading = true
  state.recordings = []
  fetchRecordings()
}

let overlay = null

function openDialog(htmlStr) {
  const o = document.createElement("div")
  o.className = "dialog-overlay"
  o.innerHTML = htmlStr
  document.body.appendChild(o)
  return o
}

function closeDialog(o) { if (o) o.remove() }

async function renameFile(rec) {
  const base = rec.filename.replace(/\.mp4$/i, "")
  const dlg = openDialog(`
    <div class="dialog-box">
      <p>“${rec.filename}” 이름 변경</p>
      <input class="rn-input" value="${base}" />
      <div class="dialog-buttons">
        <button class="btn-cancel">취소</button>
        <button class="btn-save">저장</button>
      </div>
    </div>`)
  dlg.querySelector(".btn-cancel").onclick = () => closeDialog(dlg)
  dlg.querySelector(".btn-save").onclick = async () => {
    const val = dlg.querySelector(".rn-input").value.trim()
    if (!val) return
    const oldFilename = rec.filename
    const newFilename = val + ".mp4"

    const res = await fetch("/api/screen_recordings/rename", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ old: oldFilename, new: newFilename }),
    })

    if (res.ok) {
      closeDialog(dlg)

      const recordingToUpdate = state.recordings.find(r => r.filename === oldFilename)
      if (recordingToUpdate) {
        recordingToUpdate.filename = newFilename
        recordingToUpdate.is_custom_name = true
        recordingToUpdate.png = `/screen_recordings/${val}.png`
      }

      const overlayTitleSpan = overlay.querySelector(".media-player-title span");
      if (overlayTitleSpan) {
        overlayTitleSpan.textContent = val.replace(/_/g, " ");
      }
      showSnackbar("녹화 파일 이름이 변경되었습니다!")
    } else {
      showSnackbar("이름을 변경하지 못했습니다...", "error")
    }
  }
}

function confirmDeleteFile(rec) {
  state.recordingToDelete = rec;
  state.showDeleteModal = true;
}

async function deleteFile() {
  if (!state.recordingToDelete) return;
  const rec = state.recordingToDelete;

  const res = await fetch(`/api/screen_recordings/delete/${encodeURIComponent(rec.filename)}`, { method: "DELETE" })
  if (res.ok) {
    closeOverlay();
    refresh();
    showSnackbar("화면 녹화가 삭제되었습니다!");
  } else {
    showSnackbar("삭제하지 못했습니다...", "error");
  }

  state.showDeleteModal = false;
  state.recordingToDelete = null;
}

function openOverlay(rec) {
  if (overlay) return
  overlay = document.createElement("div")
  overlay.className = "media-player-overlay"
  const displayName = rec.is_custom_name ? rec.filename.replace(/\.mp4$/i, "") : formatScreenRecordingDate(rec.timestamp);
  overlay.innerHTML = `
    <div class="media-player-content">
      <div class="media-player-title">
        <span>${displayName}</span>
        <i class="bi bi-pencil-fill action-rename-icon"></i>
      </div>
      <video controls autoplay muted>
        <source src="/api/screen_recordings/download/${rec.filename}" type="video/mp4">
      </video>
      <div class="button-row">
        <button class="close-button action-close">닫기</button>
        <button class="close-button action-download">다운로드</button>
        <button class="close-button action-delete">삭제</button>
      </div>
    </div>`
  overlay.addEventListener("click", e => { if (e.target === overlay) closeOverlay() })
  overlay.querySelector(".action-close").onclick = closeOverlay
  overlay.querySelector(".action-rename-icon").onclick = () => renameFile(rec)
  overlay.querySelector(".action-delete").onclick = () => confirmDeleteFile(rec)
  overlay.querySelector(".action-download").onclick = () => {
    const link = document.createElement("a");
    link.href = `/api/screen_recordings/download/${rec.filename}`;
    link.download = rec.filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
  document.body.appendChild(overlay)
}

function closeOverlay() {
  if (!overlay) return
  overlay.remove()
  overlay = null
  state.selectedRecording = null
}

async function deleteAllRecordings() {
  state.showDeleteAllModal = false
  state.isDeletingAll = true
  try {
    const res = await fetch("/api/screen_recordings/delete_all", { method: "DELETE" })
    if (!res.ok) throw new Error()
    await refresh()
    showSnackbar("모든 화면 녹화가 삭제되었습니다!")
  } catch {
    showSnackbar("모든 화면 녹화를 삭제하는 중 오류가 발생했습니다...", "error")
  } finally {
    state.isDeletingAll = false
  }
}

export function ScreenRecordings() {
  if (isGalaxyTunnel()) {
    return html`
      <div class="tunnel-notice">
        <div class="tunnel-notice-icon">🛰️</div>
        <h3 class="tunnel-notice-title">Galaxy에서는 화면 녹화를 이용할 수 없습니다</h3>
        <p class="tunnel-notice-body">화면 녹화를 불러오려면 장치에 직접 연결해야 합니다.<br>이 기능을 사용하려면 장치의 로컬 네트워크에 연결하세요.</p>
      </div>
    `;
  }

  if (state.selectedRecording && !overlay) openOverlay(state.selectedRecording)

  return html`
    <div class="screen-recordings-wrapper">
      <div class="screen-recordings-widget">
        <div class="screen-recordings-title">화면 녹화</div>

        ${() => {
      if (state.loading && state.recordings.length === 0) return html`<p class="screen-recordings-message">불러오는 중...</p>`
      if (state.error) return html`<p class="screen-recordings-message">${state.error}</p>`
      if (state.progress > 0 && state.progress < state.total) {
        return html`<p class="screen-recordings-message">화면 녹화 처리 중: 전체 ${state.total.toLocaleString("ko-KR")}개 중 ${state.progress.toLocaleString("ko-KR")}개</p>`
      }
      if (state.recordings.length === 0 && !state.loading) {
        return html`<p class="screen-recordings-message">저장된 화면 녹화가 없습니다.</p>`
      }
      return ""
    }}

        <div class="screen-recordings-grid">
          ${() => state.recordings.map(rec => {
      const displayName = rec.is_custom_name ? rec.filename.replace(/\.mp4$/i, "").replace(/_/g, " ") : formatScreenRecordingDate(rec.timestamp)
      return html`
              <div
                class="recording-card"
                @click="${() => { state.selectedRecording = rec }}"
              >
                <div class="recording-preview-container">
                  <img src="${rec.png}" class="recording-preview recording-preview-png" style="display:block;" loading="lazy">
                </div>
                <p class="recording-filename">${displayName}</p>
              </div>
            `
    })}
        </div>

        ${() => {
      if (state.recordings.length > 0) {
        return html`
              <button
                class="delete-all-button"
                @click="${() => (state.showDeleteAllModal = true)}"
              >
                모든 화면 녹화 삭제
              </button>
            `
      }
      return ""
    }}
      </div>
      ${() => state.showDeleteModal ? Modal({
      title: "삭제 확인",
      message: `<strong>${state.recordingToDelete.filename}</strong> 파일을 삭제하시겠습니까?`,
      onConfirm: deleteFile,
      onCancel: () => { state.showDeleteModal = false; state.recordingToDelete = null; },
      confirmText: "삭제"
    }) : ""}
      ${() => state.showDeleteAllModal ? Modal({
      title: "전체 삭제 확인",
      message: "모든 화면 녹화를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다...",
      onConfirm: deleteAllRecordings,
      onCancel: () => { state.showDeleteAllModal = false; },
      confirmText: "모두 삭제"
    }) : ""}
    </div>
  `
}

let staticUi = {}
let snackbarUi = {}

function interpolate(template, values = {}) {
  return String(template).replace(/\{([A-Za-z0-9_]+)\}/g, (match, name) => (
    Object.prototype.hasOwnProperty.call(values, name) ? String(values[name]) : match
  ))
}

export function uiText(source, values = {}) {
  return interpolate(staticUi[source] || source, values)
}

export function uiKey(key, fallback, values = {}) {
  return interpolate(staticUi[key] || fallback, values)
}

function snackbarPattern(text) {
  const patterns = [
    [/^Failed to fetch logs: (.+)$/, "failedFetchLogs", ["detail"]],
    [/^Delete failed: (.+)$/, "deleteFailedDetail", ["detail"]],
    [/^Rename failed: (.+)$/, "renameFailedDetail", ["detail"]],
    [/^Capture failed: (.+)$/, "captureFailedDetail", ["detail"]],
    [/^Delete-all failed: (.+)$/, "deleteAllFailedDetail", ["detail"]],
    [/^(.+) deleted successfully!$/, "fileDeleted", ["name"]],
    [/^(.+) renamed to (.+)!$/, "fileRenamed", ["name", "newName"]],
    [/^Failed to update (.+) location\.\.\.$/, "locationUpdateFailed", ["type"]],
    [/^"(.+)" renamed to "(.+)"!$/, "favoriteRenamed", ["name", "newName"]],
    [/^Loaded (\d+) branches\.$/, "branchesLoaded", ["count"]],
    [/^Failed to update (.+)\.$/, "updateFailed", ["name"]],
    [/^Test notification sent through (.+)\.$/, "testNotificationSent", ["channels"]],
    [/^Testing Ground (.+) set to (.+)\.$/, "testingGroundSet", ["slot", "mode"]],
    [/^(.+) reset\.$/, "sectionReset", ["name"]],
    [/^Downloading (.+) for the "(.+)" theme\.\.\.$/, "themeDownloading", ["asset", "theme"]],
    [/^Downloaded (.+) for "(.+)"\.$/, "themeDownloaded", ["asset", "theme"]],
    [/^Loaded (.+) from "(.+)"!$/, "themeAssetLoaded", ["asset", "theme"]],
    [/^File (.+) is too large! Please upload files under 5MB\.$/, "fileTooLarge", ["name"]],
    [/^Invalid file type! Please upload an (.+) file\.$/, "invalidFileType", ["type"]],
    [/^An error occurred: (.+) \((.+)\)$/, "errorWithDetail", ["error", "detail"]],
    [/^Selected "(.+)"\.$/, "modelSelected", ["name"]],
    [/^Downloading "(.+)"\.\.\.$/, "modelDownloading", ["name"]],
    [/^Deleted files for "(.+)"\.$/, "modelFilesDeleted", ["name"]],
  ]
  for (const [pattern, key, names] of patterns) {
    const match = text.match(pattern)
    if (!match) continue
    const values = Object.fromEntries(names.map((name, index) => [name, match[index + 1]]))
    return interpolate(snackbarUi[key] || text, values)
  }
  return text
}

export function localizeSnackbar(message) {
  const text = String(message ?? "")
  return snackbarUi[text] || staticUi[text] || snackbarPattern(text)
}

function excluded(node) {
  const element = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement
  return !!element?.closest?.("#snackbar_wrapper, script, style")
}

function translateTextNode(node) {
  if (excluded(node)) return
  const source = node.nodeValue || ""
  const trimmed = source.trim()
  if (!trimmed || !staticUi[trimmed]) return
  node.nodeValue = source.replace(trimmed, staticUi[trimmed])
}

function translateElement(element) {
  if (excluded(element)) return
  for (const attribute of ["placeholder", "title", "aria-label"]) {
    const source = element.getAttribute?.(attribute)
    if (source && staticUi[source]) element.setAttribute(attribute, staticUi[source])
  }
  for (const node of element.childNodes || []) {
    if (node.nodeType === Node.TEXT_NODE) translateTextNode(node)
    else if (node.nodeType === Node.ELEMENT_NODE) translateElement(node)
  }
}

export async function startStaticUiLocalization() {
  try {
    const response = await fetch("/assets/locales/ko.json", { cache: "no-store" })
    if (response.ok) {
      const locale = await response.json()
      staticUi = locale?.staticUi && typeof locale.staticUi === "object" ? locale.staticUi : {}
      snackbarUi = locale?.snackbars && typeof locale.snackbars === "object" ? locale.snackbars : {}
    }
  } catch (_) {
    staticUi = {}
    snackbarUi = {}
  }

  translateElement(document.body)
  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      if (mutation.type === "characterData") translateTextNode(mutation.target)
      if (mutation.type === "attributes") translateElement(mutation.target)
      for (const node of mutation.addedNodes) {
        if (node.nodeType === Node.TEXT_NODE) translateTextNode(node)
        else if (node.nodeType === Node.ELEMENT_NODE) translateElement(node)
      }
    }
  })
  observer.observe(document.body, {
    childList: true,
    subtree: true,
    characterData: true,
    attributes: true,
    attributeFilter: ["placeholder", "title", "aria-label"],
  })
}

window.__localizeGalaxySnackbar = localizeSnackbar

// Exposes only the few native features the UI needs (file dialogs, opening exported files).
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("cyclia", {
  pickFolder: () => ipcRenderer.invoke("pick-folder"),
  pickFile: (ext) => ipcRenderer.invoke("pick-file", ext),
  saveFile: (name, ext) => ipcRenderer.invoke("save-file", name, ext),
  openPath: (p) => ipcRenderer.invoke("open-path", p),
  showInFolder: (p) => ipcRenderer.invoke("show-in-folder", p),
  appLogPath: () => ipcRenderer.invoke("app-log-path"),
  checkUpdates: () => ipcRenderer.invoke("update-check"),
  updateState: () => ipcRenderer.invoke("update-state"),
  installUpdate: () => ipcRenderer.invoke("update-install"),
  openReleases: () => ipcRenderer.invoke("open-releases"),
  onUpdate: (fn) => ipcRenderer.on("update-status", (_e, s) => fn(s)),
});

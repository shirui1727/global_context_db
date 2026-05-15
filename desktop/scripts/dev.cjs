const path = require("node:path");
const { spawn } = require("node:child_process");
const waitOn = require("wait-on");

const projectRoot = path.resolve(__dirname, "..");
const viteBin = path.join(projectRoot, "node_modules", "vite", "bin", "vite.js");
const electronBinary = require("electron");

let viteProcess = null;
let electronProcess = null;
let shuttingDown = false;

function stopProcess(child) {
  if (!child || child.killed) {
    return;
  }
  child.kill();
}

function shutdown(code = 0) {
  if (shuttingDown) {
    return;
  }
  shuttingDown = true;
  stopProcess(electronProcess);
  stopProcess(viteProcess);
  process.exit(code);
}

viteProcess = spawn(process.execPath, [viteBin], {
  cwd: projectRoot,
  stdio: "inherit",
  env: process.env,
  windowsHide: true
});

viteProcess.on("exit", (code) => {
  if (!shuttingDown) {
    shutdown(code ?? 1);
  }
});

waitOn({
  resources: ["tcp:127.0.0.1:5173"],
  timeout: 30000
})
  .then(() => {
    if (shuttingDown) {
      return;
    }

    electronProcess = spawn(electronBinary, ["."], {
      cwd: projectRoot,
      stdio: "inherit",
      env: {
        ...process.env,
        VITE_DEV_SERVER_URL: "http://127.0.0.1:5173"
      },
      windowsHide: true
    });

    electronProcess.on("exit", (code) => {
      if (!shuttingDown) {
        shutdown(code ?? 0);
      }
    });
  })
  .catch((error) => {
    console.error("[dev] Failed to start Vite/Electron", error);
    shutdown(1);
  });

["SIGINT", "SIGTERM"].forEach((signal) => {
  process.on(signal, () => shutdown(0));
});

const path = require("node:path");
const packager = require("@electron/packager");

const projectRoot = path.resolve(__dirname, "..");

packager({
  dir: projectRoot,
  out: path.join(projectRoot, "release"),
  overwrite: true,
  platform: "win32",
  arch: "x64",
  appVersion: "0.1.0",
  executableName: "GlobalContextDB",
  name: "Global Context DB",
  ignore: [
    /^\/src($|\/)/,
    /^\/scripts($|\/)/,
    /^\/release($|\/)/,
    /^\/node_modules\/\.cache($|\/)/,
    /^\/vite\.config\.ts$/,
    /^\/tsconfig.*\.json$/
  ]
}).catch((error) => {
  console.error(error);
  process.exit(1);
});

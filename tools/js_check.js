// 桩环境跑页面JS, 定位真实报错点
const fs = require("fs");
const s = fs.readFileSync("C:/Users/love_/starpivot/static/index.html", "utf8")
  .match(/<script>([\s\S]*?)<\/script>/)[1];

const els = {};
const mkEl = () => ({
  style: {}, classList: { add() {}, toggle() {}, contains: () => false },
  addEventListener() {}, appendChild() {}, append() {},
  setAttribute() {}, dataset: {}, textContent: "", innerHTML: "",
  value: "", onclick: null, oninput: null, onkeydown: null,
  placeholder: "", src: "", className: "",
  querySelector: () => ({ textContent: "" }),
  closest: () => null,
});

global.document = {
  getElementById: id => els[id] || (els[id] = mkEl()),
  querySelector: () => mkEl(),
  querySelectorAll: () => [],
  createElement: () => mkEl(),
  addEventListener() {},
  body: { classList: { add() {}, toggle() {}, contains: () => false } },
};
global.window = global;
global.fetch = () => Promise.resolve({ json: () => Promise.resolve({}), text: () => Promise.resolve("") });
global.WebSocket = function () { this.onopen = this.onclose = this.onmessage = null; };
global.alert = () => {}; global.confirm = () => false;
global.location = { host: "x" };
global.setInterval = () => 0;
global.setTimeout = (f) => { try { f && f(); } catch (e) { console.log("异步块ERR:", e.message); } return 0; };

try {
  new Function(s)();
  console.log("OK 全脚本执行无错");
} catch (e) {
  console.log("ERR 同步段报错:", e.message);
  const m = /<anonymous>:(\d+):(\d+)/.exec(e.stack);
  if (m) {
    const ls = s.split("\n");
    const n = parseInt(m[1]);
    for (let i = Math.max(0, n - 2); i < Math.min(ls.length, n + 1); i++)
      console.log((i + 1) + ":", JSON.stringify(ls[i]).slice(0, 150));
  }
}

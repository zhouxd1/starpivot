# 星枢桌面壳(Electron)

## 结构
- `main.js` 壳主进程: 拉起后端StarPivot.exe→等就绪→加载8899界面; 托盘常驻; Alt+Shift+S呼出; 单实例锁
- `assets/icon.ico` 应用图标
- `package.json` Electron配置(main: main.js)

## 完整分发包构建
后端exe(在仓库根目录 `python build_exe.py` 产出 dist2/StarPivot)放到本目录:
```
desktop/
└── one/(自建, 不入库)
    ├── 星枢.exe          ← Electron主程序(从官方绿色版裁剪)
    └── resources/app/
        ├── main.js       ← 本目录拷入
        ├── assets/       ← 本目录拷入
        ├── package.json  ← 本目录拷入
        └── StarPivot/    ← dist2/StarPivot 拷入(先删净旧目录!)
```
注意: 合壳必须**先删净旧StarPivot目录再拷**,否则_internal残留旧文件。

## 打包要点(踩坑记录)
- 首启清缓存: main.js已内置 session.clearCache() + URL防缓存参数(防改版后壳吃旧页面)
- 单实例锁: requestSingleInstanceLock,重复双击只唤醒
- 窗口最小 1180x740(低于此三栏布局会塌成单列)

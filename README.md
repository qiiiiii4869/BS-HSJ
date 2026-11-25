# BS版HSJ

HSJ 数据分析系统的浏览器版。协联计算使用 Python。

## Windows 启动

安装 Python 3.11 或更新版本，在仓库根目录运行：

```powershell
python -m pip install -r .\bs-workbench\requirements.txt
```

双击 `BS.cmd` 启动或重启服务。关闭后台服务时运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\bs-workbench\Stop-BS.ps1
```

- [使用说明和功能文档](bs-workbench/README.md)
- [随版分析样例](测试系统实例)
- [功能迁移对照表](bs-workbench/功能迁移对照表.md)

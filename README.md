# PKU SLEEPER 睡眠打卡助手

## 环境配置

```powershell
pip install -r requirements.txt
```

## 程序运行

```powershell
python main.py
```

## 代码结构

- `main.py`：应用入口，负责创建 Qt 应用和主控制器。
- `pkusleeper/domain/`：睡眠记录、目标、成就、地图节点等数据模型。
- `pkusleeper/services/`：睡眠流程、目标、成就、地图和用户信息服务。
- `pkusleeper/storage/`：本地 JSON 数据读写。
- `pkusleeper/reports/`：睡眠评分和报告生成。
- `pkusleeper/ui/`：PySide6 界面、页面控制器和服务桥接层。
- `tests/dev_commands.py`：开发/测试用命令行工具。

## 开发者命令

```powershell
python tests/dev_commands.py --help
```

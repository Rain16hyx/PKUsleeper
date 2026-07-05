# PKU Sleeper

一款给北大学生使用的睡眠打卡助手。它可以记录夜间睡眠和午休，生成睡眠报告，管理睡眠目标，并通过成就系统和校园地图解锁机制，让健康作息成为一种习惯。

项目使用 **Python + PySide6** 构建桌面界面，数据默认保存在本地 `data/` 目录中。

## 功能概览

演示视频链接：
https://disk.pku.edu.cn/link/AA74B1C45CB53C4D7CA691479EB73E79F1

- 睡眠打卡：记录开始/结束时间、睡眠类型、环境和目标时长。
- 历史记录：查看近 7 天或 30 天的睡眠记录。
- 睡眠报告：统计平均睡眠时长、入睡/起床时间、目标完成率和质量评分。
- 目标管理：设置每日睡眠目标、入睡时间、起床时间和午休目标。
- 成就系统：根据睡眠习惯自动解锁成就。
- 校园地图：用睡眠进度解锁北大地标节点。
- 作息规划：导入或编辑课表，生成夜间睡眠和午休建议。

## 使用说明

### 1. 配置环境

推荐使用 conda 管理环境。先创建一个独立环境：

```bash
conda create -n pkusleeper python=3.10
```

### 2. 激活环境

```bash
conda activate pkusleeper
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 运行程序

```bash
python main.py
```

程序启动后会进入主界面。默认用户为 `default_user`，睡眠记录、目标和调试状态会保存在 `data/default_user/` 下。

## 程序结构

```text
PKUsleeper/
├── main.py                         # 程序入口
├── requirements.txt                # 依赖列表
├── pkusleeper/
│   ├── domain/                     # 数据模型：睡眠记录、目标、成就、地图节点等
│   ├── services/                   # 业务服务：睡眠流程、目标、成就、地图、用户信息
│   ├── states/                     # 状态对象：睡眠状态、成就状态、地图状态
│   ├── storage/                    # 本地 JSON 数据读写
│   ├── reports/                    # 睡眠评分与报告生成
│   ├── achievements/               # 默认成就目录
│   └── ui/
│       ├── shell/                  # 主窗口与侧边栏
│       ├── features/               # 各功能页面的 UI 与控制器
│       ├── bridge/                 # UI 与业务层之间的数据桥接
│       └── assets/                 # 图片与界面资源
└── tests/
    ├── dev_commands.py             # 开发调试命令
    └── DEV_COMMANDS_INSTRUCTION.md # 调试命令说明
```

整体上，项目采用分层设计：`main.py` 初始化应用和服务，`MainTracker` 统一协调业务模块，`ServiceBridge` 将业务数据整理成 UI 需要的格式，各页面控制器只负责事件绑定和界面刷新。

## 开发者命令

项目提供了一个轻量命令行工具，方便在调试 UI 时快速添加记录、调整目标、手动控制成就和地图状态。

查看帮助：

```bash
python tests/dev_commands.py --help
```

### 睡眠记录

```bash
# 添加一条记录
python tests/dev_commands.py records add --start "2026-06-01 23:30" --end "2026-06-02 07:30"

# 查看记录
python tests/dev_commands.py records list

# 编辑记录
python tests/dev_commands.py records edit <record_id> --end "2026-06-02 08:00"

# 删除或清空记录
python tests/dev_commands.py records delete <record_id>
python tests/dev_commands.py records clear --yes
```

### 睡眠目标

```bash
python tests/dev_commands.py goal show
python tests/dev_commands.py goal set --hours 7.5 --start 23:45
python tests/dev_commands.py goal reset
```

### 成就与地图

```bash
# 成就
python tests/dev_commands.py achievement list
python tests/dev_commands.py achievement unlock sleep_8h
python tests/dev_commands.py achievement lock sleep_8h
python tests/dev_commands.py achievement clear

# 地图
python tests/dev_commands.py map show
python tests/dev_commands.py map set --unlocked-count 3 --recommended-node 图书馆
python tests/dev_commands.py map unlock-node library
python tests/dev_commands.py map clear
```

手动调试状态保存在 `data/<user_id>/dev_state.json`。需要清除手动覆盖时可以运行：

```bash
python tests/dev_commands.py state reset
```

更多命令细节见 [tests/DEV_COMMANDS_INSTRUCTION.md](tests/DEV_COMMANDS_INSTRUCTION.md)。

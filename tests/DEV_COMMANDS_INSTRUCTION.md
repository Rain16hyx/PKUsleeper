# PKUSleeper 开发者指令

所有命令默认操作 `data/default_user`，使用 `pkusleeper` 环境运行：

```powershell
C:\Users\hyx20\miniconda3\envs\pkusleeper\python.exe tests\dev_commands.py --help
```

## 睡眠记录

```powershell
# 添加记录
C:\Users\hyx20\miniconda3\envs\pkusleeper\python.exe tests\dev_commands.py records add --start "2026-06-01 23:30" --end "2026-06-02 07:30"

# 查看记录
C:\Users\hyx20\miniconda3\envs\pkusleeper\python.exe tests\dev_commands.py records list

# 编辑记录
C:\Users\hyx20\miniconda3\envs\pkusleeper\python.exe tests\dev_commands.py records edit <record_id> --end "2026-06-02 08:00"

# 删除 / 清空
C:\Users\hyx20\miniconda3\envs\pkusleeper\python.exe tests\dev_commands.py records delete <record_id>
C:\Users\hyx20\miniconda3\envs\pkusleeper\python.exe tests\dev_commands.py records clear --yes
```

## 睡眠目标

```powershell
C:\Users\hyx20\miniconda3\envs\pkusleeper\python.exe tests\dev_commands.py goal show
C:\Users\hyx20\miniconda3\envs\pkusleeper\python.exe tests\dev_commands.py goal set --hours 7.5 --start 23:45
C:\Users\hyx20\miniconda3\envs\pkusleeper\python.exe tests\dev_commands.py goal reset
```

## 成就和地图

```powershell
# 成就
C:\Users\hyx20\miniconda3\envs\pkusleeper\python.exe tests\dev_commands.py achievement list
C:\Users\hyx20\miniconda3\envs\pkusleeper\python.exe tests\dev_commands.py achievement unlock sleep_8h
C:\Users\hyx20\miniconda3\envs\pkusleeper\python.exe tests\dev_commands.py achievement lock sleep_8h
C:\Users\hyx20\miniconda3\envs\pkusleeper\python.exe tests\dev_commands.py achievement clear

# 地图
C:\Users\hyx20\miniconda3\envs\pkusleeper\python.exe tests\dev_commands.py map show
C:\Users\hyx20\miniconda3\envs\pkusleeper\python.exe tests\dev_commands.py map set --unlocked-count 3 --recommended-node 图书馆
C:\Users\hyx20\miniconda3\envs\pkusleeper\python.exe tests\dev_commands.py map unlock-node library
C:\Users\hyx20\miniconda3\envs\pkusleeper\python.exe tests\dev_commands.py map clear
```

当前可用成就 ID：

```text
first_sleep       初入梦乡
sleep_8h          睡眠达人
early_sleep       早睡早起
nap_master        午休大师
deep_recovery     深度回血
power_nap         高效小憩
quiet_night       一夜安稳
dorm_regular      宿舍作息家
home_recharge     回家充电
three_checkins    小有坚持
nap_habit         午休养成
goal_five         目标收割机
streak_three      三日连胜
week_logger       一周有迹
steady_week       稳定作息周
```

成就和地图的手动状态保存在 `data/<user_id>/dev_state.json`。清除全部手动覆盖：

```powershell
C:\Users\hyx20\miniconda3\envs\pkusleeper\python.exe tests\dev_commands.py state reset
```


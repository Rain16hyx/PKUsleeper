# PKU SLEEPER 睡眠打卡助手

## 代码库介绍

### 1、环境配置

```
pip install -r requirments.txt
```

### 2、程序运行

```
python main.py
```

### 3、代码结构

后端服务

```
- service.py 调用服务

- states.py 执行功能

- models.py 组织数据

- storage.py 存取数据

- utils/
    -data_processing.py 分析数据
```

前端页面

```
- 
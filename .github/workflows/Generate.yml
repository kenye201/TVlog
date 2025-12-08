name: Generate M3U

# 允许手动和定时触发
on:
  workflow_dispatch:
  schedule:
    - cron: "0 0 * * *"  # 每天 00:00 UTC 执行一次，可根据需求调整

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      # 1. 拉取代码
      - name: Checkout repository
        uses: actions/checkout@v3

      # 2. 设置 Python 环境
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"

      # 3. 安装依赖，如果有 requirements.txt
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          if [ -f "requirements.txt" ]; then pip install -r requirements.txt; fi

      # 4. 执行 Python 脚本
      - name: Run M3U generator
        run: |
          python md/test22.py

      # 5. 可选：将生成的 demo_output.m3u 上传为工作流产物
      - name: Upload M3U output
        uses: actions/upload-artifact@v3
        with:
          name: demo_output
          path: demo_output.m3u

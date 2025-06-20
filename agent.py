#!/home/jskj/miniconda3/envs/env/bin/python

import os
import argparse
import requests
from dotenv import load_dotenv
import json
import subprocess
from typing import Optional, List
import logging
from pathlib import Path

# 配置日志
LOG_FILE = Path.home() / ".ag_command.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# 加载环境变量
load_dotenv(os.path.expanduser("~/.ag_env"))
API_KEY = os.getenv("DEEPSEEK_API_KEY")
API_URL = "https://api.deepseek.com/v1/chat/completions"

class CommandExecutor:
    """安全的命令执行器"""
    
    DANGEROUS_KEYWORDS = [
        "rm -rf", "chmod 777", "> /dev/", "dd if=", 
        "mkfs", ":(){:|:&};:", "wget -O- | sh"
    ]
    
    @classmethod
    def is_safe(cls, command: str) -> bool:
        """检查命令是否安全"""
        cmd_lower = command.lower()
        return not any(kw in cmd_lower for kw in cls.DANGEROUS_KEYWORDS)
    
    @classmethod
    def execute(cls, command: str, confirm: bool = True) -> bool:
        """执行Shell命令"""
        if not cls.is_safe(command):
            logging.warning(f"Blocked dangerous command: {command}")
            print("🛑 危险命令已被阻止执行")
            return False
            
        if confirm:
            print(f"\n\033[1;33m即将执行:\033[0m \033[1;36m{command}\033[0m")
            if input("确认执行？(y/N): ").lower() != 'y':
                print("取消执行")
                return False
        
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                check=True, 
                text=True,
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
            logging.info(f"Executed: {command}")
            if result.stdout:
                print(f"\n\033[1;32m输出:\033[0m\n{result.stdout}")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed: {command} - {e.stderr}")
            print(f"\n\033[1;31m错误:\033[0m\n{e.stderr}")
            return False

def call_deepseek(prompt: str, model: str = "deepseek-chat", **kwargs) -> str:
    """调用DeepSeek API并返回完整响应"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        **kwargs
    }
    
    full_response = ""
    try:
        response = requests.post(API_URL, headers=headers, json=data, stream=True)
        response.raise_for_status()
        
        print("\033[1;34mDeepSeek:\033[0m ", end="", flush=True)
        for chunk in response.iter_lines():
            if chunk:
                chunk_str = chunk.decode("utf-8")
                if chunk_str.startswith("data: {"):
                    json_data = json.loads(chunk_str[6:])
                    content = json_data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    print(content, end="", flush=True)
                    full_response += content
        print()
        return full_response
        
    except Exception as e:
        logging.error(f"API调用失败: {e}")
        print(f"\n\033[1;31mAPI错误:\033[0m {e}")
        return ""

def extract_commands(response: str) -> List[str]:
    """从API响应中提取命令（支持多命令）"""
    lines = response.split('\n')
    commands = []
    for line in lines:
        if line.strip().startswith("$ "):  # 识别以 $ 开头的行作为命令
            commands.append(line.strip()[2:])
    return commands

def main():
    parser = argparse.ArgumentParser(description="AI助手终端版")
    parser.add_argument("prompt", nargs="?", help="您的指令")
    parser.add_argument("-m", "--model", default="deepseek-chat", help="模型名称")
    parser.add_argument("-t", "--temperature", type=float, default=0.7, help="创造性 (0-1)")
    parser.add_argument("--no-confirm", action="store_true", help="跳过执行确认")
    args = parser.parse_args()
    
    if not args.prompt:
        print("请输入指令（Ctrl+D结束）:")
        args.prompt = sys.stdin.read()
    
    response = call_deepseek(
        args.prompt,
        model=args.model,
        temperature=args.temperature
    )
    
    commands = extract_commands(response)
    if commands:
        print("\n\033[1;35m检测到可执行命令:\033[0m")
        for cmd in commands:
            CommandExecutor.execute(cmd, confirm=not args.no_confirm)
    else:
        print("\n\033[1;33m未检测到可执行命令\033[0m")

if __name__ == "__main__":
    main()
